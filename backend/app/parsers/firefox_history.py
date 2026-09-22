from __future__ import annotations

from pathlib import Path

from app.parsers.base import (
    EventRecord,
    ParseContext,
    ParseResult,
    compact,
    open_sqlite_readonly,
    sqlite_schema,
)
from app.parsers.chrome_history import extract_domain
from app.timeutil import TimestampError, to_iso_utc

# toolkit/components/places/nsINavHistoryService.idl
VISIT_TYPES = {
    1: "link",
    2: "typed",
    3: "bookmark",
    4: "embed",
    5: "redirect_permanent",
    6: "redirect_temporary",
    7: "download",
    8: "framed_link",
    9: "reload",
}


class FirefoxPlacesParser:
    """Firefox / Firefox for Android (Fenix) ``places.sqlite`` history."""

    source = "browsing"
    name = "firefox_places"

    def sniff(self, path: Path) -> float:
        schema = sqlite_schema(path)
        if not schema:
            return 0.0
        places, visits = schema.get("moz_places"), schema.get("moz_historyvisits")
        if places and visits and {"url", "title"} <= places and {"visit_date", "place_id"} <= visits:
            return 0.95
        return 0.0

    def parse(self, path: Path, ctx: ParseContext) -> ParseResult:
        result = ParseResult()
        with open_sqlite_readonly(path) as conn:
            rows = conn.execute(
                """
                SELECT v.id AS visit_id, v.visit_date AS visit_date, v.visit_type AS visit_type,
                       p.url AS url, p.title AS title, p.visit_count AS visit_count
                FROM moz_historyvisits v
                JOIN moz_places p ON p.id = v.place_id
                ORDER BY v.visit_date, v.id
                """
            )
            for row in rows:
                try:
                    if not row["visit_date"]:
                        raise TimestampError("missing visit_date")
                    ts = ctx.timestamp(row["visit_date"], unit="us")
                except (TimestampError, TypeError, ValueError):
                    result.skip("visit_date missing or out of range")
                    continue
                url = str(row["url"] or "")
                title = (row["title"] or "").strip()
                visit_type = row["visit_type"]
                result.records.append(
                    EventRecord(
                        ts_utc=to_iso_utc(ts.utc),
                        ts_original=str(row["visit_date"]),
                        source=self.source,
                        event_type="visit",
                        title=(title or url or "visit")[:200],
                        url=url or None,
                        domain=extract_domain(url),
                        detail=compact(
                            {
                                "url": url,
                                "title": title,
                                "visit_type": visit_type,
                                "visit_type_name": VISIT_TYPES.get(visit_type),
                                "visit_count": row["visit_count"],
                            }
                        ),
                    )
                )
        return result
