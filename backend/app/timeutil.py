"""Timestamp handling shared by every parser.

Forensic timelines are only trustworthy if the way each UTC value was derived is
explicit, so :func:`coerce_timestamp` reports the *basis* alongside the value:

``absolute``  epoch numbers and strings that carry ``Z`` -- unambiguous
``offset``    strings with an explicit UTC offset, converted
``assumed``   naive local-time strings, interpreted in the case timezone
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
WEBKIT_EPOCH = datetime(1601, 1, 1, tzinfo=UTC)

BASIS_ABSOLUTE = "absolute"
BASIS_OFFSET = "offset"
BASIS_ASSUMED = "assumed"

_ONE_MS = timedelta(milliseconds=1)
_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%d.%m.%Y %H:%M:%S",
)
_TRAILING_ZONE = re.compile(r"\s*(?:UTC|GMT|Z)$", re.IGNORECASE)
_SPACED_OFFSET = re.compile(r"\s+([+-]\d{2}:?\d{2})$")
_NUMERIC = re.compile(r"^-?\d+(?:\.\d+)?$")


class TimestampError(ValueError):
    """Raised when a value cannot be interpreted as a point in time."""


@dataclass(frozen=True)
class Timestamp:
    utc: datetime
    basis: str = BASIS_ABSOLUTE


@lru_cache(maxsize=64)
def resolve_timezone(name: str) -> tzinfo:
    cleaned = (name or "UTC").strip() or "UTC"
    if cleaned.upper() in {"UTC", "Z", "GMT"}:
        return UTC
    try:
        return ZoneInfo(cleaned)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ValueError(f"Unknown timezone '{cleaned}'. Use an IANA name such as 'UTC' or 'Asia/Kolkata'.") from exc


def canonical_timezone_name(name: str) -> str:
    """Validate ``name`` and return its canonical IANA key ('UTC' for UTC synonyms)."""
    zone = resolve_timezone(name)
    return "UTC" if zone is UTC else getattr(zone, "key", None) or name.strip()


def to_iso_utc(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def now_iso() -> str:
    return to_iso_utc(datetime.now(tz=UTC))


def to_epoch_ms(dt: datetime) -> int:
    return (dt.astimezone(UTC) - EPOCH) // _ONE_MS


def from_epoch_ms(ms: int) -> datetime:
    return EPOCH + timedelta(milliseconds=ms)


def parse_utc(ts: str) -> datetime:
    """Parse an ISO-8601 string to an aware UTC datetime (naive input is taken as UTC)."""
    text = ts.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _from_number(value: float, unit: str) -> datetime:
    if unit == "auto":
        magnitude = abs(value)
        if magnitude < 1e11:
            unit = "s"
        elif magnitude < 1e14:
            unit = "ms"
        elif magnitude < 1e17:
            unit = "us"
        else:
            unit = "ns"
    divisor = {"s": 1.0, "ms": 1e3, "us": 1e6, "ns": 1e9}[unit]
    try:
        return EPOCH + timedelta(seconds=value / divisor)
    except (OverflowError, ValueError) as exc:
        raise TimestampError(f"epoch value out of range: {value!r}") from exc


_BUCKET_STEPS_MS = [
    s * 1000
    for s in (
        1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600, 43200,
        86400, 172800, 604800, 1209600, 2592000, 7776000, 31536000,
    )
]  # fmt: skip


def nice_bucket_ms(span_ms: int, target_buckets: int) -> int:
    """Smallest 'round' bucket width (1 s to 1 y) that keeps ``span_ms`` within ``target_buckets``."""
    for step in _BUCKET_STEPS_MS:
        if span_ms / step <= target_buckets:
            return step
    return _BUCKET_STEPS_MS[-1]


def webkit_to_datetime(microseconds: int | float) -> datetime:
    """Chromium/WebKit time: microseconds since 1601-01-01 UTC."""
    if not microseconds or microseconds < 0:
        raise TimestampError(f"missing WebKit timestamp: {microseconds!r}")
    try:
        return WEBKIT_EPOCH + timedelta(microseconds=int(microseconds))
    except (OverflowError, ValueError) as exc:
        raise TimestampError(f"WebKit timestamp out of range: {microseconds!r}") from exc


def coerce_timestamp(raw: object, *, tz: tzinfo = UTC, unit: str = "auto") -> Timestamp:
    """Interpret ``raw`` (epoch number, numeric string or date string) as UTC.

    ``tz`` is applied only to naive date strings. ``unit`` overrides the magnitude
    heuristic for numeric input (``s``, ``ms``, ``us``, ``ns``).
    """
    if raw is None or isinstance(raw, bool):
        raise TimestampError("empty timestamp")
    if isinstance(raw, (int, float)):
        return Timestamp(_from_number(float(raw), unit))
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return Timestamp(raw.replace(tzinfo=tz).astimezone(UTC), BASIS_ASSUMED)
        return Timestamp(raw.astimezone(UTC), BASIS_OFFSET)

    text = str(raw).strip()
    if not text:
        raise TimestampError("empty timestamp")
    if _NUMERIC.match(text):
        return Timestamp(_from_number(float(text), unit))

    text = _SPACED_OFFSET.sub(r"\1", text)
    explicit_utc = bool(_TRAILING_ZONE.search(text))
    if explicit_utc:
        text = _TRAILING_ZONE.sub("", text)
    candidate = text.replace(" ", "T", 1) if " " in text and "T" not in text else text

    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        for fmt in _FORMATS:
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise TimestampError(f"unparseable timestamp: {raw!r}")

    if parsed.tzinfo is not None:
        basis = BASIS_ABSOLUTE if explicit_utc and parsed.utcoffset() == timedelta(0) else BASIS_OFFSET
        return Timestamp(parsed.astimezone(UTC), basis)
    if explicit_utc:
        return Timestamp(parsed.replace(tzinfo=UTC), BASIS_ABSOLUTE)
    return Timestamp(parsed.replace(tzinfo=tz).astimezone(UTC), BASIS_ASSUMED)
