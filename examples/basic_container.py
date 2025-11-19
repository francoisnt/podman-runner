"""Basic usage: start a container, run a command, read logs, stop."""

from podman_runner import Container, ContainerConfig

config = ContainerConfig(
    name="basic-example",
    image="docker.io/library/alpine:latest",
    command=["sleep", "infinity"],
)

with Container(config) as c:
    print(f"Container ID: {c.container_id}")

    result = c.exec(["echo", "Hello from podman-runner!"])
    print(f"Exec output: {result.stdout.strip()}")

    print("Logs:")
    print(c.logs(tail=5))
