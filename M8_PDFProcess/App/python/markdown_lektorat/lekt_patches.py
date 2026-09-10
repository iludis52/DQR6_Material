from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .lekt_bloecke import DocumentBlock
from .lekt_schema import EditProposal, Operation


class PatchError(RuntimeError):
    pass


class UnknownTargetError(PatchError):
    pass


class SourceMismatchError(PatchError):
    pass


class PatchConflictError(PatchError):
    pass


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    replacement: str
    edit_id: str


def _line_offsets(source: str) -> list[int]:
    offsets = [0]
    pos = 0
    for line in source.splitlines(keepends=True):
        pos += len(line)
        offsets.append(pos)
    if not source.endswith(("\n", "\r")) and offsets[-1] != len(source):
        offsets.append(len(source))
    return offsets


def _block_span(source: str, block: DocumentBlock) -> tuple[int, int]:
    offsets = _line_offsets(source)
    if block.end_line >= len(offsets):
        raise PatchError(f"Block line range out of bounds: {block.block_id}")
    return offsets[block.start_line], offsets[block.end_line]


def _get_block(index: dict[str, DocumentBlock], block_id: str) -> DocumentBlock:
    try:
        return index[block_id]
    except KeyError as exc:
        raise UnknownTargetError(block_id) from exc


def _simple_span(source: str, block: DocumentBlock, edit: EditProposal) -> _Span:
    start, end = _block_span(source, block)
    op = edit.operation
    if op in {Operation.REPLACE_TEXT, Operation.REPLACE_TABLE}:
        if edit.replacement_text is None:
            raise PatchError(f"{op.value} requires replacement_text")
        replacement = edit.replacement_text
        # preserve a single trailing newline when source block occupied whole lines
        if source[start:end].endswith("\n") and not replacement.endswith("\n"):
            replacement += "\n"
    elif op == Operation.DELETE_DUPLICATE:
        replacement = ""
    elif op is Operation.UNRESOLVED:
        replacement = source[start:end]
    elif op in {Operation.MERGE_BLOCKS, Operation.MOVE_TEXT_BLOCK, Operation.MOVE_CAPTION}:
        raise PatchError(f"Operation {op.value} handled separately")
    else:
        raise PatchError(f"Unsupported operation: {op.value}")
    return _Span(start, end, replacement, edit.edit_id)


def _ensure_no_overlap(spans: list[_Span]) -> None:
    ordered = sorted(spans, key=lambda s: (s.start, s.end))
    for left, right in zip(ordered, ordered[1:]):
        if right.start < left.end:
            raise PatchConflictError(f"Overlapping edits: {left.edit_id}, {right.edit_id}")


def apply_edits(source: str, blocks: Iterable[DocumentBlock], edits: Iterable[EditProposal]) -> str:
    block_list = list(blocks)
    index = {b.block_id: b for b in block_list}
    edits = list(edits)

    # Validate every referenced ID before any mutation.
    for edit in edits:
        for bid in edit.target_ids:
            _get_block(index, bid)
        if edit.destination_id is not None:
            _get_block(index, edit.destination_id)

    spans: list[_Span] = []
    move_edits: list[EditProposal] = []

    for edit in edits:
        if edit.operation in {Operation.MOVE_CAPTION, Operation.MOVE_TEXT_BLOCK, Operation.MERGE_BLOCKS}:
            move_edits.append(edit)
            continue
        target = _get_block(index, edit.target_ids[0])
        spans.append(_simple_span(source, target, edit))

    # Initial overlap check for simple edits.
    _ensure_no_overlap(spans)

    # Move-like operations are converted into removal + insertion spans against the same source state.
    for edit in move_edits:
        target = _get_block(index, edit.target_ids[0])
        t_start, t_end = _block_span(source, target)

        if edit.operation == Operation.MERGE_BLOCKS:
            if edit.replacement_text is None:
                raise PatchError("merge_blocks requires replacement_text")
            target_blocks = [_get_block(index, bid) for bid in edit.target_ids]
            starts_ends = [_block_span(source, b) for b in target_blocks]
            start = min(x[0] for x in starts_ends)
            end = max(x[1] for x in starts_ends)
            replacement = edit.replacement_text
            if source[start:end].endswith("\n") and not replacement.endswith("\n"):
                replacement += "\n"
            spans.append(_Span(start, end, replacement, edit.edit_id))
            continue

        if edit.destination_id is None:
            raise PatchError(f"{edit.operation.value} requires destination_id")
        dest = _get_block(index, edit.destination_id)
        d_start, d_end = _block_span(source, dest)
        moved_text = source[t_start:t_end]
        spans.append(_Span(t_start, t_end, "", edit.edit_id + ":remove"))
        placement = (edit.placement or "after").lower()
        if placement == "before":
            insert_at = d_start
            insertion = moved_text
        elif placement == "after":
            insert_at = d_end
            insertion = moved_text
        else:
            raise PatchError(f"Unknown placement: {edit.placement}")
        spans.append(_Span(insert_at, insert_at, insertion, edit.edit_id + ":insert"))

    _ensure_no_overlap([s for s in spans if s.start != s.end])

    result = source
    for span in sorted(spans, key=lambda s: (s.start, s.end), reverse=True):
        result = result[:span.start] + span.replacement + result[span.end:]
    return result
