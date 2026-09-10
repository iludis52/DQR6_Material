from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
from pathlib import Path
import os
import tempfile


@dataclass
class CheckpointState:
    source_sha256: str
    model: str
    current_pass: str
    next_chunk_index: int
    completed_chunk_ids: list[str] = field(default_factory=list)
    current_corrected_sha256: str = ""
    status: str = "running"
    entries: list[dict] = field(default_factory=list)
    applied_edits: list[dict] = field(default_factory=list)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', errors='strict', newline='') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def save_checkpoint(path: str | Path, state: CheckpointState) -> None:
    p = Path(path)
    _atomic_write(p, json.dumps(asdict(state), ensure_ascii=False, indent=2) + '\n')


def load_checkpoint(path: str | Path) -> CheckpointState:
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    return CheckpointState(**data)
