from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.timeutil import (
    BASIS_ABSOLUTE,
    BASIS_ASSUMED,
    BASIS_OFFSET,
    TimestampError,
    canonical_timezone_name,
    coerce_timestamp,
    nice_bucket_ms,
    parse_utc,
    resolve_timezone,
    to_epoch_ms,
    to_iso_utc,
    webkit_to_datetime,
)

NEW_YORK = resolve_timezone("America/New_York")


def test_iso_roundtrip_and_ms_precision():
    dt = parse_utc("2024-06-15T10:00:00.123Z")
    assert to_iso_utc(dt) == "2024-06-15T10:00:00.123Z"
    assert to_epoch_ms(dt) == 1718445600123


@pytest.mark.parametrize(
    ("raw", "unit", "expected"),
    [
        (1718445600, "auto", "2024-06-15T10:00:00.000Z"),
        (1718445600123, "auto", "2024-06-15T10:00:00.123Z"),
        (1718445600123456, "auto", "2024-06-15T10:00:00.123Z"),
        ("1718445600123", "auto", "2024-06-15T10:00:00.123Z"),
        (1718445600, "s", "2024-06-15T10:00:00.000Z"),
        (1718445600000, "ms", "2024-06-15T10:00:00.000Z"),
    ],
)
def test_numeric_epoch_units(raw, unit, expected):
    ts = coerce_timestamp(raw, unit=unit)
    assert to_iso_utc(ts.utc) == expected
    assert ts.basis == BASIS_ABSOLUTE


def test_explicit_utc_is_absolute():
    for raw in ("2024-06-15T10:00:00Z", "2024-06-15 10:00:00 UTC", "2024-06-15T10:00:00+00:00"):
        assert coerce_timestamp(raw).utc == datetime(2024, 6, 15, 10, tzinfo=UTC), raw
    assert coerce_timestamp("2024-06-15T10:00:00Z").basis == BASIS_ABSOLUTE


def test_offset_is_converted_not_assumed():
    ts = coerce_timestamp("2024-06-15T10:00:00-05:00")
    assert ts.utc == datetime(2024, 6, 15, 15, tzinfo=UTC)
    assert ts.basis == BASIS_OFFSET
    assert coerce_timestamp("2024-06-15 10:00:00 +0530").utc == datetime(2024, 6, 15, 4, 30, tzinfo=UTC)


def test_naive_uses_case_timezone_and_is_flagged():
    ts = coerce_timestamp("2024-06-15 10:00:00", tz=NEW_YORK)
    assert ts.utc == datetime(2024, 6, 15, 14, tzinfo=UTC)  # EDT = UTC-4
    assert ts.basis == BASIS_ASSUMED


def test_naive_respects_dst_transitions():
    winter = coerce_timestamp("2024-01-15 10:00:00", tz=NEW_YORK)
    assert winter.utc == datetime(2024, 1, 15, 15, tzinfo=UTC)  # EST = UTC-5


@pytest.mark.parametrize("raw", ["2024-06-15T10:00:00.123456789Z", "2024-06-15 10:00:00.5"])
def test_fractional_seconds_of_any_length(raw):
    assert coerce_timestamp(raw).utc.year == 2024


def test_us_style_date_from_plaso():
    ts = coerce_timestamp("06/15/2024 10:00:00")
    assert ts.utc == datetime(2024, 6, 15, 10, tzinfo=UTC)


@pytest.mark.parametrize("raw", [None, "", "   ", "not a date", "2024-13-45 99:99:99", True])
def test_rejects_garbage(raw):
    with pytest.raises(TimestampError):
        coerce_timestamp(raw)


def test_huge_epoch_is_an_error_not_a_crash():
    with pytest.raises(TimestampError):
        coerce_timestamp(10**30)


def test_webkit_time():
    dt = webkit_to_datetime((1718445600 + 11_644_473_600) * 1_000_000)
    assert dt == datetime(2024, 6, 15, 10, tzinfo=UTC)
    for bad in (0, None, -5, 10**30):
        with pytest.raises(TimestampError):
            webkit_to_datetime(bad)


def test_timezone_resolution():
    assert resolve_timezone("utc") is UTC
    assert canonical_timezone_name("UTC") == "UTC"
    assert canonical_timezone_name("Asia/Kolkata") == "Asia/Kolkata"
    with pytest.raises(ValueError, match="Unknown timezone"):
        resolve_timezone("Mars/Olympus")


def test_parse_utc_treats_naive_as_utc():
    assert parse_utc("2024-06-15T10:00:00") == datetime(2024, 6, 15, 10, tzinfo=UTC)
    assert parse_utc("2024-06-15T10:00:00+02:00") == datetime(2024, 6, 15, 8, tzinfo=UTC)


def test_nice_bucket_keeps_bucket_count_bounded():
    for span in (1000, 60_000, 3_600_000, 86_400_000 * 3, 86_400_000 * 400):
        bucket = nice_bucket_ms(span, 240)
        assert span / bucket <= 240 or bucket == 31_536_000_000
    assert nice_bucket_ms(1000, 240) == 1000
    assert nice_bucket_ms(timedelta(hours=2).total_seconds() * 1000, 240) == 30_000  # 240 buckets of 30 s


def test_tz_offset_object_is_supported():
    ts = coerce_timestamp("2024-06-15 10:00:00", tz=timezone(timedelta(hours=2)))
    assert ts.utc == datetime(2024, 6, 15, 8, tzinfo=UTC)
