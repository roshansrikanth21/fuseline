from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.db import init_case_db, registry_conn, row_to_dict
from app.models import CaseCreate, CaseOut

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@router.get("", response_model=list[CaseOut])
def list_cases() -> list[CaseOut]:
    with registry_conn() as conn:
        rows = conn.execute("SELECT * FROM cases ORDER BY updated_at DESC").fetchall()
    return [CaseOut(**dict(r)) for r in rows]


@router.post("", response_model=CaseOut, status_code=201)
def create_case(body: CaseCreate) -> CaseOut:
    case_id = str(uuid.uuid4())
    now = _utcnow()
    with registry_conn() as conn:
        conn.execute(
            """
            INSERT INTO cases (id, name, examiner, timezone, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                body.name.strip(),
                body.examiner.strip(),
                body.timezone.strip() or "UTC",
                body.notes.strip(),
                now,
                now,
            ),
        )
    init_case_db(case_id)
    return CaseOut(
        id=case_id,
        name=body.name.strip(),
        examiner=body.examiner.strip(),
        timezone=body.timezone.strip() or "UTC",
        notes=body.notes.strip(),
        created_at=now,
        updated_at=now,
        event_count=0,
        artifact_count=0,
        session_count=0,
    )


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str) -> CaseOut:
    from app.security import assert_safe_case_id

    try:
        case_id = assert_safe_case_id(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    with registry_conn() as conn:
        row = row_to_dict(conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone())
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseOut(**row)


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: str) -> None:
    import shutil

    from app.config import UPLOADS_DIR
    from app.db import case_db_path
    from app.security import assert_safe_case_id, assert_under

    try:
        case_id = assert_safe_case_id(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    with registry_conn() as conn:
        row = conn.execute("SELECT id FROM cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Case not found")
        conn.execute("DELETE FROM cases WHERE id=?", (case_id,))
    db_path = case_db_path(case_id)
    if db_path.exists():
        db_path.unlink()
    upload_dir = assert_under(UPLOADS_DIR / case_id, UPLOADS_DIR)
    if upload_dir.exists():
        shutil.rmtree(upload_dir, ignore_errors=True)