"""Central path and config loading for the pipeline.

All modules read paths and YAML configs through this module. Keeps absolute
paths and YAML parsing logic out of the fetch and feature modules.

Home nation: `NATION` (env var, default "cze") selects
`config/nations/<NATION>.yaml` (see `nation()`), which carries every
home-nation-specific value the pipeline used to hardcode (FBref country code,
population, peers, squads, ...). Every processed/output path is namespaced
under that nation's directory (`data/processed/<NATION>/`,
`outputs/<NATION>/`, `data/snapshot/<NATION>/`) so more than one nation's data
can live in the repo at once. `NATION=cze` (the default) reproduces the
pipeline's original, single-nation behaviour byte-for-byte.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml

# --- Home nation ---------------------------------------------------------

NATION: str = os.environ.get("NATION", "cze").lower()

# --- Paths -------------------------------------------------------------------

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_DIR: Path = ROOT_DIR / "config"
DATA_DIR: Path = ROOT_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed" / NATION
SEED_DIR: Path = DATA_DIR / "seed"
OUTPUTS_DIR: Path = ROOT_DIR / "outputs" / NATION
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


SNAPSHOT_DIR: Path = DATA_DIR / "snapshot" / NATION


def countries() -> dict[str, Any]:
    """Return the countries.yaml config dict (every peer country the pipeline
    knows about, across every home nation -- not nation-scoped)."""
    return load_yaml("countries.yaml")


def seasons() -> dict[str, str]:
    """Return the seasons.yaml config dict."""
    return load_yaml("seasons.yaml")


def features() -> dict[str, Any]:
    """Return the feature_definitions.yaml config dict."""
    return load_yaml("feature_definitions.yaml")


@cache
def nation() -> dict[str, Any]:
    """Return the selected home nation's config (`config/nations/<NATION>.yaml`).

    `NATION` (module-level, from the `NATION` env var) picks the file; every
    home-nation-specific value the pipeline used to hardcode lives here (FBref
    country code/page, population, peers, squads, ...) -- see
    config/nations/cze.yaml for the full shape.

    Raises:
        FileNotFoundError: if config/nations/<NATION>.yaml doesn't exist (a
            typo'd or unconfigured NATION) -- fails loudly rather than
            silently falling back to another nation's config.
    """
    path = CONFIG_DIR / "nations" / f"{NATION}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"No config for NATION={NATION!r}: {path} not found. "
            f"Add config/nations/{NATION}.yaml, or set NATION to a configured home nation."
        )
    return load_yaml(f"nations/{NATION}.yaml")


def squads() -> dict[str, Any]:
    """Return the home nation's squads config (`nation()["squads"]`; moved out
    of config/squads.yaml into config/nations/<NATION>.yaml in Task 14a)."""
    return nation()["squads"]


HOME: str = nation()["code"]


def nt_years() -> str:
    """'2024–26': span of the home nation's squad events (national-team flag window)."""
    years = [int(e["year"]) for e in squads()["events"]]
    return f"{min(years)}–{str(max(years))[-2:]}"


HEADLINE_LEAGUES: list[str] = list(leagues()["headline"])
DOMESTIC_LEAGUE: str = nation()["domestic_league"]
PEER_COUNTRIES: list[str] = list(nation()["cohort_countries"])


def peers_meta() -> dict[str, Any]:
    """countries.yaml's peer metadata (name, population_m), restricted to and
    ordered by the home nation's benchmark set (`PEER_COUNTRIES`).

    `countries.yaml::peers` is one shared registry across every home nation
    (Task 14a adds England's peers alongside Czechia's); callers that need
    "the peers to benchmark the home nation against" (the per-capita
    benchmark, cohort table, Big-5 series) go through this instead of
    `countries()["peers"]` directly, so a run for one nation never pulls in
    another nation's peers.
    """
    all_peers = countries()["peers"]
    return {c: all_peers[c] for c in PEER_COUNTRIES}


# --- Reproducibility ---------------------------------------------------------

RANDOM_SEED: int = 42
"""Pipeline-wide random seed. Set in every stochastic operation (KMeans, UMAP,
train/test splits if any). Documented in methodology section of the report."""
