#!/usr/bin/env python3
"""Wait for a service to be ready using a health command."""

from podman_runner import Container, ContainerConfig

config = ContainerConfig(
    name="health-example",
    image="docker.io/library/redis:alpine",
    health_cmd=["redis-cli", "ping"],
)

with Container(config) as c:
    print(f"Redis ready! ID: {c.container_id}")
    result = c.exec(["redis-cli", "SET", "demo", "podman-runner"])
    print(f"SET result: {result.stdout.strip()}")
