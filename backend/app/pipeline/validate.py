from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.pipeline.normalize import parse_utc


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def validate_case(
    *,
    artifact_hashes: list[str],
    event_timestamps: list[str],
    source_counts: dict[str, int],
    events_added: int,
) -> list[Finding]:
    findings: list[Finding] = []

    if events_added == 0:
        findings.append(
            Finding("fail", "NO_EVENTS", "Ingest produced zero events — check artifact format.")
        )
    else:
        findings.append(
            Finding("pass", "EVENTS_PRESENT", f"Ingested {events_added} normalized events.")
        )

    if len(source_counts) >= 2:
        findings.append(
            Finding(
                "pass",
                "MULTI_SOURCE",
                f"Multiple artifact sources present: {', '.join(sorted(source_counts))}.",
            )
        )
    elif len(source_counts) == 1:
        findings.append(
            Finding(
                "warn",
                "SINGLE_SOURCE",
                f"Only one source type ingested ({next(iter(source_counts))}). Correlation needs ≥2.",
            )
        )
    else:
        findings.append(Finding("fail", "NO_SOURCES", "No source types recorded."))

    # Hash uniqueness
    if len(artifact_hashes) != len(set(artifact_hashes)):
        findings.append(
            Finding("warn", "DUPLICATE_HASH", "Duplicate artifact hashes detected in case.")
        )
    elif artifact_hashes:
        findings.append(
            Finding("pass", "HASH_INVENTORY", f"{len(artifact_hashes)} artifact hash(es) recorded.")
        )

    # Timestamp sanity / gaps
    parsed: list = []
    bad = 0
    for ts in event_timestamps:
        try:
            parsed.append(parse_utc(ts))
        except ValueError:
            bad += 1
    if bad:
        findings.append(
            Finding("fail", "BAD_TIMESTAMPS", f"{bad} event(s) have unparseable timestamps.")
        )
    elif parsed:
        parsed.sort()
        span = parsed[-1] - parsed[0]
        findings.append(
            Finding(
                "info",
                "TIME_SPAN",
                f"Timeline spans {span} from {parsed[0].isoformat()} to {parsed[-1].isoformat()}.",
            )
        )
        # Large gap detection
        max_gap = timedelta(0)
        for i in range(1, len(parsed)):
            gap = parsed[i] - parsed[i - 1]
            if gap > max_gap:
                max_gap = gap
        if max_gap > timedelta(days=7):
            findings.append(
                Finding(
                    "warn",
                    "LARGE_GAP",
                    f"Largest inter-event gap is {max_gap} — possible missing evidence or clock skew.",
                )
            )
        else:
            findings.append(
                Finding("pass", "GAP_OK", f"Largest inter-event gap is {max_gap}.")
            )

        # Future timestamps
        from datetime import datetime, timezone

        now = datetime.now(tz=timezone.utc)
        future = sum(1 for p in parsed if p > now + timedelta(days=1))
        if future:
            findings.append(
                Finding(
                    "warn",
                    "FUTURE_TS",
                    f"{future} event(s) are more than 1 day in the future — check timezone assumptions.",
                )
            )

    return findings


def findings_with_ids(findings: list[Finding], created_at: str) -> list[dict]:
    rows = []
    for f in findings:
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "severity": f.severity,
                "code": f.code,
                "message": f.message,
                "created_at": created_at,
            }
        )
    return rows