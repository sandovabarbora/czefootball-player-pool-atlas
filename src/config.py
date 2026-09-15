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
    """Return the leagues.yaml config dict.

    `leagues.yaml`'s own `domestic:` key is a fetch-scope literal ("which
    league did Task 2 originally point the fetcher at"), still hardcoded to
    "CZE-First League" -- it predates Task 14a's nation configuration and
    was never updated to track it. Every caller that reads `leagues()
    ["domestic"]` actually wants "this run's home nation's domestic
    league" (`config.DOMESTIC_LEAGUE`, from `nation()["domestic_league"]`,
    correctly "ENG-Premier League" under NATION=eng): `src.pathways.
    destinations()`'s tier bucketing, its `domestic_multiplier` for the
    sideways definition, `src.render._country_sideways_share`'s slide-8
    column for the home nation's own row, and `src.fetch_fbref`'s
    fetch-list. Left as the stale literal, every one of those silently
    computed against Czechia's domestic league under NATION=eng: the
    England run's own top-flight players were never recognised as
    "domestic" at all (indistinguishable from `headline`, itself checked
    first) and every "sideways" share was measured against a 0.434
    multiplier instead of the Premier League's own 1.0 -- discovered via a
    6.25% "moved sideways" figure that made no sense once England's
    multiplier IS the highest in the table (nothing can be sideways from
    it under the wrong threshold, everything is under the right one).
    Overridden here, every call, on a *copy* of the cached dict -- `load_yaml`
    is `@cache`d, so mutating the dict it returns in place would leak this
    override into every other caller of `load_yaml("leagues.yaml")` for the
    rest of the process (observable as a false pass/fail in whichever test
    happens to call `load_yaml("leagues.yaml")` directly after `leagues()`
    has already run once, e.g. under NATION=eng: the override value differs
    from cze's, unlike under NATION=cze where it coincidentally matches the
    yaml literal already).
    """
    cfg = dict(load_yaml("leagues.yaml"))
    # nation()["domestic_league"], not the module-level DOMESTIC_LEAGUE
    # constant below -- this function is called at import time (by
    # HEADLINE_LEAGUES, below) before that constant exists.
    cfg["domestic"] = nation()["domestic_league"]
    return cfg


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


def cluster_labels() -> dict[str, Any]:
    """Return the cluster-labels config (Task 14b).

    `nation()["cluster_labels"]` may point a home nation at its own labels
    file (e.g. "config/cluster_labels.eng.yaml"); the default is the shared
    `config/cluster_labels.yaml` -- the cluster fit is on the all-nationality
    corpus, so the archetypes themselves are nation-independent and only a
    nation that wants a different editorial read needs an override.
    """
    rel = nation().get("cluster_labels", "cluster_labels.yaml")
    return load_yaml(rel.removeprefix("config/"))


def build_process() -> dict[str, Any]:
    """Return the build-process config (Task 21d): the "How this was built"
    diagram's stages and which model runs each one -- not nation-scoped
    (the agentic workflow that produced this report, same for every
    NATION). Numeric counts (tasks, reviews, rulings) are computed live at
    render time from `docs/superpowers/ledgers/*.md` and `tests/*.py`
    (`src.render`), not stored here.
    """
    return load_yaml("build_process.yaml")


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
