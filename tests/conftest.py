import shutil
from pathlib import Path

import pytest

# Skip all tests if podman is not available
pytestmark = pytest.mark.skipif(not shutil.which("podman"), reason="podman executable not found")


@pytest.fixture
def tmp_init_dir(tmp_path: Path) -> Path:
    """Create a temp dir for init scripts."""
    return tmp_path / "init.d"


@pytest.fixture
def init_script(tmp_init_dir: Path) -> Path:
    """Create a simple init script."""
    script = tmp_init_dir / "setup.sh"
    script.write_text("#!/bin/sh\necho 'INIT OK' > /init-ok.txt\n")
    script.chmod(0o755)
    return script
