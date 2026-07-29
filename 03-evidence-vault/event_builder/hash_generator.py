from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional


def hash_file(file_path: Path, chunk_size: int = 65536) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_string(content: str, encoding: str = "utf-8") -> str:
    return hash_bytes(content.encode(encoding))


def hash_json_file(json_path: Path) -> str:
    return hash_file(json_path)


def verify_hash(file_path: Path, expected_hash: str) -> bool:
    return hash_file(file_path) == expected_hash


def verify_bytes(data: bytes, expected_hash: str) -> bool:
    return hash_bytes(data) == expected_hash
