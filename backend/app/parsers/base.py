from __future__ import annotations

import csv
import json
import sqlite3
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import tzinfo
from pathlib import Path
from typing import Any, Protocol

from app.security import quote_ident
from app.timeutil import BASIS_ASSUMED, UTC, Timestamp, coerce_timestamp, resolve_timezone

SQLITE_MAGIC = b"SQLite format 3\x00"
MAX_NOTE_REASONS = 8
MAX_DETAIL_VALUE_CHARS = 2000
SQLITE_QUERY_BUDGET_SECONDS = 60.0

csv.field_size_limit(16 * 1024 * 1024)


@dataclass
class EventRecord:
    ts_utc: str
    ts_original: str
    source: str
    event_type: str
    title: str
    tz_assumed: str = "UTC"
    ts_basis: str = "absolute"
    detail: dict[str, Any] = field(default_factory=dict)
    lat: float | None = None
    lon: float | None = None
    package: str | None = None
    url: str | None = None
    domain: str | None = None
    confidence: float = 1.0
    ts_ms: int = 0

    def detail_json(self) -> str:
        return json.dumps(self.detail, ensure_ascii=False, default=str)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParseContext:
    """Per-case parsing settings. ``tz`` only ever applies to naive local-time strings."""

    tz_name: str = "UTC"
    tz: tzinfo = UTC

    @classmethod
    def for_timezone(cls, name: str) -> ParseContext:
        cleaned = (name or "UTC").strip() or "UTC"
        tz = resolve_timezone(cleaned)
        return cls(tz_name="UTC" if tz is UTC else cleaned, tz=tz)

    def timestamp(self, raw: object, unit: str = "auto") -> Timestamp:
        return coerce_timestamp(raw, tz=self.tz, unit=unit)

    def tz_label(self, ts: Timestamp) -> str:
        return self.tz_name if ts.basis == BASIS_ASSUMED else "UTC"


@dataclass
class ParseResult:
    records: list[EventRecord] = field(default_factory=list)
    skipped: int = 0
    reasons: Counter[str] = field(default_factory=Counter)

    def skip(self, reason: str) -> None:
        self.skipped += 1
        self.reasons[reason] += 1

    def notes(self) -> list[str]:
        return [f"{count} row(s) skipped: {reason}" for reason, count in self.reasons.most_common(MAX_NOTE_REASONS)]


class ArtifactParser(Protocol):
    source: str
    name: str

    def sniff(self, path: Path) -> float:
        """Return confidence in [0, 1] that ``path`` is this format; 0 means no."""
        ...

    def parse(self, path: Path, ctx: ParseContext) -> ParseResult: ...


def clip(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_DETAIL_VALUE_CHARS:
        return value[:MAX_DETAIL_VALUE_CHARS] + "…"
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    return value


def compact(mapping: dict[Any, Any]) -> dict[str, Any]:
    """Drop empty values and clip oversized ones so detail blobs stay readable."""
    return {str(k): clip(v) for k, v in mapping.items() if k is not None and v not in (None, "")}


def read_head(path: Path, size: int = 8192) -> bytes:
    with path.open("rb") as fh:
        return fh.read(size)


def is_sqlite(path: Path) -> bool:
    try:
        return read_head(path, 16) == SQLITE_MAGIC
    except OSError:
        return False


@contextmanager
def open_sqlite_readonly(path: Path) -> Iterator[sqlite3.Connection]:
    """Open evidence read-only and immutable, with a wall-clock cap on any single query."""
    uri = f"{path.resolve().as_uri()}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    deadline = time.monotonic() + SQLITE_QUERY_BUDGET_SECONDS
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 100_000)
    try:
        conn.execute("PRAGMA query_only = ON")
        yield conn
    finally:
        conn.close()


def sqlite_schema(path: Path) -> dict[str, set[str]] | None:
    """Map real (non-view) table name -> lowercase column names, or None if not readable SQLite."""
    if not is_sqlite(path):
        return None
    try:
        with open_sqlite_readonly(path) as conn:
            tables = [str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            return {t: table_columns(conn, t) for t in tables}
    except sqlite3.Error:
        return None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({quote_ident(table)})").fetchall()
    return {str(r[1]).lower() for r in rows}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def looks_binary(head: bytes) -> bool:
    return b"\x00" in head


def detect_delimiter(header_line: str) -> str:
    counts = {d: header_line.count(d) for d in (",", ";", "\t", "|")}
    best = max(counts, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def read_text_head(path: Path, size: int = 8192) -> str | None:
    head = read_head(path, size)
    if not head or looks_binary(head):
        return None
    return head.decode("utf-8-sig", errors="replace")


def csv_header(path: Path) -> list[str] | None:
    """Lower-cased header fields of a delimited text file, or None if it isn't one."""
    text = read_text_head(path)
    if text is None:
        return None
    lines = text.splitlines()
    first = lines[0] if lines else ""
    if not first or first.lstrip()[:1] in {"{", "[", "<"}:
        return None
    delim = detect_delimiter(first)
    fields = next(csv.reader([first], delimiter=delim), [])
    return [f.strip().lower() for f in fields]


def csv_rows(path: Path) -> Iterator[dict[str, str]]:
    """Yield rows keyed by lower-cased header names; tolerant of BOMs, delimiters and ragged rows."""
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        first = fh.readline()
        fh.seek(0)
        reader = csv.reader(fh, delimiter=detect_delimiter(first))
        header = next(reader, None)
        if header is None:
            return
        keys = [h.strip().lower() for h in header]
        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue
            yield {k: v for k, v in zip(keys, row, strict=False) if k}
