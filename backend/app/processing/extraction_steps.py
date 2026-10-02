"""Phase 6 pipeline steps: video metadata, document text, entity & event extraction.

RAW EVIDENCE → VALIDATION → EXTRACTION → NORMALIZATION → STRUCTURING  (plan §13)
                             ▲ text, metadata   ▲ normalize.py   ▲ sink.py (entities, events)
"""

from datetime import timedelta

from app.extraction import media, nlp, structured
from app.extraction.sink import (
    ExtractionSink,
    Provenance,
    clear_automatic_results,
    remove_orphan_entities,
)
from app.extraction.text import extract_text, has_document_text
from app.models import Evidence
from app.processing.pipeline import StepContext, StepFailed, merge_metadata
from app.storage import local as storage

TEXT_PREVIEW_CHARS = 3000


def is_video(evidence: Evidence) -> bool:
    return evidence.media_type.startswith("video/")


# ---------- Video metadata ----------------------------------------------------------------


def extract_video_metadata(ctx: StepContext) -> str:
    evidence = ctx.evidence
    try:
        info = media.video_metadata(evidence.storage_key)
    except Exception as error:  # PyAV raises many error types for damaged files
        raise StepFailed("The video could not be read. It may be damaged or incomplete.") from error
    provenance: dict[str, str] = {}
    start = media.recording_start(info)
    if start and evidence.collected_at is None:
        evidence.collected_at = start[0]
        provenance["collected_at"] = "extracted (video creation_time)"
    if provenance:
        info["provenance"] = provenance
    merge_metadata(evidence, "video", info)
    parts = [f"{info.get('width')}×{info.get('height')} {info.get('codec', '')}".strip()]
    if info.get("duration_s"):
        parts.append(f"{info['duration_s']} s")
    if start:
        parts.append(f"recorded {start[0].isoformat(timespec='seconds')}")
    return "Extracted: " + ", ".join(parts)


# ---------- Document text -----------------------------------------------------------------


def extract_document_text(ctx: StepContext) -> str:
    evidence = ctx.evidence
    try:
        result = extract_text(evidence, ctx.warnings)
    except Exception as error:
        raise StepFailed("The document's text could not be read. It may be damaged.") from error

    ctx.text, ctx.text_method, ctx.text_confidence = result.text, result.method, result.confidence
    storage.save_derived(
        result.text.encode("utf-8"), f"derived/{evidence.investigation_id}/{evidence.id}/text.txt"
    )
    merge_metadata(
        evidence,
        "document",
        {
            "method": result.method,
            "pages": result.pages,
            "characters": len(result.text),
            "ocr_pages": result.ocr_pages,
            "ocr_confidence": round(result.ocr_confidence, 3) if result.ocr_confidence else None,
            "text_preview": result.text[:TEXT_PREVIEW_CHARS],
        },
    )
    if not result.text.strip():
        ctx.warnings.append("No readable text was found in this document.")
        return "No text found."
    if result.ocr_pages:
        if result.confidence < 0.8:
            ctx.warnings.append(
                f"Text was read by OCR with low confidence ({result.confidence:.0%}); "
                "check names and numbers against the original."
            )
        return (
            f"Read {len(result.text):,} characters; OCR used on {len(result.ocr_pages)} page(s), "
            f"average confidence {result.confidence:.0%}."
        )
    return f"Read {len(result.text):,} characters ({result.method})."


# ---------- Entities & events -------------------------------------------------------------


def extract_entities_and_events(ctx: StepContext) -> str:
    evidence = ctx.evidence
    clear_automatic_results(ctx.db, evidence)  # re-running never duplicates facts
    sink = ExtractionSink(ctx.db, evidence)

    if structured.supports(evidence.evidence_type, evidence.media_type):
        structured.extract(sink, ctx.warnings)
    if ctx.text:
        nlp.extract_entities(sink, ctx.text, ctx.text_confidence, ctx.text_method)
    _media_events(sink, evidence)

    ctx.db.flush()
    remove_orphan_entities(ctx.db, evidence)
    return f"Found {len(sink.entities_found)} entities and created {sink.events_created} events."


def _media_events(sink: ExtractionSink, evidence: Evidence) -> None:
    """A photo/video/document is itself evidence that something happened at a time."""
    if evidence.collected_at is None:
        return
    metadata = evidence.file_metadata or {}
    if evidence.media_type.startswith("image/") and evidence.evidence_type == "image":
        kind, verb, section = "photo_taken", "Photo taken", "image"
    elif is_video(evidence):
        kind, verb, section = "video_recorded", "Video recorded", "video"
    elif has_document_text(evidence):
        kind, verb, section = "document_created", "Document dated", "document"
    else:
        return
    origin = (metadata.get(section) or {}).get("provenance", {}).get("collected_at")
    provenance = Provenance(
        assertion="extracted" if origin else "user_entered",
        confidence=0.9 if origin else 1.0,
        extractor="file-metadata" if origin else "evidence-record",
        source_location=origin or "collection time entered at upload",
    )
    duration = (metadata.get("video") or {}).get("duration_s")
    sink.event(
        kind,
        evidence.collected_at,
        provenance,
        description=f"{verb}: {evidence.description or evidence.original_filename}",
        ended_at=evidence.collected_at + timedelta(seconds=duration) if duration else None,
        latitude=evidence.latitude,
        longitude=evidence.longitude,
        location_text=evidence.location_text,
    )
