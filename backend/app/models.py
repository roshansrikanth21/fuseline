from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal["location", "browsing", "app_usage", "plaso"]
Severity = Literal["pass", "warn", "fail", "info"]


class CaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    examiner: str = Field(default="", max_length=200)
    timezone: str = Field(default="UTC", max_length=64)
    notes: str = Field(default="", max_length=4000)


class CaseOut(BaseModel):
    id: str
    name: str
    examiner: str
    timezone: str
    notes: str
    created_at: str
    updated_at: str
    event_count: int = 0
    artifact_count: int = 0
    session_count: int = 0


class ArtifactOut(BaseModel):
    id: str
    source_type: str
    original_name: str
    sha256: str
    ingested_at: str
    row_count: int


class EventOut(BaseModel):
    id: str
    artifact_id: str
    ts_utc: str
    ts_original: str
    tz_assumed: str
    source: str
    event_type: str
    title: str
    detail: dict[str, Any] = Field(default_factory=dict)
    lat: float | None = None
    lon: float | None = None
    package: str | None = None
    url: str | None = None
    domain: str | None = None
    confidence: float = 1.0


class SessionOut(BaseModel):
    id: str
    start_utc: str
    end_utc: str
    score: float
    summary: str
    member_event_ids: list[str]
    sources: list[str]


class ValidationFindingOut(BaseModel):
    id: str
    severity: str
    code: str
    message: str
    created_at: str


class TimelineResponse(BaseModel):
    case_id: str
    events: list[EventOut]
    total: int
    sources: dict[str, int]


class IngestResult(BaseModel):
    artifact: ArtifactOut
    events_added: int
    sessions_rebuilt: int
    findings: list[ValidationFindingOut]


class DemoLoadResult(BaseModel):
    artifacts: list[ArtifactOut]
    events_added: int
    sessions_rebuilt: int
    findings: list[ValidationFindingOut]


class ReportSummary(BaseModel):
    case: CaseOut
    artifacts: list[ArtifactOut]
    event_count: int
    source_counts: dict[str, int]
    session_count: int
    findings: list[ValidationFindingOut]
    sessions: list[SessionOut]
    sample_events: list[EventOut]