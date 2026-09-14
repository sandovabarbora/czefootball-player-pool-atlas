"""Central path and config loading for the pipeline.

All modules read paths and YAML configs through this module. Keeps absolute
paths and YAML parsing logic out of the fetch and feature modules.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

# --- Paths -------------------------------------------------------------------

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_DIR: Path = ROOT_DIR / "config"
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
SEED_DIR: Path = DATA_DIR / "seed"
OUTPUTS_DIR: Path = ROOT_DIR / "outputs"
TEMPLATES_DIR: Path = ROOT_DIR / "templates"


def ensure_dirs() -> None:
    """Create runtime directories that may not exist on a fresh clone."""
    for d in (RAW_DIR, PROCESSED_DIR, OUTPUTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# --- Config loading ----------------------------------------------------------


@cache
def load_yaml(name: str) -> dict[str, Any]:
    """Load a YAML config from the config/ directory.

    Args:
        name: filename including .yaml extension (e.g. "leagues.yaml")

    Returns:
        Parsed YAML as a dict.

    Raises:
        FileNotFoundError: if the config file is missing.
    """
    path = CONFIG_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def leagues() -> dict[str, Any]:
    """Return the leagues.yaml config dict."""
    return load_yaml("leagues.yaml")


def league_quality() -> dict[str, Any]:
    """Return the league_quality.yaml config dict.

    Note: config/league_quality.yaml is written by Task 5. Calling this
    before that task lands will raise FileNotFoundError.
    """
    return load_yaml("league_quality.yaml")


SNAPSHOT_DIR: Path = DATA_DIR / "snapshot"


def countries() -> dict[str, Any]:
    """Return the countries.yaml config dict."""
    return load_yaml("countries.yaml")


def seasons() -> dict[str, str]:
    """Return the seasons.yaml config dict."""
    return load_yaml("seasons.yaml")


def features() -> dict[str, Any]:
    """Return the feature_definitions.yaml config dict."""
    return load_yaml("feature_definitions.yaml")


def nt_years() -> str:
    """'2024–26': span of the squad events in config/squads.yaml (national-team flag window)."""
    years = [int(e["year"]) for e in load_yaml("squads.yaml")["events"]]
    return f"{min(years)}–{str(max(years))[-2:]}"


HEADLINE_LEAGUES: list[str] = list(leagues()["headline"])
DOMESTIC_LEAGUE: str = leagues()["domestic"]
PEER_COUNTRIES: list[str] = list(countries()["peers"])


# --- Reproducibility ---------------------------------------------------------

RANDOM_SEED: int = 42
"""Pipeline-wide random seed. Set in every stochastic operation (KMeans, UMAP,
train/test splits if any). Documented in methodology section of the report."""
