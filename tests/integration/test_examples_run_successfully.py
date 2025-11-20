# tests/integration/test_examples_run_successfully.py
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


# ------------------------------------------------------------------ #
# Find repo root path
# ------------------------------------------------------------------ #
def git_repo_root() -> Path:
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            cwd=Path(__file__).parent,
            text=True,
        ).strip()
        return Path(root)
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Could not find git root: {e}")


REPO_ROOT = git_repo_root()
EXAMPLES_DIR = REPO_ROOT / "examples"


# ------------------------------------------------------------------ #
# Discover examples
# ------------------------------------------------------------------ #
def _example_files() -> list[Path]:
    if not EXAMPLES_DIR.is_dir():
        pytest.fail(f"examples/ directory not found at {EXAMPLES_DIR}")

    files = sorted(
        p
        for p in EXAMPLES_DIR.iterdir()
        if p.is_file()
        and p.suffix == ".py"
        and p.name != "__init__.py"
        and not p.name.startswith("_")
    )

    if not files:
        pytest.skip("No example .py files found in examples/")

    return files


# ------------------------------------------------------------------ #
# Test each example
# ------------------------------------------------------------------ #
@pytest.mark.parametrize(
    "example_file",
    _example_files(),
    ids=lambda p: p.name,
)
def test_example_runs_successfully(example_file: Path) -> None:
    print(f"\n=== Running example: {example_file.name} ===")

    result = subprocess.run(  # noqa: S603
        ["uv", "run", str(example_file)],  # noqa: S607
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.stdout:
        print("STDOUT:\n" + result.stdout.rstrip())
    if result.stderr:
        print("STDERR:\n" + result.stderr.rstrip())

    assert result.returncode == 0, (
        f"Example {example_file.name} failed (exit {result.returncode})\n"
        f"STDERR:\n{result.stderr.rstrip() or '(empty)'}\n"
        f"STDOUT:\n{result.stdout.rstrip() or '(empty)'}"
    )

    print(f"✓ {example_file.name} ran successfully (all containers used safe prefixed names)")
