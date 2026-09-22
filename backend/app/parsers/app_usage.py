from __future__ import annotations

import re
from pathlib import Path

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from app.parsers.base import (
    EventRecord,
    ParseContext,
    ParseResult,
    compact,
    csv_header,
    csv_rows,
    open_sqlite_readonly,
    read_text_head,
    sqlite_schema,
    table_columns,
)
from app.timeutil import TimestampError, to_iso_utc

# android.app.usage.UsageEvents.Event
EVENT_TYPES = {
    1: "move_to_foreground",
    2: "move_to_background",
    3: "end_of_day",
    4: "continue_previous_day",
    5: "configuration_change",
    6: "system_interaction",
    7: "user_interaction",
    8: "shortcut_invocation",
    9: "chooser_action",
    10: "notification_seen",
    11: "standby_bucket_changed",
    12: "notification_interruption",
    13: "slice_pinned_priv",
    14: "slice_pinned",
    15: "screen_interactive",
    16: "screen_non_interactive",
    17: "keyguard_shown",
    18: "keyguard_hidden",
    19: "foreground_service_start",
    20: "foreground_service_stop",
    21: "continuing_foreground_service",
    22: "rollover_foreground_service",
    23: "activity_stopped",
    24: "activity_destroyed",
    25: "flush_to_disk",
    26: "device_shutdown",
    27: "device_startup",
    28: "user_unlocked",
    29: "user_stopped",
    30: "locus_id_set",
    31: "app_component_used",
}

PACKAGE_KEYS = ("package", "package_name", "packagename")
TIME_KEYS = ("lasttimeactive", "lasttimeused", "timestamp", "lastime", "time", "last_time_used")
TYPE_KEYS = ("types", "usage_type", "type", "event_type")
_SNAKE = re.compile(r"[^a-z0-9]+")


def _snake(value: str) -> str:
    return _SNAKE.sub("_", value.strip().lower()).strip("_") or "activity"


def _first(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None and value.strip():
            return value.strip()
    return None


class AppUsageParser:
    """Android UsageStats: Plaso-style SQLite, ALEAPP-style CSV, or UsageStats XML."""

    source = "app_usage"
    name = "android_app_usage"

    def sniff(self, path: Path) -> float:
        schema = sqlite_schema(path)
        if schema is not None:
            events, packages = schema.get("events"), schema.get("packages")
            if events and packages and {"timestamp", "package_id"} <= events and "package_name" in packages:
                return 0.95
            return 0.0

        head = read_text_head(path)
        if head is None:
            return 0.0
        lowered = head.lower()
        if head.lstrip().startswith("<"):
            has_usage_root = "<usagestats" in lowered or "<usage-stats" in lowered
            has_attrs = "package=" in lowered and any(
                k in lowered for k in ("lasttimeactive", "lasttimeused", " time=")
            )
            return 0.75 if has_usage_root or has_attrs else 0.0

        header = csv_header(path)
        if header and any(k in header for k in PACKAGE_KEYS) and any(k in header for k in TIME_KEYS):
            return 0.8
        return 0.0

    def parse(self, path: Path, ctx: ParseContext) -> ParseResult:
        if sqlite_schema(path) is not None:
            return self._parse_sqlite(path, ctx)
        head = read_text_head(path) or ""
        if head.lstrip().startswith("<"):
            return self._parse_xml(path, ctx)
        return self._parse_csv(path, ctx)

    def _parse_sqlite(self, path: Path, ctx: ParseContext) -> ParseResult:
        result = ParseResult()
        with open_sqlite_readonly(path) as conn:
            pkg_cols = table_columns(conn, "packages")
            pk = next((c for c in ("_id", "id") if c in pkg_cols), "rowid")
            rows = conn.execute(
                f"""
                SELECT events.timestamp AS timestamp, packages.package_name AS package_name,
                       events.type AS type
                FROM events
                JOIN packages ON packages.{pk} = events.package_id
                ORDER BY events.timestamp, events.rowid
                """
            )
            for row in rows:
                try:
                    ts = ctx.timestamp(row["timestamp"], unit="ms")
                except (TimestampError, TypeError, ValueError, OverflowError):
                    result.skip("timestamp missing or out of range")
                    continue
                package = str(row["package_name"] or "").strip()
                code = row["type"]
                type_name = EVENT_TYPES.get(code) if isinstance(code, int) else None
                result.records.append(
                    EventRecord(
                        ts_utc=to_iso_utc(ts.utc),
                        ts_original=str(row["timestamp"]),
                        source=self.source,
                        event_type=type_name or (f"type_{code}" if code is not None else "usage_event"),
                        title=package or "unknown package",
                        package=package or None,
                        tz_assumed=ctx.tz_label(ts),
                        ts_basis=ts.basis,
                        detail=compact({"package_name": package, "type": code, "type_name": type_name}),
                    )
                )
        return result

    def _parse_csv(self, path: Path, ctx: ParseContext) -> ParseResult:
        result = ParseResult()
        for row in csv_rows(path):
            raw_ts = _first(row, TIME_KEYS)
            package = _first(row, PACKAGE_KEYS)
            if not package:
                result.skip("no package")
                continue
            if not raw_ts:
                result.skip("no timestamp")
                continue
            try:
                ts = ctx.timestamp(raw_ts)
            except (TimestampError, OverflowError):
                result.skip("unparseable timestamp")
                continue
            usage = _first(row, TYPE_KEYS)
            result.records.append(
                EventRecord(
                    ts_utc=to_iso_utc(ts.utc),
                    ts_original=raw_ts,
                    source=self.source,
                    event_type=_snake(usage) if usage else "activity",
                    title=package,
                    package=package,
                    tz_assumed=ctx.tz_label(ts),
                    ts_basis=ts.basis,
                    detail=compact(row),
                    confidence=0.9,
                )
            )
        return result

    def _parse_xml(self, path: Path, ctx: ParseContext) -> ParseResult:
        result = ParseResult()
        try:
            root = SafeET.parse(str(path)).getroot()
        except (SafeET.ParseError, DefusedXmlException) as exc:
            raise ValueError(f"invalid or unsafe XML: {exc}") from exc
        for el in root.iter():
            package = el.attrib.get("package") or el.attrib.get("name")
            raw_ts = el.attrib.get("lastTimeActive") or el.attrib.get("lastTimeUsed") or el.attrib.get("time")
            if not package or not raw_ts:
                continue
            try:
                ts = ctx.timestamp(raw_ts, unit="ms")
            except (TimestampError, OverflowError):
                result.skip("unparseable timestamp")
                continue
            result.records.append(
                EventRecord(
                    ts_utc=to_iso_utc(ts.utc),
                    ts_original=raw_ts,
                    source=self.source,
                    event_type=_snake(el.tag),
                    title=package,
                    package=package,
                    tz_assumed=ctx.tz_label(ts),
                    ts_basis=ts.basis,
                    detail=compact(dict(el.attrib)),
                    confidence=0.85,
                )
            )
        return result
