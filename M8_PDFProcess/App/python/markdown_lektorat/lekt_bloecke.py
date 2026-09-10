from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


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
