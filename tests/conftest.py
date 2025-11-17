from __future__ import annotations

import shutil
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest

from podman_py.helpers import tmp_path_factory_safe

podman_path = shutil.which("podman")
if not podman_path:
    raise RuntimeError(
        "\n'podman' executable not found in PATH.\n"
        "Install Podman: https://podman.io/getting-started/install\n"
    )

# TEST CONSTANTS
PODMAN_EXE = podman_path
TEST_CONTAINER_PREFIX = "podman-py-integration-test"


@pytest.fixture(scope="session")
def podman_exe() -> str:
    """Expose PODMAN_EXE for testing session."""
    return PODMAN_EXE


@pytest.fixture(scope="session")
def container_prefix() -> str:
    """Expose the test container prefix for advanced use."""
    return TEST_CONTAINER_PREFIX


# Safe, Self-Contained Temp Path Fixtures
@pytest.fixture(scope="session")
def tmp_path() -> Generator[Path, None, None]:
    with tmp_path_factory_safe(prefix="podman_py_test_") as session_tmp_path:
        yield session_tmp_path


@pytest.fixture
def tmp_init_dir(tmp_path: Path) -> Path:
    """Create a temp dir for init scripts."""
    init_dir = tmp_path / "init.d"
    init_dir.mkdir(exist_ok=True)
    return init_dir


@pytest.fixture
def init_script(tmp_init_dir: Path) -> Path:
    """Create a simple init script."""
    script = tmp_init_dir / "setup.sh"
    script.write_text("#!/bin/sh\necho 'INIT OK' > /init-ok.txt\n")
    script.chmod(0o755)
    return script


@pytest.fixture
def bad_script(tmp_init_dir: Path) -> Path:
    """Create a failing init script."""
    script = tmp_init_dir / "fail.sh"
    script.write_text("#!/bin/sh\necho 'FAIL' >&2\nexit 1\n")
    script.chmod(0o755)
    return script


@pytest.fixture
def data_file(tmp_path: Path) -> Path:
    """Create a generic data file for volume tests."""
    file = tmp_path / "data.txt"
    file.write_text("hello from host\n")
    return file


@pytest.fixture(autouse=True, scope="session")
def cleanup_stale_containers(podman_exe: str) -> Generator[None, None, None]:
    yield
    # After all tests
    subprocess.run(  # noqa: S603
        [podman_exe, "rm", "-f", "--filter", f"name=^{TEST_CONTAINER_PREFIX}alpine-"],
        check=False,
    )
