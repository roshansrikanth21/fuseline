from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def demo_dir() -> Path:
    demo = ROOT / "samples" / "demo_case"
    if not (demo / "app_usage.db").exists():
        sys.path.insert(0, str(ROOT / "scripts"))
        import seed_demo

        seed_demo.main()
    return demo
