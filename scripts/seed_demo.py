#!/usr/bin/env python3
"""Generate synthetic Android forensic artifacts for the Fuseline demo case."""

from __future__ import annotations

import csv
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "samples" / "demo_case"

# Chromium epoch
WEBKIT_EPOCH_DELTA = 11644473600


def utc_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def to_webkit(dt: datetime) -> int:
    return int((dt.timestamp() + WEBKIT_EPOCH_DELTA) * 1_000_000)


def build_app_usage(base: datetime) -> None:
    path = DEMO / "app_usage.db"
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE packages (
          _id INTEGER PRIMARY KEY,
          package_name TEXT UNIQUE
        );
        CREATE TABLE events (
          _id INTEGER PRIMARY KEY,
          timestamp INTEGER NOT NULL,
          type INTEGER NOT NULL,
          package_id INTEGER NOT NULL REFERENCES packages(_id)
        );
        """
    )
    packages = [
        (1, "com.google.android.apps.maps"),
        (2, "com.android.chrome"),
        (3, "com.whatsapp"),
        (4, "com.spotify.music"),
    ]
    conn.executemany("INSERT INTO packages (_id, package_name) VALUES (?, ?)", packages)
    events = [
        (1, utc_ms(base + timedelta(minutes=0)), 1, 1),  # maps
        (2, utc_ms(base + timedelta(minutes=1)), 1, 2),  # chrome
        (3, utc_ms(base + timedelta(minutes=12)), 1, 3),  # whatsapp
        (4, utc_ms(base + timedelta(minutes=45)), 1, 4),  # spotify
        (5, utc_ms(base + timedelta(hours=2)), 1, 2),
        (6, utc_ms(base + timedelta(hours=2, minutes=2)), 1, 1),
    ]
    conn.executemany(
        "INSERT INTO events (_id, timestamp, type, package_id) VALUES (?, ?, ?, ?)",
        events,
    )
    conn.commit()
    conn.close()


def build_chrome_history(base: datetime) -> None:
    path = DEMO / "History"
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE urls (
          id INTEGER PRIMARY KEY,
          url TEXT,
          title TEXT,
          visit_count INTEGER,
          typed_count INTEGER,
          last_visit_time INTEGER,
          hidden INTEGER DEFAULT 0
        );
        CREATE TABLE visits (
          id INTEGER PRIMARY KEY,
          url INTEGER,
          visit_time INTEGER,
          from_visit INTEGER,
          transition INTEGER,
          segment_id INTEGER,
          visit_duration INTEGER DEFAULT 0
        );
        """
    )
    urls = [
        (1, "https://maps.google.com/directions", "Directions", 3, 1, to_webkit(base + timedelta(minutes=2)), 0),
        (2, "https://news.example.com/local", "Local News", 1, 0, to_webkit(base + timedelta(minutes=20)), 0),
        (3, "https://mail.google.com/", "Gmail", 5, 2, to_webkit(base + timedelta(hours=2, minutes=1)), 0),
        (4, "https://open.spotify.com/", "Spotify Web", 2, 0, to_webkit(base + timedelta(minutes=46)), 0),
    ]
    visits = [
        (1, 1, to_webkit(base + timedelta(minutes=2)), 0, 1, 0, 0),
        (2, 2, to_webkit(base + timedelta(minutes=20)), 0, 1, 0, 0),
        (3, 4, to_webkit(base + timedelta(minutes=46)), 0, 1, 0, 0),
        (4, 3, to_webkit(base + timedelta(hours=2, minutes=1)), 0, 1, 0, 0),
        (5, 1, to_webkit(base + timedelta(hours=2, minutes=3)), 0, 1, 0, 0),
    ]
    conn.executemany(
        "INSERT INTO urls VALUES (?, ?, ?, ?, ?, ?, ?)",
        urls,
    )
    conn.executemany(
        "INSERT INTO visits VALUES (?, ?, ?, ?, ?, ?, ?)",
        visits,
    )
    conn.commit()
    conn.close()


def build_location_csv(base: datetime) -> None:
    path = DEMO / "location.csv"
    rows = [
        {
            "timestamp": (base + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "latitude": "12.971600",
            "longitude": "77.594600",
            "accuracy": "12",
            "provider": "gps",
        },
        {
            "timestamp": (base + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "latitude": "12.975000",
            "longitude": "77.599000",
            "accuracy": "18",
            "provider": "network",
        },
        {
            "timestamp": (base + timedelta(hours=2, minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "latitude": "12.980200",
            "longitude": "77.605100",
            "accuracy": "10",
            "provider": "gps",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["timestamp", "latitude", "longitude", "accuracy", "provider"])
        writer.writeheader()
        writer.writerows(rows)


def build_plaso_sample(base: datetime) -> None:
    path = DEMO / "plaso_sample.l2t.csv"
    # Extra correlated event via Plaso import path
    t = base + timedelta(minutes=3)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["date", "time", "timezone", "source", "desc", "message", "URL"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "date": t.strftime("%Y-%m-%d"),
                "time": t.strftime("%H:%M:%S"),
                "timezone": "UTC",
                "source": "WEBHIST",
                "desc": "Chrome History",
                "message": "Visited https://maps.google.com/search?q=cafe",
                "URL": "https://maps.google.com/search?q=cafe",
            }
        )


LARGE = ROOT / "samples" / "large_demo"
HOME = (12.9716, 77.5946)
OFFICE = (12.9352, 77.6245)
APPS = [
    ("com.whatsapp", 5),
    ("com.google.android.apps.maps", 2),
    ("com.android.chrome", 5),
    ("com.instagram.android", 3),
    ("com.spotify.music", 3),
    ("com.google.android.gm", 2),
    ("com.google.android.youtube", 3),
    ("org.telegram.messenger", 2),
]
SITES = [
    ("https://news.example.com/top", "Top stories"),
    ("https://mail.google.com/mail/u/0/", "Inbox"),
    ("https://www.google.com/search?q=cafe+near+me", "cafe near me - Google Search"),
    ("https://en.wikipedia.org/wiki/Bengaluru", "Bengaluru - Wikipedia"),
    ("https://maps.google.com/directions", "Directions"),
    ("https://www.youtube.com/watch?v=abc123", "Lo-fi beats"),
    ("https://shop.example.com/cart", "Your cart"),
    ("https://docs.example.org/guide", "Team guide"),
]


def _outings(day: datetime) -> list[tuple[datetime, datetime, tuple, tuple, int]]:
    """(start, end, from, to, seconds-per-fix): commute, lunch stroll, commute home, evening walk."""
    at = lambda h, m=0: day.replace(hour=h, minute=m)  # noqa: E731
    lunch = (OFFICE[0] + 0.004, OFFICE[1] + 0.003)
    return [
        (at(8, 30), at(9, 15), HOME, OFFICE, 10),
        (at(13, 0), at(13, 30), OFFICE, lunch, 15),
        (at(17, 40), at(18, 25), OFFICE, HOME, 10),
        (at(19, 0), at(19, 40), HOME, (HOME[0] + 0.006, HOME[1] - 0.004), 12),
    ]


def build_large(out: Path = LARGE) -> Path:
    """Three days of plausible activity (~8,000 events) for exercising the timeline at scale."""
    import math
    import random

    rng = random.Random(1337)
    out.mkdir(parents=True, exist_ok=True)
    first_day = datetime(2024, 6, 14, tzinfo=UTC)
    days = [first_day + timedelta(days=i) for i in range(3)]

    # --- location: dense fixes while moving, sparse otherwise
    rows = []
    for day in days:
        for start, end, a, b, step in _outings(day):
            total = int((end - start).total_seconds())
            for sec in range(0, total, step):
                s = sec / total
                lat = a[0] + (b[0] - a[0]) * s + 0.0008 * math.sin(3 * math.pi * s) + rng.gauss(0, 0.00012)
                lon = a[1] + (b[1] - a[1]) * s + rng.gauss(0, 0.00012)
                rows.append((start + timedelta(seconds=sec), lat, lon, rng.choice([6, 9, 14, 22, 35]), "gps"))
        for hour in (7, 10, 11, 12, 14, 15, 16, 21, 22):  # stationary network fixes
            where = OFFICE if 9 <= hour <= 17 else HOME
            rows.append((day.replace(hour=hour, minute=rng.randrange(60)), where[0], where[1], 60, "network"))
    rows.sort()
    with (out / "location.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["timestamp", "latitude", "longitude", "accuracy", "provider"])
        for t, lat, lon, acc, prov in rows:
            w.writerow([t.strftime("%Y-%m-%dT%H:%M:%SZ"), f"{lat:.6f}", f"{lon:.6f}", acc, prov])

    # --- app usage: foreground/background pairs during waking hours, busier on the move
    usage_db = out / "app_usage.db"
    usage_db.unlink(missing_ok=True)
    conn = sqlite3.connect(usage_db)
    conn.executescript(
        "CREATE TABLE packages (_id INTEGER PRIMARY KEY, package_name TEXT UNIQUE);"
        "CREATE TABLE events (_id INTEGER PRIMARY KEY, timestamp INTEGER NOT NULL, type INTEGER NOT NULL,"
        " package_id INTEGER NOT NULL REFERENCES packages(_id));"
    )
    conn.executemany("INSERT INTO packages VALUES (?, ?)", [(i + 1, p) for i, (p, _) in enumerate(APPS)])
    weights = [w for _, w in APPS]
    events = []
    for day in days:
        t = day.replace(hour=7, minute=rng.randrange(30))
        stop = day.replace(hour=23)
        while t < stop:
            app = rng.choices(range(len(APPS)), weights)[0] + 1
            length = timedelta(seconds=rng.randint(20, 420))
            events.append((utc_ms(t), 1, app))
            events.append((utc_ms(t + length), 2, app))
            t += length + timedelta(seconds=rng.randint(15, 240))
            if rng.random() < 0.06:  # screen off for a while
                events.append((utc_ms(t), 16, 1))
                t += timedelta(minutes=rng.randint(10, 90))
                events.append((utc_ms(t), 15, 1))
    conn.executemany("INSERT INTO events (timestamp, type, package_id) VALUES (?, ?, ?)", events)
    conn.commit()
    conn.close()

    # --- browsing: daytime-weighted visits, some searches and downloads
    hist = out / "History"
    hist.unlink(missing_ok=True)
    conn = sqlite3.connect(hist)
    conn.executescript(
        "CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT, visit_count INTEGER,"
        " last_visit_time INTEGER);"
        "CREATE TABLE visits (id INTEGER PRIMARY KEY, url INTEGER, visit_time INTEGER, from_visit INTEGER,"
        " transition INTEGER, visit_duration INTEGER DEFAULT 0);"
        "CREATE TABLE keyword_search_terms (keyword_id INTEGER, url_id INTEGER, term TEXT, normalized_term TEXT);"
        "CREATE TABLE downloads (id INTEGER PRIMARY KEY, target_path TEXT, start_time INTEGER, end_time INTEGER,"
        " total_bytes INTEGER, mime_type TEXT, tab_url TEXT);"
        "CREATE TABLE downloads_url_chains (id INTEGER, chain_index INTEGER, url TEXT);"
    )
    conn.executemany(
        "INSERT INTO urls VALUES (?, ?, ?, ?, ?)",
        [(i + 1, u, t, 1, 0) for i, (u, t) in enumerate(SITES)],
    )
    vid = 0
    for day in days:
        for _ in range(rng.randint(130, 190)):
            hour = min(23, max(7, int(rng.gauss(14, 4))))
            when = day.replace(hour=hour, minute=rng.randrange(60), second=rng.randrange(60))
            url_id = rng.randrange(len(SITES)) + 1
            vid += 1
            conn.execute(
                "INSERT INTO visits VALUES (?, ?, ?, 0, ?, ?)",
                (vid, url_id, to_webkit(when), rng.choice([0, 1, 1, 2, 805306376]), rng.randint(0, 90) * 1_000_000),
            )
            if url_id == 3:
                conn.execute("INSERT INTO keyword_search_terms VALUES (2, 3, 'cafe near me', 'cafe near me')")
    for n, day in enumerate(days, start=1):
        when = day.replace(hour=11, minute=20)
        conn.execute(
            "INSERT INTO downloads VALUES (?, ?, ?, ?, 48213, 'application/pdf', NULL)",
            (n, f"/storage/emulated/0/Download/statement_{n}.pdf", to_webkit(when), to_webkit(when) + 5_000_000),
        )
        conn.execute(
            "INSERT INTO downloads_url_chains VALUES (?, 0, ?)", (n, f"https://docs.example.org/files/{n}.pdf")
        )
    conn.commit()
    conn.close()
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--large" in args:
        print(f"Seeded large sample evidence in {build_large()}")
        return 0
    DEMO.mkdir(parents=True, exist_ok=True)
    base = datetime(2024, 6, 15, 10, 0, 0, tzinfo=UTC)
    build_app_usage(base)
    build_chrome_history(base)
    build_location_csv(base)
    build_plaso_sample(base)
    print(f"Seeded sample evidence in {DEMO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
