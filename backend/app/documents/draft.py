"""Draft documents FALCON pre-fills from the case record: certificates and requisition letters.

One plain structure, two renderings: JSON for the printable page in the browser, and HTML
(below) for the court bundle. FALCON only DRAFTS: every document says so, leaves the
signature to a person, and lists what must still be checked or filled in by hand.
"""

import html
from dataclasses import dataclass, field

BLANK = "________________"  # a gap the signing officer fills in by hand


@dataclass
class Section:
    heading: str = ""
    paragraphs: list[str] = field(default_factory=list)
    fields: list[tuple[str, str]] = field(default_factory=list)
    items: list[str] = field(default_factory=list)  # a numbered list
    signatures: list[str] = field(default_factory=list)  # one signature block per label


@dataclass
class DraftDocument:
    kind: str
    title: str
    subtitle: str
    reference: str  # what it is about, e.g. "CASE-2026-005 / CCTV-001"
    notice: str  # why it is a draft and what to check
    sections: list[Section] = field(default_factory=list)
    to_check: list[str] = field(default_factory=list)


def to_html(doc: DraftDocument) -> str:
    """A self-contained, printable HTML page (no scripts, no external files)."""
    e = html.escape
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>{e(doc.title)}</title><style>",
        "body{font:12pt/1.5 Georgia,serif;max-width:46rem;margin:2rem auto;color:#111}",
        "h1{font-size:15pt;text-align:center;margin:0}h2{font-size:12pt;margin-top:1.6rem}",
        ".sub{text-align:center;color:#444}.notice{border:1px solid #b45309;padding:.5rem;",
        "background:#fff7ed;font:10pt sans-serif}table{border-collapse:collapse;width:100%}",
        "td{border:1px solid #999;padding:.25rem .5rem;vertical-align:top}",
        "td:first-child{width:35%;color:#333}.sig{margin-top:2.5rem;display:inline-block;",
        "width:45%;margin-right:4%;border-top:1px solid #111;padding-top:.25rem}",
        "</style></head><body>",
        f"<p class='notice'>{e(doc.notice)}</p>",
        f"<h1>{e(doc.title)}</h1><p class='sub'>{e(doc.subtitle)}<br>{e(doc.reference)}</p>",
    ]
    for section in doc.sections:
        if section.heading:
            parts.append(f"<h2>{e(section.heading)}</h2>")
        parts += [f"<p>{e(p)}</p>" for p in section.paragraphs]
        if section.fields:
            rows = "".join(f"<tr><td>{e(k)}</td><td>{e(v)}</td></tr>" for k, v in section.fields)
            parts.append(f"<table>{rows}</table>")
        if section.items:
            parts.append("<ol>" + "".join(f"<li>{e(i)}</li>" for i in section.items) + "</ol>")
        parts += [f"<div class='sig'>{e(s)}</div>" for s in section.signatures]
    if doc.to_check:
        parts.append("<h2>Before signing, check</h2><ul>")
        parts += [f"<li>{e(c)}</li>" for c in doc.to_check]
        parts.append("</ul>")
    parts.append("</body></html>")
    return "".join(parts)
