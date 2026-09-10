from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re


IMAGE_RE = re.compile(r"!\[[^\]\n]*\]\([^\n)]*\)")
PAGEBREAK_RE = re.compile(r"<!--\s*Seitenumbruch\s*-->")


class ProtectedIntegrityError(RuntimeError):
    """Raised when a protected source invariant is violated."""


@dataclass(frozen=True)
class ProtectedElement:
    kind: str
    literal_text: str
    occurrence_index: int
    source_position: int
    digest: str


@dataclass(frozen=True)
class ProtectedInventory:
    images: tuple[ProtectedElement, ...]
    pagebreaks: tuple[ProtectedElement, ...]


def _collect(pattern: re.Pattern[str], source: str, kind: str) -> tuple[ProtectedElement, ...]:
    result: list[ProtectedElement] = []
    for idx, match in enumerate(pattern.finditer(source)):
        literal = match.group(0)
        result.append(ProtectedElement(
            kind=kind,
            literal_text=literal,
            occurrence_index=idx,
            source_position=match.start(),
            digest=sha256(literal.encode('utf-8')).hexdigest(),
        ))
    return tuple(result)


def inventory_protected(source: str) -> ProtectedInventory:
    return ProtectedInventory(
        images=_collect(IMAGE_RE, source, "image"),
        pagebreaks=_collect(PAGEBREAK_RE, source, "pagebreak"),
    )


def _literal_sequence(items: tuple[ProtectedElement, ...]) -> list[str]:
    return [x.literal_text for x in items]


def validate_protected(original: ProtectedInventory, target_source: str) -> None:
    target = inventory_protected(target_source)
    if _literal_sequence(original.images) != _literal_sequence(target.images):
        raise ProtectedIntegrityError("Protected image references changed, disappeared, or were reordered")
    if _literal_sequence(original.pagebreaks) != _literal_sequence(target.pagebreaks):
        raise ProtectedIntegrityError("Protected page-break markers changed, disappeared, or were reordered")
