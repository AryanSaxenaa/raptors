"""Shared fixtures for in-process HTTP tests."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from dogfood.app import bootstrap, create_app
from dogfood.config import REPO_ROOT, Settings
from dogfood.db import connect

FIXTURES_PATH = REPO_ROOT / "fixtures.json"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    db_path = tmp_path / "pytest.sqlite3"
    return Settings(
        db_path=db_path,
        fixtures_path=FIXTURES_PATH,
        host="127.0.0.1",
        port=8080,
        base_url="http://127.0.0.1:8080",
        dev_tokens=True,
        strict_origin=False,
        templates_dir=REPO_ROOT / "src" / "dogfood" / "templates",
        static_dir=REPO_ROOT / "src" / "dogfood" / "static",
    )


@pytest.fixture
def seeded_conn(settings):
    """SQLite connection after schema + fixtures (no HTTP app)."""
    bootstrap(settings.db_path, FIXTURES_PATH, dev_tokens=True)
    conn = connect(settings.db_path)
    yield conn
    conn.close()


@pytest.fixture
def app(settings: Settings) -> Generator:
    os.environ["DOGFOOD_DB"] = str(settings.db_path)
    os.environ["DOGFOOD_DEV_TOKENS"] = "1"
    summary = bootstrap(settings.db_path, settings.fixtures_path, dev_tokens=True)
    assert summary.get("seeded"), summary
    application = create_app(settings, run_bootstrap=False)
    application.state.quiet = True
    application.state.seed_summary = summary
    yield application


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client
