from __future__ import annotations

import random
import time
from datetime import timedelta

import pytest
from builders import BASE, iso

from app.pipeline.correlate import RawEvent, correlate_events


def ev(eid: str, minutes: float, source: str, **kw) -> RawEvent:
    return RawEvent(
        eid, iso(BASE + timedelta(minutes=minutes)).replace("Z", ".000Z"), source, kw.pop("title", eid), **kw
    )


def test_no_session_from_a_single_source():
    assert correlate_events([ev("a", 0, "app_usage"), ev("b", 1, "app_usage")]) == []


def test_no_events_no_sessions():
    assert correlate_events([]) == []


def test_multi_source_session_with_summary_and_geo():
    events = [
        ev("1", 0, "app_usage", package="com.maps"),
        ev("2", 1, "browsing", domain="maps.google.com"),
        ev("3", 2, "location", lat=12.97, lon=77.59),
        ev("4", 2.5, "location", lat=12.9701, lon=77.5901),
        ev("5", 300, "app_usage", package="com.alone"),
    ]
    (session,) = correlate_events(events, window_seconds=300)
    assert set(session.sources) == {"app_usage", "browsing", "location"}
    assert session.member_event_ids == ["1", "2", "3", "4"]
    assert session.centroid_lat == pytest.approx(12.97005, abs=1e-4)
    assert 0 < session.radius_m < 20
    assert (
        "apps: com.maps" in session.summary
        and "sites: maps.google.com" in session.summary
        and "near 12.97" in session.summary
    )


def test_score_prefers_location():
    with_loc = correlate_events([ev("1", 0, "app_usage"), ev("2", 1, "location", lat=1.0, lon=2.0)])[0]
    without = correlate_events([ev("3", 0, "app_usage"), ev("4", 1, "browsing")])[0]
    assert with_loc.score > without.score


def test_every_event_is_in_at_most_one_session_and_result_is_order_independent():
    random.seed(7)
    events = [
        ev(f"e{i}", random.uniform(0, 600), random.choice(["app_usage", "browsing", "location"])) for i in range(400)
    ]
    first = correlate_events(events)
    shuffled = events[:]
    random.shuffle(shuffled)
    second = correlate_events(shuffled)
    assert [(s.id, s.member_event_ids) for s in first] == [(s.id, s.member_event_ids) for s in second]
    members = [m for s in first for m in s.member_event_ids]
    assert len(members) == len(set(members))


def test_session_ids_are_deterministic_across_runs():
    events = [ev("1", 0, "app_usage"), ev("2", 1, "browsing")]
    assert correlate_events(events)[0].id == correlate_events(list(reversed(events)))[0].id


def test_single_linkage_chains_across_a_long_pause_free_stream():
    # Events every 4 min alternate sources: each is within the 5 min window of its neighbour, so with
    # a generous span cap the whole hour is one session (the old seed-centred scan chopped it up).
    events = [ev(f"e{i}", 4 * i, "browsing" if i % 2 else "app_usage") for i in range(16)]
    (session,) = correlate_events(events, window_seconds=300, max_span_seconds=7200)
    assert session.event_count == 16


def test_span_cap_splits_at_the_widest_pause():
    events = [
        ev("a1", 0, "app_usage"), ev("b1", 1, "browsing"),
        ev("a2", 5, "app_usage"), ev("b2", 6, "browsing"),
        # 4 minute pause is the widest gap inside this cluster
        ev("a3", 10, "app_usage"), ev("b3", 11, "browsing"),
    ]  # fmt: skip
    sessions = correlate_events(events, window_seconds=300, max_span_seconds=600)
    assert all((s.event_count == 4 or s.event_count == 2) and s.sources == ["app_usage", "browsing"] for s in sessions)
    assert sorted(m for s in sessions for m in s.member_event_ids) == ["a1", "a2", "a3", "b1", "b2", "b3"]
    for s in sessions:
        span_min = (RawEvent("x", s.end_utc, "x", "x").millis() - RawEvent("x", s.start_utc, "x", "x").millis()) / 60000
        assert span_min <= 10


def test_min_sources_is_configurable():
    events = [ev("1", 0, "app_usage"), ev("2", 1, "browsing"), ev("3", 2, "location")]
    assert len(correlate_events(events, min_sources=3)) == 1
    assert correlate_events(events[:2], min_sources=3) == []
    assert len(correlate_events(events[:1], min_sources=1)) == 1


def test_window_is_respected():
    events = [ev("1", 0, "app_usage"), ev("2", 10, "browsing")]
    assert correlate_events(events, window_seconds=300) == []
    assert len(correlate_events(events, window_seconds=601)) == 1


def test_identical_timestamps_do_not_loop_forever():
    events = [ev(str(i), 0, "app_usage" if i % 2 else "browsing") for i in range(50)]
    (session,) = correlate_events(events, max_span_seconds=30)
    assert session.event_count == 50


def test_scales_to_large_inputs():
    random.seed(1)
    events = [
        ev(f"x{i}", random.uniform(0, 3 * 24 * 60), random.choice(["browsing", "app_usage", "location"]))
        for i in range(30_000)
    ]
    started = time.perf_counter()
    correlate_events(events)
    assert time.perf_counter() - started < 3.0
