from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import event_from_row, require_case_id, session_from_row
from app.db import case_conn
from app.models import CorrelationParamsIn, EventOut, SessionOut, ValidationFindingOut
from app.pipeline.ingest import (
    CorrelationParams,
    get_case,
    get_correlation_params,
    rebuild_sessions,
    run_validation,
)

router = APIRouter(prefix="/api/cases/{case_id}", tags=["sessions"])

_CHUNK = 500


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(case_id: str) -> list[SessionOut]:
    case_id = require_case_id(case_id)
    with case_conn(case_id) as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY score DESC, start_utc, id").fetchall()
    return [session_from_row(r) for r in rows]


@router.get("/sessions/params", response_model=CorrelationParamsIn)
def get_params(case_id: str) -> CorrelationParamsIn:
    case_id = require_case_id(case_id)
    with case_conn(case_id) as conn:
        return CorrelationParamsIn(**asdict(get_correlation_params(conn)))


@router.post("/sessions/rebuild", response_model=list[SessionOut])
def rebuild(
    case_id: str,
    window_seconds: int = Query(default=300, ge=1, le=3600),
    max_span_seconds: int = Query(default=1800, ge=30, le=86_400),
    min_sources: int = Query(default=2, ge=1, le=4),
) -> list[SessionOut]:
    case_id = require_case_id(case_id)
    rebuild_sessions(
        case_id,
        CorrelationParams(window_seconds, max_span_seconds, min_sources),
        actor=get_case(case_id)["examiner"],
    )
    return list_sessions(case_id)


@router.get("/sessions/{session_id}/events", response_model=list[EventOut])
def session_events(case_id: str, session_id: str) -> list[EventOut]:
    case_id = require_case_id(case_id)
    with case_conn(case_id) as conn:
        row = conn.execute("SELECT member_event_ids FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")
        ids = json.loads(row["member_event_ids"])
        events: list[EventOut] = []
        for i in range(0, len(ids), _CHUNK):
            chunk = ids[i : i + _CHUNK]
            marks = ",".join("?" for _ in chunk)
            events += [event_from_row(r) for r in conn.execute(f"SELECT * FROM events WHERE id IN ({marks})", chunk)]
    events.sort(key=lambda e: (e.ts_ms, e.id))
    return events


@router.get("/validation", response_model=list[ValidationFindingOut])
def get_validation(case_id: str, refresh: bool = Query(default=False)) -> list[ValidationFindingOut]:
    case_id = require_case_id(case_id)
    if refresh:
        return [ValidationFindingOut(**r) for r in run_validation(case_id)]
    with case_conn(case_id) as conn:
        rows = conn.execute("SELECT * FROM validation_findings ORDER BY rowid").fetchall()
    return [ValidationFindingOut(**dict(r)) for r in rows]
