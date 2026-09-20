from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.parsers.registry import detect_parser
from app.security import assert_safe_case_id, assert_under, sanitize_filename


def test_reject_path_traversal_case_id():
    with pytest.raises(ValueError):
        assert_safe_case_id("../etc/passwd")
    with pytest.raises(ValueError):
        assert_safe_case_id("not-a-uuid")


def test_accept_uuid_case_id():
    cid = "479280c8-9ae9-49fe-8d25-2c7d749678bf"
    assert assert_safe_case_id(cid) == cid


def test_sanitize_filename_strips_paths():
    assert sanitize_filename("../../evil.db") == "evil.db"
    assert sanitize_filename("ok History") == "ok History"
    with pytest.raises(ValueError):
        sanitize_filename("..")


def test_assert_under_blocks_escape(tmp_path: Path):
    root = tmp_path / "uploads"
    root.mkdir()
    good = root / "a" / "b.db"
    good.parent.mkdir()
    good.write_text("x")
    assert assert_under(good, root) == good.resolve()
    with pytest.raises(ValueError):
        assert_under(tmp_path / "outside.db", root)


def test_parser_hint_requires_sniff(demo_dir: Path):
    loc = demo_dir / "location.csv"
    with pytest.raises(ValueError, match="does not match source hint"):
        detect_parser(loc, preferred_source="browsing")
    assert detect_parser(loc, preferred_source="location") is not None
