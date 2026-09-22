from __future__ import annotations

import os
import shutil
import stat
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app import audit
from app.config import UPLOADS_DIR
from app.db import case_db_path, forget_case, init_case_db, registry_conn, row_to_dict
from app.models import CaseCreate, CaseOut, CaseUpdate
from app.security import assert_safe_case_id, assert_under
from app.timeutil import now_iso

router = APIRouter(prefix="/api/cases", tags=["cases"])


def _safe_id(case_id: str) -> str:
    try:
        return assert_safe_case_id(case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _fetch(case_id: str) -> dict:
    with registry_conn() as conn:
        row = row_to_dict(conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone())
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return row


def _force_remove(func, path, _exc) -> None:
    # Evidence copies are read-only; clear the flag so the case can be deleted on Windows.
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    func(path)


@router.get("", response_model=list[CaseOut])
def list_cases() -> list[CaseOut]:
    with registry_conn() as conn:
        rows = conn.execute("SELECT * FROM cases ORDER BY updated_at DESC").fetchall()
    return [CaseOut(**dict(r)) for r in rows]


@router.post("", response_model=CaseOut, status_code=201)
def create_case(body: CaseCreate) -> CaseOut:
    case_id = str(uuid.uuid4())
    now = now_iso()
    with registry_conn() as conn:
        conn.execute(
            """
            INSERT INTO cases (id, name, examiner, timezone, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (case_id, body.name, body.examiner, body.timezone, body.notes, now, now),
        )
    init_case_db(case_id)
    audit.record(
        "case.create",
        case_id=case_id,
        actor=body.examiner,
        detail={"name": body.name, "timezone": body.timezone},
    )
    return CaseOut(id=case_id, created_at=now, updated_at=now, **body.model_dump())


@router.get("/{case_id}", response_model=CaseOut)
def get_case(case_id: str) -> CaseOut:
    return CaseOut(**_fetch(_safe_id(case_id)))


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(case_id: str, body: CaseUpdate) -> CaseOut:
    case_id = _safe_id(case_id)
    before = _fetch(case_id)
    changes = body.model_dump(exclude_none=True)
    if changes:
        assignments = ", ".join(f"{col} = ?" for col in changes)
        with registry_conn() as conn:
            conn.execute(
                f"UPDATE cases SET {assignments}, updated_at = ? WHERE id = ?",
                (*changes.values(), now_iso(), case_id),
            )
        audit.record(
            "case.update",
            case_id=case_id,
            actor=changes.get("examiner", before["examiner"]),
            detail={k: {"from": before[k], "to": v} for k, v in changes.items() if before[k] != v},
        )
    return CaseOut(**_fetch(case_id))


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: str) -> None:
    case_id = _safe_id(case_id)
    case = _fetch(case_id)
    with registry_conn() as conn:
        conn.execute("DELETE FROM cases WHERE id=?", (case_id,))
    db_path = case_db_path(case_id)
    for suffix in ("", "-wal", "-shm"):
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)
    forget_case(case_id)
    upload_dir = assert_under(UPLOADS_DIR / case_id, UPLOADS_DIR)
    if upload_dir.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(upload_dir, onexc=_force_remove)
        else:
            shutil.rmtree(upload_dir, onerror=_force_remove)
    audit.record(
        "case.delete",
        case_id=case_id,
        actor=case["examiner"],
        detail={"name": case["name"], "events": case["event_count"], "artifacts": case["artifact_count"]},
    )
