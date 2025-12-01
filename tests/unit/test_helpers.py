# tests/unit/test_helpers_mocked.py
from __future__ import annotations

from unittest.mock import patch

import pytest


def test_get_podman_exe_found() -> None:
    """Test when podman is in PATH."""
    with patch("shutil.which", return_value="/usr/bin/podman"):
        from podman_runner.helpers import get_podman_exe

        assert get_podman_exe() == "/usr/bin/podman"


def test_get_podman_exe_not_found() -> None:
    """Test when podman is NOT in PATH."""
    with patch("shutil.which", return_value=None):
        from podman_runner.helpers import get_podman_exe

        with pytest.raises(RuntimeError, match="podman not found in PATH"):
            get_podman_exe()


def test_tmp_path_factory_safe_success() -> None:
    """Test tmp_path_factory_safe normal operation."""
    with patch("tempfile.mkdtemp", return_value="/mock/tmp_dir"):
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("shutil.rmtree") as rmtree_mock:
                    from podman_runner.helpers import tmp_path_factory_safe

                    with tmp_path_factory_safe("test") as path:
                        assert str(path) == "/mock/tmp_dir"
                    rmtree_mock.assert_called_once()


def test_tmp_path_factory_safe_mkdtemp_fails() -> None:
    """Test tmp_path_factory_safe when mkdtemp fails."""
    with patch("tempfile.mkdtemp", side_effect=OSError("Disk full")):
        from podman_runner.helpers import tmp_path_factory_safe

        with pytest.raises(RuntimeError, match="Failed to create temporary directory"):
            with tmp_path_factory_safe("test"):
                pass


def test_tmp_path_factory_safe_rmtree_fails() -> None:
    """Test tmp_path_factory_safe when rmtree fails."""
    with patch("tempfile.mkdtemp", return_value="/mock/tmp_dir"):
        with patch("pathlib.Path.is_dir", return_value=True):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("shutil.rmtree", side_effect=Exception("Permission denied")):
                    with patch("warnings.warn") as warn_mock:
                        from podman_runner.helpers import tmp_path_factory_safe

                        with tmp_path_factory_safe("test"):
                            pass
                        warn_mock.assert_called_once()
