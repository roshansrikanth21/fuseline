#!/usr/bin/env python3
"""Download Google Android Platform Tools into tools/platform-tools/ (project-local adb).

Idempotent: skips the download when adb is already present there.
Safe to run from scripts/run_dev.* so device import works without a global SDK install.
"""

from __future__ import annotations

import platform
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "tools" / "platform-tools"

ZIP_URLS = {
    "Windows": "https://dl.google.com/android/repository/platform-tools-latest-windows.zip",
    "Linux": "https://dl.google.com/android/repository/platform-tools-latest-linux.zip",
    "Darwin": "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip",
}


def adb_binary() -> Path:
    name = "adb.exe" if sys.platform == "win32" else "adb"
    return DEST / name


def ensure() -> Path:
    binary = adb_binary()
    if binary.is_file():
        print(f"platform-tools already present: {binary}")
        return binary

    system = platform.system()
    url = ZIP_URLS.get(system)
    if not url:
        raise SystemExit(f"Unsupported OS for bundled platform-tools: {system}")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Android Platform Tools for {system}...")
    print(f"  {url}")
    zip_path = DEST.parent / "platform-tools.zip"
    try:
        urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(DEST.parent)
    finally:
        zip_path.unlink(missing_ok=True)

    if not binary.is_file():
        raise SystemExit(f"Download finished but {binary} is missing — extract failed.")

    if sys.platform != "win32":
        binary.chmod(binary.stat().st_mode | 0o111)

    print(f"Installed: {binary}")
    return binary


if __name__ == "__main__":
    ensure()
