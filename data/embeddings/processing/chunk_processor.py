"""
Text chunking strategies
"""
"""
Overview :
- This module provides sentence/paragraph-based greedy chunking with token
  limits and token-overlap to preserve context across chunks.
- It is tokenizer-agnostic: if `tiktoken` is available, it uses `cl100k_base`;
  otherwise it falls back to a whitespace tokenizer (approximation).
- Bullet-style lines (e.g., '-', '*', '•') are treated as standalone sentences.

Design:
- Tokenizers:
    * BaseTokenizer (interface)
    * TiktokenTokenizer (preferred if available)
    * WhitespaceTokenizer (fallback)
- Data models:
    * Chunk: holds text, token count, and sentence index range
    * SentenceChunkerConfig: configuration (max_tokens, overlap, patterns)
- Orchestrator:
    * SentenceChunker: high-level API (`chunk(text) -> List[Chunk]`)
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Protocol
from common.logger import logger



class BaseTokenizer(Protocol):
    """Minimal tokenizer interface."""

    def encode(self, text: str) -> List[int]:
        ...

    def count(self, text: str) -> int:
        ...


class WhitespaceTokenizer:
    """
    Approximate tokenizer using whitespace splitting.
    Useful as a fallback when `tiktoken` is not installed.
    """

    def encode(self, text: str) -> List[int]:
        # Represent each whitespace-separated token with a dummy integer.
        # Only length matters for our use-case.
        return list(range(len(text.split())))  # cheap & deterministic

    def count(self, text: str) -> int:
        return len(text.split())


class TiktokenTokenizer:
    """
    `tiktoken`-backed tokenizer. If `tiktoken` is not available, creation should
    fall back to `WhitespaceTokenizer` in the chunker constructor.
    """

    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        import tiktoken  # type: ignore
        self._enc = tiktoken.get_encoding(encoding_name)

    def encode(self, text: str) -> List[int]:
        return self._enc.encode(text)

    def count(self, text: str) -> int:
        return len(self._enc.encode(text))




def _split_paragraphs(text: str) -> List[str]:
    """
    Split text into paragraphs using one-or-more blank lines as separators.
    """
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


@dataclass
class Chunk:
    """
    A contiguous chunk of text with token count and sentence index range.

    Attributes:
        text: The concatenated text of the chunk.
        n_tokens: The token count of `text` under the configured tokenizer.
        start_index: Inclusive start sentence index (over the flattened sentence list).
        end_index: Inclusive end sentence index (over the flattened sentence list).
    """
    text: str
    n_tokens: int
    start_index: int
    end_index: int


@dataclass(frozen=True)
class SentenceChunkerConfig:
    """
    Configuration for sentence-based greedy chunking.

    Attributes:
        max_tokens: Hard cap on tokens per chunk.
        overlap_tokens: Max tokens to carry over from the tail of the previous
                        chunk into the next one (to preserve context).
        sentence_split_regex: Regex to split sentences inside a paragraph.
            Default heuristic: split on [.?!] + whitespace + [A-Z0-9].
        bullet_line_regex: Regex to detect bullet-style lines that should be
            treated as standalone sentences.
        tiktoken_encoding: Optional name of tiktoken encoding to use.
    """
    max_tokens: int = 512 
    overlap_tokens: int = 32  
    sentence_split_regex: str = r"(?<=[\.\!\?])\s+(?=[A-Z0-9])"
    bullet_line_regex: str = r"(?m)^\s*[-•\*]\s+"
    tiktoken_encoding: Optional[str] = "cl100k_base"

    def __post_init__(self):
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be > 0")
        if self.overlap_tokens < 0:
            raise ValueError("overlap_tokens must be >= 0")
        if self.overlap_tokens >= self.max_tokens:
            object.__setattr__(self, "overlap_tokens", max(0, self.max_tokens - 1))


class SentenceChunker:
    """
    Sentence-based greedy chunker with token overlap.

    Algorithm (high-level):
      1) Split text into paragraphs (blank-line separated).
      2) For each paragraph:
           - Treat bullet lines as standalone sentences.
           - Merge non-bullet lines and split them into sentences using a
             lightweight regex (English-centric, adjustable via config).
      3) Greedily pack sentences into chunks until `max_tokens` is reached.
      4) If an individual sentence exceeds `max_tokens`, split it by words into
         sub-sentences, each <= `max_tokens` tokens.
      5) Apply token-overlap (`overlap_tokens`) by carrying the tail of the
         previous chunk into the next chunk.

    Notes:
      - The tokenizer is pluggable; if `tiktoken` is available it will be used,
        otherwise the fallback whitespace tokenizer is applied.
      - Sentence indices (`start_index`, `end_index`) refer to the flattened
        sentence list before any sub-splitting of long sentences.
    """

    def __init__(
        self,
        config: Optional[SentenceChunkerConfig] = None,
        tokenizer: Optional[BaseTokenizer] = None,
    ) -> None:
        self.config = config or SentenceChunkerConfig()

        # Prefer tiktoken if available; otherwise fallback to whitespace.
        if tokenizer is not None:
            self.tok = tokenizer
        else:
            self.tok = self._make_default_tokenizer()

        # Pre-compile patterns for speed.
        self._sent_split_re = re.compile(self.config.sentence_split_regex, re.MULTILINE)
        self._bullet_line_re = re.compile(self.config.bullet_line_regex, re.MULTILINE)


    def chunk(self, text: str) -> List[Chunk]:
        """
        Chunk input text into `Chunk` objects based on sentence boundaries,
        token limits, and configured overlap.

        Args:
            text: Cleaned text (ideally already preprocessed).

        Returns:
            List[Chunk]: ordered chunks covering the entire input text.
        """
        text = (text or "").strip()
        if not text:
            return []

        # Flattened sentence list across all paragraphs.
        sentences = self._sentences_from_text(text)
        if not sentences:
            return []

        chunks: List[Chunk] = []
        buf: List[str] = []           # sentence buffer for the current chunk
        buf_tok: int = 0              # token count of current buffer
        buf_start_idx: int = 0        # where the current chunk started in `sentences`
        i: int = 0                    # sentence index (over flattened list)

        while i < len(sentences):
            s = sentences[i]
            s_tok = self.tok.count(s)

            # Case A: single sentence longer than the budget → split by words
            if s_tok > self.config.max_tokens:
                long_pieces = self._split_long_sentence_by_words(s)
                for j, piece in enumerate(long_pieces):
                    p_tok = self.tok.count(piece)

                    # Try to append to current chunk if it fits, otherwise flush first
                    if (buf and buf_tok + p_tok <= self.config.max_tokens) or (not buf and p_tok <= self.config.max_tokens):
                        if not buf:
                            buf_start_idx = i  # chunk starts at original sentence i
                        buf.append(piece)
                        buf_tok += p_tok
                    else:
                        # Flush current chunk
                        if buf:
                            if buf_tok > self.config.max_tokens:
                                logger.warning(
                                    f"[Chunker] Warning: created chunk exceeding max_tokens ({buf_tok} > {self.config.max_tokens})"
                                )
                            chunks.append(
                                Chunk(" ".join(buf), buf_tok, buf_start_idx, i)
                            )
                            # Build overlap tail and start a new buffer
                            buf = self._build_overlap_tail(buf)
                            buf_tok = sum(self.tok.count(x) for x in buf)
                            buf_start_idx = i  # next chunk still corresponds to sentence i

                        # Start with current piece
                        buf.append(piece)
                        buf_tok += p_tok

                i += 1
                continue

            # Case B: normal sentence
            if buf and (buf_tok + s_tok) <= self.config.max_tokens:
                # Append to current chunk
                buf.append(s)
                buf_tok += s_tok
                i += 1
            elif not buf:
                # Start a new chunk with this sentence
                buf_start_idx = i
                buf.append(s)
                buf_tok += s_tok
                i += 1
            else:
                # Current chunk is full → flush and create overlap
                chunks.append(Chunk(" ".join(buf), buf_tok, buf_start_idx, i - 1))
                buf = self._build_overlap_tail(buf)
                buf_tok = sum(self.tok.count(x) for x in buf)
                buf_start_idx = i  # next chunk starts at current sentence

        # Flush the last buffer
        if buf:
            chunks.append(Chunk(" ".join(buf), buf_tok, buf_start_idx, len(sentences) - 1))

        return chunks

    # ----------------------------- Internals -----------------------------

    def _make_default_tokenizer(self) -> BaseTokenizer:
        """Try to build a tiktoken tokenizer; fallback to whitespace on failure."""
        if self.config.tiktoken_encoding:
            try:
                return TiktokenTokenizer(self.config.tiktoken_encoding)
            except Exception:
                pass
        return WhitespaceTokenizer()

    def _sentences_from_text(self, text: str) -> List[str]:
        """
        Convert raw text into a flat list of sentences, preserving bullets
        as separate sentences and splitting non-bullet blocks with a regex rule.
        """
        paras = _split_paragraphs(text)
        sentences: List[str] = []
        for p in paras:
            sentences.extend(self._split_sentences_keep_bullets(p))
        return sentences

    def _split_sentences_keep_bullets(self, paragraph: str) -> List[str]:
        """
        Within a paragraph:
          - Treat bullet-style lines as standalone sentences (drop bullet marker).
          - Merge consecutive non-bullet lines into blocks, then sentence-split.
        """
        lines = paragraph.split("\n")
        buffer: List[str] = []   # current non-bullet block lines
        blocks: List[str] = []   # accumulated bullet or merged blocks

        def flush_buffer():
            if buffer:
                blocks.append(" ".join(buffer).strip())
                buffer.clear()

        for ln in lines:
            if not ln.strip():
                flush_buffer()
                continue

            if self._bullet_line_re.match(ln):
                # Bullet → standalone block
                flush_buffer()
                blocks.append(self._bullet_line_re.sub("", ln).strip())
            else:
                buffer.append(ln.strip())

        flush_buffer()

        # Now split each block into sentences with the configured regex rule.
        out: List[str] = []
        for block in blocks:
            parts = self._sent_split_re.split(block.strip())
            out.extend([p.strip() for p in parts if p.strip()])
        return out

    def _split_long_sentence_by_words(self, s: str) -> List[str]:
        """
        Split an overlong sentence by words so that each piece fits max_tokens.

        Strategy:
          - Greedily add words to a piece until adding the next word would exceed
            `max_tokens`, then start a new piece.
        """
        words = s.split()
        if not words:
            return [s]
        
        pieces: List[str] = []
        buf: List[str] = []

        for w in words:
            w_tok = self.tok.count(w)
            # If a word exceeds max_tokens -> fallback hard split by character
            if w_tok > self.config.max_tokens:
                # flush buffer first
                if buf:
                    pieces.append(" ".join(buf)); buf = []
                # hard-split long words
                chars = list(w)
                sub = []
                for ch in chars:
                    cand = ("".join(sub) + ch)
                    if self.tok.count(cand) <= self.config.max_tokens or not sub:
                        sub.append(ch)
                    else:
                        pieces.append("".join(sub))
                        sub = [ch]
                if sub:
                    pieces.append("".join(sub))
                continue

            candidate = (" ".join(buf + [w])).strip()
            if not buf or self.tok.count(candidate) <= self.config.max_tokens:
                buf.append(w)
            else:
                pieces.append(" ".join(buf))
                buf = [w]

        if buf:
            pieces.append(" ".join(buf))
        return pieces

    def _build_overlap_tail(self, sentences: Sequence[str]) -> List[str]:
        """
        Build a tail of sentences whose total tokens <= overlap_tokens.

        The chosen tail is appended to the *beginning* of the next chunk to
        preserve context between adjacent chunks.
        """
        if self.config.overlap_tokens == 0:
            return []

        tail: List[str] = []
        total = 0
        for s in reversed(sentences):
            t = self.tok.count(s)
            if total + t <= self.config.overlap_tokens:
                tail.append(s)
                total += t
            else:
                break
        tail.reverse()
        return tail


class ChunkProcessor:
    """
    Adapter class to provide a simple chunk_text method that matches
    the interface expected by DocumentIndexer.
    """
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Initialize the chunk processor with default configuration.
        
        Args:
            chunk_size: Maximum number of tokens per chunk
            chunk_overlap: Number of tokens to overlap between chunks
        """
        config = SentenceChunkerConfig(
            max_tokens=chunk_size,
            overlap_tokens=chunk_overlap
        )
        self.chunker = SentenceChunker(config=config)
    
    def chunk_text(self, text: str, chunk_size: int = 512, chunk_overlap: int = 50) -> List[str]:
        """
        Split text into chunks of specified size with overlap.
        
        Args:
            text: Input text to be chunked
            chunk_size: Maximum number of tokens per chunk
            chunk_overlap: Number of tokens to overlap between chunks
            
        Returns:
            List of text chunks
        """
        # Create a temporary chunker with the specified parameters
        config = SentenceChunkerConfig(
            max_tokens=chunk_size,
            overlap_tokens=chunk_overlap
        )
        chunker = SentenceChunker(config=config)
        chunks = chunker.chunk(text)
            
        return [chunk.text for chunk in chunks]