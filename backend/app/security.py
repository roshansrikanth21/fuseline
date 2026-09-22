from __future__ import annotations

import re
import uuid
from pathlib import Path

CASE_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

READ_CHUNK = 1024 * 1024
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def assert_safe_case_id(case_id: str) -> str:
    if not case_id or not CASE_ID_RE.match(case_id):
        raise ValueError("Invalid case id")
    # Defense in depth against path tricks even if UUID pattern changes later
    if any(part in case_id for part in ("..", "/", "\\")):
        raise ValueError("Invalid case id")
    try:
        uuid.UUID(case_id)
    except ValueError as exc:
        raise ValueError("Invalid case id") from exc
    return case_id


def sanitize_filename(name: str) -> str:
    base = Path(name).name
    base = base.replace("\x00", "")
    if not base or base in {".", ".."} or "/" in base or "\\" in base:
        raise ValueError("Invalid filename")
    # Keep it filesystem-friendly and bounded
    cleaned = re.sub(r"[^\w.\- ()\[\]]+", "_", base, flags=re.UNICODE).strip(" .")
    if not cleaned:
        raise ValueError("Invalid filename")
    return cleaned[:180]


def assert_under(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("Path escapes allowed directory") from exc
    return resolved


def quote_ident(name: str) -> str:
    """Quote an SQLite identifier. Table/column names inside evidence databases are untrusted."""
    return '"' + str(name).replace('"', '""') + '"'


def csv_safe(value: object) -> object:
    """Neutralise spreadsheet formula injection in exported cells.

    Titles, URLs and package names come from evidence and may be attacker-controlled; a
    leading ``=``/``+``/``-``/``@`` would execute as a formula when the CSV is opened in
    Excel or LibreOffice. The JSON export stays byte-for-byte faithful.
    """
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value
