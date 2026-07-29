from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from .storage_config import ensure_dirs, file_path, submission_path


def save_submission(submission_id: str, data: Dict[str, Any]) -> Path:
    ensure_dirs()
    path = submission_path(submission_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def load_submission(submission_id: str) -> Optional[Dict[str, Any]]:
    path = submission_path(submission_id)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def save_file(submission_id: str, filename: str, content: bytes) -> Path:
    ensure_dirs()
    path = file_path(submission_id, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def load_file(submission_id: str, filename: str) -> Optional[bytes]:
    path = file_path(submission_id, filename)
    if not path.exists():
        return None
    return path.read_bytes()


def list_files(submission_id: str) -> list[Path]:
    base = file_path(submission_id, "").parent
    if not base.exists():
        return []
    return [p for p in base.iterdir() if p.is_file()]


def delete_submission(submission_id: str) -> None:
    path = submission_path(submission_id)
    if path.exists():
        path.unlink()
