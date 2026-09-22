from __future__ import annotations

import re

from app.parsers.base import EventRecord
from app.timeutil import parse_utc, to_epoch_ms, to_iso_utc

__all__ = ["normalize_record", "normalize_records", "parse_utc", "to_iso_utc"]

# Control characters and bidirectional overrides let hostile evidence spoof what an
# examiner sees (e.g. right-to-left override making "exe.txt" read as "txt.exe").
_DISPLAY_UNSAFE = re.compile("[\x00-\x1f\x7f‎‏‪-‮⁦-⁩]")


def normalize_record(record: EventRecord, case_timezone: str = "UTC") -> EventRecord:
    """Canonicalise ``ts_utc`` (ms-precision ISO-8601 Zulu) and tidy display fields.

    Raises ``ValueError`` if ``ts_utc`` is not a parseable timestamp.
    """
    dt = parse_utc(record.ts_utc)
    record.ts_utc = to_iso_utc(dt)
    record.ts_ms = to_epoch_ms(dt)
    if not record.tz_assumed:
        record.tz_assumed = "UTC"
    if record.title:
        record.title = _DISPLAY_UNSAFE.sub(" ", record.title).strip()[:300] or "(untitled)"
    if record.domain:
        record.domain = record.domain.lower()
    if record.package:
        record.package = record.package.strip()
    return record


def normalize_records(records: list[EventRecord], case_timezone: str = "UTC") -> list[EventRecord]:
    """Normalise every record, dropping any whose timestamp cannot be parsed."""
    out: list[EventRecord] = []
    for record in records:
        try:
            out.append(normalize_record(record, case_timezone))
        except ValueError:
            continue
    return out
