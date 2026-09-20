from __future__ import annotations

from fastapi import HTTPException

from app.db import case_db_path
from app.security import assert_safe_case_id


def require_case_id(case_id: str) -> str:
    try:
        safe = assert_safe_case_id(case_id)
        if not case_db_path(safe).exists():
            raise HTTPException(status_code=404, detail="Case not found")
        return safe
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
