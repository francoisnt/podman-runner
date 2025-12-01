from importlib.metadata import PackageNotFoundError, version

from .core import Container, ContainerConfig

try:
    __version__ = version("podman-runner")
except PackageNotFoundError:
    __version__ = "dev"

__all__ = ["Container", "ContainerConfig", "__version__"]
