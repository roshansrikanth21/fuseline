from __future__ import annotations

import json

from fastapi import APIRouter, Query

from app.api.deps import require_case_id
from app.db import case_conn
from app.models import SessionOut, ValidationFindingOut
from app.pipeline.ingest import rebuild_sessions, run_validation

router = APIRouter(prefix="/api/cases/{case_id}", tags=["sessions"])


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(case_id: str) -> list[SessionOut]:
    case_id = require_case_id(case_id)
    with case_conn(case_id) as conn:
        rows = conn.execute("SELECT * FROM sessions ORDER BY score DESC, start_utc").fetchall()
    return [
        SessionOut(
            id=r["id"],
            start_utc=r["start_utc"],
            end_utc=r["end_utc"],
            score=r["score"],
            summary=r["summary"],
            member_event_ids=json.loads(r["member_event_ids"]),
            sources=json.loads(r["sources"]),
        )
        for r in rows
    ]


@router.post("/sessions/rebuild", response_model=list[SessionOut])
def rebuild(case_id: str, window_seconds: int = Query(default=300, ge=30, le=3600)) -> list[SessionOut]:
    case_id = require_case_id(case_id)
    rebuild_sessions(case_id, window_seconds=window_seconds)
    return list_sessions(case_id)


@router.get("/validation", response_model=list[ValidationFindingOut])
def get_validation(case_id: str, refresh: bool = Query(default=False)) -> list[ValidationFindingOut]:
    case_id = require_case_id(case_id)
    if refresh:
        rows = run_validation(case_id)
        return [ValidationFindingOut(**r) for r in rows]
    with case_conn(case_id) as conn:
        rows = conn.execute(
            "SELECT * FROM validation_findings ORDER BY created_at"
        ).fetchall()
    return [
        ValidationFindingOut(
            id=r["id"],
            severity=r["severity"],
            code=r["code"],
            message=r["message"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
