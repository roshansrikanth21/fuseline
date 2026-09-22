"""Append-only, hash-chained audit log.

Every entry stores the hash of the entry before it, so removing or editing a row breaks
the chain and :func:`verify_chain` reports where. The log lives in the registry database
(not the per-case one) so it survives case deletion.
"""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

from app.db import registry_conn
from app.timeutil import now_iso

GENESIS_HASH = "0" * 64
_lock = threading.Lock()


def _entry_hash(prev_hash: str, ts: str, case_id: str | None, actor: str, action: str, detail_json: str) -> str:
    material = "\x1f".join([prev_hash, ts, case_id or "", actor, action, detail_json])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def record(
    action: str,
    *,
    case_id: str | None = None,
    actor: str = "",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ts = now_iso()
    detail_json = json.dumps(detail or {}, sort_keys=True, ensure_ascii=False, default=str)
    with _lock, registry_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        prev_hash = row[0] if row else GENESIS_HASH
        entry_hash = _entry_hash(prev_hash, ts, case_id, actor, action, detail_json)
        cur = conn.execute(
            """
            INSERT INTO audit_log (ts, case_id, actor, action, detail_json, prev_hash, entry_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, case_id, actor, action, detail_json, prev_hash, entry_hash),
        )
        entry_id = cur.lastrowid
    return {"id": entry_id, "ts": ts, "action": action, "entry_hash": entry_hash}


def list_entries(case_id: str, limit: int = 500) -> list[dict[str, Any]]:
    with registry_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log WHERE case_id = ? ORDER BY id LIMIT ?", (case_id, limit)
        ).fetchall()
    entries = []
    for r in rows:
        item = dict(r)
        item["detail"] = json.loads(item.pop("detail_json") or "{}")
        entries.append(item)
    return entries


def verify_chain() -> tuple[bool, int | None]:
    """Recompute the whole chain. Returns ``(ok, first_bad_entry_id)``."""
    prev = GENESIS_HASH
    with registry_conn() as conn:
        for r in conn.execute("SELECT * FROM audit_log ORDER BY id"):
            expected = _entry_hash(prev, r["ts"], r["case_id"], r["actor"], r["action"], r["detail_json"])
            if r["prev_hash"] != prev or r["entry_hash"] != expected:
                return False, int(r["id"])
            prev = r["entry_hash"]
    return True, None
