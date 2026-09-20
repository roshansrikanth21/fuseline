from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app.api.deps import require_case_id
from app.models import (
    ArtifactOut,
    CaseOut,
    EventOut,
    ReportSummary,
    SessionOut,
    ValidationFindingOut,
)
from app.report.build import export_events_csv, export_events_json, gather_report_data, render_html_report

router = APIRouter(prefix="/api/cases/{case_id}/report", tags=["report"])


@router.get("", response_model=ReportSummary)
def report_summary(case_id: str) -> ReportSummary:
    case_id = require_case_id(case_id)
    try:
        data = gather_report_data(case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ReportSummary(
        case=CaseOut(**data["case"]),
        artifacts=[
            ArtifactOut(
                id=a["id"],
                source_type=a["source_type"],
                original_name=a["original_name"],
                sha256=a["sha256"],
                ingested_at=a["ingested_at"],
                row_count=a["row_count"],
            )
            for a in data["artifacts"]
        ],
        event_count=data["event_count"],
        source_counts=data["source_counts"],
        session_count=data["session_count"],
        findings=[ValidationFindingOut(**f) for f in data["findings"]],
        sessions=[
            SessionOut(
                id=s["id"],
                start_utc=s["start_utc"],
                end_utc=s["end_utc"],
                score=s["score"],
                summary=s["summary"],
                member_event_ids=s["member_event_ids"],
                sources=s["sources"],
            )
            for s in data["sessions"]
        ],
        sample_events=[
            EventOut(
                id=e["id"],
                artifact_id=e["artifact_id"],
                ts_utc=e["ts_utc"],
                ts_original=e["ts_original"],
                tz_assumed=e["tz_assumed"],
                source=e["source"],
                event_type=e["event_type"],
                title=e["title"],
                detail=e.get("detail") or {},
                lat=e.get("lat"),
                lon=e.get("lon"),
                package=e.get("package"),
                url=e.get("url"),
                domain=e.get("domain"),
                confidence=e.get("confidence", 1.0),
            )
            for e in data["sample_events"]
        ],
    )


@router.get("/html")
def report_html(case_id: str) -> HTMLResponse:
    case_id = require_case_id(case_id)
    html = render_html_report(case_id)
    return HTMLResponse(content=html)


@router.get("/csv")
def report_csv(case_id: str) -> Response:
    case_id = require_case_id(case_id)
    content = export_events_csv(case_id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="fuseline_{case_id}.csv"'},
    )


@router.get("/json")
def report_json(case_id: str) -> PlainTextResponse:
    case_id = require_case_id(case_id)
    content = export_events_json(case_id)
    return PlainTextResponse(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="fuseline_{case_id}.json"'},
    )
