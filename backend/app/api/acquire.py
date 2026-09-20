from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import MAX_UPLOAD_BYTES
from app.db import case_conn
from app.models import ArtifactOut, DemoLoadResult, IngestResult, ValidationFindingOut
from app.pipeline.ingest import ingest_file, load_demo_case
from app.api.deps import require_case_id
from app.security import READ_CHUNK, sanitize_filename

router = APIRouter(prefix="/api/cases/{case_id}", tags=["acquire"])


async def _read_upload_capped(upload: UploadFile, suffix: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = Path(tmp.name)
    total = 0
    try:
        while True:
            chunk = await upload.read(READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Upload exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB limit",
                )
            tmp.write(chunk)
        tmp.close()
        if total == 0:
            raise HTTPException(status_code=400, detail="Empty upload")
        return tmp_path
    except Exception:
        tmp.close()
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


@router.post("/acquire", response_model=IngestResult)
async def acquire_artifact(
    case_id: str,
    file: UploadFile = File(...),
    source_hint: str | None = Form(default=None),
) -> IngestResult:
    case_id = require_case_id(case_id)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    try:
        safe_name = sanitize_filename(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    hint = source_hint.strip() if source_hint else None
    if hint == "auto":
        hint = None

    suffix = Path(safe_name).suffix
    tmp_path: Path | None = None
    try:
        tmp_path = await _read_upload_capped(file, suffix)
        result = ingest_file(case_id, tmp_path, safe_name, preferred_source=hint)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    return IngestResult(
        artifact=ArtifactOut(**result["artifact"]),
        events_added=result["events_added"],
        sessions_rebuilt=result["sessions_rebuilt"],
        findings=[ValidationFindingOut(**f) for f in result["findings"]],
    )


@router.post("/acquire/demo", response_model=DemoLoadResult)
def acquire_demo(case_id: str) -> DemoLoadResult:
    case_id = require_case_id(case_id)
    try:
        result = load_demo_case(case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DemoLoadResult(
        artifacts=[ArtifactOut(**a) for a in result["artifacts"]],
        events_added=result["events_added"],
        sessions_rebuilt=result["sessions_rebuilt"],
        findings=[ValidationFindingOut(**f) for f in result["findings"]],
    )


@router.get("/artifacts", response_model=list[ArtifactOut])
def list_artifacts(case_id: str) -> list[ArtifactOut]:
    case_id = require_case_id(case_id)
    with case_conn(case_id) as conn:
        rows = conn.execute("SELECT * FROM artifacts ORDER BY ingested_at").fetchall()
    return [
        ArtifactOut(
            id=r["id"],
            source_type=r["source_type"],
            original_name=r["original_name"],
            sha256=r["sha256"],
            ingested_at=r["ingested_at"],
            row_count=r["row_count"],
        )
        for r in rows
    ]
