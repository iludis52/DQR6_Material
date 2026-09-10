from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable

from .lekt_bloecke import DocumentBlock


class ContextBudgetError(RuntimeError):
    pass


@dataclass(frozen=True)
class ContextBlock:
    block_id: str
    block_type: str
    raw_text: str
    editable: bool


@dataclass(frozen=True)
class ContextWindow:
    target_ids: tuple[str, ...]
    blocks: tuple[ContextBlock, ...]


def estimate_tokens(text: str, *, chars_per_token: float = 3.0) -> int:
    """Conservative tokenizer-independent estimate for local context budgeting.

    This is deliberately not used for semantic decisions. It only prevents very
    large requests. The real model context limit in LM Studio remains the hard
    upper bound.
    """
    if not text:
        return 0
    return max(1, ceil(len(text) / chars_per_token))


def partition_target_ids(
    blocks: Iterable[DocumentBlock],
    target_ids: list[str],
    *,
    max_target_tokens: int,
) -> list[list[str]]:
    if max_target_tokens <= 0:
        raise ValueError("max_target_tokens must be > 0")

    block_list = list(blocks)
    by_id = {b.block_id: b for b in block_list}
    missing = [bid for bid in target_ids if bid not in by_id]
    if missing:
        raise KeyError(f"Unknown target ids: {missing}")

    batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0

    for bid in target_ids:
        block_tokens = estimate_tokens(by_id[bid].raw_text)
        if current and current_tokens + block_tokens > max_target_tokens:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(bid)
        current_tokens += block_tokens

    if current:
        batches.append(current)
    return batches


def build_context_window(blocks: Iterable[DocumentBlock], target_ids: list[str], *, overlap: int = 2) -> ContextWindow:
    block_list = list(blocks)
    index = {b.block_id: i for i, b in enumerate(block_list)}
    missing = [bid for bid in target_ids if bid not in index]
    if missing:
        raise KeyError(f"Unknown target ids: {missing}")
    if not target_ids:
        return ContextWindow((), ())

    target_positions = [index[bid] for bid in target_ids]
    lo = max(0, min(target_positions) - max(0, overlap))
    hi = min(len(block_list), max(target_positions) + max(0, overlap) + 1)
    target_set = set(target_ids)
    selected = tuple(
        ContextBlock(b.block_id, b.block_type, b.raw_text, b.block_id in target_set)
        for b in block_list[lo:hi]
    )
    return ContextWindow(tuple(target_ids), selected)
