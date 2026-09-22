from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.timeutil import from_epoch_ms, to_epoch_ms

LARGE_GAP = timedelta(days=7)
EARLY_CUTOFF_MS = to_epoch_ms(datetime(2008, 1, 1, tzinfo=UTC))


@dataclass
class Finding:
    severity: str
    code: str
    message: str


@dataclass
class CaseStats:
    event_count: int = 0
    source_ranges: dict[str, tuple[int, int, int]] = field(default_factory=dict)  # lo_ms, hi_ms, n
    artifact_hashes: list[str] = field(default_factory=list)
    skipped_rows: int = 0
    max_gap_ms: int = 0
    future_events: int = 0
    early_events: int = 0
    assumed_by_tz: dict[str, int] = field(default_factory=dict)
    session_count: int = 0

    @property
    def source_counts(self) -> dict[str, int]:
        return {s: r[2] for s, r in self.source_ranges.items()}

    @property
    def span_ms(self) -> tuple[int, int] | None:
        if not self.source_ranges:
            return None
        return (
            min(r[0] for r in self.source_ranges.values()),
            max(r[1] for r in self.source_ranges.values()),
        )


def gather_stats(conn: sqlite3.Connection) -> CaseStats:
    stats = CaseStats()
    stats.event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    for r in conn.execute(
        "SELECT source, MIN(ts_ms) AS lo, MAX(ts_ms) AS hi, COUNT(*) AS n FROM events GROUP BY source"
    ):
        stats.source_ranges[r["source"]] = (int(r["lo"]), int(r["hi"]), int(r["n"]))
    stats.artifact_hashes = [r[0] for r in conn.execute("SELECT sha256 FROM artifacts")]
    stats.skipped_rows = conn.execute("SELECT COALESCE(SUM(skipped_rows), 0) FROM artifacts").fetchone()[0]
    stats.max_gap_ms = (
        conn.execute(
            "SELECT MAX(gap) FROM (SELECT ts_ms - LAG(ts_ms) OVER (ORDER BY ts_ms) AS gap FROM events)"
        ).fetchone()[0]
        or 0
    )
    now_ms = to_epoch_ms(datetime.now(tz=UTC))
    stats.future_events = conn.execute(
        "SELECT COUNT(*) FROM events WHERE ts_ms > ?", (now_ms + 86_400_000,)
    ).fetchone()[0]
    stats.early_events = conn.execute("SELECT COUNT(*) FROM events WHERE ts_ms < ?", (EARLY_CUTOFF_MS,)).fetchone()[0]
    stats.assumed_by_tz = {
        r[0]: r[1]
        for r in conn.execute("SELECT tz_assumed, COUNT(*) FROM events WHERE ts_basis = 'assumed' GROUP BY tz_assumed")
    }
    stats.session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    return stats


def _fmt_ms(ms: int) -> str:
    return from_epoch_ms(ms).strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_duration(ms: int) -> str:
    seconds = max(0, ms) // 1000
    days, rem = divmod(seconds, 86_400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days} d {hours} h"
    if hours:
        return f"{hours} h {minutes} m"
    if minutes:
        return f"{minutes} m {secs} s"
    return f"{secs} s"


def validate_case(stats: CaseStats) -> list[Finding]:
    findings: list[Finding] = []
    sources = stats.source_counts

    if stats.event_count == 0:
        findings.append(Finding("fail", "NO_EVENTS", "Case contains no events — check the artifact formats."))
    else:
        findings.append(Finding("pass", "EVENTS_PRESENT", f"Case contains {stats.event_count:,} normalized events."))

    if len(sources) >= 2:
        findings.append(Finding("pass", "MULTI_SOURCE", f"Multiple sources present: {', '.join(sorted(sources))}."))
    elif len(sources) == 1:
        findings.append(
            Finding(
                "warn",
                "SINGLE_SOURCE",
                f"Only one source type ingested ({next(iter(sources))}). Correlation needs at least two.",
            )
        )
    else:
        findings.append(Finding("fail", "NO_SOURCES", "No source types recorded."))

    if len(stats.artifact_hashes) != len(set(stats.artifact_hashes)):
        findings.append(Finding("warn", "DUPLICATE_HASH", "Duplicate artifact hashes detected in case."))
    elif stats.artifact_hashes:
        findings.append(
            Finding("pass", "HASH_INVENTORY", f"{len(stats.artifact_hashes)} artifact SHA-256 hash(es) recorded.")
        )

    if stats.skipped_rows:
        findings.append(
            Finding(
                "warn",
                "ROWS_SKIPPED",
                f"{stats.skipped_rows:,} source row(s) could not be parsed and were skipped — "
                "see each artifact's notes for the reasons.",
            )
        )

    for tz, count in sorted(stats.assumed_by_tz.items()):
        findings.append(
            Finding(
                "warn",
                "TZ_ASSUMED",
                f"{count:,} event(s) carried local timestamps with no offset and were interpreted as {tz}. "
                "Confirm the device timezone before relying on cross-source ordering.",
            )
        )

    span = stats.span_ms
    if span is not None:
        lo, hi = span
        findings.append(
            Finding(
                "info",
                "TIME_SPAN",
                f"Timeline spans {_fmt_duration(hi - lo)} from {_fmt_ms(lo)} to {_fmt_ms(hi)}.",
            )
        )
        gap = timedelta(milliseconds=stats.max_gap_ms)
        if gap > LARGE_GAP:
            findings.append(
                Finding(
                    "warn",
                    "LARGE_GAP",
                    f"Largest inter-event gap is {_fmt_duration(stats.max_gap_ms)} — "
                    "possible missing evidence or clock skew.",
                )
            )
        else:
            findings.append(Finding("pass", "GAP_OK", f"Largest inter-event gap is {_fmt_duration(stats.max_gap_ms)}."))

    ranges = sorted(stats.source_ranges.items())
    for i, (a, (a_lo, a_hi, _)) in enumerate(ranges):
        for b, (b_lo, b_hi, _) in ranges[i + 1 :]:
            if a_hi < b_lo or b_hi < a_lo:
                findings.append(
                    Finding(
                        "warn",
                        "NO_TIME_OVERLAP",
                        f"{a} ({_fmt_ms(a_lo)} → {_fmt_ms(a_hi)}) and {b} ({_fmt_ms(b_lo)} → {_fmt_ms(b_hi)}) "
                        "never overlap in time, so they cannot correlate — check timezone or clock skew.",
                    )
                )

    if len(sources) >= 2:
        if stats.session_count:
            findings.append(
                Finding("pass", "SESSIONS_FOUND", f"{stats.session_count:,} proximity session(s) correlated.")
            )
        else:
            findings.append(
                Finding(
                    "info",
                    "NO_SESSIONS",
                    "No events from different sources fall close enough together to form a session.",
                )
            )

    if stats.future_events:
        findings.append(
            Finding(
                "warn",
                "FUTURE_TS",
                f"{stats.future_events:,} event(s) are more than 1 day in the future — check timezone assumptions.",
            )
        )
    if stats.early_events:
        findings.append(
            Finding(
                "warn",
                "EARLY_TS",
                f"{stats.early_events:,} event(s) are dated before 2008 — often zero/epoch placeholder values.",
            )
        )
    return findings


def findings_with_ids(findings: list[Finding], created_at: str) -> list[dict]:
    return [
        {
            "id": str(uuid.uuid4()),
            "severity": f.severity,
            "code": f.code,
            "message": f.message,
            "created_at": created_at,
        }
        for f in findings
    ]
