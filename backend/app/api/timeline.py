from __future__ import annotations

import json

from fastapi import APIRouter, Query

from app.api.deps import require_case_id
from app.db import case_conn
from app.models import EventOut, TimelineResponse

router = APIRouter(prefix="/api/cases/{case_id}", tags=["timeline"])


@router.get("/timeline", response_model=TimelineResponse)
def get_timeline(
    case_id: str,
    source: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=20000),
) -> TimelineResponse:
    case_id = require_case_id(case_id)

    clauses: list[str] = []
    params: list[object] = []
    if source:
        sources = [s.strip() for s in source.split(",") if s.strip()]
        if sources:
            placeholders = ",".join("?" for _ in sources)
            clauses.append(f"source IN ({placeholders})")
            params.extend(sources)
    if q:
        clauses.append("(title LIKE ? OR package LIKE ? OR url LIKE ? OR domain LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like, like])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with case_conn(case_id) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM events {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT * FROM events
            {where}
            ORDER BY ts_utc
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        source_rows = conn.execute(
            "SELECT source, COUNT(*) AS c FROM events GROUP BY source"
        ).fetchall()

    events = []
    for r in rows:
        events.append(
            EventOut(
                id=r["id"],
                artifact_id=r["artifact_id"],
                ts_utc=r["ts_utc"],
                ts_original=r["ts_original"],
                tz_assumed=r["tz_assumed"],
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
        )

    return TimelineResponse(
        case_id=case_id,
        events=events,
        total=total,
        sources={r["source"]: r["c"] for r in source_rows},
    )