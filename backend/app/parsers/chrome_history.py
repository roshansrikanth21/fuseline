from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from app.parsers.base import (
    EventRecord,
    ParseContext,
    ParseResult,
    compact,
    open_sqlite_readonly,
    sqlite_schema,
    table_columns,
    table_exists,
)
from app.security import quote_ident
from app.timeutil import TimestampError, to_iso_utc, webkit_to_datetime

# chromium/src/ui/base/page_transition_types.h
TRANSITION_CORE = {
    0: "link",
    1: "typed",
    2: "auto_bookmark",
    3: "auto_subframe",
    4: "manual_subframe",
    5: "generated",
    6: "auto_toplevel",
    7: "form_submit",
    8: "reload",
    9: "keyword",
    10: "keyword_generated",
}
TRANSITION_QUALIFIERS = (
    (0x00800000, "blocked"),
    (0x01000000, "forward_back"),
    (0x02000000, "from_address_bar"),
    (0x04000000, "home_page"),
    (0x08000000, "from_api"),
    (0x10000000, "chain_start"),
    (0x20000000, "chain_end"),
    (0x40000000, "client_redirect"),
    (0x80000000, "server_redirect"),
)

_PATH_SPLIT = re.compile(r"[\\/]")


def extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).hostname
    except ValueError:
        return None


def decode_transition(value: int | None) -> tuple[str | None, list[str]]:
    if value is None:
        return None, []
    value = int(value) & 0xFFFFFFFF
    name = TRANSITION_CORE.get(value & 0xFF, f"unknown_{value & 0xFF}")
    return name, [label for bit, label in TRANSITION_QUALIFIERS if value & bit]


class ChromiumHistoryParser:
    """Chromium/Chrome/Edge/Brave ``History`` databases: page visits, search terms and downloads."""

    source = "browsing"
    name = "chromium_history"

    def sniff(self, path: Path) -> float:
        schema = sqlite_schema(path)
        if not schema:
            return 0.0
        urls, visits = schema.get("urls"), schema.get("visits")
        if urls and visits and {"url", "title"} <= urls and {"url", "visit_time"} <= visits:
            return 0.95
        return 0.0

    def parse(self, path: Path, ctx: ParseContext) -> ParseResult:
        result = ParseResult()
        with open_sqlite_readonly(path) as conn:
            self._parse_visits(conn, ctx, result)
            self._parse_downloads(conn, ctx, result)
        return result

    def _parse_visits(self, conn, ctx: ParseContext, result: ParseResult) -> None:
        visit_cols = table_columns(conn, "visits")
        url_cols = table_columns(conn, "urls")
        select = [
            "visits.rowid AS visit_id",
            "visits.visit_time AS visit_time",
            "urls.url AS url",
            "urls.title AS title",
            "urls.id AS url_id",
        ]
        for col in ("transition", "from_visit", "visit_duration"):
            if col in visit_cols:
                select.append(f"visits.{quote_ident(col)} AS {col}")
        if "visit_count" in url_cols:
            select.append("urls.visit_count AS visit_count")

        terms = self._search_terms(conn)
        rows = conn.execute(
            f"SELECT {', '.join(select)} FROM visits JOIN urls ON urls.id = visits.url "
            "ORDER BY visits.visit_time, visits.rowid"
        )
        for row in rows:
            keys = row.keys()
            try:
                ts = webkit_to_datetime(row["visit_time"])
            except (TimestampError, TypeError, ValueError):
                result.skip("visit_time missing or out of range")
                continue
            url = str(row["url"] or "")
            title = (row["title"] or "").strip()
            transition = row["transition"] if "transition" in keys else None
            transition_name, qualifiers = decode_transition(transition)
            duration = row["visit_duration"] if "visit_duration" in keys else None
            result.records.append(
                EventRecord(
                    ts_utc=to_iso_utc(ts),
                    ts_original=str(row["visit_time"]),
                    source=self.source,
                    event_type="visit",
                    title=(title or url or "visit")[:200],
                    url=url or None,
                    domain=extract_domain(url),
                    detail=compact(
                        {
                            "url": url,
                            "title": title,
                            "transition": transition,
                            "transition_name": transition_name,
                            "transition_qualifiers": qualifiers or None,
                            "visit_count": row["visit_count"] if "visit_count" in keys else None,
                            "visit_duration_us": duration if duration else None,
                            "from_visit": row["from_visit"] if "from_visit" in keys else None,
                            "search_term": terms.get(row["url_id"]),
                        }
                    ),
                )
            )

    @staticmethod
    def _search_terms(conn) -> dict[int, str]:
        if not table_exists(conn, "keyword_search_terms"):
            return {}
        cols = table_columns(conn, "keyword_search_terms")
        if not {"url_id", "term"} <= cols:
            return {}
        return {
            int(r["url_id"]): str(r["term"])
            for r in conn.execute("SELECT url_id, term FROM keyword_search_terms")
            if r["url_id"] is not None and r["term"]
        }

    def _parse_downloads(self, conn, ctx: ParseContext, result: ParseResult) -> None:
        if not table_exists(conn, "downloads"):
            return
        cols = table_columns(conn, "downloads")
        path_col = next((c for c in ("target_path", "current_path") if c in cols), None)
        if path_col is None or "start_time" not in cols:
            return

        chains: dict[int, str] = {}
        if table_exists(conn, "downloads_url_chains"):
            for r in conn.execute("SELECT id, url FROM downloads_url_chains ORDER BY id, chain_index"):
                chains[int(r["id"])] = str(r["url"])

        optional = [
            c
            for c in (
                "end_time",
                "received_bytes",
                "total_bytes",
                "mime_type",
                "tab_url",
                "tab_referrer_url",
                "state",
                "danger_type",
                "interrupt_reason",
                "opened",
            )
            if c in cols
        ]
        select = ["id", f"{quote_ident(path_col)} AS file_path", "start_time"]
        select += [quote_ident(c) for c in optional]
        for row in conn.execute(f"SELECT {', '.join(select)} FROM downloads ORDER BY start_time, id"):
            try:
                ts = webkit_to_datetime(row["start_time"])
            except (TimestampError, TypeError, ValueError):
                result.skip("download start_time missing or out of range")
                continue
            file_path = str(row["file_path"] or "")
            filename = _PATH_SPLIT.split(file_path)[-1] if file_path else "unknown file"
            keys = row.keys()
            url = chains.get(int(row["id"])) or (row["tab_url"] if "tab_url" in keys else None) or None
            detail = {"file_path": file_path, "final_url": url}
            detail.update({c: row[c] for c in optional})
            result.records.append(
                EventRecord(
                    ts_utc=to_iso_utc(ts),
                    ts_original=str(row["start_time"]),
                    source=self.source,
                    event_type="download",
                    title=f"Downloaded {filename}"[:200],
                    url=url,
                    domain=extract_domain(url),
                    detail=compact(detail),
                )
            )
