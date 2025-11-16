from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

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
def tmp_path_factory_safe() -> Generator[Path, None, None]:
    """Create a unique temporary directory for the entire test session."""
    try:
        temp_dir_str = tempfile.mkdtemp(prefix="podman_py_test_")
        temp_dir = Path(temp_dir_str)
    except (OSError, PermissionError) as e:
        raise RuntimeError(
            f"Failed to create temporary directory for tests: {e}\n"
            "Check disk space, permissions, and TMPDIR environment variable."
        ) from e

    if not temp_dir.is_dir():
        raise RuntimeError(f"Expected temp directory not created: {temp_dir}")

    yield temp_dir

    #  Cleanup: Fail loudly if cleanup fails
    try:
        shutil.rmtree(temp_dir)
    except Exception as e:
        import warnings

        warnings.warn(
            f"Failed to clean up test temp dir {temp_dir}: {e}", ResourceWarning, stacklevel=2
        )


@pytest.fixture
def tmp_init_dir(tmp_path_factory_safe: Path) -> Path:
    """Create a temp dir for init scripts."""
    init_dir = tmp_path_factory_safe / "init.d"
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
def data_file(tmp_path_factory_safe: Path) -> Path:
    """Create a generic data file for volume tests."""
    file = tmp_path_factory_safe / "data.txt"
    file.write_text("hello from host\n")
    return file


@pytest.fixture(autouse=True, scope="session")
def cleanup_stale_containers(podman_exe: str) -> Generator[None, None, None]:
    yield
    # After all tests
    subprocess.run(
        [podman_exe, "rm", "-f", "--filter", f"name=^{TEST_CONTAINER_PREFIX}alpine-"],
        check=False,
    )
