from __future__ import annotations

from pathlib import Path

from app.parsers.app_usage import AppUsageParser
from app.parsers.chrome_history import ChromeHistoryParser
from app.parsers.location import LocationParser
from app.parsers.plaso_l2tcsv import PlasoL2TCSVParser

PARSERS = [
    AppUsageParser(),
    ChromeHistoryParser(),
    LocationParser(),
    PlasoL2TCSVParser(),
]

VALID_SOURCES = {p.source for p in PARSERS}


def detect_parser(path: Path, preferred_source: str | None = None):
    if preferred_source:
        if preferred_source not in VALID_SOURCES:
            raise ValueError(f"Unknown source hint: {preferred_source}")
        for parser in PARSERS:
            if parser.source == preferred_source and parser.sniff(path):
                return parser
        raise ValueError(
            f"File does not match source hint '{preferred_source}'. "
            "Use auto-detect or upload a matching artifact."
        )
    for parser in PARSERS:
        if parser.sniff(path):
            return parser
    return None


def parse_artifact(path: Path, preferred_source: str | None = None):
    parser = detect_parser(path, preferred_source)
    if parser is None:
        raise ValueError(
            f"No parser matched for {path.name}. "
            "Provide app_usage DB/CSV, Chromium History, location CSV/DB, or Plaso L2TCSV."
        )
    try:
        records = parser.parse(path)
    except Exception as exc:
        raise ValueError(f"Failed to parse {path.name}: {exc}") from exc
    return parser, records
