from __future__ import annotations

from datetime import datetime, timezone

from app.parsers.base import EventRecord


def parse_utc(ts: str) -> datetime:
    text = ts.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso_utc(dt: datetime) -> str:
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def normalize_record(record: EventRecord, case_timezone: str = "UTC") -> EventRecord:
    """Ensure ts_utc is canonical ISO-8601 Zulu; retain original."""
    try:
        dt = parse_utc(record.ts_utc)
        record.ts_utc = to_iso_utc(dt)
    except ValueError:
        # Leave as-is; validation will flag
        pass
    if not record.tz_assumed:
        record.tz_assumed = case_timezone or "UTC"
    if record.title:
        record.title = record.title.strip()[:300]
    if record.domain:
        record.domain = record.domain.lower()
    if record.package:
        record.package = record.package.strip()
    return record


def normalize_records(records: list[EventRecord], case_timezone: str = "UTC") -> list[EventRecord]:
    return [normalize_record(r, case_timezone) for r in records]