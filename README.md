# podman-runner · Simple, safe Podman containers for Python tests and scripts

[![PyPI](https://img.shields.io/pypi/v/podman-runner?color=blue)](https://pypi.org/project/podman-runner/)
[![Podman-ready integration tests](https://img.shields.io/badge/integration%20tests-Podman--ready-brightgreen?style=flat&logo=podman&logoColor=white)](https://github.com/Francois-NT/podman-runner)

**podman-runner** brings the convenience of `testcontainers` to the rootless, daemonless world of **Podman**.

Start containers, wait for them to be ready, run commands, mount init scripts, map ports — all with a clean context-manager API and automatic cleanup.

Perfect for integration tests, local development scripts, or anything that needs a real database/service without Docker.

```python
from podman_runner import Container, ContainerConfig

with Container(
    ContainerConfig(
        name="my-postgres",
        image="docker.io/library/postgres:16-alpine",
        env={"POSTGRES_PASSWORD": "secret"},
        health_cmd=["pg_isready", "-U", "postgres"],
    )
) as pg:
    pg.exec(["psql", "-U", "postgres", "-c", "CREATE TABLE test(id serial);"])
    # → container stops and is removed automatically
```

## Features

- Context manager → guaranteed cleanup (even on exceptions or Ctrl-C)
- Automatic health-check polling (`health_cmd`)
- Smart port mapping (fixed or dynamic)
- Auto-mount init scripts into `/docker-entrypoint-initdb.d`-style directories
- Full volume and environment support
- Detailed pre-flight checks that catch the most common Podman pitfalls (WSL shm, Docker conflict, socket not running, Snap sandbox, etc.)
- 100% type-annotated, fully tested, zero external runtime dependencies

## Installation

Requires **Podman ≥ 4.0** and **Python ≥ 3.11**.

```bash
pip install podman-runner
```

Or with the fast `uv` tool (recommended):

```bash
uv pip install podman-runner
```

### Install Podman

```bash
# Ubuntu/Debian
sudo apt install podman

# Fedora
sudo dnf install podman

# macOS (via Homebrew)
brew install podman
podman machine init
podman machine start

# Windows (WSL2 recommended)
# See https://podman.io/getting-started/install.html
```

## Quick Examples

### Basic container

```python
from podman_runner import Container, ContainerConfig

with Container(ContainerConfig(
    name="demo",
    image="docker.io/library/alpine:latest",
    command=["sleep", "infinity"],
)) as c:
    print(c.exec(["echo", "Hello Podman!"]).stdout)
```

### PostgreSQL with init scripts

```python
from pathlib import Path
from podman_runner import Container, ContainerConfig

script = Path("01-setup.sql")
script.write_text("CREATE TABLE users(id serial PRIMARY KEY);\n")

with Container(ContainerConfig(
    name="pg-init",
    image="docker.io/library/postgres:16-alpine",
    env={"POSTGRES_PASSWORD": "secret"},
    init_dir="/docker-entrypoint-initdb.d",
    init_scripts=[script],
    health_cmd=["pg_isready", "-U", "postgres"],
)) as pg:
    result = pg.exec(["psql", "-U", "postgres", "-c", "\\dt"])
    print(result.stdout)
```

### Redis with health check

```python
with Container(ContainerConfig(
    name="redis",
    image="docker.io/library/redis:alpine",
    health_cmd=["redis-cli", "ping"],
)) as r:
    assert r.exec(["redis-cli", "PING"]).stdout.strip() == "PONG"
```

### Nginx with port mapping

```python
import requests

with Container(ContainerConfig(
    name="web",
    image="docker.io/library/nginx:alpine",
    ports={80: 8080},        # fixed host port
    # ports={443: None},     # auto-assign free host port
)) as web:
    host_port = web.get_port(80)
    resp = requests.get(f"http://localhost:{host_port}")
    assert resp.status_code == 200
```

See the [`examples/`](examples/) directory for more.

## API Reference

### `ContainerConfig`

| Parameter          | Type                          | Description                                                                 |
|--------------------|-------------------------------|-----------------------------------------------------------------------------|
| `name`             | `str`                         | Unique container name (required)                                            |
| `image`            | `str`                         | Image to run (required)                                                     |
| `command`          | `list[str] \| None`           | Override container command                                                  |
| `env`              | `dict[str, str] \| None`      | Environment variables                                                       |
| `ports`            | `dict[int, int \| None] \| None`| `{container_port: host_port_or_None}` — `None` = auto-assign            |
| `volumes`          | `dict[Path, str] \| None`     | Host path → container path (`:ro` suffix for read-only)                     |
| `init_dir`         | `str \| None`                 | Target init directory (e.g. `"/docker-entrypoint-initdb.d"`)               |
| `init_scripts`     | `list[Path] \| None`          | Scripts auto-mounted with `00-`, `01-` prefix and `:ro`                     |
| `health_cmd`       | `list[str] \| None`           | Command that exits 0 when service is ready                                  |
| `health_timeout`   | `int`                         | Seconds to wait for health check (default: 30)                              |
| `health_interval`  | `float`                       | Seconds between health checks (default: 1.0)                                |

### `Container`

| Method                        | Description                                                      |
|-------------------------------|------------------------------------------------------------------|
| `container_id: str \| None`   | Podman container ID after start                                  |
| `start()`                     | Start container (called automatically in context manager)       |
| `stop()`                      | Stop and remove container                                        |
| `exec(cmd: list[str])`        | Run command inside container → `CompletedProcess`                |
| `logs(tail: int \| None = None, follow=False)` | Get container logs                          |
| `get_port(internal: int)`     | Return host port mapped to container port (or `None`)            |
| `check_status()`              | Return current status string (`"running"`, `"exited"`, etc.)     |

## Development

```bash
git clone https://github.com/Francois-NT/podman-runner.git
cd podman-runner

# Install with dev dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run task unittest        # fast unit tests
uv run task integration     # requires running Podman socket
```

## Why Podman instead of Docker?

- No daemon → works great in CI and restricted environments
- Rootless by default
- Full Docker CLI compatibility
- Native on Linux, excellent macOS/Windows support via `podman machine`

## Similar Projects

| Project                     | Docker | Podman | Context Manager | Init Script Support | Health Polling |
|-----------------------------|--------|--------|------------------|----------------------|----------------|
| testcontainers-python      | Yes    | No     | Yes              | No                   | Yes            |
| podman-compose              | No     | Yes    | No               | No                   | No             |
| podman-py                   | No     | Yes    | No               | No                   | No             |
| **podman-runner**           | No     | Yes    | Yes              | Yes                  | Yes            |

## License

MIT © François Naggar-Tremblay

---

**Happy testing with real, rootless containers!**