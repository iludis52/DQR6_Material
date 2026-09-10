from __future__ import annotations

from dataclasses import dataclass
from markdown_it import MarkdownIt

from .lekt_bloecke import DocumentBlock, make_block


@dataclass(frozen=True)
class ParsedMarkdown:
    source: str
    blocks: tuple[DocumentBlock, ...]


def _raw_lines(source: str, start: int, end: int) -> str:
    # splitlines() deliberately drops only newline separators, preserving content literals.
    return "\n".join(source.splitlines()[start:end])


def parse_markdown(source: str) -> ParsedMarkdown:
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    tokens = md.parse(source)
    blocks: list[DocumentBlock] = []
    page_segment = 0
    container_depth = 0

    for i, token in enumerate(tokens):
        if token.type in {"bullet_list_open", "ordered_list_open"} and token.map:
            raw = _raw_lines(source, *token.map)
            blocks.append(make_block(block_type="list", start_line=token.map[0], end_line=token.map[1], raw_text=raw, page_segment=page_segment))
            container_depth += 1
            continue
        if token.type in {"bullet_list_close", "ordered_list_close"}:
            container_depth = max(0, container_depth - 1)
            continue
        if token.type == "table_open" and token.map:
            raw = _raw_lines(source, *token.map)
            blocks.append(make_block(block_type="table", start_line=token.map[0], end_line=token.map[1], raw_text=raw, page_segment=page_segment))
            container_depth += 1
            continue
        if token.type == "table_close":
            container_depth = max(0, container_depth - 1)
            continue
        if container_depth:
            continue

        if token.type == "heading_open" and token.map:
            raw = _raw_lines(source, *token.map)
            blocks.append(make_block(block_type="heading", start_line=token.map[0], end_line=token.map[1], raw_text=raw, page_segment=page_segment))
        elif token.type == "paragraph_open" and token.map:
            raw = _raw_lines(source, *token.map)
            inline = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
            if inline and inline.children and any(c.type == "image" for c in inline.children):
                kind = "image"
            elif raw.strip().startswith("$$") and raw.strip().endswith("$$"):
                kind = "math"
            else:
                kind = "paragraph"
            blocks.append(make_block(block_type=kind, start_line=token.map[0], end_line=token.map[1], raw_text=raw, page_segment=page_segment))
        elif token.type == "html_block" and token.map:
            raw = _raw_lines(source, *token.map)
            blocks.append(make_block(block_type="html_comment", start_line=token.map[0], end_line=token.map[1], raw_text=raw, page_segment=page_segment))
            if "<!-- Seitenumbruch -->" in raw:
                page_segment += 1

    return ParsedMarkdown(source=source, blocks=tuple(blocks))


def reparse_markdown(source: str) -> ParsedMarkdown:
    return parse_markdown(source)
