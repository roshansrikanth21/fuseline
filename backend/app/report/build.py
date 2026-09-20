from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.db import case_conn, registry_conn, row_to_dict

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def gather_report_data(case_id: str) -> dict:
    with registry_conn() as reg:
        case = row_to_dict(reg.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone())
    if not case:
        raise FileNotFoundError(f"Case not found: {case_id}")

    with case_conn(case_id) as conn:
        artifacts = [dict(r) for r in conn.execute("SELECT * FROM artifacts ORDER BY ingested_at").fetchall()]
        findings = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM validation_findings ORDER BY created_at"
            ).fetchall()
        ]
        sessions_raw = [
            dict(r) for r in conn.execute("SELECT * FROM sessions ORDER BY score DESC").fetchall()
        ]
        sessions = []
        for s in sessions_raw:
            sessions.append(
                {
                    **s,
                    "member_event_ids": json.loads(s["member_event_ids"]),
                    "sources": json.loads(s["sources"]),
                }
            )
        source_rows = conn.execute(
            "SELECT source, COUNT(*) AS c FROM events GROUP BY source"
        ).fetchall()
        source_counts = {r["source"]: r["c"] for r in source_rows}
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        sample_events = []
        for r in conn.execute(
            "SELECT * FROM events ORDER BY ts_utc LIMIT 50"
        ).fetchall():
            item = dict(r)
            item["detail"] = json.loads(item.pop("detail_json") or "{}")
            sample_events.append(item)

    return {
        "case": case,
        "artifacts": artifacts,
        "event_count": event_count,
        "source_counts": source_counts,
        "session_count": len(sessions),
        "findings": findings,
        "sessions": sessions,
        "sample_events": sample_events,
    }


def render_html_report(case_id: str) -> str:
    data = gather_report_data(case_id)
    template = _env().get_template("report.html.j2")
    return template.render(**data)


def export_events_csv(case_id: str) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "ts_utc",
            "ts_original",
            "source",
            "event_type",
            "title",
            "package",
            "url",
            "domain",
            "lat",
            "lon",
            "confidence",
        ]
    )
    with case_conn(case_id) as conn:
        for r in conn.execute(
            """
            SELECT id, ts_utc, ts_original, source, event_type, title, package, url, domain, lat, lon, confidence
            FROM events ORDER BY ts_utc
            """
        ).fetchall():
            writer.writerow(
                [
                    r["id"],
                    r["ts_utc"],
                    r["ts_original"],
                    r["source"],
                    r["event_type"],
                    r["title"],
                    r["package"],
                    r["url"],
                    r["domain"],
                    r["lat"],
                    r["lon"],
                    r["confidence"],
                ]
            )
    return buf.getvalue()


def export_events_json(case_id: str) -> str:
    data = gather_report_data(case_id)
    with case_conn(case_id) as conn:
        events = []
        for r in conn.execute("SELECT * FROM events ORDER BY ts_utc").fetchall():
            item = dict(r)
            item["detail"] = json.loads(item.pop("detail_json") or "{}")
            events.append(item)
    payload = {
        "case": data["case"],
        "artifacts": data["artifacts"],
        "findings": data["findings"],
        "sessions": data["sessions"],
        "events": events,
        "source_counts": data["source_counts"],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)