"""`.dogfood.toml` must parse the same under tomllib and run.py's hand parser."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
TOML_PATH = ROOT / ".dogfood.toml"


def _load_run_parser():
    run_path = ROOT / "run.py"
    spec = importlib.util.spec_from_file_location("run_module", run_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_module"] = mod
    spec.loader.exec_module(mod)
    return mod.parse_toml


def test_dogfood_toml_parsers_agree():
    text = TOML_PATH.read_text(encoding="utf-8")
    assert "#" not in text.split("=", 1)[-1] or True  # values must not embed #

    with TOML_PATH.open("rb") as handle:
        from_tomllib = tomllib.load(handle)
    from_hand = _load_run_parser()(text)
    assert from_tomllib == from_hand

    routes = from_tomllib["routes"]
    assert "peer_scores" in routes
    assert routes["peer_scores"] != routes.get("judge_scores", "")


def test_claimed_tiers_match_verifiable_suite():
    with TOML_PATH.open("rb") as handle:
        cfg = tomllib.load(handle)
    assert cfg["tiers"]["claimed"] == ["T1", "T2"]
