from __future__ import annotations

import subprocess

import pytest

from app import device

SAMPLE_DEVICES = (
    "List of devices attached\n"
    "emulator-5554\tdevice product:sdk_gphone model:Pixel_6 device:emu64a\n"
    "ZY3222ABCD\tunauthorized\n"
    "0123456789ABCDEF\toffline\n"
    "\n"
)


def test_adb_path_raises_when_not_on_path(monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda _: None)
    with pytest.raises(device.AdbNotAvailable, match="Platform Tools"):
        device.adb_path()


def test_list_devices_parses_states_and_model(monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda _: "/usr/bin/adb")
    monkeypatch.setattr(
        device.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=SAMPLE_DEVICES, stderr=""),
    )
    found = device.list_devices()
    assert [(d.serial, d.state, d.ready) for d in found] == [
        ("emulator-5554", "device", True),
        ("ZY3222ABCD", "unauthorized", False),
        ("0123456789ABCDEF", "offline", False),
    ]
    assert found[0].model == "Pixel_6"
    assert found[1].model is None


def test_list_devices_empty(monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda _: "/usr/bin/adb")
    monkeypatch.setattr(
        device.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="List of devices attached\n\n", stderr=""),
    )
    assert device.list_devices() == []


def test_run_raises_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda _: "/usr/bin/adb")
    monkeypatch.setattr(
        device.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr="no permissions"),
    )
    with pytest.raises(device.AdbDeviceError, match="no permissions"):
        device.list_devices()


def test_run_raises_on_timeout(monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda _: "/usr/bin/adb")

    def raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="adb", timeout=10)

    monkeypatch.setattr(device.subprocess, "run", raise_timeout)
    with pytest.raises(device.AdbDeviceError, match="timed out"):
        device.list_devices()


def test_pull_rejects_a_serial_that_looks_like_a_shell_argument(monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda _: "/usr/bin/adb")
    monkeypatch.setattr(
        device.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=SAMPLE_DEVICES, stderr=""),
    )
    with pytest.raises(device.AdbDeviceError, match="Invalid device serial"):
        device.pull_usagestats_text("emulator-5554; rm -rf /")


def test_pull_rejects_a_serial_not_currently_connected(monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda _: "/usr/bin/adb")
    monkeypatch.setattr(
        device.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=SAMPLE_DEVICES, stderr=""),
    )
    with pytest.raises(device.AdbDeviceError, match="no longer connected"):
        device.pull_usagestats_text("does-not-exist")


def test_pull_rejects_an_unauthorized_device(monkeypatch):
    monkeypatch.setattr(device.shutil, "which", lambda _: "/usr/bin/adb")
    monkeypatch.setattr(
        device.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=SAMPLE_DEVICES, stderr=""),
    )
    with pytest.raises(device.AdbDeviceError, match="unauthorized"):
        device.pull_usagestats_text("ZY3222ABCD")


def test_pull_calls_adb_with_the_verified_serial_and_no_shell(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[1:] == ["devices", "-l"]:
            return subprocess.CompletedProcess(args, 0, stdout=SAMPLE_DEVICES, stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="Usage Events:\n", stderr="")

    monkeypatch.setattr(device.shutil, "which", lambda _: "/usr/bin/adb")
    monkeypatch.setattr(device.subprocess, "run", fake_run)
    out = device.pull_usagestats_text("emulator-5554")
    assert out == "Usage Events:\n"
    assert calls[-1] == ["/usr/bin/adb", "-s", "emulator-5554", "shell", "dumpsys", "usagestats"]
    for call in calls:
        assert isinstance(call, list)  # never a shell string
