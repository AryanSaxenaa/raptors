"""CLI: `python -m dogfood [serve|init|export-openapi|reset]`.

`serve` is the default and is what the container runs. `init` is the seeding
step on its own, so the container entrypoint can prove the database is loaded
before anything binds a port.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .app import bootstrap, create_app, serve
from .config import settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m dogfood")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the portal (default)")
    sub.add_parser("init", help="create the schema and load fixtures, then exit")
    sub.add_parser("reset", help="delete the database file, then re-seed")
    export = sub.add_parser("export-openapi", help="write the OpenAPI document to a file")
    export.add_argument("path", nargs="?", default="docs/openapi.json")

    args = parser.parse_args(argv)
    command = args.command or "serve"

    if command == "init":
        summary = bootstrap(
            settings.db_path, settings.fixtures_path, dev_tokens=settings.dev_tokens
        )
        print(json.dumps(summary, indent=2))
        return 0 if summary.get("seeded") else 1

    if command == "reset":
        for suffix in ("", "-wal", "-shm"):
            path = Path(str(settings.db_path) + suffix)
            if path.exists():
                path.unlink()
        summary = bootstrap(
            settings.db_path, settings.fixtures_path, dev_tokens=settings.dev_tokens
        )
        print(json.dumps(summary.get("counts", {}), indent=2))
        return 0

    if command == "export-openapi":
        app = create_app(run_bootstrap=False)
        target = Path(args.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {target}")
        return 0

    return serve()


if __name__ == "__main__":
    sys.exit(main())
