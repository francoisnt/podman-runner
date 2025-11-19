"""Auto-mount init scripts into /docker-entrypoint-initdb.d-style directory."""

from pathlib import Path

from podman_runner import Container, ContainerConfig
from podman_runner.helpers import tmp_path_factory_safe

with tmp_path_factory_safe("scripts") as tmp_dir:
    init_dir = Path("/docker-entrypoint-initdb.d")
    scripts = [
        tmp_dir / "01-create-table.sql",
        tmp_dir / "02-seed-data.py",
    ]

    scripts[0].write_text("CREATE TABLE products (id SERIAL, name TEXT);\n", encoding="utf-8")
    scripts[1].write_text('print("Seeding data...")\n', encoding="utf-8")

    config = ContainerConfig(
        name="init-scripts-example",
        image="docker.io/library/postgres:16-alpine",
        init_dir=str(init_dir),
        init_scripts=scripts,
        env={"POSTGRES_PASSWORD": "secret"},
        health_cmd=[
            "sh",
            "-c",
            "pg_isready -U postgres && "
            "psql -U postgres -d postgres -c 'SELECT 1 FROM products LIMIT 1' >/dev/null",
        ],
    )

    with Container(config) as c:
        print(f"Postgres with init scripts started: {c.container_id}")
        result = c.exec(["psql", "-U", "postgres", "-c", "\\dt"])
        print(result.stdout)
