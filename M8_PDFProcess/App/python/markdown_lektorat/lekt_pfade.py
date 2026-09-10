from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class OutputExistsError(FileExistsError):
    """Raised when a target artifact exists and overwriting is disabled."""


@dataclass(frozen=True)
class DocumentPaths:
    source: Path
    corrected: Path
    review: Path


def resolve_document_paths(
    source: str | Path,
    *,
    output_dir: str | Path | None = None,
    overwrite: bool = False,
) -> DocumentPaths:
    src = Path(source)
    if not src.is_file():
        raise FileNotFoundError(src)
    if src.suffix.lower() != ".md":
        raise ValueError(f"Expected a .md source file, got: {src.name}")

    out_dir = Path(output_dir) if output_dir is not None else src.parent
    corrected = out_dir / f"{src.stem}_korr.md"
    review = out_dir / f"{src.stem}_review.md"

    if not overwrite:
        existing = [p for p in (corrected, review) if p.exists()]
        if existing:
            names = ", ".join(str(p) for p in existing)
            raise OutputExistsError(f"Output exists and overwrite=False: {names}")

    return DocumentPaths(source=src, corrected=corrected, review=review)
