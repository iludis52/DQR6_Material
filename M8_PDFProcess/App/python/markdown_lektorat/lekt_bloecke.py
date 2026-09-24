from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re


# Genau die Zeilentrenner, die markdown-it zählt (core rule "normalize").
# str.splitlines() trennt zusätzlich an \x0c, \x1c-\x1e, \x85,  ,   –
# ein einziges solches Zeichen im OCR-Text verschob sonst alle folgenden
# Blockgrenzen, und Korrekturen landeten auf der falschen Zeile.
_ZEILENENDE = re.compile(r"\r\n|\r|\n")


def line_offsets(source: str) -> list[int]:
    """Startoffset jeder Zeile im Sinne von markdown-it, plus `len(source)` am Ende.

    Zeile i umfasst `source[offsets[i]:offsets[i + 1]]` einschließlich ihres
    Zeilenendes; `token.map = (a, b)` entspricht `offsets[a]:offsets[b]`.
    """
    offsets = [0]
    offsets.extend(m.end() for m in _ZEILENENDE.finditer(source))
    if offsets[-1] != len(source):
        offsets.append(len(source))
    return offsets


def raw_lines(source: str, offsets: list[int], start: int, end: int) -> str:
    """Zeilen [start, end) ohne das abschließende Zeilenende."""
    end = min(end, len(offsets) - 1)
    text = source[offsets[start]:offsets[end]]
    return _ZEILENENDE.sub("\n", text).removesuffix("\n")


@dataclass(frozen=True)
class DocumentBlock:
    block_id: str
    block_type: str
    start_line: int
    end_line: int
    raw_text: str
    content_hash: str
    page_segment: int


def make_block(*, block_type: str, start_line: int, end_line: int, raw_text: str, page_segment: int) -> DocumentBlock:
    digest = sha256(raw_text.encode('utf-8')).hexdigest()
    stable = sha256(f"{block_type}:{start_line}:{end_line}:{digest}".encode('utf-8')).hexdigest()[:16]
    return DocumentBlock(
        block_id=f"blk_{stable}",
        block_type=block_type,
        start_line=start_line,
        end_line=end_line,
        raw_text=raw_text,
        content_hash=digest,
        page_segment=page_segment,
    )
