from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from .helpers import get_podman_exe


def _podman_exe() -> str:
    return get_podman_exe()


# --------------------------------------------------------------------------- #
# Pretty failure printer
# --------------------------------------------------------------------------- #
def _fail(msg: str) -> None:
    header = "=" * 70
    print(f"\n{header}\n[ERROR] {msg}\n{header}\n", file=sys.stderr)  # noqa: T201
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #
def _check_podman_in_path() -> None:
    if not shutil.which("podman"):
        _fail("'podman' not found in PATH\nInstall: https://podman.io/getting-started/install.html")


def _check_podman_version() -> None:
    result = subprocess.run(  # noqa: S603
        [_podman_exe(), "--version"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return  # Already failed in PATH check
    import re

    match = re.search(r"(\d+\.\d+)", result.stdout)
    if not match:
        return
    version = tuple(map(int, match.group(1).split(".")))
    if version < (4, 0):
        _fail(
            f"podman >= 4.0 required, found {result.stdout.strip()}\n"
            "Upgrade your system packages or use a newer image in CI"
        )


def _check_podman_socket() -> None:
    result = subprocess.run(  # noqa: S603
        [_podman_exe(), "info", "--format", "{{.Host.RemoteSocket.Exists}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or result.stdout.strip() != "true":
        _fail(
            "Podman socket not running\n"
            "On Linux: systemctl --user start podman.socket\n"
            "On macOS/WSL: podman machine init && podman machine start"
        )


def _check_storage_writable() -> None:
    result = subprocess.run(  # noqa: S603
        [_podman_exe(), "info", "--format", "{{.Store.GraphRoot}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return
    graph_root = Path(result.stdout.strip())
    if not graph_root.exists():
        _fail(f"Podman storage path missing: {graph_root}")
    test_file = graph_root / ".podman-test-write"
    try:
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        _fail(
            f"Podman storage not writable: {graph_root}\n"
            f"Error: {e}\n"
            "Fix: chown $USER -R ~/.local/share/containers"
        )


def _check_docker_conflict() -> None:
    if shutil.which("docker") and not os.environ.get("PODMAN_IGNORE_DOCKER"):
        _fail(
            "'docker' CLI found in PATH — may shadow 'podman'\n"
            "Fix:\n"
            "  - Remove/rename 'docker' binary\n"
            "  - Or set: export PODMAN_IGNORE_DOCKER=1"
        )


def _check_wsl_shm() -> None:
    proc_path = Path("/proc/version")
    if not proc_path.exists():
        return  # Not Linux → not WSL
    proc = proc_path.read_text().lower()
    if "microsoft" not in proc:
        return  # Not WSL
    shm_size = Path("/dev/shm").stat().st_size  # noqa: S108
    if shm_size < 64 * 1024 * 1024:  # < 64MB
        _fail(
            f"WSL2: /dev/shm too small ({shm_size // 1024 // 1024}MB)\n"
            "MySQL/PostgreSQL will crash\n"
            "Fix in ~/.wslconfig:\n"
            "  [wsl2]\n"
            "  memory=8GB\n"
            "  swap=2GB"
        )


def _check_snap_sandbox() -> None:
    if "snap" in os.environ.get("XDG_DATA_HOME", "").lower():
        _fail(
            "Running inside Snap sandbox!\n"
            "Podman containers will be invisible in Podman Desktop\n"
            "Fix:\n"
            "  1. Right-click project in VS Code\n"
            "  2. 'Open in External Terminal'\n"
            "  3. Run: uv run pytest"
        )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
CHECKS: list[Callable[[], None]] = [
    _check_snap_sandbox,
    _check_podman_in_path,
    _check_podman_version,
    _check_podman_socket,
    _check_storage_writable,
    _check_docker_conflict,
    _check_wsl_shm,
]


def run_preflight_checks(custom_checks: list[Callable[[], None]] | None = None) -> None:
    """Runtime environment checks for Podman-based tests."""
    all_checks = CHECKS + (custom_checks or [])
    for check in all_checks:
        try:
            check()
        except Exception as e:
            _fail(str(e))
