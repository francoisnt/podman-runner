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
