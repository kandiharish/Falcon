"""Decide what a file really is from its CONTENT ("magic bytes"), not its name.

A file called holiday.jpg can be a Windows program. Trusting the extension would let
dangerous files in, so we read the first bytes and compare them with known signatures.
"""

from pathlib import PurePath

import filetype

# Programs and scripts are never accepted as evidence uploads in this phase.
BLOCKED_TYPES = {
    "application/x-msdownload",
    "application/x-dosexec",
    "application/x-executable",
    "application/x-elf",
    "application/x-mach-binary",
    "application/vnd.microsoft.portable-executable",
}
BLOCKED_EXTENSIONS = {".exe", ".dll", ".bat", ".cmd", ".ps1", ".sh", ".msi", ".scr", ".js", ".vbs"}

TEXT_TYPES_BY_EXTENSION = {
    ".csv": "text/csv",
    ".json": "application/json",
    ".gpx": "application/gpx+xml",
    ".xml": "application/xml",
    ".txt": "text/plain",
    ".log": "text/plain",
}

# Which content types make sense for each kind of evidence.
ALLOWED_BY_EVIDENCE_TYPE: dict[str, set[str] | None] = {
    "video": {"video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm"},
    "image": {"image/jpeg", "image/png", "image/tiff", "image/webp", "image/heic", "image/bmp"},
    "document": {
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "witness_statement": {
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "gps": {"text/csv", "application/json", "application/gpx+xml", "application/xml", "text/plain"},
    "call_records": {"text/csv", "application/json", "text/plain"},
    "financial": {"text/csv", "application/json", "text/plain", "application/pdf"},
    "mobile": {"text/csv", "application/json", "application/xml", "text/plain", "application/zip"},
    "vehicle": {"text/csv", "application/json", "text/plain"},
    "digital_file": None,  # any non-blocked type
    "other": None,
}


def detect_media_type(head: bytes, filename: str) -> str:
    """Best guess of the real content type from the first bytes of the file."""
    kind = filetype.guess(head)
    if kind is not None:
        return kind.mime
    if _looks_like_text(head):
        return TEXT_TYPES_BY_EXTENSION.get(PurePath(filename).suffix.lower(), "text/plain")
    return "application/octet-stream"


def _looks_like_text(head: bytes) -> bool:
    if b"\x00" in head:
        return False
    try:
        head.decode("utf-8")
    except UnicodeDecodeError as error:
        # A multi-byte character may be cut at the end of the sample; that is still text.
        return error.start >= len(head) - 3
    return True


def rejection_reason(media_type: str, filename: str, evidence_type: str) -> str | None:
    """None if acceptable; otherwise a message the investigator can act on."""
    suffix = PurePath(filename).suffix.lower()
    if media_type in BLOCKED_TYPES or suffix in BLOCKED_EXTENSIONS:
        return "Programs and scripts cannot be uploaded as evidence."
    allowed = ALLOWED_BY_EVIDENCE_TYPE.get(evidence_type)
    if allowed is not None and media_type not in allowed:
        return (
            f"This file's content looks like '{media_type}', which does not match the evidence "
            f"type '{evidence_type.replace('_', ' ')}'. Choose the correct evidence type or file."
        )
    return None


def safe_extension(filename: str) -> str:
    """'.jpg' for 'photo.JPG'; '' when the extension is missing or unusual."""
    suffix = PurePath(filename).suffix.lower()
    return suffix if 2 <= len(suffix) <= 6 and suffix[1:].isalnum() else ""
