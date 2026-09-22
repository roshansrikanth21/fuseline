from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

# The data directory must be redirected before any `app` module is imported.
_DATA_DIR = tempfile.mkdtemp(prefix="fuseline-test-")
os.environ["FUSELINE_DATA_DIR"] = _DATA_DIR

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def _force_remove(func, path, _exc):
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    func(path)


def pytest_sessionfinish(session, exitstatus):
    if sys.version_info >= (3, 12):
        shutil.rmtree(_DATA_DIR, onexc=_force_remove, ignore_errors=False)
    else:
        shutil.rmtree(_DATA_DIR, onerror=_force_remove)


@pytest.fixture(scope="session")
def demo_dir() -> Path:
    demo = ROOT / "samples" / "demo_case"
    if not (demo / "app_usage.db").exists():
        import seed_demo

        seed_demo.main()
    return demo


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app

    return TestClient(app, base_url="http://127.0.0.1")


@pytest.fixture
def make_case(client: TestClient):
    def _make(timezone: str = "UTC", examiner: str = "Tester", name: str = "case") -> str:
        r = client.post("/api/cases", json={"name": name, "examiner": examiner, "timezone": timezone})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    return _make


@pytest.fixture
def case_id(make_case) -> str:
    return make_case()


@pytest.fixture
def upload(client: TestClient):
    def _upload(case: str, name: str, data: bytes | Path, hint: str = "auto"):
        content = data.read_bytes() if isinstance(data, Path) else data
        return client.post(f"/api/cases/{case}/acquire", files={"file": (name, content)}, data={"source_hint": hint})

    return _upload
