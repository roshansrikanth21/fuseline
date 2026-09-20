from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.parsers.app_usage import AppUsageParser
from app.parsers.chrome_history import ChromeHistoryParser
from app.parsers.location import LocationParser
from app.parsers.plaso_l2tcsv import PlasoL2TCSVParser
from app.pipeline.correlate import RawEvent, correlate_events
from app.pipeline.normalize import normalize_record, parse_utc
from app.parsers.base import EventRecord


@pytest.fixture(scope="session")
def demo_dir() -> Path:
    demo = ROOT / "samples" / "demo_case"
    if not (demo / "app_usage.db").exists():
        sys.path.insert(0, str(ROOT / "scripts"))
        import seed_demo

        seed_demo.main()
    return demo


def test_app_usage_parser(demo_dir: Path):
    path = demo_dir / "app_usage.db"
    parser = AppUsageParser()
    assert parser.sniff(path)
    events = parser.parse(path)
    assert len(events) >= 4
    assert all(e.source == "app_usage" for e in events)
    assert any(e.package and "maps" in e.package for e in events)


def test_chrome_history_parser(demo_dir: Path):
    path = demo_dir / "History"
    parser = ChromeHistoryParser()
    assert parser.sniff(path)
    events = parser.parse(path)
    assert len(events) >= 3
    assert all(e.source == "browsing" for e in events)
    assert any(e.domain and "google" in e.domain for e in events)


def test_location_parser(demo_dir: Path):
    path = demo_dir / "location.csv"
    parser = LocationParser()
    assert parser.sniff(path)
    events = parser.parse(path)
    assert len(events) == 3
    assert events[0].lat is not None and events[0].lon is not None


def test_plaso_parser(demo_dir: Path):
    path = demo_dir / "plaso_sample.l2t.csv"
    parser = PlasoL2TCSVParser()
    assert parser.sniff(path)
    events = parser.parse(path)
    assert len(events) == 1
    assert events[0].source == "browsing"


def test_normalize_utc():
    rec = EventRecord(
        ts_utc="2024-06-15T10:00:00+00:00",
        ts_original="raw",
        source="app_usage",
        event_type="launch",
        title="com.example",
    )
    out = normalize_record(rec)
    assert out.ts_utc.endswith("Z")
    assert parse_utc(out.ts_utc).tzinfo is not None


def test_correlate_multi_source():
    base = datetime(2024, 6, 15, 10, 0, 0, tzinfo=timezone.utc)

    def iso(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    events = [
        RawEvent("1", iso(base), "app_usage", "maps", package="com.maps"),
        RawEvent("2", iso(base + timedelta(minutes=1)), "browsing", "Directions", domain="maps.google.com"),
        RawEvent(
            "3",
            iso(base + timedelta(minutes=2)),
            "location",
            "fix",
            lat=12.97,
            lon=77.59,
        ),
        RawEvent("4", iso(base + timedelta(hours=5)), "app_usage", "lonely", package="com.alone"),
    ]
    sessions = correlate_events(events, window_seconds=300)
    assert len(sessions) >= 1
    top = sessions[0]
    assert set(top.sources) >= {"app_usage", "browsing", "location"}
    assert len(top.member_event_ids) >= 3