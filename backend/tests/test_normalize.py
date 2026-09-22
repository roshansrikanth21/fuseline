from __future__ import annotations

from app.parsers.base import EventRecord
from app.pipeline.normalize import normalize_record, normalize_records
from app.timeutil import parse_utc, to_iso_utc


def record(**overrides) -> EventRecord:
    base = {
        "ts_utc": "2024-06-15T10:00:00+00:00",
        "ts_original": "raw",
        "source": "browsing",
        "event_type": "visit",
        "title": "Hello",
    }
    return EventRecord(**{**base, **overrides})


def test_canonical_utc_and_epoch_millis():
    out = normalize_record(record())
    assert out.ts_utc == "2024-06-15T10:00:00.000Z"
    assert out.ts_ms == 1718445600000


def test_roundtrip():
    assert to_iso_utc(parse_utc("2024-06-15T10:00:00.123Z")) == "2024-06-15T10:00:00.123Z"


def test_title_domain_package_are_tidied():
    out = normalize_record(record(title="  Hello  ", domain="Example.COM", package="  com.x  "))
    assert (out.title, out.domain, out.package) == ("Hello", "example.com", "com.x")


def test_display_spoofing_characters_are_stripped_from_titles():
    out = normalize_record(record(title="invoice‮gpj.exe\x00\nnext"))
    assert "‮" not in out.title and "\x00" not in out.title and "\n" not in out.title


def test_empty_title_gets_a_placeholder():
    assert normalize_record(record(title="‮\x00")).title == "(untitled)"


def test_unparseable_records_are_dropped_not_stored_corrupt():
    good, bad = record(), record(ts_utc="2024-06-15T10:01:00-05:00Z")
    assert normalize_records([good, bad]) == [good]
