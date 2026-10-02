"""Entities and events from structured records (CSV): calls, GPS, transactions, vehicles.

Structured records are the most reliable source: each row states its facts directly, so
results are labelled EXTRACTED with high confidence. Times without a time zone get a lower
confidence and a note, because they could be off by hours.

Column names differ between providers, so each kind of record accepts common aliases.
"""

import csv
import io
from collections.abc import Iterator
from datetime import datetime, timedelta

from app.extraction.sink import ExtractionSink, Provenance
from app.extraction.timeparse import ParsedTime, parse_timestamp
from app.storage import local as storage

MAX_ROWS = 20_000

ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "call_records": {
        "caller": ("caller", "from", "calling_number", "a_number", "source", "originator"),
        "callee": ("callee", "to", "called_number", "b_number", "destination", "recipient"),
        "time": (
            "started_at",
            "start_time",
            "timestamp",
            "datetime",
            "date_time",
            "call_time",
            "time",
        ),
        "duration": ("duration_s", "duration_seconds", "duration"),
        "cell": ("cell_site", "cell_id", "tower", "cell"),
    },
    "gps": {
        "device": ("device_id", "device", "imei", "tracker", "phone"),
        "time": ("recorded_at", "timestamp", "datetime", "time", "fix_time"),
        "lat": ("latitude", "lat"),
        "lon": ("longitude", "lon", "lng", "long"),
    },
    "financial": {
        "account": ("account", "account_id", "card", "card_number", "from_account"),
        "merchant": ("merchant", "payee", "counterparty", "to_account"),
        "amount": ("amount", "value"),
        "currency": ("currency", "ccy"),
        "time": ("occurred_at", "timestamp", "transaction_time", "datetime", "date"),
        "id": ("transaction_id", "txn_id", "reference", "id"),
    },
    "vehicle": {
        "plate": ("plate", "registration", "plate_number", "number_plate", "vrm"),
        "time": ("seen_at", "timestamp", "datetime", "time", "detected_at"),
        "camera": ("camera", "camera_id", "site", "location"),
        "lat": ("latitude", "lat"),
        "lon": ("longitude", "lon", "lng"),
    },
}
REQUIRED = {
    "call_records": ("caller", "callee", "time"),
    "gps": ("device", "time", "lat", "lon"),
    "financial": ("account", "time"),
    "vehicle": ("plate", "time"),
}


def supports(evidence_type: str, media_type: str) -> bool:
    return evidence_type in ALIASES and media_type == "text/csv"


def extract(sink: ExtractionSink, warnings: list[str]) -> None:
    evidence = sink.evidence
    kind = evidence.evidence_type
    rows = _rows(evidence.storage_key)
    header = next(rows, None)
    if header is None:
        warnings.append("The file has no rows to extract.")
        return
    columns = _map_columns(header, ALIASES[kind])
    missing = [name for name in REQUIRED[kind] if name not in columns]
    if missing:
        warnings.append(
            f"Could not find column(s) for {', '.join(missing)} in this {kind.replace('_', ' ')} "
            f"file (found: {', '.join(header)}). No events were extracted."
        )
        return

    unzoned = 0
    for line_number, row in enumerate(rows, start=2):
        if line_number - 1 > MAX_ROWS:
            warnings.append(f"Only the first {MAX_ROWS:,} rows were extracted.")
            break
        value = _getter(row, columns)
        when = parse_timestamp(value("time"))
        if when and not when.zone_known:
            unzoned += 1
        HANDLERS[kind](sink, value, when, line_number)
    if unzoned:
        warnings.append(
            f"{unzoned} row(s) have times without a time zone; they were read as UTC and "
            "marked with lower confidence."
        )


# ---------- per record type ---------------------------------------------------------------


def _calls(sink: ExtractionSink, value, when: ParsedTime | None, line: int) -> None:
    caller = sink.entity("phone_number", value("caller"), _prov(line, "caller", value("caller")))
    callee = sink.entity("phone_number", value("callee"), _prov(line, "callee", value("callee")))
    duration = _number(value("duration"))
    attributes = {
        k: v for k, v in {"duration_s": duration, "cell_site": value("cell")}.items() if v
    }
    sink.event(
        "call_made",
        _time(when),
        _prov(line, "row", "", when),
        description=_call_description(caller, callee, duration),
        participants=[(caller, "caller"), (callee, "callee")],
        ended_at=_plus_seconds(_time(when), duration),
        attributes=attributes,
    )


def _call_description(caller, callee, duration: float | None) -> str:
    text = f"Call from {caller.label if caller else '?'} to {callee.label if callee else '?'}"
    return text + (f" ({int(duration)} s)" if duration else "")


def _gps(sink: ExtractionSink, value, when: ParsedTime | None, line: int) -> None:
    lat, lon = _number(value("lat")), _number(value("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return
    device = sink.entity("device", value("device"), _prov(line, "device", value("device")))
    sink.event(
        "location_recorded",
        _time(when),
        _prov(line, "row", "", when),
        description=f"{device.label if device else 'Device'} recorded at {lat:.5f}, {lon:.5f}",
        participants=[(device, "device")],
        latitude=lat,
        longitude=lon,
    )


def _transactions(sink: ExtractionSink, value, when: ParsedTime | None, line: int) -> None:
    account = sink.entity("account", value("account"), _prov(line, "account", value("account")))
    merchant = sink.entity(
        "organization", value("merchant"), _prov(line, "merchant", value("merchant"))
    )
    amount, currency = _number(value("amount")), value("currency")
    money = f"{amount:,.2f} {currency}".strip() if amount is not None else "a payment"
    sink.event(
        "transaction_completed",
        _time(when),
        _prov(line, "row", "", when),
        description=f"{account.label if account else 'Account'} paid {money}"
        + (f" to {merchant.label}" if merchant else ""),
        participants=[(account, "payer"), (merchant, "payee")],
        attributes={
            k: v
            for k, v in {
                "amount": amount,
                "currency": currency,
                "transaction_id": value("id"),
            }.items()
            if v
        },
    )


def _vehicles(sink: ExtractionSink, value, when: ParsedTime | None, line: int) -> None:
    vehicle = sink.entity("vehicle", value("plate"), _prov(line, "plate", value("plate")))
    lat, lon = _number(value("lat")), _number(value("lon"))
    camera = value("camera")
    sink.event(
        "vehicle_detected",
        _time(when),
        _prov(line, "row", "", when),
        description=f"Vehicle {vehicle.label if vehicle else '?'} detected"
        + (f" by {camera}" if camera else ""),
        participants=[(vehicle, "vehicle")],
        latitude=lat,
        longitude=lon,
        location_text=camera,
        attributes={"camera": camera} if camera else {},
    )


HANDLERS = {
    "call_records": _calls,
    "gps": _gps,
    "financial": _transactions,
    "vehicle": _vehicles,
}


# ---------- helpers -----------------------------------------------------------------------


def _rows(key: str) -> Iterator[list[str]]:
    with storage.open_file(key) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8-sig", errors="replace", newline="")
        yield from csv.reader(text)


def _map_columns(header: list[str], aliases: dict[str, tuple[str, ...]]) -> dict[str, int]:
    cleaned = [h.strip().lower().replace(" ", "_") for h in header]
    mapping: dict[str, int] = {}
    for name, options in aliases.items():
        for option in options:
            if option in cleaned:
                mapping[name] = cleaned.index(option)
                break
    return mapping


def _getter(row: list[str], columns: dict[str, int]):
    def value(name: str) -> str:
        index = columns.get(name)
        return row[index].strip() if index is not None and index < len(row) else ""

    return value


def _prov(line: int, column: str, raw: str, when: ParsedTime | None = None) -> Provenance:
    confidence = 0.95 if when is None or when.zone_known else 0.8
    location = f"line {line}" if column == "row" else f"line {line}, column {column}"
    return Provenance("extracted", confidence, "csv-records", location, raw)


def _time(when: ParsedTime | None) -> datetime | None:
    return when.value if when else None


def _number(raw: str) -> float | None:
    try:
        return float(raw.replace(",", "")) if raw else None
    except ValueError:
        return None


def _plus_seconds(start: datetime | None, seconds: float | None) -> datetime | None:
    return start + timedelta(seconds=seconds) if start and seconds else None
