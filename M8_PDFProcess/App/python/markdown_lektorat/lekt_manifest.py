from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4


def file_sha256(path: Path) -> str:
    h = sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(
    *, input_path: Path, model: str, base_url: str,
    inference_parameters: dict, skill_version: str,
    pass_status: dict, output_hashes: dict, run_id: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        'run_id': run_id or uuid4().hex,
        'started_at': now,
        'finished_at': now,
        'input_path': str(input_path),
        'input_sha256': file_sha256(input_path),
        'model': model,
        'base_url': base_url,
        'inference_parameters': inference_parameters,
        'skill_version': skill_version,
        'pass_status': pass_status,
        'output_hashes': output_hashes,
    }
