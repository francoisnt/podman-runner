import subprocess
from collections.abc import Generator
from functools import partial

import pytest

from podman_runner import Container, ContainerConfig


@pytest.fixture(scope="class")
def podman_container(
    container_prefix: str, request: pytest.FixtureRequest
) -> Generator[Container, None, None]:
    """One container per test class, unique across workers."""
    # Use class name + random suffix
    class_name = request.cls.__name__.lower().replace("test", "")
    unique_id = __import__("uuid").uuid4().hex[:8]

    name = f"{container_prefix}-{class_name}-{unique_id}"

    config = ContainerConfig(
        name=name,
        image="docker.io/library/alpine",
        command=["sleep", "infinity"],
    )
    container = Container(config)
    with container:
        yield container


class TestAlpineContainerBasics:
    def test_container_starts_and_has_id(self, podman_container: Container) -> None:
        """Ensure container is started and has a valid container ID."""
        assert podman_container.container_id is not None

    def test_container_repr_includes_name(
        self, podman_container: Container, container_prefix: str
    ) -> None:
        """Check that the container's repr includes its name."""
        assert podman_container.config.name in podman_container.__repr__()

    def test_container_can_exec_command(self, podman_container: Container) -> None:
        """Verify the container can execute commands and return output."""
        result = podman_container.exec(["echo", "hello"])
        assert result.stdout.strip() == "hello"
        assert result.returncode == 0


class TestDoubleStart:
    def test_container_double_start(self, podman_container: Container) -> None:
        """Test that calling start again creates a new container instance."""
        assert podman_container.container_id is not None
        first_id = podman_container.container_id
        podman_container.start()  # should stop old one
        assert podman_container.container_id is not None
        assert podman_container.container_id != first_id


class TestLyfecycle:
    def test_container_stop(self, podman_container: Container, podman_exe: str) -> None:
        """Test that stopping the container removes it from podman ps --all."""
        assert podman_container.container_id is not None
        c_id: str = podman_container.container_id

        check = partial(
            subprocess.run,
            [podman_exe, "ps", "--all", "--filter", f"id={c_id}", "--quiet"],
            capture_output=True,
            text=True,
            check=False,
        )

        result_1 = check()
        assert result_1.stdout.strip() != ""

        podman_container.stop()  # should stop old one

        result_2 = check()
        assert result_2.stdout.strip() == ""
