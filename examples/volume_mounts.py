"""Mount host directories and files into container."""

from podman_py import Container, ContainerConfig
from podman_py.helpers import tmp_path_factory_safe

with tmp_path_factory_safe("host_data") as host_root:
    host_data = host_root / "data"
    host_data.mkdir()
    (host_data / "input.txt").write_text("Hello from host directory!\n")
    (host_data / "secret.txt").write_text("s3cr3t\n")

    config_file = host_root / "app_config.json"
    config_file.write_text(
        '{"debug": true, "log_level": "info", "feature": "demo"}\n',
        encoding="utf-8",
    )

    config = ContainerConfig(
        name="volume-example",
        image="docker.io/library/alpine:latest",
        volumes={
            host_data: "/mnt/data",  # directory
            config_file: "/app/config.json:ro",  # read-only file
        },
        command=["sleep", "infinity"],
    )

    with Container(config) as c:
        print("Mounted directory listing:")
        ls_result = c.exec(["ls", "-l", "/mnt/data"])
        print(ls_result.stdout)

        print("Config file content:")
        cat_result = c.exec(["cat", "/app/config.json"])
        print(cat_result.stdout)

        # Directory is writable
        print("Before writing:")
        print(c.exec(["ls", "-l", "/mnt/data"]).stdout)
        c.exec(["sh", "-c", "echo 'written from container' > /mnt/data/from_container.txt"])
        print("After writing:")
        print(c.exec(["ls", "-l", "/mnt/data"]).stdout)
