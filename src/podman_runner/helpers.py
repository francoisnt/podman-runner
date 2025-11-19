import shutil
import tempfile
import warnings
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


def get_podman_exe() -> str:
    """Find podman executable."""
    exe = shutil.which("podman")
    if not exe:
        raise RuntimeError("podman not found in PATH")

    return exe


@contextmanager
def tmp_path_factory_safe(prefix: str) -> Generator[Path, None, None]:
    """Context manager that creates a unique temporary directory with a prefix."""
    temp_dir: Path | None = None
    try:
        temp_dir_str = tempfile.mkdtemp(prefix=prefix)
        temp_dir = Path(temp_dir_str)

        if not temp_dir.is_dir():
            raise RuntimeError(f"Expected temp directory not created: {temp_dir}")

        yield temp_dir

    except (OSError, PermissionError) as e:
        raise RuntimeError(
            f"Failed to create temporary directory for tests: {e}\n"
            "Check disk space, permissions, and TMPDIR environment variable."
        ) from e

    finally:
        if temp_dir is not None and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                warnings.warn(
                    f"Failed to clean up test temp dir {temp_dir}: {e}",
                    ResourceWarning,
                    stacklevel=2,
                )
