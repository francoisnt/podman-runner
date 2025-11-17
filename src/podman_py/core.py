from __future__ import annotations

import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .helpers import get_podman_exe
from .preflight import run_preflight_checks

__all__ = ["Container", "ContainerConfig"]


# Run preflight checks on import
run_preflight_checks()


@dataclass
class ContainerConfig:
    """Generic container configuration.

    Key features:
    - ``init_dir`` + ``init_scripts`` → auto-mounted to official init directory
      with ``00-``, ``01-`` prefix for correct execution order.
    - ``volumes`` → arbitrary additional mounts
    - ``ports`` → auto-bind if ``None``
    - ``health_cmd`` → wait-for-ready
    """

    name: str
    image: str
    ports: dict[int, int | None] | None = None  # {internal: host | None}
    env: dict[str, str] | None = None
    init_dir: str | None = None  # e.g. "/docker-entrypoint-initdb.d"
    init_scripts: list[Path] | None = None  # auto-named 00-, 01-
    volumes: dict[Path, str] | None = None  # host → container
    health_cmd: list[str] | None = None
    command: list[str] | None = None


class Container:
    """Lifecycle-managed Podman container with context manager support."""

    _podman_exe: str | None = None

    def __init__(self, config: ContainerConfig):
        """Initialize a container."""
        self.config = config
        self.container_id: str | None = None
        self._host_ports: dict[int, int] = {}

    # --------------------------------------------------------------------- #
    # Podman executable
    # --------------------------------------------------------------------- #
    def _get_podman(self) -> str:
        if Container._podman_exe is None:
            exe = get_podman_exe()
            Container._podman_exe = exe
        return Container._podman_exe

    # --------------------------------------------------------------------- #
    # Dynamic port binding
    # --------------------------------------------------------------------- #
    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            _, port = s.getsockname()
            return int(port)

    def get_port(self, internal_port: int) -> int:
        """Return host port mapped to internal port."""
        if internal_port not in self._host_ports:
            host_port = (self.config.ports or {}).get(internal_port)
            if host_port is None:
                host_port = self._find_free_port()
            self._host_ports[internal_port] = host_port
        return self._host_ports[internal_port]

    # --------------------------------------------------------------------- #
    # Build podman run command
    # --------------------------------------------------------------------- #
    def _build_run_cmd(self) -> list[str]:
        cmd = [
            self._get_podman(),
            "run",
            "-d",
            "--name",
            self.config.name,
        ]

        # Ports
        for internal, host in (self.config.ports or {}).items():
            host_port = host if host is not None else self.get_port(internal)
            cmd += ["-p", f"{host_port}:{internal}"]

        # Environment
        for k, v in (self.config.env or {}).items():
            cmd += ["-e", f"{k}={v}"]

        # === INIT SCRIPTS: auto-mount to init_dir with 00-, 01- prefix ===
        if self.config.init_dir and self.config.init_scripts:
            init_dir = self.config.init_dir.rstrip("/")
            # Sort for deterministic order
            for i, script_path in enumerate(sorted(self.config.init_scripts)):
                if not script_path.is_file():
                    raise FileNotFoundError(f"Init script not found: {script_path}")
                filename = f"{i:02d}-{script_path.name}"
                container_path = f"{init_dir}/{filename}"
                cmd += ["-v", f"{script_path}:{container_path}:ro"]

        # === GENERAL VOLUMES ===
        for host_path, container_path in (self.config.volumes or {}).items():
            cmd += ["-v", f"{host_path}:{container_path}"]

        # Image
        cmd.append(self.config.image)

        # Command override
        if self.config.command:
            cmd += [*self.config.command]

        return cmd

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #
    def start(self) -> Container:
        """Start container and wait for health check."""
        self.stop()
        try:
            result = subprocess.run(  # noqa: S603
                self._build_run_cmd(),
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to start container: {e.stderr}") from e

        self.container_id = result.stdout.strip()

        if not self.container_id:
            raise RuntimeError("Container started but no ID returned")

        self._wait_for_ready()
        return self

    def check_status(self) -> str:
        """Check container status."""
        if not self.container_id:
            return "Not running"

        result = subprocess.run(  # noqa: S603
            [self._get_podman(), "inspect", self.container_id, "--format", "'{{.State.Status}}'"],
            capture_output=True,
            text=True,
        )

        return result.stdout

    def _wait_for_ready(self) -> None:
        """Poll health_cmd until success or timeout."""
        if not self.config.health_cmd or not self.container_id:
            return
        deadline = time.time() + 30
        while time.time() < deadline:
            result = subprocess.run(  # noqa: S603
                [self._get_podman(), "exec", self.container_id, *self.config.health_cmd],
                capture_output=True,
            )
            if result.returncode == 0:
                return
            time.sleep(1)
        raise TimeoutError(f"Container {self.config.name} did not become ready in 30s")

    def stop(self) -> None:
        """Stop and remove container."""
        if not self.container_id:
            return
        subprocess.run(  # noqa: S603
            [self._get_podman(), "stop", self.container_id], capture_output=True, check=False
        )
        subprocess.run(  # noqa: S603
            [self._get_podman(), "rm", "-f", self.container_id], capture_output=True, check=False
        )
        self.container_id = None

    def exec(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        """Run command inside container."""
        if not self.container_id:
            raise RuntimeError("Container not started")
        try:
            return subprocess.run(  # noqa: S603
                [self._get_podman(), "exec", self.container_id, *cmd],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Command {' '.join(cmd)!r} failed in container {self.config.name}:\n"
                f"stdout: {e.stdout}\nstderr: {e.stderr}"
            ) from e

    def logs(self, follow: bool = False, tail: int | None = None) -> str:
        """Get the container logs."""
        if not self.container_id:
            raise RuntimeError("Container not started")
        cmd = [self._get_podman(), "logs"]
        if tail:
            cmd += ["--tail", str(tail)]
        if follow:
            cmd += ["-f"]
        cmd += [self.container_id]
        return subprocess.check_output(cmd, text=True)  # noqa: S603

    # --------------------------------------------------------------------- #
    # Context manager
    # --------------------------------------------------------------------- #
    def __enter__(self) -> Container:
        """Enter the runtime context for the container.

        Called when entering a ``with`` block.
        """
        return self.start()

    def __exit__(self, *args: Any) -> None:
        """Exit the runtime context and clean up the container.

        Called when leaving a ``with`` block.
        """
        self.stop()

    def __del__(self) -> None:
        """Make sure to stop the container on cleanup."""
        if self.container_id:
            self.stop()

    def __repr__(self) -> str:
        """Return a string representation of the container."""
        status = "running" if self.container_id else "stopped"
        return f"<Container {self.config.name} [{status}] id={self.container_id}>"
