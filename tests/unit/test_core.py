# tests/unit/test_core_mocked.py
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from podman_runner import Container, ContainerConfig


@pytest.fixture
def config(container_prefix: str) -> ContainerConfig:
    """Generate a container configuration."""
    return ContainerConfig(
        name=container_prefix + "unit",
        image="alpine:latest",
        command=["sleep", "10"],
    )


def test_build_run_cmd_no_options(container_prefix: str, config: ContainerConfig) -> None:
    c = Container(config)
    with patch.object(c, "_get_podman", return_value="podman"):
        cmd = c._build_run_cmd()
    expected = [
        "podman",
        "run",
        "-d",
        "--name",
        (container_prefix + "unit"),
        "alpine:latest",
        "sleep",
        "10",
    ]
    assert cmd == expected


def test_build_run_cmd_with_env(config: ContainerConfig) -> None:
    config.env = {"MY_VAR": "value1"}
    c = Container(config)
    with patch.object(c, "_get_podman", return_value="podman"):
        cmd = c._build_run_cmd()
    assert "-e" in cmd
    assert "MY_VAR=value1" in cmd


def test_build_run_cmd_with_multiple_env(config: ContainerConfig) -> None:
    config.env = {"VAR1": "val1", "VAR2": "val2"}
    c = Container(config)
    with patch.object(c, "_get_podman", return_value="podman"):
        cmd = c._build_run_cmd()
    assert cmd.count("-e") == 2
    assert "VAR1=val1" in cmd
    assert "VAR2=val2" in cmd


def test_build_run_cmd_with_init_scripts(
    config: ContainerConfig,
    tmp_init_dir: Path,
    init_script: Path,
) -> None:
    config.init_dir = "/init.d"
    config.init_scripts = [init_script]
    c = Container(config)
    with patch.object(c, "_get_podman", return_value="podman"):
        cmd = c._build_run_cmd()
    assert f"-v {init_script}:/init.d/00-setup.sh:ro" in " ".join(cmd)


def test_build_run_cmd_missing_init_script(
    config: ContainerConfig,
    tmp_init_dir: Path,
) -> None:
    config.init_dir = "/init.d"
    config.init_scripts = [Path("/nonexistent.sh")]
    c = Container(config)
    with patch.object(c, "_get_podman", return_value="podman"):
        with pytest.raises(FileNotFoundError):
            c._build_run_cmd()


def test_build_run_cmd_with_volumes(config: ContainerConfig) -> None:
    config.volumes = {Path("/host/path"): "/container/path"}
    c = Container(config)
    with patch.object(c, "_get_podman", return_value="podman"):
        cmd = c._build_run_cmd()
    assert "-v" in cmd
    assert f"{Path('/host/path')}:/container/path" in " ".join(cmd)


def test_container_start_stop(config: ContainerConfig) -> None:
    c = Container(config)

    run_mock = MagicMock(return_value=subprocess.CompletedProcess([], 0, stdout="abc123\n"))
    with (
        patch.object(c, "_get_podman", return_value="podman"),
        patch.object(c, "_build_run_cmd", return_value=["podman", "run", "..."]),
        patch("subprocess.run", run_mock),
        patch.object(c, "_wait_for_ready"),
    ):
        c.start()

    assert c.container_id == "abc123"
    run_mock.assert_called_once()

    stop_mock = MagicMock()
    rm_mock = MagicMock()
    with patch.object(c, "_get_podman", return_value="podman"), patch("subprocess.run") as sub_mock:
        sub_mock.side_effect = [stop_mock, rm_mock]
        c.stop()

    sub_mock.assert_has_calls(
        [
            call(["podman", "stop", "abc123"], capture_output=True, check=False, env=None),
            call(["podman", "rm", "-f", "abc123"], capture_output=True, check=False, env=None),
        ]
    )
    assert c.container_id is None


def test_container_start_fails_no_id(config: ContainerConfig) -> None:
    c = Container(config)
    with (
        patch.object(c, "_build_run_cmd", return_value=["podman", "run"]),
        patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="\n")),
    ):
        with pytest.raises(RuntimeError, match="no ID returned"):
            c.start()


def test_container_start_subprocess_error(config: ContainerConfig) -> None:
    c = Container(config)
    err = subprocess.CalledProcessError(1, ["podman"], stderr="boom")
    with (
        patch.object(c, "_build_run_cmd", return_value=["podman", "run"]),
        patch("subprocess.run", side_effect=err),
    ):
        with pytest.raises(RuntimeError, match="Failed to start container"):
            c.start()


def test_container_exec_success(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    proc = subprocess.CompletedProcess([], 0, stdout="hello\n")
    with (
        patch.object(c, "_get_podman", return_value="podman"),
        patch("subprocess.run", return_value=proc) as run_mock,
    ):
        result = c.exec(["echo", "hello"])
    run_mock.assert_called_once_with(
        ["podman", "exec", "abc123", "echo", "hello"],
        check=True,
        capture_output=True,
        text=True,
        env=None,
    )
    assert result == proc


def test_container_exec_failure(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    err = subprocess.CalledProcessError(1, ["podman"], output="out", stderr="err")
    with patch("subprocess.run", side_effect=err):
        with pytest.raises(RuntimeError, match="Command 'echo hello' failed"):
            c.exec(["echo", "hello"])


def test_container_logs_no_options(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    with (
        patch.object(c, "_get_podman", return_value="podman"),
        patch("subprocess.check_output", return_value="logline\n") as co_mock,
    ):
        logs = c.logs()
    co_mock.assert_called_once_with(["podman", "logs", "abc123"], text=True, env=None)
    assert logs == "logline\n"


def test_container_logs_with_options(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    with (
        patch.object(c, "_get_podman", return_value="podman"),
        patch("subprocess.check_output") as co_mock,
    ):
        c.logs(follow=True, tail=5)
    co_mock.assert_called_once_with(
        ["podman", "logs", "--tail", "5", "-f", "abc123"], text=True, env=None
    )


def test_container_check_status_running(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    mock = MagicMock(stdout="running")
    with patch("subprocess.run", return_value=mock):
        assert c.check_status() == "running"


def test_container_check_status_not_running(config: ContainerConfig) -> None:
    c = Container(config)
    with patch("subprocess.run", return_value=MagicMock(stdout="")):
        assert c.check_status() == "Not running"


def test_wait_for_ready_skipped_when_no_health_cmd(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    c.config.health_cmd = None
    c._wait_for_ready()  # no subprocess call


def test_wait_for_ready_success_first_try(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    c.config.health_cmd = ["true"]
    mock = MagicMock(return_value=subprocess.CompletedProcess([], 0))
    with patch("subprocess.run", mock), patch("time.time", side_effect=[0, 1]):
        c._wait_for_ready()
    mock.assert_called_once()


def test_wait_for_ready_timeout(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    c.config.health_cmd = ["false"]
    mock = MagicMock(return_value=subprocess.CompletedProcess([], 1))
    time_values = [0, *list(range(1, 32))]
    with (
        patch("subprocess.run", mock),
        patch("time.time", side_effect=time_values),
        patch("time.sleep"),
    ):
        with pytest.raises(TimeoutError, match="did not become ready in 30s"):
            c._wait_for_ready()


def test_context_manager(config: ContainerConfig) -> None:
    c = Container(config)
    with (
        patch.object(c, "start", return_value=c) as start_mock,
        patch.object(c, "stop") as stop_mock,
    ):
        with c:
            pass
    start_mock.assert_called_once()
    stop_mock.assert_called_once()


def test_del_stops_container(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    with patch.object(c, "stop") as stop_mock:
        c.__del__()
    stop_mock.assert_called_once()


def test_repr_running(config: ContainerConfig) -> None:
    c = Container(config)
    c.container_id = "abc123"
    assert repr(c) == f"<Container {c.config.name} [running] id=abc123>"


def test_repr_stopped(config: ContainerConfig) -> None:
    c = Container(config)
    assert repr(c) == f"<Container {c.config.name} [stopped] id=None>"


def test_check_status_execution(config: ContainerConfig) -> None:
    """Test that check_status actually executes its return statement."""
    c = Container(config)
    c.container_id = "abc123"
    # Mock subprocess.run to return a CompletedProcess, allowing the return result.stdout to execute
    result_mock = subprocess.CompletedProcess([], 0, stdout="running", stderr="")
    with patch("subprocess.run", return_value=result_mock) as run_mock:
        result = c.check_status()
    assert result == "running"
    run_mock.assert_called_once()


def test_context_manager_execution(config: ContainerConfig) -> None:
    """Test context manager with partial mocking to allow __exit__ execution."""
    c = Container(config)
    with (
        patch.object(c, "_get_podman", return_value="podman"),
        patch.object(c, "_build_run_cmd", return_value=["podman", "run", "..."]),
        patch.object(c, "_wait_for_ready"),
        patch("subprocess.run") as run_mock,
    ):
        # Mock the start process and configure side effects
        run_mock.side_effect = [
            subprocess.CompletedProcess([], 0, stdout="abc123\n"),  # Start container
            None,  # Stop container
            None,  # Remove container
        ]

        # This should actually call __enter__ and __exit__
        with c as container:
            assert container is c
            assert c.container_id == "abc123"

        assert c.container_id is None


def test_exec_raises_when_container_not_started(config: ContainerConfig) -> None:
    c = Container(config)
    # container_id is None → not started
    with pytest.raises(RuntimeError, match="Container not started"):
        c.exec(["echo", "hello"])


def test_logs_raises_when_container_not_started(config: ContainerConfig) -> None:
    """Ensure logs() raises when container_id is None."""
    c = Container(config)
    # container_id is None → container not started
    with pytest.raises(RuntimeError, match="Container not started"):
        c.logs()


def test_repr_execution_running(config: ContainerConfig) -> None:
    """Ensure __repr__ return statement executes when running."""
    c = Container(config)
    c.container_id = "test-123"
    result = repr(c)  # This should execute the return statement
    assert "[running]" in result and "id=test-123" in result
    assert result.startswith("<Container ") and result.endswith(">")


def test_start_successful_execution(config: ContainerConfig) -> None:
    """Test that the successful path in start() is covered, including setting container_id."""
    c = Container(config)
    result_mock = subprocess.CompletedProcess(
        ["podman", "run"], 0, stdout="success-123\n", stderr=""
    )
    with (
        patch.object(c, "_get_podman", return_value="podman"),
        patch.object(c, "_build_run_cmd", return_value=["podman", "run", "..."]),
        patch.object(c, "_wait_for_ready"),
        patch("subprocess.run", return_value=result_mock) as run_mock,
    ):
        result = c.start()
        assert result is c
        assert c.container_id == "success-123"
        run_mock.assert_called_once()
