"""StorageService: where evidence files live.

Today: a folder on this computer (storage/, ignored by Git).
Later: any S3-compatible cloud store — only this module changes.

Rules:
  • Originals are written once, through a temp file, while computing SHA-256 (one pass).
  • The final path is built from an ID we generate — never from the uploader's file name
    (a name like "..\\..\\app\\main.py" must not be able to write anywhere).
  • Originals are made read-only after writing (preservation, plan §27).
  • Derived files (previews, extracted text) live in a separate folder.
"""

import hashlib
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings

CHUNK = 1024 * 1024  # read and hash 1 MB at a time: memory use stays flat for huge files


class FileTooLargeError(Exception):
    pass


@dataclass(frozen=True)
class StoredFile:
    key: str
    sha256: str
    size_bytes: int


def _root() -> Path:
    return Path(get_settings().storage_dir)


def _path(key: str) -> Path:
    root = _root().resolve()
    path = (root / key).resolve()
    if root not in path.parents:  # defence in depth: keys must stay inside storage/
        raise ValueError("Invalid storage key")
    return path


def path_of(key: str) -> Path:
    """Filesystem path for serving a file (validated to stay inside storage)."""
    return _path(key)


def save_original(source: BinaryIO, key: str, max_bytes: int) -> StoredFile:
    """Stream `source` into storage under `key`, hashing as we go."""
    target = _path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    fd, temp_name = tempfile.mkstemp(dir=target.parent, prefix=".upload-")
    try:
        with os.fdopen(fd, "wb") as temp:
            while chunk := source.read(CHUNK):
                size += len(chunk)
                if size > max_bytes:
                    raise FileTooLargeError
                digest.update(chunk)
                temp.write(chunk)
        os.replace(temp_name, target)  # atomic: the file appears complete or not at all
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    os.chmod(target, stat.S_IREAD)  # read-only original
    return StoredFile(key=key, sha256=digest.hexdigest(), size_bytes=size)


def save_derived(data: bytes, key: str) -> str:
    target = _path(key)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return key


def open_file(key: str) -> BinaryIO:
    return _path(key).open("rb")


def iter_file(key: str) -> Iterator[bytes]:
    with open_file(key) as handle:
        while chunk := handle.read(CHUNK):
            yield chunk


def sha256_of(key: str) -> str:
    digest = hashlib.sha256()
    for chunk in iter_file(key):
        digest.update(chunk)
    return digest.hexdigest()


def exists(key: str) -> bool:
    return _path(key).is_file()


def delete(key: str) -> None:
    """Only used to roll back a failed upload — originals are otherwise never deleted."""
    path = _path(key)
    if path.exists():
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        path.unlink()


def copy_to(key: str, destination: Path) -> None:
    with open_file(key) as src, destination.open("wb") as dst:
        shutil.copyfileobj(src, dst, CHUNK)
