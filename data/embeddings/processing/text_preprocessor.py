"""
Text preprocessing for embeddings
"""
from __future__ import annotations
import re
import logging
import unicodedata
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TextPreprocessorConfig:
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
    Làm sạch nhẹ đầu ra từ PDFExtractor để chuẩn bị chunk.
    """

    SENT_SPLIT = re.compile(r"(?<=[\.\!\?])\s+(?=[A-Z0-9])")

    def __init__(self, config: Optional[TextPreprocessorConfig] = None) -> None:
        self.config = config or TextPreprocessorConfig()

    # ---- public API ----
    def preprocess(self, text: str) -> str:
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

        # pass cuối để dọn trắng thừa
        s = self._final_trim(s)
        return s

    def split_sentences(self, text: str) -> List[str]:
        text = text.strip()
        if not text:
            return []
        parts = self.SENT_SPLIT.split(text)
        return [p.strip() for p in parts if p.strip()]

    def paragraphs(self, text: str) -> List[str]:
        return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    # ---- internals ----
    def _normalize(self, s: str) -> str:
        return unicodedata.normalize("NFC", s)

    def _collapse_spaces_and_newlines(self, s: str) -> str:
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        s = s.replace("\ufeff", "")
        s = re.sub(r"[^\S\r\n\t]+", " ", s)  # collapse spaces but keep \n,\t
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s

    def _strip_controls(self, s: str) -> str:
        return "".join(ch for ch in s if (ch == "\n" or ch == "\t" or (ord(ch) >= 32)))

    def _dehyphenate_line_breaks(self, s: str) -> str:
        return re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", s)

    def _merge_hard_wraps(self, s: str) -> str:
        lines = s.split("\n")
        out_lines: List[str] = []
        buf: List[str] = []

        def flush_buf():
            if buf:
                out_lines.append(" ".join(buf))
                buf.clear()

        for ln in lines:
            if not ln.strip():
                flush_buf()
                out_lines.append("")
                continue

            if not buf:
                buf.append(ln.strip())
                continue

            prev = buf[-1]
            if re.search(r"[A-Za-z0-9]$", prev) and re.match(r"^[a-z0-9(]", ln.strip()):
                buf[-1] = prev + " " + ln.strip()
            else:
                buf.append(ln.strip())

        flush_buf()
        s2 = "\n".join(out_lines)
        s2 = re.sub(r"\n{3,}", "\n\n", s2).strip()
        return s2

    def _remove_repeated_headers_footers(self, s: str, min_len: int, max_line_len: int) -> str:
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
                if prev_blank or next_blank:
                    i += 1
                    continue
            out.append(ln)
            i += 1

        res = "\n".join(out)
        res = re.sub(r"\n{3,}", "\n\n", res).strip()
        return res

    def _final_trim(self, s: str) -> str:
        lines = [ln.strip() for ln in s.split("\n")]
        s = "\n".join(lines).strip()
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s
