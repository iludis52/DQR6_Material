from __future__ import annotations

from markdown_it import MarkdownIt

from .lekt_schutz import ProtectedInventory, validate_protected


class MarkdownValidationError(RuntimeError):
    pass


def validate_document_integrity(original: ProtectedInventory, target_source: str) -> None:
    validate_protected(original, target_source)


def _pipe_count(line: str) -> int:
    stripped = line.strip()
    if not stripped.startswith('|') or not stripped.endswith('|'):
        raise MarkdownValidationError('Table row must start and end with |')
    return len(stripped.split('|')) - 2


def validate_markdown_table(table: str) -> str:
    lines = [ln for ln in table.splitlines() if ln.strip()]
    if len(lines) < 2:
        raise MarkdownValidationError('Markdown table requires at least header and separator')
    expected = _pipe_count(lines[0])
    if expected < 1:
        raise MarkdownValidationError('Table has no columns')
    if _pipe_count(lines[1]) != expected:
        raise MarkdownValidationError('Table separator column count mismatch')
    sep_cells = [c.strip() for c in lines[1].strip().strip('|').split('|')]
    if any(not c or set(c.replace(':','')) != {'-'} for c in sep_cells):
        raise MarkdownValidationError('Invalid Markdown table separator row')
    for line in lines[2:]:
        if _pipe_count(line) != expected:
            raise MarkdownValidationError('Table row column count mismatch')
    return table


def validate_markdown_structure(source: str) -> str:
    # markdown-it accepts some malformed constructs by design; unmatched fences are
    # a concrete structural corruption we explicitly reject before finalization.
    fence_lines = [ln for ln in source.splitlines() if ln.lstrip().startswith(('```', '~~~'))]
    if len(fence_lines) % 2:
        raise MarkdownValidationError('Unclosed fenced code block')
    try:
        MarkdownIt('commonmark', {'html': True}).enable('table').parse(source)
    except Exception as exc:
        raise MarkdownValidationError(str(exc)) from exc
    return source
