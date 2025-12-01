# Contributing to podman-runner

Thanks for your interest in contributing! This guide will get you up and running in minutes.

## Prerequisites

- **Podman** ≥ 4.0 – [Installation guide](https://podman.io/getting-started/install.html)
- **uv** – modern Python project & environment manager

```bash
# Install uv (recommended one-liner)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use pipx, brew, etc.
# pipx install uv
# brew install uv
```

## Quick Start Checklist

```bash
# 1. Clone the repository
git clone https://github.com/Francois-NT/podman-runner.git
cd podman-runner

# 2. Install dependencies + dev extras
uv sync --all-extras

# 3. Install pre-commit hooks
uv run pre-commit install

# 4. Verify setup (lint + tests)
uv run pre-commit run --all-files   # runs ruff, mypy, unit tests
uv run mypy                         # type checking
uv run task unit                    # fast unit tests
uv run task integration             # requires running Podman socket
```
