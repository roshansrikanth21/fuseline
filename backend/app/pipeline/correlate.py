from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from app.config import DEFAULT_CORRELATION_WINDOW_SECONDS
from app.pipeline.normalize import parse_utc


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


@dataclass
class SessionResult:
    id: str
    start_utc: str
    end_utc: str
    score: float
    summary: str
    member_event_ids: list[str]
    sources: list[str]


def _centroid(points: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    if not points:
        return None, None
    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)
    return lat, lon


def _summary(members: list[RawEvent]) -> str:
    packages = [m.package for m in members if m.package]
    domains = [m.domain for m in members if m.domain]
    locs = [(m.lat, m.lon) for m in members if m.lat is not None and m.lon is not None]
    parts: list[str] = []
    if packages:
        parts.append("apps: " + ", ".join(list(dict.fromkeys(packages))[:3]))
    if domains:
        parts.append("sites: " + ", ".join(list(dict.fromkeys(domains))[:3]))
    lat, lon = _centroid([(float(a), float(b)) for a, b in locs if a is not None and b is not None])
    if lat is not None and lon is not None:
        parts.append(f"near {lat:.4f},{lon:.4f}")
    sources = sorted({m.source for m in members})
    head = " + ".join(sources)
    body = "; ".join(parts) if parts else members[0].title
    return f"{head}: {body}"


def correlate_events(
    events: list[RawEvent],
    window_seconds: int = DEFAULT_CORRELATION_WINDOW_SECONDS,
) -> list[SessionResult]:
    if not events:
        return []

    ordered = sorted(events, key=lambda e: e.ts_utc)
    window = timedelta(seconds=max(30, window_seconds))
    used: set[str] = set()
    sessions: list[SessionResult] = []

    for i, seed in enumerate(ordered):
        if seed.id in used:
            continue
        seed_dt = parse_utc(seed.ts_utc)
        cluster = [seed]
        sources = {seed.source}

        j = i + 1
        while j < len(ordered):
            candidate = ordered[j]
            cand_dt = parse_utc(candidate.ts_utc)
            if cand_dt - seed_dt > window:
                break
            if candidate.id not in used:
                cluster.append(candidate)
                sources.add(candidate.source)
            j += 1

        # Also look slightly backward within window from seed for density
        k = i - 1
        while k >= 0:
            candidate = ordered[k]
            cand_dt = parse_utc(candidate.ts_utc)
            if seed_dt - cand_dt > window:
                break
            if candidate.id not in used:
                cluster.append(candidate)
                sources.add(candidate.source)
            k -= 1

        if len(sources) < 2:
            continue

        # Expand cluster to include all members within window of any member (one pass)
        cluster = sorted(cluster, key=lambda e: e.ts_utc)
        start_dt = parse_utc(cluster[0].ts_utc)
        end_dt = parse_utc(cluster[-1].ts_utc)
        expanded: list[RawEvent] = []
        cluster_ids = {c.id for c in cluster}
        for ev in ordered:
            if ev.id in used and ev.id not in cluster_ids:
                continue
            ev_dt = parse_utc(ev.ts_utc)
            if start_dt - window <= ev_dt <= end_dt + window:
                if abs((ev_dt - start_dt).total_seconds()) <= window.total_seconds() or abs(
                    (ev_dt - end_dt).total_seconds()
                ) <= window.total_seconds():
                    expanded.append(ev)
        if not expanded:
            expanded = cluster

        sources = {e.source for e in expanded}
        if len(sources) < 2:
            continue

        for ev in expanded:
            used.add(ev.id)

        start_utc = min(e.ts_utc for e in expanded)
        end_utc = max(e.ts_utc for e in expanded)
        score = float(len(sources)) + (0.5 if "location" in sources else 0.0)
        score += min(1.0, len(expanded) / 10.0)

        sessions.append(
            SessionResult(
                id=str(uuid.uuid4()),
                start_utc=start_utc,
                end_utc=end_utc,
                score=round(score, 2),
                summary=_summary(expanded),
                member_event_ids=[e.id for e in sorted(expanded, key=lambda x: x.ts_utc)],
                sources=sorted(sources),
            )
        )

    sessions.sort(key=lambda s: (-s.score, s.start_utc))
    return sessions


def group_source_counts(events: list[RawEvent]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for e in events:
        counts[e.source] += 1
    return dict(counts)