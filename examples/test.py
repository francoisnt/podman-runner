from src.podman_py.core import Container, ContainerConfig

config: ContainerConfig = ContainerConfig(
    name="test",
    image="docker.io/library/alpine",
    command=["sleep", "infinity"],
)

container = Container(config)

print(" ".join(container._build_run_cmd()))

container.start()
print(container.container_id)
result = container.exec(["echo", "hello"])
print(result.stdout)
print(result.stdout.strip())
print(result.returncode)
print(result.stdout.strip() == "hello")
print()
print(container.logs())
container.stop()
