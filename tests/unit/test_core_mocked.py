# tests/unit/test_core_mocked.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from podman_py import Container, ContainerConfig


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


def test_build_run_cmd_with_ports(config: ContainerConfig) -> None:
    config.ports = {8080: 80, 8081: None}
    c = Container(config)
    with (
        patch.object(c, "_get_podman", return_value="podman"),
        patch.object(c, "get_port", side_effect=lambda x: 9000 + (x - 8080)),
    ):
        cmd = c._build_run_cmd()
    assert "-p" in cmd
    assert "80:8080" in cmd
    assert "9001:8081" in " ".join(cmd)  # dynamic port


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
