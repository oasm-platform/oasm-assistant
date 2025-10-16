"""
Text preprocessing for embeddings
"""
from __future__ import annotations
import re
import unicodedata
from typing import Dict, List, Optional


class TextPreprocessorConfig:
    """
    Configuration flags controlling preprocessing behavior.

    Attributes:
        normalize_unicode (bool):
            If True, normalize to NFC form to standardize composed characters.
        collapse_spaces (bool):
            If True, collapse repeated spaces and reduce excessive newlines
            while preserving paragraph breaks.
        strip_control_chars (bool):
            If True, remove non-printable control chars (except '\n' and '\t').
        dehyphenate (bool):
            If True, join hyphenated line breaks (e.g., 'co-\noperate' → 'cooperate').
        merge_hard_wraps (bool):
            If True, merge hard-wrapped lines into coherent paragraphs using
            lightweight heuristics.
        remove_headers_footers (bool):
            If True, attempt to remove short lines that repeat across pages
            (likely headers/footers) using frequency + context heuristics.
        min_header_len (int):
            Minimum length for a line to be considered a header/footer candidate.
        max_header_line_len (int):
            Maximum length for a single line to be considered a candidate; longer
            lines are unlikely to be headers/footers.
    """
    normalize_unicode: bool = True
    collapse_spaces: bool = True
    strip_control_chars: bool = True
    dehyphenate: bool = True
    merge_hard_wraps: bool = True
    remove_headers_footers: bool = True
    min_header_len: int = 8
    max_header_line_len: int = 120


class TextPreprocessor:
    """
    Light-touch cleaner for PDF-extracted text prior to chunking/embedding.

    The methods here are conservative and idempotent where possible. The goal
    is to fix extraction noise (line-wrapping, hyphenation, rogue controls)
    while preserving semantic content and paragraph boundaries.

    Typical use:
        tp = TextPreprocessor()
        clean = tp.preprocess(raw_text)
        sentences = tp.split_sentences(clean)
        paragraphs = tp.paragraphs(clean)
    """

    # Sentence-splitting heuristic for English-like punctuation:
    # split on ". ! ?" followed by whitespace and then an uppercase letter or digit.
    SENT_SPLIT = re.compile(r"(?<=[\.\!\?])\s+(?=[A-Z0-9])")

    def __init__(self, config: Optional[TextPreprocessorConfig] = None) -> None:
        """
        Initialize the preprocessor with optional configuration.

        Args:
            config: Optional TextPreprocessorConfig. If None, defaults are used.
        """
        self.config = config or TextPreprocessorConfig()


    def preprocess(self, text: str) -> str:
        """
        Run the configured preprocessing pipeline on input text.
        
        The sequence (guarded by flags) is:
          normalize -> collapse spaces/newlines -> strip controls
          -> dehyphenate -> merge hard wraps -> remove headers/footers -> improve paragraph handling -> final trim
        
        Args:
            text: Raw text, typically from a PDF extractor.
        
        Returns:
            Cleaned text suitable for chunking and embedding.
        """
        if not text:
            return ""
        s = text

        if self.config.normalize_unicode:
            s = self._normalize(s)

        if self.config.collapse_spaces:
            s = self._collapse_spaces_and_newlines(s)

        if self.config.strip_control_chars:
            s = self._strip_controls(s)

        if self.config.dehyphenate:
            s = self._dehyphenate_line_breaks(s)

        if self.config.merge_hard_wraps:
            s = self._merge_hard_wraps(s)

        if self.config.remove_headers_footers:
            s = self._remove_repeated_headers_footers(
                s, min_len=self.config.min_header_len, max_line_len=self.config.max_header_line_len
            )

        # Improve paragraph handling for better segmentation support
        s = self._improve_paragraph_handling(s)

        # Final pass to remove accidental trailing spaces and compress newlines.
        s = self._final_trim(s)
        return s


    def split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using a minimalist regex heuristic.

        Caveats:
        - This is a lightweight rule for common English punctuation patterns.
        - For multilingual or domain-specific texts, consider a dedicated
          sentence splitter.

        Args:
            text: Cleaned text.

        Returns:
            List of sentences (whitespace-trimmed, empty entries removed).
        """
        text = text.strip()
        if not text:
            return []
        parts = self.SENT_SPLIT.split(text)
        return [p.strip() for p in parts if p.strip()]


    def paragraphs(self, text: str) -> List[str]:
        """
        Split text into paragraphs by blank-line separators.

        Args:
            text: Cleaned text.

        Returns:
            List of paragraph strings (whitespace-trimmed, empty entries removed).
        """
        return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


    def _normalize(self, s: str) -> str:
        """
        Normalize Unicode to NFC (composed) form.

        This makes string equality and downstream tokenization more predictable.
        """
        return unicodedata.normalize("NFC", s)


    def _collapse_spaces_and_newlines(self, s: str) -> str:
        """
        Collapse repeated spaces and reduce excessive newlines.

        - Unify newlines: convert CRLF/CR → LF
        - Remove BOMs
        - Collapse runs of spaces/tabs (but keep tabs/newlines intact)
        - Compress 3+ consecutive newlines to at most 2 (paragraph break)
        """
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        s = s.replace("\ufeff", "")
        s = re.sub(r"[^\S\r\n\t]+", " ", s)  # collapse spaces but keep \n and \t
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s


    def _strip_controls(self, s: str) -> str:
        """
        Remove control characters while preserving '\\n' and '\\t'.

        Rationale: PDF extractors can emit stray control bytes that confuse
        tokenizers and storage systems.
        """
        return "".join(ch for ch in s if (ch == "\n" or ch == "\t" or (ord(ch) >= 32)))


    def _dehyphenate_line_breaks(self, s: str) -> str:
        """
        Join hyphenated words split across line breaks.

        Example: "co-\noperate" → "cooperate"
        """
        return re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", s)


    def _merge_hard_wraps(self, s: str) -> str:
        """
        Merge hard-wrapped lines into natural paragraphs using simple heuristics.

        Heuristic details:
        - Maintain a buffer for current paragraph lines.
        - If the previous fragment ends with an alnum and the next line starts
          with a lowercase letter, digit, or '(', we treat it as a wrap and
          join with a space.
        - Preserve blank lines as paragraph separators.
        - After merging, compress 3+ newlines to 2 and strip outer whitespace.
        """
        lines = s.split("\n")
        out_lines: List[str] = []
        buf: List[str] = []

        def flush_buf():
            if buf:
                out_lines.append(" ".join(buf))
                buf.clear()

        for ln in lines:
            if not ln.strip():
                # Blank line → end current paragraph buffer
                flush_buf()
                out_lines.append("")
                continue

            if not buf:
                buf.append(ln.strip())
                continue

            prev = buf[-1]
            # If previous ends with [A-Za-z0-9] and current begins with [a-z0-9(],
            # it's likely a wrapped line rather than a new paragraph.
            if re.search(r"[A-Za-z0-9]$", prev) and re.match(r"^[a-z0-9(]", ln.strip()):
                buf[-1] = prev + " " + ln.strip()
            else:
                buf.append(ln.strip())

        flush_buf()
        s2 = "\n".join(out_lines)
        s2 = re.sub(r"\n{3,}", "\n\n", s2).strip()
        return s2
    

    def _remove_repeated_headers_footers(self, s: str, min_len: int, max_line_len: int) -> str:
        """
        Remove lines that likely correspond to repeating headers/footers.

        Approach:
        - Count frequency of trimmed lines whose length is within [min_len, max_line_len].
        - Any line that appears 2+ times becomes a candidate.
        - When a candidate is encountered, we drop it if it is adjacent to a blank
          line (before or after). This favors top/bottom-of-page placements.

        Args:
            s: Input text (with newlines).
            min_len: Minimum candidate length.
            max_line_len: Maximum candidate line length.

        Returns:
            Text with suspected repeating headers/footers removed, and with
            excessive newlines compressed.
        """
        lines = s.split("\n")
        freq: Dict[str, int] = {}

        for ln in lines:
            ls = ln.strip()
            if 0 < len(ls) <= max_line_len:
                freq[ls] = freq.get(ls, 0) + 1

        candidates = {k for k, v in freq.items() if v >= 2 and len(k) >= min_len}

        out: List[str] = []
        i = 0
        while i < len(lines):
            ln = lines[i]
            ln_s = ln.strip()
            if ln_s in candidates:
                prev_blank = (i - 1 >= 0 and lines[i - 1].strip() == "")
                next_blank = (i + 1 < len(lines) and lines[i + 1].strip() == "")
                # Only drop when placed like a margin line (near blank), not within body.
                if prev_blank or next_blank:
                    i += 1
                    continue
            out.append(ln)
            i += 1

        res = "\n".join(out)
        res = re.sub(r"\n{3,}", "\n\n", res).strip()
        return res

    def _improve_paragraph_handling(self, s: str) -> str:
        """
        Improve paragraph handling by adding clear breaks
        to support better segmentation.
        """
        # Replace special character strings with spaces to improve sentence splitting
        s = re.sub(r'[•\u2022\u25E6\u25CF]', ' * ', s)  # Special bullet characters
        # Replace multiple spaces with single space, but preserve international characters
        s = re.sub(r'\s+', ' ', s)
        return s

    def _final_trim(self, s: str) -> str:
        """
        Strip leading/trailing spaces per line and compress excessive newlines.

        This is a final cleanup pass after all structural transforms.
        """
        lines = [ln.strip() for ln in s.split("\n")]
        s = "\n".join(lines).strip()
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s
