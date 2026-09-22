from __future__ import annotations

import json
import sqlite3

from fastapi import HTTPException

from app.db import case_db_path
from app.models import EventOut, SessionOut
from app.security import assert_safe_case_id
from app.timeutil import parse_utc, to_epoch_ms


def require_case_id(case_id: str) -> str:
    try:
        safe = assert_safe_case_id(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not case_db_path(safe).exists():
        raise HTTPException(status_code=404, detail="Case not found")
    return safe


def parse_bound(value: str | None, name: str) -> int | None:
    """Convert an ISO-8601 query bound to epoch milliseconds (naive input is taken as UTC)."""
    if value is None or value == "":
        return None
    try:
        return to_epoch_ms(parse_utc(value))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid '{name}': expected an ISO-8601 timestamp") from exc


def event_from_row(r: sqlite3.Row) -> EventOut:
    return EventOut(
        id=r["id"],
        artifact_id=r["artifact_id"],
        ts_utc=r["ts_utc"],
        ts_ms=r["ts_ms"],
        ts_original=r["ts_original"],
        tz_assumed=r["tz_assumed"],
        ts_basis=r["ts_basis"],
        source=r["source"],
        event_type=r["event_type"],
        title=r["title"],
        detail=json.loads(r["detail_json"] or "{}"),
        lat=r["lat"],
        lon=r["lon"],
        package=r["package"],
        url=r["url"],
        domain=r["domain"],
        confidence=r["confidence"],
    )


def session_from_row(r: sqlite3.Row) -> SessionOut:
    return SessionOut(
        id=r["id"],
        start_utc=r["start_utc"],
        end_utc=r["end_utc"],
        score=r["score"],
        summary=r["summary"],
        member_event_ids=json.loads(r["member_event_ids"]),
        sources=json.loads(r["sources"]),
        event_count=r["event_count"] or len(json.loads(r["member_event_ids"])),
        centroid_lat=r["centroid_lat"],
        centroid_lon=r["centroid_lon"],
        radius_m=r["radius_m"],
    )
