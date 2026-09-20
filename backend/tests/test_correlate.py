from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.pipeline.correlate import RawEvent, correlate_events


def test_no_session_single_source():
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    events = [
        RawEvent("a", base.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "app_usage", "a"),
        RawEvent(
            "b",
            (base + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "app_usage",
            "b",
        ),
    ]
    assert correlate_events(events) == []


def test_session_score_prefers_location():
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def iso(m: int) -> str:
        return (base + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    with_loc = [
        RawEvent("1", iso(0), "app_usage", "x", package="p"),
        RawEvent("2", iso(1), "location", "y", lat=1.0, lon=2.0),
    ]
    without = [
        RawEvent("3", iso(0), "app_usage", "x", package="p"),
        RawEvent("4", iso(1), "browsing", "y", domain="example.com"),
    ]
    s1 = correlate_events(with_loc)[0]
    s2 = correlate_events(without)[0]
    assert s1.score >= s2.score