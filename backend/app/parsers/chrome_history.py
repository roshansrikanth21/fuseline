from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.parsers.base import EventRecord, open_sqlite_readonly, table_columns, table_exists

# Chromium stores timestamps as microseconds since 1601-01-01 UTC
WEBKIT_EPOCH_DELTA = 11644473600


def webkit_to_utc(webkit_us: int | float | str) -> tuple[str, str]:
    value = int(float(webkit_us))
    seconds = (value / 1_000_000) - WEBKIT_EPOCH_DELTA
    if seconds < 0:
        # Already unix microseconds?
        seconds = value / 1_000_000
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    iso = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return iso, str(webkit_us)


def extract_domain(url: str) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        return parsed.hostname
    except Exception:
        return None


class ChromeHistoryParser:
    """Parse Chromium History SQLite (urls + visits)."""

    source = "browsing"

    def sniff(self, path: Path) -> bool:
        name = path.name.lower()
        if path.suffix.lower() not in {".db", ".sqlite", ".sqlite3", ""} and "history" not in name:
            # Chromium History file often has no extension
            if name != "history" and not name.endswith("history"):
                return False
        try:
            with open_sqlite_readonly(path) as conn:
                if not (table_exists(conn, "urls") and table_exists(conn, "visits")):
                    return False
                cols_u = table_columns(conn, "urls")
                cols_v = table_columns(conn, "visits")
                return {"url", "title"}.issubset(cols_u) and "visit_time" in cols_v
        except Exception:
            return False

    def parse(self, path: Path) -> list[EventRecord]:
        events: list[EventRecord] = []
        with open_sqlite_readonly(path) as conn:
            rows = conn.execute(
                """
                SELECT
                  visits.visit_time AS visit_time,
                  urls.url AS url,
                  urls.title AS title,
                  visits.transition AS transition,
                  urls.visit_count AS visit_count
                FROM visits
                JOIN urls ON urls.id = visits.url
                ORDER BY visits.visit_time
                """
            ).fetchall()
            for row in rows:
                ts_utc, ts_original = webkit_to_utc(row["visit_time"])
                url = str(row["url"] or "")
                title = (row["title"] or "").strip() or url or "visit"
                domain = extract_domain(url)
                events.append(
                    EventRecord(
                        ts_utc=ts_utc,
                        ts_original=ts_original,
                        source=self.source,
                        event_type="visit",
                        title=title[:200],
                        url=url or None,
                        domain=domain,
                        detail={
                            "url": url,
                            "title": row["title"],
                            "transition": row["transition"],
                            "visit_count": row["visit_count"],
                        },
                        confidence=1.0,
                    )
                )
        return events