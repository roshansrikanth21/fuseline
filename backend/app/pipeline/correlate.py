from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass

from app.config import (
    DEFAULT_CORRELATION_WINDOW_SECONDS,
    DEFAULT_MAX_SESSION_SPAN_SECONDS,
    DEFAULT_MIN_SOURCES,
)
from app.geo import centroid, radius_m
from app.timeutil import parse_utc, to_epoch_ms

SESSION_NAMESPACE = uuid.UUID("6f0d1e0c-56b5-4c3e-9f0a-5f1e2b7d9a11")


@dataclass
class RawEvent:
    id: str
    ts_utc: str
    source: str
    title: str
    package: str | None = None
    domain: str | None = None
    lat: float | None = None
    lon: float | None = None
    ts_ms: int | None = None

    def millis(self) -> int:
        if self.ts_ms is None:
            self.ts_ms = to_epoch_ms(parse_utc(self.ts_utc))
        return self.ts_ms


@dataclass
class SessionResult:
    id: str
    start_utc: str
    end_utc: str
    score: float
    summary: str
    member_event_ids: list[str]
    sources: list[str]
    event_count: int = 0
    centroid_lat: float | None = None
    centroid_lon: float | None = None
    radius_m: float | None = None


def _top(values: list[str], limit: int = 3) -> list[str]:
    return [v for v, _ in Counter(values).most_common(limit)]


def _summary(members: list[RawEvent], center: tuple[float, float] | None, radius: float | None) -> str:
    parts: list[str] = []
    packages = _top([m.package for m in members if m.package])
    domains = _top([m.domain for m in members if m.domain])
    if packages:
        parts.append("apps: " + ", ".join(packages))
    if domains:
        parts.append("sites: " + ", ".join(domains))
    if center is not None:
        where = f"near {center[0]:.4f},{center[1]:.4f}"
        if radius is not None and radius >= 1:
            where += f" (±{radius:.0f} m)"
        parts.append(where)
    head = " + ".join(sorted({m.source for m in members}))
    return f"{head}: {'; '.join(parts) if parts else members[0].title}"


def _split(cluster: list[RawEvent]) -> tuple[list[RawEvent], list[RawEvent]]:
    """Cut a too-long cluster at its widest internal pause (nearest the middle on ties)."""
    times = [e.millis() for e in cluster]
    middle = (times[0] + times[-1]) / 2
    best_index, best_key = 1, (-1, 0.0)
    for i in range(1, len(cluster)):
        gap = times[i] - times[i - 1]
        key = (gap, -abs((times[i] + times[i - 1]) / 2 - middle))
        if key > best_key:
            best_index, best_key = i, key
    return cluster[:best_index], cluster[best_index:]


def _build(cluster: list[RawEvent]) -> SessionResult:
    sources = sorted({e.source for e in cluster})
    fixes = [(e.lat, e.lon) for e in cluster if e.lat is not None and e.lon is not None]
    center = centroid(fixes) if fixes else None
    radius = radius_m(center, fixes) if center is not None else None
    score = len(sources) + (0.5 if "location" in sources else 0.0) + min(1.0, len(cluster) / 10.0)
    member_ids = [e.id for e in cluster]
    return SessionResult(
        id=str(uuid.uuid5(SESSION_NAMESPACE, ",".join(member_ids))),
        start_utc=cluster[0].ts_utc,
        end_utc=cluster[-1].ts_utc,
        score=round(score, 2),
        summary=_summary(cluster, center, radius),
        member_event_ids=member_ids,
        sources=sources,
        event_count=len(cluster),
        centroid_lat=center[0] if center else None,
        centroid_lon=center[1] if center else None,
        radius_m=round(radius, 1) if radius is not None else None,
    )


def correlate_events(
    events: list[RawEvent],
    window_seconds: int = DEFAULT_CORRELATION_WINDOW_SECONDS,
    max_span_seconds: int = DEFAULT_MAX_SESSION_SPAN_SECONDS,
    min_sources: int = DEFAULT_MIN_SOURCES,
) -> list[SessionResult]:
    """Group events into proximity sessions.

    Events are chained into a cluster while each is within ``window_seconds`` of the
    previous one (single linkage), so every event lands in at most one session and the
    result does not depend on which event a scan happens to start from. A cluster is kept
    if it spans at least ``min_sources`` distinct sources. Clusters longer than
    ``max_span_seconds`` are cut at their widest pauses so continuous activity cannot fuse
    into one all-day session. Output is deterministic: ids derive from member ids.
    """
    if not events:
        return []
    window_ms = max(1, int(window_seconds)) * 1000
    span_ms = max(window_ms, int(max_span_seconds) * 1000)
    needed = max(1, int(min_sources))

    ordered = sorted(events, key=lambda e: (e.millis(), e.id))
    clusters: list[list[RawEvent]] = []
    current = [ordered[0]]
    for event in ordered[1:]:
        if event.millis() - current[-1].millis() <= window_ms:
            current.append(event)
        else:
            clusters.append(current)
            current = [event]
    clusters.append(current)

    sessions: list[SessionResult] = []
    stack = clusters[::-1]
    while stack:
        cluster = stack.pop()
        if len({e.source for e in cluster}) < needed:
            continue
        if len(cluster) > 1 and cluster[-1].millis() - cluster[0].millis() > span_ms:
            left, right = _split(cluster)
            stack.append(right)
            stack.append(left)
            continue
        sessions.append(_build(cluster))

    sessions.sort(key=lambda s: (-s.score, s.start_utc, s.id))
    return sessions
