# podman-runner · Real, rootless Podman containers for Python tests & scripts

[![PyPI version](https://img.shields.io/pypi/v/podman-runner?color=%2334D058&logo=pypi&logoColor=white)](https://pypi.org/project/podman-runner/)
[![Python versions](https://img.shields.io/pypi/pyversions/podman-runner.svg)](https://pypi.org/project/podman-runner/)
[![CI](https://img.shields.io/github/actions/workflow/status/Francois-NT/podman-runner/ci.yml?branch=main&label=tests&logo=github)](https://github.com/Francois-NT/podman-runner/actions)
[![Coverage](https://img.shields.io/codecov/c/gh/Francois-NT/podman-runner?logo=codecov)](https://codecov.io/gh/Francois-NT/podman-runner)
[![License: MIT](https://img.shields.io/github/license/Francois-NT/podman-runner?color=blue)](#license)

[![PyPI version](https://img.shields.io/pypi/v/podman-runner?color=%2334D058&logo=pypi&logoColor=white)](https://pypi.org/project/podman-runner/)
[![Python versions](https://img.shields.io/pypi/pyversions/podman-runner.svg)](https://pypi.org/project/pypi.org/project/podman-runner/)
[![License: MIT](https://img.shields.io/github/license/Francois-NT/podman-runner?color=blue)](#license)


**The `testcontainers-python` experience — but daemonless, rootless, and built for Podman.**

Spin up real databases, caches, and services with automatic health checks, port mapping, init scripts, and guaranteed cleanup — even on exceptions or Ctrl+C.

Perfect for integration tests, local dev scripts, or any Python project that needs real services without Docker.

```python
from podman_runner import Container, ContainerConfig

with Container(
    ContainerConfig(
        name="my-pg",
        image="docker.io/library/postgres:16-alpine",
        env={"POSTGRES_PASSWORD": "secret"},
        health_cmd=["pg_isready", "-U", "postgres"],
    )
) as pg:
    pg.exec(["psql", "-U", "postgres", "-c", "CREATE TABLE demo(id serial);"])
    # Container is removed automatically when block exits
```

## Why podman-runner?

| Feature                        | podman-runner | testcontainers-python | podman-py | Docker required? |
|-------------------------------|---------------|------------------------|----------|------------------|
| Rootless / daemonless         | Yes           | No                     | Yes      | No               |
| Context manager + auto cleanup| Yes           | Yes                    | No       | —                |
| Health-check polling          | Yes           | Yes                    | No       | —                |
| Init script auto-mounting     | Yes           | No                     | No       | —                |
| Dynamic & fixed port mapping  | Yes           | Yes                    | Partial  | —                |
| Works in restricted CI        | Yes           | Rarely                 | Yes      | No               |
| Zero runtime dependencies     | Yes           | No (heavy)             | Yes      | —                |
| Smart preflight checks        | Yes           | No                     | No       | —                |

## Installation

Requires **Podman ≥ 4.0** and **Python ≥ 3.11**.

```bash
# Recommended — lightning fast
uv pip install podman-runner

# or classic pip
pip install podman-runner
```

### Install Podman (one-liner per platform)

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install podman -y

# Fedora / RHEL
sudo dnf install podman -y

# macOS (Apple Silicon & Intel)
brew install podman && podman machine init && podman machine start

# Windows (WSL2 recommended)
# https://podman.io/docs/installation#windows
```

## 30-Second Quick Start

```python
from podman_runner import Container, ContainerConfig

with Container(
    ContainerConfig(
        name="pg-demo",
        image="docker.io/library/postgres:16-alpine",
        env={"POSTGRES_PASSWORD": "dev"},
        health_cmd=["pg_isready", "-U", "postgres"],
        ports={5432: None},  # auto-map to free host port
    )
) as pg:
    print(f"Postgres ready at localhost:{pg.get_port(5432)}")
```

## Real-World Examples

### Redis with health check

```python
with Container(ContainerConfig(
    name="redis",
    image="docker.io/library/redis:alpine",
    health_cmd=["redis-cli", "ping"],
)) as r:
    assert r.exec(["redis-cli", "PING"]).stdout.strip() == "PONG"
```

### Nginx — accessible from host

```python
import requests

with Container(ContainerConfig(
    name="web",
    image="docker.io/library/nginx:alpine",
    ports={80: 8080},
)) as web:
    resp = requests.get("http://localhost:8080")
    assert resp.status_code == 200
```

### Postgres + init scripts (official entrypoint style)

```python
from pathlib import Path

Path("01-init.sql").write_text("CREATE TABLE users(id serial PRIMARY KEY);\n")

with Container(ContainerConfig(
    name="pg-init",
    image="docker.io/library/postgres:16-alpine",
    env={"POSTGRES_PASSWORD": "secret"},
    init_dir="/docker-entrypoint-initdb.d",
    init_scripts=[Path("01-init.sql")],
    health_cmd=["pg_isready", "-U", "postgres"],
)) as pg:
    print(pg.exec(["psql", "-U", "postgres", "-c", "\\dt"]).stdout)
```

More examples → [`examples/`](examples/)

## API Reference

### `ContainerConfig`

| Parameter           | Type                          | Description |
|---------------------|-------------------------------|-----------|
| `name`              | `str`                         | Required — unique container name |
| `image`             | `str`                         | Required — image to run |
| `command`           | `list[str] \| None`           | Override entrypoint |
| `env`               | `dict[str, str] \| None`      | Environment variables |
| `ports`             | `dict[int, int \| None] \| None`| `{container_port: host_port_or_None}` |
| `volumes`           | `dict[Path, str] \| None`      | Host → container path (`:ro` for read-only) |
| `init_dir`          | `str \| None`                  | e.g. `"/docker-entrypoint-initdb.d"` |
| `init_scripts`      | `list[Path] \| None`           | Auto-mounted with `00-`, `01-` prefix |
| `health_cmd`        | `list[str] \| None`           | Command that exits 0 when ready |
| `health_timeout`    | `int` (default 30)            | Seconds to wait |
| `podman_host`       | `str \| None`                  | Remote Podman socket |

### `Container` methods

| Method                  | Returns                    | Description |
|-------------------------|----------------------------|-----------|
| `get_port(internal)`    | `int \| None`               | Host port for container port |
| `exec(["cmd", ...])`    | `CompletedProcess[str]`    | Run command inside container |
| `logs(tail=N)`          | `str`                      | Container logs |
| `check_status()`        | `str`                      | `"running"`, `"exited"`, etc. |
| `stop()`                | —                          | Stop + remove |

## Smart Preflight Checks

On first import, `podman-runner` runs comprehensive checks and fails early with clear fixes:

- Podman ≥ 4.0 in PATH
- Socket running
- Storage writable
- Docker CLI conflict
- WSL2 `/dev/shm` size
- Snap sandbox detection

No more cryptic crashes — you get helpful messages instead.

## Development & Contributing

```bash
git clone https://github.com/Francois-NT/podman-runner.git
cd podman-runner

# Blazing fast setup
uv sync --all-extras

# Hooks + lint + tests
uv run pre-commit install
uv run pre-commit run --all-files
uv run task test
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) — contributions very welcome!

## Related Projects

- [`testcontainers-python`](https://github.com/testcontainers/testcontainers-python) – Docker-only
- [`podman-py`](https://github.com/containers/podman-py) – raw bindings
- [`podman-compose`](https://github.com/containers/podman-compose) – YAML orchestration

**Only `podman-runner` gives you testcontainers-style ergonomics with full Podman rootless power.**

## License

[MIT © François Naggar-Tremblay](LICENSE)

---

**Happy testing with real, rootless containers!**