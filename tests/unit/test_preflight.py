# tests/unit/test_preflight_mocked.py
from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from podman_runner.preflight import (
    _check_docker_conflict,
    _check_podman_in_path,
    _check_podman_socket,
    _check_podman_version,
    _check_snap_sandbox,
    _check_storage_writable,
    _check_wsl_shm,
    _fail,
    run_preflight_checks,
)


# --------------------------------------------------------------------------- #
# Helper: Mock _fail to avoid sys.exit() in tests
# --------------------------------------------------------------------------- #
def mock_fail(msg: str) -> None:
    raise RuntimeError(f"FAIL: {msg}")


# --------------------------------------------------------------------------- #
# 100% Coverage Tests
# --------------------------------------------------------------------------- #
def test_run_preflight_checks_all_pass() -> None:
    """All checks pass → no failure."""
    with patch("podman_runner.preflight.CHECKS", []):
        run_preflight_checks()  # Should not raise


def test_run_preflight_checks_one_fails() -> None:
    """One check raises → _fail is called."""

    def bad_check() -> None:
        raise RuntimeError("boom")

    with (
        patch("podman_runner.preflight.CHECKS", [bad_check]),
        patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock,
    ):
        with pytest.raises(RuntimeError, match="FAIL: boom"):
            run_preflight_checks()
    fail_mock.assert_called_once_with("boom")


def test_check_snap_sandbox_not_snap(monkeypatch: pytest.MonkeyPatch) -> None:
    """XDG_DATA_HOME does not contain 'snap'."""
    monkeypatch.setenv("XDG_DATA_HOME", "/home/user/.local/share")
    _check_snap_sandbox()  # Should not raise


def test_check_snap_sandbox_is_snap(monkeypatch: pytest.MonkeyPatch) -> None:
    """XDG_DATA_HOME contains 'snap' → fail."""
    monkeypatch.setenv("XDG_DATA_HOME", "/home/user/snap/vscodium/current")
    with patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock:
        with pytest.raises(RuntimeError, match="FAIL: Running inside Snap sandbox!"):
            _check_snap_sandbox()
    fail_mock.assert_called_once()


def test_check_podman_in_path_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Podman is in PATH."""
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/podman")
    _check_podman_in_path()  # Should not raise


def test_check_podman_in_path_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """Podman not in PATH → fail."""
    monkeypatch.setattr("shutil.which", lambda x: None)
    with patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock:
        with pytest.raises(RuntimeError, match="FAIL: 'podman' not found in PATH"):
            _check_podman_in_path()
    fail_mock.assert_called_once()


def test_check_podman_version_good(monkeypatch: pytest.MonkeyPatch) -> None:
    """Podman version >= 4.0."""
    mock = MagicMock(
        return_value=subprocess.CompletedProcess([], 0, stdout="podman version 5.2.1\n")
    )
    monkeypatch.setattr("subprocess.run", mock)
    _check_podman_version()  # Should not raise


def test_check_podman_version_no_version_in_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Podman --version succeeds but output has no version number → skip."""
    mock = MagicMock(
        return_value=subprocess.CompletedProcess([], 0, stdout="podman version: unknown\n")
    )
    monkeypatch.setattr("subprocess.run", mock)
    _check_podman_version()  # Should not raise or fail


def test_check_podman_version_old(monkeypatch: pytest.MonkeyPatch) -> None:
    """Podman version < 4.0 → fail."""
    mock = MagicMock(
        return_value=subprocess.CompletedProcess([], 0, stdout="podman version 3.4.4\n")
    )
    monkeypatch.setattr("subprocess.run", mock)
    with patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock:
        with pytest.raises(RuntimeError, match="FAIL: podman >= 4.0 required"):
            _check_podman_version()
    fail_mock.assert_called_once()


def test_check_podman_version_no_version_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Podman --version fails → skip (already failed PATH check)."""
    mock = MagicMock(return_value=subprocess.CompletedProcess([], 1))
    monkeypatch.setattr("subprocess.run", mock)
    _check_podman_version()  # Should not raise (graceful skip)


def test_check_podman_socket_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """Podman socket exists and reports true."""
    mock = MagicMock(return_value=subprocess.CompletedProcess([], 0, stdout="true\n"))
    monkeypatch.setattr("subprocess.run", mock)
    _check_podman_socket()  # Should not raise


def test_check_podman_socket_not_running(monkeypatch: pytest.MonkeyPatch) -> None:
    """Socket not running → fail."""
    mock = MagicMock(return_value=subprocess.CompletedProcess([], 0, stdout="false\n"))
    monkeypatch.setattr("subprocess.run", mock)
    with patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock:
        with pytest.raises(RuntimeError, match="FAIL: Podman socket not running"):
            _check_podman_socket()
    fail_mock.assert_called_once()


def test_check_podman_socket_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Podman info command fails → fail with message."""
    mock = MagicMock(return_value=subprocess.CompletedProcess([], 1))
    monkeypatch.setattr("subprocess.run", mock)

    with patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock:
        with pytest.raises(RuntimeError, match="FAIL: Podman socket not running"):
            _check_podman_socket()

    fail_mock.assert_called_once_with(
        "Podman socket not running\n"
        "On Linux: systemctl --user start podman.socket\n"
        "On macOS/WSL: podman machine init && podman machine start"
    )


def _wsl_path_new(
    original_new: Callable[[type[Path], Any, Any], Path],
    *,
    proc_content: str = "Microsoft",
    shm_size: int = 32 * 1024 * 1024,
) -> Callable[[type[Path], Any, Any], Path]:
    """Factory for ``Path.__new__`` that mocks ``/proc/version`` and ``/dev/shm``.

    Parameters
    ----------
    original_new
        The original ``Path.__new__`` method.
    proc_content
        Text returned by ``Path("/proc/version").read_text()``.
    shm_size
        Value returned by ``Path("/dev/shm").stat().st_size``.

    Returns:
    -------
    Callable
        A drop-in replacement for ``Path.__new__``.
    """

    def path_new(cls: type[Path], *args: Any, **kwargs: Any) -> Path:
        path_str = str(args[0]) if args else ""
        if path_str == "/proc/version":
            mock = MagicMock()
            mock.read_text.return_value = proc_content
            return mock
        if path_str == "/dev/shm":  # noqa: S108
            mock = MagicMock()
            mock.stat.return_value.st_size = shm_size
            return mock
        return original_new(cls, *args, **kwargs)

    return path_new


def test_check_wsl_shm_small_shm(monkeypatch: pytest.MonkeyPatch) -> None:
    """WSL with a tiny ``/dev/shm`` → failure."""
    original_new = Path.__new__
    monkeypatch.setattr(Path, "__new__", _wsl_path_new(original_new))

    with patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock:
        with pytest.raises(RuntimeError, match="FAIL: WSL2: /dev/shm too small"):
            _check_wsl_shm()
    fail_mock.assert_called_once()


def test_check_wsl_shm_large_shm(monkeypatch: pytest.MonkeyPatch) -> None:
    """WSL with a sufficiently large ``/dev/shm`` → pass."""
    original_new = Path.__new__
    monkeypatch.setattr(
        Path,
        "__new__",
        _wsl_path_new(
            original_new,
            proc_content="Linux ... Microsoft ...",
            shm_size=128 * 1024 * 1024,  # 128 MiB
        ),
    )

    _check_wsl_shm()  # should **not** raise


def test_check_storage_writable_exists_and_writable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GraphRoot exists and is writable."""
    graph_root = tmp_path / "podman"
    graph_root.mkdir()
    (graph_root / ".podman-test-write").touch()

    mock_info = MagicMock(
        return_value=subprocess.CompletedProcess([], 0, stdout=str(graph_root) + "\n")
    )
    monkeypatch.setattr("subprocess.run", mock_info)

    _check_storage_writable()  # Should not raise


def test_check_storage_writable_not_writable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """GraphRoot exists but not writable → fail."""
    graph_root = tmp_path / "podman"
    graph_root.mkdir(exist_ok=True)
    # Make it read-only
    graph_root.chmod(0o555)

    mock_info = MagicMock(
        return_value=subprocess.CompletedProcess([], 0, stdout=str(graph_root) + "\n")
    )
    monkeypatch.setattr("subprocess.run", mock_info)

    with patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock:
        with pytest.raises(RuntimeError, match="FAIL: Podman storage not writable"):
            _check_storage_writable()
    fail_mock.assert_called_once()


def test_check_storage_writable_missing_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """GraphRoot does not exist → fail."""
    mock_info = MagicMock(
        return_value=subprocess.CompletedProcess([], 0, stdout="/nonexistent/podman\n")
    )
    monkeypatch.setattr("subprocess.run", mock_info)

    with patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock:
        with pytest.raises(RuntimeError, match="FAIL: Podman storage path missing"):
            _check_storage_writable()

    fail_mock.assert_called_once_with("Podman storage path missing: /nonexistent/podman")


def test_check_storage_writable_command_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """Podman info fails → skip."""
    mock = MagicMock(return_value=subprocess.CompletedProcess([], 1))
    monkeypatch.setattr("subprocess.run", mock)
    _check_storage_writable()  # Should not raise


def test_check_docker_conflict_docker_not_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docker CLI not in PATH."""
    monkeypatch.setattr("shutil.which", lambda x: None if x == "docker" else "/usr/bin/podman")
    monkeypatch.delenv("PODMAN_IGNORE_DOCKER", raising=False)
    _check_docker_conflict()  # Should not raise


def test_check_docker_conflict_docker_present_but_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docker in PATH but PODMAN_IGNORE_DOCKER=1."""
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/docker" if x == "docker" else None)
    monkeypatch.setenv("PODMAN_IGNORE_DOCKER", "1")
    _check_docker_conflict()  # Should not raise


def test_check_docker_conflict_docker_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docker in PATH and not ignored → fail."""
    monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/docker" if x == "docker" else None)
    monkeypatch.delenv("PODMAN_IGNORE_DOCKER", raising=False)

    with patch("podman_runner.preflight._fail", side_effect=mock_fail) as fail_mock:
        with pytest.raises(RuntimeError, match="FAIL: 'docker' CLI found in PATH"):
            _check_docker_conflict()
    fail_mock.assert_called_once()


def test_fail_printer(capsys: pytest.CaptureFixture[str]) -> None:
    """_fail() prints formatted error and exits."""
    with patch.object(sys, "exit") as mock_exit:
        try:
            _fail("test error")
        except SystemExit:
            pass
    mock_exit.assert_called_once_with(1)
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert "test error" in captured.err
    assert "=" * 70 in captured.err
