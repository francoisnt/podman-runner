# tests/unit/test_init.py
from podman_runner import __version__


def test_version_exists() -> None:
    """Test that __version__ is set."""
    assert isinstance(__version__, str)
    assert __version__
