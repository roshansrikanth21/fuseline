"""Minimal, read-only ADB wrapper for the "import from a connected phone" flow.

Everything here only ever reads from the device (``adb devices``, ``adb shell dumpsys
usagestats``) — nothing writes to or modifies the phone. A device serial received from the
API is never trusted blindly: it is re-checked against a fresh ``adb devices`` listing before
use, and every subprocess call passes arguments as a list (never ``shell=True``), so there is
no shell-injection surface regardless.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

SERIAL_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
LIST_TIMEOUT_SECONDS = 10
PULL_TIMEOUT_SECONDS = 45
PLATFORM_TOOLS_URL = "https://developer.android.com/tools/releases/platform-tools"


class AdbNotAvailable(RuntimeError):
    """adb is not installed / not on PATH."""


class AdbDeviceError(RuntimeError):
    """The requested device is not connected, not authorised, or the pull failed."""


@dataclass
class AdbDevice:
    serial: str
    state: str  # "device" (ready), "unauthorized", "offline", ...
    model: str | None = None

    @property
    def ready(self) -> bool:
        return self.state == "device"


def adb_path() -> str:
    path = shutil.which("adb")
    if not path:
        raise AdbNotAvailable(
            "adb was not found on this machine. Install Android Platform Tools "
            f"({PLATFORM_TOOLS_URL}) and make sure 'adb' is on your PATH, then refresh."
        )
    return path


def _run(args: list[str], timeout: int) -> str:
    try:
        proc = subprocess.run(  # list args, no shell=True, adb path resolved via shutil.which
            [adb_path(), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdbDeviceError(f"adb {' '.join(args)} timed out after {timeout}s.") from exc
    except OSError as exc:
        raise AdbNotAvailable(f"Could not run adb: {exc}") from exc
    if proc.returncode != 0:
        raise AdbDeviceError(proc.stderr.strip() or f"adb {' '.join(args)} failed (exit {proc.returncode}).")
    return proc.stdout


def list_devices() -> list[AdbDevice]:
    """Devices `adb devices -l` currently reports. Read-only; touches nothing on the phone."""
    out = _run(["devices", "-l"], LIST_TIMEOUT_SECONDS)
    devices: list[AdbDevice] = []
    for line in out.splitlines()[1:]:  # first line is the "List of devices attached" header
        parts = line.split()
        if not parts:
            continue
        serial, state = parts[0], parts[1] if len(parts) > 1 else "unknown"
        model = next((p.split(":", 1)[1] for p in parts[2:] if p.startswith("model:")), None)
        devices.append(AdbDevice(serial=serial, state=state, model=model))
    return devices


def _require_ready_device(serial: str) -> AdbDevice:
    if not SERIAL_RE.match(serial):
        raise AdbDeviceError("Invalid device serial.")
    match = next((d for d in list_devices() if d.serial == serial), None)
    if match is None:
        raise AdbDeviceError("That device is no longer connected. Refresh the device list and try again.")
    if not match.ready:
        raise AdbDeviceError(
            f"Device is '{match.state}', not ready. Check the phone screen and accept the "
            "USB debugging authorisation prompt, then refresh."
        )
    return match


def pull_usagestats_text(serial: str) -> str:
    """Raw `dumpsys usagestats` text from the given, currently-connected, authorised device."""
    device = _require_ready_device(serial)
    return _run(["-s", device.serial, "shell", "dumpsys", "usagestats"], PULL_TIMEOUT_SECONDS)
