from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.parsers.base import EventRecord
from app.pipeline.normalize import normalize_records, parse_utc, to_iso_utc


def test_parse_and_roundtrip():
    dt = parse_utc("2024-06-15T10:00:00.123Z")
    assert to_iso_utc(dt) == "2024-06-15T10:00:00.123Z"


def test_normalize_batch():
    records = [
        EventRecord(
            ts_utc="2024-06-15T10:00:00Z",
            ts_original="x",
            source="browsing",
            event_type="visit",
            title="  Hello  ",
            domain="Example.COM",
        )
    ]
    out = normalize_records(records)
    assert out[0].title == "Hello"
    assert out[0].domain == "example.com"