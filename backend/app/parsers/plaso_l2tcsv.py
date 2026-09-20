from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.parsers.base import EventRecord


def _combine_date_time(date_str: str, time_str: str) -> str:
    date_str = (date_str or "").strip()
    time_str = (time_str or "").strip()
    if not date_str:
        raise ValueError("Missing date in Plaso row")
    if not time_str:
        time_str = "00:00:00"
    # L2TCSV often uses MM/DD/YYYY
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", fmt.replace("T", " ") if "T" in fmt else fmt)
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except ValueError:
            continue
    # Fallback ISO pieces
    cleaned = f"{date_str}T{time_str}"
    if not cleaned.endswith("Z"):
        cleaned += "Z"
    return cleaned


def _map_source(raw_source: str, desc: str, message: str) -> tuple[str, str]:
    blob = f"{raw_source} {desc} {message}".lower()
    if any(k in blob for k in ("chrome", "firefox", "browser", "history", "visit", "url")):
        return "browsing", "plaso_browse"
    if any(k in blob for k in ("app_usage", "android_app", "usage", "package")):
        return "app_usage", "plaso_app"
    if any(k in blob for k in ("location", "gps", "geo", "latitude")):
        return "location", "plaso_location"
    return "plaso", "plaso_event"


class PlasoL2TCSVParser:
    """Import Plaso psort L2TCSV or JSONL output."""

    source = "plaso"

    def sniff(self, path: Path) -> bool:
        name = path.name.lower()
        suffix = path.suffix.lower()
        if suffix == ".csv" and ("l2t" in name or "plaso" in name or "timeline" in name):
            return True
        if suffix in {".jsonl", ".json"} and ("plaso" in name or "l2t" in name):
            return True
        if suffix == ".csv":
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as fh:
                    header = fh.readline().lower()
                return "date" in header and "time" in header and (
                    "desc" in header or "source" in header or "message" in header
                )
            except Exception:
                return False
        return False

    def parse(self, path: Path) -> list[EventRecord]:
        if path.suffix.lower() in {".jsonl", ".json"}:
            return self._parse_jsonl(path)
        return self._parse_csv(path)

    def _parse_csv(self, path: Path) -> list[EventRecord]:
        events: list[EventRecord] = []
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                date_s = row.get("date") or row.get("Date") or ""
                time_s = row.get("time") or row.get("Time") or ""
                if not date_s:
                    continue
                try:
                    ts_utc = _combine_date_time(date_s, time_s)
                except ValueError:
                    continue
                desc = row.get("desc") or row.get("description") or row.get("Filename") or ""
                message = row.get("message") or row.get("Message") or desc or "plaso event"
                raw_source = row.get("source") or row.get("Source") or "plaso"
                mapped, event_type = _map_source(raw_source, desc, message)
                url = row.get("URL") or row.get("url")
                domain = None
                if url:
                    try:
                        domain = urlparse(url).hostname
                    except Exception:
                        domain = None
                package = row.get("package") or row.get("Package")
                lat = _maybe_float(row.get("latitude") or row.get("lat"))
                lon = _maybe_float(row.get("longitude") or row.get("lon"))
                events.append(
                    EventRecord(
                        ts_utc=ts_utc,
                        ts_original=f"{date_s} {time_s}".strip(),
                        source=mapped,
                        event_type=event_type,
                        title=(message or desc)[:200],
                        url=url,
                        domain=domain,
                        package=package,
                        lat=lat,
                        lon=lon,
                        detail={k: v for k, v in row.items() if v},
                        confidence=0.8,
                    )
                )
        return events

    def _parse_jsonl(self, path: Path) -> list[EventRecord]:
        events: list[EventRecord] = []
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, list):
                    for item in obj:
                        if isinstance(item, dict):
                            events.extend(self._from_json_obj(item))
                    continue
                if isinstance(obj, dict):
                    events.extend(self._from_json_obj(obj))
        return events

    def _from_json_obj(self, obj: dict) -> list[EventRecord]:
        date_s = str(obj.get("date") or obj.get("datetime") or "")
        time_s = str(obj.get("time") or "")
        if "T" in date_s and not time_s:
            ts_utc = date_s if date_s.endswith("Z") else date_s + "Z"
            ts_original = date_s
        else:
            try:
                ts_utc = _combine_date_time(date_s, time_s)
            except ValueError:
                return []
            ts_original = f"{date_s} {time_s}".strip()
        message = str(obj.get("message") or obj.get("display_name") or "plaso event")
        raw_source = str(obj.get("source_short") or obj.get("source") or "plaso")
        mapped, event_type = _map_source(raw_source, str(obj.get("desc") or ""), message)
        return [
            EventRecord(
                ts_utc=ts_utc,
                ts_original=ts_original,
                source=mapped,
                event_type=event_type,
                title=message[:200],
                detail=obj,
                confidence=0.8,
            )
        ]


def _maybe_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None