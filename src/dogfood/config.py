"""Runtime configuration, resolved once at import from the environment.

Every value has a working default so that `python -m dogfood` needs no
environment at all. docker-compose.yml sets the two that matter for a judge:
DOGFOOD_DB and DOGFOOD_DEV_TOKENS.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _find_fixtures() -> Path:
    """Locate fixtures.json the same way run.py does, plus the packaged copy.

    run.py searches CWD, its own directory, the config directory and
    <config>/data. Keeping the file at the repo root satisfies all four, so the
    repo root is checked first here too.
    """
    explicit = os.environ.get("DOGFOOD_FIXTURES")
    candidates = [Path(explicit)] if explicit else []
    candidates += [
        Path.cwd() / "fixtures.json",
        REPO_ROOT / "fixtures.json",
        REPO_ROOT / "data" / "fixtures.json",
        PACKAGE_DIR / "data" / "fixtures.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return REPO_ROOT / "fixtures.json"


@dataclass(frozen=True)
class Settings:
    db_path: Path
    fixtures_path: Path
    host: str
    port: int
    base_url: str

    # Deterministic seeded session tokens. Convenient (the committed
    # .dogfood.toml keeps working across restarts and on a stranger's laptop)
    # and a backdoor in production, so it is opt-in and announces itself
    # loudly at boot. See app.py:_startup_banner.
    dev_tokens: bool

    # Origin checking on writes. Disabled by default because the acceptance
    # suite sends no Origin header at all and a JSON-only API with an opaque
    # bearer credential is not CSRF-reachable from a browser form post.
    strict_origin: bool

    templates_dir: Path
    static_dir: Path


def load_settings() -> Settings:
    db_raw = os.environ.get("DOGFOOD_DB", str(REPO_ROOT / "var" / "dogfood.sqlite3"))
    port = int(os.environ.get("DOGFOOD_PORT", "8080"))
    host = os.environ.get("DOGFOOD_HOST", "0.0.0.0")
    return Settings(
        db_path=Path(db_raw),
        fixtures_path=_find_fixtures(),
        host=host,
        port=port,
        base_url=os.environ.get("DOGFOOD_BASE_URL", f"http://localhost:{port}"),
        dev_tokens=_env_bool("DOGFOOD_DEV_TOKENS", True),
        strict_origin=_env_bool("DOGFOOD_STRICT_ORIGIN", False),
        templates_dir=PACKAGE_DIR / "templates",
        static_dir=PACKAGE_DIR / "static",
    )


settings = load_settings()

# Gallery page size. Deliberately far above the 41-project fixture set: the
# acceptance suite greps page one of the gallery for fixture project titles, so
# page one has to be the whole fixture event at fixture scale.
GALLERY_PAGE_SIZE = 200

SCHEMA_VERSION = "1"
