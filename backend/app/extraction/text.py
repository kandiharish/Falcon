"""Get the text out of a document, so names, phones and plates can be found in it.

    .txt  → read directly
    .pdf  → the PDF's own text layer (pdfium); pages WITHOUT text (scans) → OCR
    .docx → paragraphs and tables
    image (when the evidence is a document/statement) → OCR

OCR reads letters from pixels, so it can be wrong. Its confidence is kept and lowers the
confidence of everything found in that text.
"""

import io
import logging
import re
from dataclasses import dataclass, field

from PIL import Image

from app.core.config import get_settings
from app.models import Evidence
from app.storage import local as storage

log = logging.getLogger("falcon.extraction")

MAX_PAGES = 50
MIN_TEXT_PER_PAGE = 20  # fewer characters than this → treat the page as a scan
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
DOCUMENT_EVIDENCE = {"document", "witness_statement"}


@dataclass
class TextResult:
    text: str
    method: str  # "text" | "pdf-text" | "ocr" | "pdf-text+ocr" | "docx"
    pages: int = 1
    ocr_pages: list[int] = field(default_factory=list)
    ocr_confidence: float | None = None

    @property
    def confidence(self) -> float:
        return self.ocr_confidence if self.ocr_confidence is not None else 1.0


def has_document_text(evidence: Evidence) -> bool:
    if evidence.media_type in ("application/pdf", DOCX_TYPE):
        return True
    if evidence.evidence_type in DOCUMENT_EVIDENCE:
        return evidence.media_type == "text/plain" or evidence.media_type.startswith("image/")
    return False


def extract_text(evidence: Evidence, warnings: list[str]) -> TextResult:
    media = evidence.media_type
    if media == "application/pdf":
        return _pdf(evidence.storage_key, warnings)
    if media == DOCX_TYPE:
        return _docx(evidence.storage_key)
    if media.startswith("image/"):
        with storage.open_file(evidence.storage_key) as handle, Image.open(handle) as image:
            text, confidence = ocr_image(image.convert("RGB"))
        return TextResult(text=text, method="ocr", ocr_pages=[1], ocr_confidence=confidence)
    with storage.open_file(evidence.storage_key) as handle:
        raw = handle.read(2_000_000)
    return TextResult(text=raw.decode("utf-8", errors="replace"), method="text")


def _pdf(key: str, warnings: list[str]) -> TextResult:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(storage.path_of(key)))
    try:
        page_count = len(pdf)
        texts: list[str] = []
        ocr_pages: list[int] = []
        ocr_scores: list[float] = []
        for index in range(min(page_count, MAX_PAGES)):
            page = pdf[index]
            text = page.get_textpage().get_text_range()
            if len(text.strip()) < MIN_TEXT_PER_PAGE and get_settings().ocr_enabled:
                image = page.render(scale=2).to_pil().convert("RGB")
                text, score = ocr_image(image)
                ocr_pages.append(index + 1)
                ocr_scores.append(score)
            texts.append(text)
        if page_count > MAX_PAGES:
            warnings.append(f"Only the first {MAX_PAGES} of {page_count} pages were read.")
    finally:
        pdf.close()
    method = (
        "pdf-text" if not ocr_pages else ("ocr" if len(ocr_pages) == len(texts) else "pdf-text+ocr")
    )
    confidence = sum(ocr_scores) / len(ocr_scores) if ocr_scores else None
    return TextResult("\n\n".join(texts), method, page_count, ocr_pages, confidence)


def _docx(key: str) -> TextResult:
    import docx

    with storage.open_file(key) as handle:
        document = docx.Document(io.BytesIO(handle.read()))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text for cell in row.cells))
    return TextResult("\n".join(parts), "docx")


# ---------- OCR (RapidOCR: offline, models bundled with the package) ----------------------

_ocr_engine = None


def ocr_image(image: Image.Image) -> tuple[str, float]:
    """Text found in the image, and the average confidence of the recognised lines (0–1)."""
    global _ocr_engine
    import numpy as np

    if _ocr_engine is None:  # loading takes a few seconds; do it once per worker
        from rapidocr_onnxruntime import RapidOCR

        log.info("Loading OCR models…")
        _ocr_engine = RapidOCR()
    result, _ = _ocr_engine(np.array(image))
    if not result:
        return "", 0.0
    lines = [repair_ocr_spacing(text) for _box, text, _score in result]
    scores = [float(score) for _box, _text, score in result]
    return "\n".join(lines), sum(scores) / len(scores)


_JOINED_WORDS = re.compile(r"(?<=[a-z])(?=[A-Z])")  # "AnitaShah" → "Anita Shah"
_PUNCT_BEFORE_CAPITAL = re.compile(r"([.:;,])(?=[A-Z])")  # "Name:Anita" → "Name: Anita"


def repair_ocr_spacing(line: str) -> str:
    """OCR models sometimes drop the spaces between words. These two safe rules put most of
    them back; the original scan is always available to check against."""
    return _PUNCT_BEFORE_CAPITAL.sub(r"\1 ", _JOINED_WORDS.sub(" ", line))
