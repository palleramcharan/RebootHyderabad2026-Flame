from __future__ import annotations

from pathlib import Path
from typing import Optional

from event_builder.hash_generator import hash_bytes, hash_file, hash_string


def verify_file_integrity(file_path: Path, expected_hash: str) -> bool:
    return hash_file(file_path) == expected_hash


def verify_data_integrity(data: bytes, expected_hash: str) -> bool:
    return hash_bytes(data) == expected_hash


def verify_string_integrity(content: str, expected_hash: str) -> bool:
    return hash_string(content) == expected_hash
