"""Read timestamps from records. Time zones are the classic source of wrong timelines."""

from dataclasses import dataclass
from datetime import UTC, datetime

_NAIVE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%d/%m/%Y %H:%M")


@dataclass(frozen=True)
class ParsedTime:
    value: datetime  # always timezone-aware
    zone_known: bool


def parse_timestamp(raw: str | None) -> ParsedTime | None:
    """ISO 8601 with an offset ("2026-09-28T20:33:00+05:30", "…Z") keeps its zone.
    A time without a zone is stored as UTC and flagged, so nobody trusts it blindly."""
    if not raw or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00").replace("z", "+00:00")
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        value = None
        for fmt in _NAIVE_FORMATS:
            try:
                value = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if value is None:
            return None
    if value.tzinfo is None:
        return ParsedTime(value.replace(tzinfo=UTC), zone_known=False)
    return ParsedTime(value, zone_known=True)
