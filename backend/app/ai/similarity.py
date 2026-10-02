"""Pure helpers for similarity: cutting text into chunks, and fingerprinting images.

TEXT  ── chunks of ~600 characters ──► embedding model ──► 384 numbers each ──► pgvector
IMAGE ── shrink to 9×8 grey pixels ──► "is each pixel brighter than its right neighbour?"
         ──► 64 yes/no bits = the difference hash (dHash)

Two near-identical photos (resized, re-compressed, slightly brightened) keep almost the same
bits; the number of differing bits (Hamming distance) says how close they are.
"""

import re
from pathlib import Path

from PIL import Image

CHUNK_CHARS = 600  # all-MiniLM reads ~256 tokens; 600 characters stays safely below
CHUNK_OVERLAP = 100  # a sentence cut in two still appears whole in one of the chunks
NEAR_DUPLICATE_BITS = 10  # ≤ 10 of 64 bits different = probably the same picture


def chunk_text(text: str) -> list[str]:
    """Split on paragraphs/sentences, packing them into chunks of about CHUNK_CHARS."""
    clean = re.sub(r"[ \t]+", " ", text).strip()
    if not clean:
        return []
    pieces = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n{2,}", clean) if p.strip()]
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        while len(piece) > CHUNK_CHARS:  # one enormous sentence: cut it hard
            chunks.append(piece[:CHUNK_CHARS])
            piece = piece[CHUNK_CHARS - CHUNK_OVERLAP :]
        if current and len(current) + 1 + len(piece) > CHUNK_CHARS:
            chunks.append(current)
            tail = current[-CHUNK_OVERLAP:]
            current = f"{tail[tail.find(' ') + 1 :]} {piece}" if " " in tail else piece
        else:
            current = f"{current} {piece}".strip()
    if current:
        chunks.append(current)
    return chunks


def dhash(path: Path) -> str:
    """64-bit difference hash as 16 hex characters."""
    with Image.open(path) as image:
        small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(small.tobytes())  # one byte (0–255) per grey pixel
    bits = 0
    for row in range(8):
        for col in range(8):
            left, right = pixels[row * 9 + col], pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    """How many of the 64 bits differ."""
    return (int(a, 16) ^ int(b, 16)).bit_count()
