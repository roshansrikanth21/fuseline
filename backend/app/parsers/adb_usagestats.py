from __future__ import annotations

import re
from pathlib import Path

from app.parsers.base import EventRecord, ParseContext, ParseResult, compact, read_text_head
from app.timeutil import TimestampError, to_iso_utc

# `adb shell dumpsys usagestats` prints a "Usage Events:" section with lines like:
#   time="2024-06-15 10:00:00" type=MOVE_TO_FOREGROUND package=com.whatsapp class=... instanceId=12
# The exact field set varies across Android versions; only time/type/package are required here,
# every other key=value pair is captured into detail generically.
_EVENT_LINE = re.compile(r'time="(?P<time>[^"]+)"\s+type=(?P<type>\w+)\s+package=(?P<package>\S+)(?P<rest>.*)')
_KV = re.compile(r"(\w+)=(\S+)")
_SECTION_HEADER = re.compile(r"^[A-Za-z][\w ]*:$")


class AdbUsageStatsParser:
    """Live pull via ADB: `adb shell dumpsys usagestats` text output, no root required."""

    source = "app_usage"
    name = "adb_usagestats_dump"

    def sniff(self, path: Path) -> float:
        # The "Usage Events:" section can sit well past the first 64 KiB on a device with
        # months of history, so this reads a generous window rather than a small head.
        head = read_text_head(path, 4_000_000)
        if head is None:
            return 0.0
        return 0.9 if "Usage Events:" in head and _EVENT_LINE.search(head) else 0.0

    def parse(self, path: Path, ctx: ParseContext) -> ParseResult:
        result = ParseResult()
        in_events = False
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if line.startswith("Usage Events:"):
                    in_events = True
                    continue
                if not in_events or not line:
                    continue
                if _SECTION_HEADER.match(line) and "=" not in line:
                    in_events = False  # a new dumpsys section starts; events block is over
                    continue
                match = _EVENT_LINE.match(line)
                if not match:
                    result.skip("unrecognised usage-event line")
                    continue
                try:
                    ts = ctx.timestamp(match.group("time"))
                except (TimestampError, OverflowError):
                    result.skip("unparseable timestamp")
                    continue
                package = match.group("package")
                extra = dict(_KV.findall(match.group("rest")))
                result.records.append(
                    EventRecord(
                        ts_utc=to_iso_utc(ts.utc),
                        ts_original=match.group("time"),
                        source=self.source,
                        event_type=match.group("type").lower(),
                        title=package,
                        package=package,
                        tz_assumed=ctx.tz_label(ts),
                        ts_basis=ts.basis,
                        detail=compact({"type": match.group("type"), **extra}),
                        confidence=0.85,
                    )
                )
        return result
