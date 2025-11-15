import subprocess

import pytest

from podman_py import Container, ContainerConfig


def test_container_lifecycle() -> None:
    config = ContainerConfig(
        name="alpine-test", image="docker.io/library/alpine:latest", command=["sleep", "5"]
    )
    with Container(config) as c:
        assert c.container_id is not None
        assert "podman-test-alpine-test" in c.__repr__()

        # exec works
        result = c.exec(["echo", "hello"])
        assert result.stdout.strip() == "hello"

    # Container is stopped
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(
            ["podman", "ps", "--filter", f"id={c.container_id}"], check=True, capture_output=True
        )
