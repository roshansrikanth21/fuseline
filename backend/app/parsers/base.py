from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class EventRecord:
    ts_utc: str
    ts_original: str
    source: str
    event_type: str
    title: str
    tz_assumed: str = "UTC"
    detail: dict[str, Any] = field(default_factory=dict)
    lat: float | None = None
    lon: float | None = None
    package: str | None = None
    url: str | None = None
    domain: str | None = None
    confidence: float = 1.0

    def detail_json(self) -> str:
        return json.dumps(self.detail, ensure_ascii=False)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArtifactParser(Protocol):
    source: str

    def sniff(self, path: Path) -> bool: ...

    def parse(self, path: Path) -> list[EventRecord]: ...


def open_sqlite_readonly(path: Path):
    import sqlite3

    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def table_columns(conn, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None