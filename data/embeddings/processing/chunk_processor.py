"""
Text chunking strategies
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ===== Optional tokenizer (OpenAI) =====
_TIKTOKEN = None
try:
    import tiktoken  # type: ignore
    _TIKTOKEN = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TIKTOKEN = None


def _encode_tokens(text: str) -> List[int]:
    if _TIKTOKEN is not None:
        return _TIKTOKEN.encode(text)
    # Fallback: xấp xỉ bằng split theo khoảng trắng
    # (mỗi "từ" xem như 1 token xấp xỉ)
    return text.split()


def _count_tokens(text: str) -> int:
    return len(_encode_tokens(text))


def _split_paragraphs(text: str) -> List[str]:
    # Tách theo 1 dòng trống trở lên
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


# Tách câu đơn giản: kết thúc bằng . ! ? + khoảng trắng + chữ/ số đầu câu.
# Có xử lý bullet đứng đầu dòng như 1 "câu".
_SENT_SPLIT = re.compile(r"(?<=[\.\!\?])\s+(?=[A-Z0-9])", re.MULTILINE)
_BULLET_LINE = re.compile(r"(?m)^\s*[-•\*]\s+")


def _split_sentences_keep_bullets(paragraph: str) -> List[str]:
    lines = paragraph.split("\n")
    buffer = []
    acc: List[str] = []

    def flush_buffer():
        if buffer:
            acc.append(" ".join(buffer).strip())
            buffer.clear()

    for ln in lines:
        if not ln.strip():
            flush_buffer()
            continue

        # Bullet line: tách thành 1 câu riêng
        if _BULLET_LINE.match(ln):
            flush_buffer()
            acc.append(_BULLET_LINE.sub("", ln).strip())  # bỏ ký hiệu đầu dòng
        else:
            buffer.append(ln.strip())

    flush_buffer()

    # Bây giờ acc là các block đã gộp theo dòng; tiếp tục tách câu trong từng block
    out: List[str] = []
    for block in acc:
        parts = _SENT_SPLIT.split(block.strip())
        out.extend([p.strip() for p in parts if p.strip()])

    return out


@dataclass
class Chunk:
    text: str
    n_tokens: int
    start_index: int  # index câu bắt đầu (flattened)
    end_index: int    # index câu kết thúc (inclusive)


class SentenceChunker:
    """
    Chunk theo câu với greedy packing:
      - Gom câu vào chunk tới khi chạm max_tokens.
      - Nếu 1 câu quá dài > max_tokens: cắt nhỏ theo từ.
      - Dùng overlap theo tokens: giữ lại phần đuôi của chunk trước (theo câu)
        có tổng token <= overlap_tokens và prepend cho chunk sau.
    """

    def __init__(self,
                 max_tokens: int = 500,
                 overlap_tokens: int = 60):
        assert max_tokens > 0 and overlap_tokens >= 0
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens

    def _split_long_sentence_by_words(self, s: str) -> List[str]:
        """Cắt 1 câu quá dài bằng cách chia theo từ để mỗi mảnh <= max_tokens."""
        words = s.split()
        pieces: List[str] = []
        buf: List[str] = []
        for w in words:
            candidate = (" ".join(buf + [w])).strip()
            if _count_tokens(candidate) <= self.max_tokens or not buf:
                buf.append(w)
            else:
                pieces.append(" ".join(buf))
                buf = [w]
        if buf:
            pieces.append(" ".join(buf))
        return pieces

    def _build_overlap_tail(self, sentences: List[str]) -> List[str]:
        """Lấy đuôi các câu sao cho tổng tokens <= overlap_tokens."""
        tail: List[str] = []
        total = 0
        for s in reversed(sentences):
            t = _count_tokens(s)
            if total + t <= self.overlap_tokens:
                tail.append(s)
                total += t
            else:
                break
        tail.reverse()
        return tail

    def chunk(self, text: str) -> List[Chunk]:
        if not text.strip():
            return []

        # 1) Tách paragraph -> sentence list (flatten)
        paragraphs = _split_paragraphs(text)
        sentences: List[str] = []
        for p in paragraphs:
            sentences.extend(_split_sentences_keep_bullets(p))

        chunks: List[Chunk] = []
        if not sentences:
            return chunks

        buf: List[str] = []
        buf_tok = 0
        buf_start_idx = 0  # index câu trong list sentences khi chunk bắt đầu
        i = 0

        while i < len(sentences):
            s = sentences[i]
            s_tok = _count_tokens(s)

            if s_tok > self.max_tokens:
                # cắt câu quá dài thành nhiều mảnh
                long_pieces = self._split_long_sentence_by_words(s)
                for j, piece in enumerate(long_pieces):
                    p_tok = _count_tokens(piece)
                    if buf_tok + p_tok <= self.max_tokens and (buf or j == 0):
                        # nhét vào chunk hiện tại
                        if not buf:
                            buf_start_idx = i  # start tại câu i (mặc dù là mảnh)
                        buf.append(piece)
                        buf_tok += p_tok
                    else:
                        # flush chunk cũ
                        if buf:
                            chunks.append(Chunk(" ".join(buf), buf_tok, buf_start_idx, i))
                            # overlap
                            overlap_tail = self._build_overlap_tail(buf)
                            buf = overlap_tail[:]
                            buf_tok = sum(_count_tokens(x) for x in buf)
                            buf_start_idx = i  # vẫn là câu i

                        # bắt đầu chunk mới với piece
                        buf.append(piece)
                        buf_tok += p_tok
                i += 1
                continue

            # Câu thường
            if buf_tok + s_tok <= self.max_tokens and buf:
                buf.append(s)
                buf_tok += s_tok
                i += 1
            elif not buf:
                # Buffer trống: khởi tạo với s
                buf_start_idx = i
                buf.append(s)
                buf_tok += s_tok
                i += 1
            else:
                # đầy: flush chunk, tạo overlap
                chunks.append(Chunk(" ".join(buf), buf_tok, buf_start_idx, i - 1))
                overlap_tail = self._build_overlap_tail(buf)
                buf = overlap_tail[:]
                buf_tok = sum(_count_tokens(x) for x in buf)
                buf_start_idx = i  # chunk mới bắt đầu tại câu hiện tại

        # flush phần cuối
        if buf:
            chunks.append(Chunk(" ".join(buf), buf_tok, buf_start_idx, len(sentences) - 1))

        return chunks
