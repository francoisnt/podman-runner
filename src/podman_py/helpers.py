import shutil


def get_podman_exe() -> str:
    """Find podman executable."""
    exe = shutil.which("podman")
    if not exe:
        raise RuntimeError("podman not found in PATH")

    return exe
