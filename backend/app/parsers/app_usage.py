from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from app.parsers.base import EventRecord, open_sqlite_readonly, table_columns, table_exists


def _ms_to_utc(ms: int | float | str) -> tuple[str, str]:
    value = int(float(ms))
    # Heuristic: seconds vs milliseconds
    if value < 10_000_000_000:
        value *= 1000
    dt = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    iso = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return iso, str(ms)


class AppUsageParser:
    """Parse Android app_usage SQLite (Plaso-compatible) or UsageStats CSV/XML."""

    source = "app_usage"

    def sniff(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        name = path.name.lower()
        if suffix == ".csv" and ("usage" in name or "app" in name):
            return True
        if suffix == ".xml" and "usagestats" in name:
            return True
        if suffix in {".db", ".sqlite", ".sqlite3"}:
            try:
                with open_sqlite_readonly(path) as conn:
                    if table_exists(conn, "events") and table_exists(conn, "packages"):
                        cols_e = table_columns(conn, "events")
                        cols_p = table_columns(conn, "packages")
                        return {"timestamp", "package_id"}.issubset(cols_e) and "package_name" in cols_p
            except Exception:
                return False
        return False

    def parse(self, path: Path) -> list[EventRecord]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self._parse_csv(path)
        if suffix == ".xml":
            return self._parse_xml(path)
        return self._parse_sqlite(path)

    def _parse_sqlite(self, path: Path) -> list[EventRecord]:
        events: list[EventRecord] = []
        with open_sqlite_readonly(path) as conn:
            rows = conn.execute(
                """
                SELECT events.timestamp, packages.package_name, events.type
                FROM events
                JOIN packages ON packages._id = events.package_id
                ORDER BY events.timestamp
                """
            ).fetchall()
            for row in rows:
                ts_utc, ts_original = _ms_to_utc(row["timestamp"])
                package = str(row["package_name"] or "")
                event_type = f"type_{row['type']}" if row["type"] is not None else "launch"
                events.append(
                    EventRecord(
                        ts_utc=ts_utc,
                        ts_original=ts_original,
                        source=self.source,
                        event_type=event_type,
                        title=package or "unknown package",
                        package=package or None,
                        detail={"package_name": package, "type": row["type"]},
                        confidence=1.0,
                    )
                )
        return events

    def _parse_csv(self, path: Path) -> list[EventRecord]:
        events: list[EventRecord] = []
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                raw_ts = (
                    row.get("lasttimeactive")
                    or row.get("timestamp")
                    or row.get("lastime")
                    or row.get("time")
                )
                package = (row.get("package") or row.get("package_name") or "").strip()
                if not raw_ts or not package:
                    continue
                # CSV may already be datetime string
                if "T" in str(raw_ts) or "-" in str(raw_ts) and ":" in str(raw_ts):
                    ts_utc = _normalize_datetime_string(str(raw_ts))
                    ts_original = str(raw_ts)
                else:
                    ts_utc, ts_original = _ms_to_utc(raw_ts)
                usage_type = (row.get("types") or row.get("usage_type") or "ACTIVITY").strip()
                events.append(
                    EventRecord(
                        ts_utc=ts_utc,
                        ts_original=ts_original,
                        source=self.source,
                        event_type=usage_type,
                        title=package,
                        package=package,
                        detail={k: v for k, v in row.items() if v},
                        confidence=0.9,
                    )
                )
        return events

    def _parse_xml(self, path: Path) -> list[EventRecord]:
        events: list[EventRecord] = []
        tree = ET.parse(path)
        root = tree.getroot()
        for el in root.iter():
            package = el.attrib.get("package") or el.attrib.get("name")
            raw_ts = (
                el.attrib.get("lastTimeActive")
                or el.attrib.get("lastTimeUsed")
                or el.attrib.get("time")
            )
            if not package or not raw_ts:
                continue
            ts_utc, ts_original = _ms_to_utc(raw_ts)
            events.append(
                EventRecord(
                    ts_utc=ts_utc,
                    ts_original=ts_original,
                    source=self.source,
                    event_type=el.tag,
                    title=package,
                    package=package,
                    detail=dict(el.attrib),
                    confidence=0.85,
                )
            )
        return events


def _normalize_datetime_string(value: str) -> str:
    cleaned = value.strip().replace(" ", "T")
    if cleaned.endswith("Z"):
        return cleaned if "." in cleaned else cleaned.replace("Z", ".000Z")
    try:
        # Assume UTC if naive
        if "+" not in cleaned and cleaned.count("-") <= 2:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    except ValueError:
        pass
    return cleaned if cleaned.endswith("Z") else cleaned + "Z"