from __future__ import annotations

from pathlib import Path
from typing import Optional

EVIDENCE_ROOT: Path = Path(__file__).resolve().parent.parent.parent / "data"
SUBMISSIONS_DIR: Path = EVIDENCE_ROOT / "submissions"
FILES_DIR: Path = EVIDENCE_ROOT / "files"


def ensure_dirs() -> None:
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)


def submission_path(submission_id: str) -> Path:
    return SUBMISSIONS_DIR / f"{submission_id}.json"


def file_path(submission_id: str, filename: str) -> Path:
    return FILES_DIR / submission_id / filename
