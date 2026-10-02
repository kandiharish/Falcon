"""Processing steps available in Phase 5. Phase 6 adds OCR, entity and event extraction.

Provenance: values read from inside a file (e.g. EXIF GPS) are stored as EXTRACTED and only
fill fields the uploader left empty — they never overwrite what a person entered.
"""

import csv
import io
from datetime import UTC, datetime, tzinfo
from typing import Any
from zoneinfo import ZoneInfo

from PIL import ExifTags, Image, UnidentifiedImageError

from app.ai.provider import AIUnavailable
from app.extraction.text import has_document_text
from app.models import Evidence
from app.processing.extraction_steps import (
    extract_document_text,
    extract_entities_and_events,
    extract_video_metadata,
    is_video,
)
from app.processing.pipeline import Step, StepContext, StepFailed, merge_metadata
from app.services import ai_index_service
from app.storage import local as storage

PREVIEW_MAX_PX = 1024
TEXT_SAMPLE_BYTES = 64 * 1024


# ---------- 1. Validation: is the stored original still exactly what was uploaded? ------


def validate_integrity(ctx: StepContext) -> str:
    evidence = ctx.evidence
    if not storage.exists(evidence.storage_key):
        raise StepFailed("The original file is missing from evidence storage.")
    actual = storage.sha256_of(evidence.storage_key)
    evidence.integrity_checked_at = datetime.now(UTC)
    evidence.integrity_ok = actual == evidence.sha256
    if not evidence.integrity_ok:
        raise StepFailed(
            "The stored file no longer matches its SHA-256 fingerprint from upload. "
            "The original may have been altered; it must be reviewed."
        )
    return "SHA-256 fingerprint matches the value recorded at upload."


# ---------- 2. Metadata extraction --------------------------------------------------------


def extract_image_metadata(ctx: StepContext) -> str:
    evidence = ctx.evidence
    try:
        with storage.open_file(evidence.storage_key) as handle, Image.open(handle) as image:
            info: dict[str, Any] = {
                "width": image.width,
                "height": image.height,
                "format": image.format,
                "mode": image.mode,
            }
            exif = image.getexif()
    except (UnidentifiedImageError, OSError) as error:
        raise StepFailed("The image could not be read. It may be damaged or incomplete.") from error

    exif_values = _readable_exif(exif)
    if exif_values:
        info["exif"] = exif_values

    provenance: dict[str, str] = {}
    case_zone_name = evidence.investigation.time_zone or "UTC"
    taken_info = _exif_datetime(exif, ZoneInfo(case_zone_name))
    taken = taken_info[0] if taken_info else None
    if taken_info and evidence.collected_at is None:
        evidence.collected_at, zone_known = taken_info
        provenance["collected_at"] = (
            "extracted (EXIF DateTimeOriginal with time zone)"
            if zone_known
            else "extracted (EXIF DateTimeOriginal; camera time zone not recorded, "
            f"read in the case's time zone {case_zone_name})"
        )
        if not zone_known:
            ctx.warnings.append(
                "The photo's capture time has no time zone; confirm it against other evidence."
            )
    gps = _exif_gps(exif)
    if gps and evidence.latitude is None:
        evidence.latitude, evidence.longitude = gps
        provenance["latitude"] = provenance["longitude"] = "extracted (EXIF GPS)"
    if provenance:
        info["provenance"] = provenance
    merge_metadata(evidence, "image", info)

    parts = [f"{info['width']}×{info['height']} {info['format']}"]
    if taken:
        parts.append(f"taken {taken.isoformat(timespec='minutes')}")
    if gps:
        parts.append(f"GPS {gps[0]:.5f}, {gps[1]:.5f}")
    if not exif_values:
        ctx.warnings.append("The image has no EXIF metadata (it may have been stripped).")
    return "Extracted: " + ", ".join(parts)


def extract_text_metadata(ctx: StepContext) -> str:
    evidence = ctx.evidence
    with storage.open_file(evidence.storage_key) as handle:
        sample = handle.read(TEXT_SAMPLE_BYTES)
    text = sample.decode("utf-8", errors="replace")
    info: dict[str, Any] = {
        "encoding": "utf-8",
        "sample_lines": text.count("\n") + 1,
        "text_preview": text[:2000],
    }
    if evidence.media_type == "text/csv":
        rows = list(csv.reader(io.StringIO(text)))
        if rows:
            info["columns"] = rows[0]
            info["sample_rows"] = rows[1:6]
            # Row count of the whole file (the sample may be only part of it)
            info["row_count"] = _count_lines(evidence.storage_key) - 1
    merge_metadata(evidence, "text", info)
    if "columns" in info:
        return f"CSV with {len(info['columns'])} columns and {info['row_count']} data rows."
    return f"Text file, {info['sample_lines']} lines in the first 64 KB."


def _count_lines(key: str) -> int:
    return sum(chunk.count(b"\n") for chunk in storage.iter_file(key))


# ---------- 3. Preview (a derived copy for viewing; the original is untouched) ----------


def build_image_preview(ctx: StepContext) -> str:
    evidence = ctx.evidence
    with storage.open_file(evidence.storage_key) as handle, Image.open(handle) as image:
        preview = image.convert("RGB")
        preview.thumbnail((PREVIEW_MAX_PX, PREVIEW_MAX_PX))
        buffer = io.BytesIO()
        preview.save(buffer, format="JPEG", quality=85)  # no EXIF copied into the preview
    evidence.preview_key = storage.save_derived(
        buffer.getvalue(), f"derived/{evidence.investigation_id}/{evidence.id}/preview.jpg"
    )
    return f"Preview created ({preview.width}×{preview.height})."


# ---------- Registry ----------------------------------------------------------------------


TEXT_MEDIA_TYPES = {"application/json", "application/xml", "application/gpx+xml"}


def fingerprint_image(ctx: StepContext) -> str:
    """Perceptual hash for near-duplicate detection (no AI: a fixed algorithm)."""
    value = ai_index_service.fingerprint_image(ctx.evidence)
    return f"Fingerprint {value}."


def index_for_similarity(ctx: StepContext) -> str:
    """Embed the document's text so similar documents can be found. Needs the local AI;
    if it is not running the step is skipped, never failed: processing must not depend on AI."""
    if not ctx.text or not ctx.text.strip():
        return "No text to index."
    try:
        count = ai_index_service.index_text(ctx.db, ctx.evidence, ctx.text)
    except AIUnavailable:
        return "Skipped: the local AI service is not running. Use “Rebuild AI index” later."
    return f"Indexed {count} passage{'s' if count != 1 else ''} for similarity search."


def is_image(evidence: Evidence) -> bool:
    return evidence.media_type.startswith("image/")


def is_text(evidence: Evidence) -> bool:
    return evidence.media_type.startswith("text/") or evidence.media_type in TEXT_MEDIA_TYPES


def _structured_text(evidence: Evidence) -> bool:
    """Text that is a record file (CSV, JSON …), not a document to be read as prose."""
    return is_text(evidence) and not has_document_text(evidence)


# Steps run in this order; each decides from the file's real content whether it applies.
STEPS: list[Step] = [
    Step("integrity", "Validation", validate_integrity),
    Step("image_metadata", "Metadata extraction", extract_image_metadata, is_image),
    Step("video_metadata", "Metadata extraction", extract_video_metadata, is_video),
    Step("text_metadata", "Metadata extraction", extract_text_metadata, _structured_text),
    Step("document_text", "Text extraction", extract_document_text, has_document_text),
    Step("entities_events", "Entity & event extraction", extract_entities_and_events),
    Step("image_preview", "Preview generation", build_image_preview, is_image),
    Step("image_fingerprint", "Image fingerprint", fingerprint_image, is_image),
    Step("similarity_index", "AI similarity index", index_for_similarity, has_document_text),
]


# ---------- EXIF helpers ------------------------------------------------------------------

_EXIF_TAGS_OF_INTEREST = {
    "Make",
    "Model",
    "Software",
    "DateTimeOriginal",
    "DateTime",
    "OffsetTimeOriginal",
}
# EXIF text values are often padded with NUL characters and spaces.
_EXIF_PADDING = "\x00 "


def _readable_exif(exif: Image.Exif) -> dict[str, str]:
    values: dict[str, str] = {}
    merged = dict(exif.items()) | dict(exif.get_ifd(ExifTags.IFD.Exif).items())
    for tag_id, value in merged.items():
        name = ExifTags.TAGS.get(tag_id)
        if name in _EXIF_TAGS_OF_INTEREST and isinstance(value, str | int | float):
            values[name] = str(value).strip(_EXIF_PADDING)
    return values


def _exif_datetime(exif: Image.Exif, assumed_zone: tzinfo = UTC) -> tuple[datetime, bool] | None:
    """(time, zone_known). EXIF stores the camera's local clock time; newer cameras add the
    UTC offset in OffsetTimeOriginal (e.g. "+05:30"). Without it the zone is unknown and we
    read the clock time in the investigation's zone, flagged so investigators know."""
    exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
    raw = exif_ifd.get(ExifTags.Base.DateTimeOriginal) or exif.get(ExifTags.Base.DateTime)
    if not isinstance(raw, str):
        return None
    try:
        local = datetime.strptime(raw.strip(_EXIF_PADDING), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    offset = exif_ifd.get(ExifTags.Base.OffsetTimeOriginal) or exif_ifd.get(
        ExifTags.Base.OffsetTime
    )
    if isinstance(offset, str):
        try:
            with_zone = f"{local:%Y-%m-%d %H:%M:%S}{offset.strip(_EXIF_PADDING)}"
            return datetime.strptime(with_zone, "%Y-%m-%d %H:%M:%S%z"), True
        except ValueError:
            pass
    return local.replace(tzinfo=assumed_zone), False


def _exif_gps(exif: Image.Exif) -> tuple[float, float] | None:
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    try:
        lat = _dms_to_degrees(gps[ExifTags.GPS.GPSLatitude], gps[ExifTags.GPS.GPSLatitudeRef])
        lon = _dms_to_degrees(gps[ExifTags.GPS.GPSLongitude], gps[ExifTags.GPS.GPSLongitudeRef])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 7), round(lon, 7)


def _dms_to_degrees(dms: Any, ref: str) -> float:
    degrees, minutes, seconds = (float(part) for part in dms)
    value = degrees + minutes / 60 + seconds / 3600
    return -value if ref in ("S", "W") else value
