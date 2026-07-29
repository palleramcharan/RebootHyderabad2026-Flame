from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from event_builder.hash_generator import hash_bytes, hash_file
from ev_storage.file_store import load_submission
from ev_storage.storage_config import ensure_dirs, submission_path


def cross_check_hash(
    submission_id: str,
    stored_content: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    record = load_submission(submission_id)
    if record is None:
        return False, None, None

    stored_hash = record.get("sha256_hash") or record.get("fields", {}).get("sha256_hash", "")
    if not stored_hash:
        return False, None, None

    if stored_content is not None:
        current_hash = hash_bytes(stored_content.encode("utf-8"))
    else:
        ensure_dirs()
        spath = submission_path(submission_id)
        if not spath.exists():
            return False, stored_hash, None
        current_hash = hash_file(spath)

    match = current_hash == stored_hash
    return match, stored_hash, current_hash


def verify_all_files(submission_id: str) -> Dict[str, bool]:
    from ev_storage.file_store import list_files

    results: Dict[str, bool] = {}
    for fpath in list_files(submission_id):
        name = fpath.name
        record = load_submission(submission_id)
        expected = (record or {}).get("file_hashes", {}).get(name, "")
        if not expected:
            results[name] = False
        else:
            results[name] = hash_file(fpath) == expected
    return results
