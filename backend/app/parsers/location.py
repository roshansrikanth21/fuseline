from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from app.parsers.base import EventRecord, open_sqlite_readonly, table_columns, table_exists


def _to_utc_iso(raw: str | int | float) -> tuple[str, str]:
    original = str(raw)
    if isinstance(raw, (int, float)) or (isinstance(raw, str) and raw.strip().isdigit()):
        value = int(float(raw))
        if value > 10_000_000_000:
            # ms
            seconds = value / 1000
        else:
            seconds = value
        dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", original

    text = str(raw).strip().replace(" ", "T")
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", original
    except ValueError as exc:
        raise ValueError(f"Unparseable location timestamp: {raw}") from exc


class LocationParser:
    """Parse GPS CSV or SQLite tables with lat/lon/time columns."""

    source = "location"

    TIME_KEYS = ("timestamp", "time", "ts", "datetime", "date_time", "fix")
    LAT_KEYS = ("lat", "latitude", "y")
    LON_KEYS = ("lon", "lng", "longitude", "x")

    def sniff(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        name = path.name.lower()
        if suffix == ".csv" and ("loc" in name or "gps" in name or "position" in name):
            return True
        if suffix in {".db", ".sqlite", ".sqlite3"}:
            try:
                with open_sqlite_readonly(path) as conn:
                    tables = [
                        r[0]
                        for r in conn.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    ]
                    for table in tables:
                        cols = {c.lower() for c in table_columns(conn, table)}
                        if self._has_geo_cols(cols):
                            return True
            except Exception:
                return False
        return False

    def _has_geo_cols(self, cols: set[str]) -> bool:
        has_lat = any(k in cols for k in self.LAT_KEYS)
        has_lon = any(k in cols for k in self.LON_KEYS)
        has_time = any(k in cols for k in self.TIME_KEYS)
        return has_lat and has_lon and has_time

    def _pick(self, mapping: dict[str, object], keys: tuple[str, ...]):
        lower = {str(k).lower(): v for k, v in mapping.items()}
        for key in keys:
            if key in lower and lower[key] not in (None, ""):
                return lower[key]
        return None

    def parse(self, path: Path) -> list[EventRecord]:
        if path.suffix.lower() == ".csv":
            return self._parse_csv(path)
        return self._parse_sqlite(path)

    def _parse_csv(self, path: Path) -> list[EventRecord]:
        events: list[EventRecord] = []
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                raw_ts = self._pick(row, self.TIME_KEYS)
                lat_raw = self._pick(row, self.LAT_KEYS)
                lon_raw = self._pick(row, self.LON_KEYS)
                if raw_ts is None or lat_raw is None or lon_raw is None:
                    continue
                try:
                    ts_utc, ts_original = _to_utc_iso(raw_ts)
                    lat = float(lat_raw)
                    lon = float(lon_raw)
                except (TypeError, ValueError):
                    continue
                accuracy = self._pick(row, ("accuracy", "acc", "horizontal_accuracy"))
                title = f"{lat:.5f}, {lon:.5f}"
                events.append(
                    EventRecord(
                        ts_utc=ts_utc,
                        ts_original=ts_original,
                        source=self.source,
                        event_type="fix",
                        title=title,
                        lat=lat,
                        lon=lon,
                        detail={
                            "lat": lat,
                            "lon": lon,
                            "accuracy": accuracy,
                            **{k: v for k, v in row.items() if v},
                        },
                        confidence=0.95,
                    )
                )
        return events

    def _parse_sqlite(self, path: Path) -> list[EventRecord]:
        events: list[EventRecord] = []
        with open_sqlite_readonly(path) as conn:
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            target = None
            colmap: dict[str, str] = {}
            for table in tables:
                cols = table_columns(conn, table)
                lower_map = {c.lower(): c for c in cols}
                if not self._has_geo_cols(set(lower_map)):
                    continue
                target = table
                for key in self.TIME_KEYS:
                    if key in lower_map:
                        colmap["time"] = lower_map[key]
                        break
                for key in self.LAT_KEYS:
                    if key in lower_map:
                        colmap["lat"] = lower_map[key]
                        break
                for key in self.LON_KEYS:
                    if key in lower_map:
                        colmap["lon"] = lower_map[key]
                        break
                break
            if not target or len(colmap) < 3:
                return events
            rows = conn.execute(
                f'SELECT "{colmap["time"]}" AS t, "{colmap["lat"]}" AS lat, "{colmap["lon"]}" AS lon FROM "{target}"'
            ).fetchall()
            for row in rows:
                if row["t"] is None or row["lat"] is None or row["lon"] is None:
                    continue
                try:
                    ts_utc, ts_original = _to_utc_iso(row["t"])
                    lat = float(row["lat"])
                    lon = float(row["lon"])
                except (TypeError, ValueError):
                    continue
                events.append(
                    EventRecord(
                        ts_utc=ts_utc,
                        ts_original=ts_original,
                        source=self.source,
                        event_type="fix",
                        title=f"{lat:.5f}, {lon:.5f}",
                        lat=lat,
                        lon=lon,
                        detail={"table": target, "lat": lat, "lon": lon},
                        confidence=0.95,
                    )
                )
        return events