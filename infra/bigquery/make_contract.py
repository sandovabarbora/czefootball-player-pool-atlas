"""Generate the model-output JSON contract (Task 21b).

Chapter IV's eight model-output JSONs (`data/processed/<nation>/*.json`)
aren't loaded into BigQuery by `load.sh` -- they're small, nested, one-off
model summaries, not flat tables -- but a downstream consumer (this
report's own `src/render.py`, or someone else's pipeline) still needs to
know their shape without reading the model code. This script introspects
each file's *top-level* keys and types and pairs them with a short,
hand-written note (what the field means and its unit, from the module that
writes it) and a one-line season/nation scope, then writes the combined
table to `infra/bigquery/model_outputs.md`.

The introspection (keys, python types, list/dict sizes) is generated fresh
from the JSON files on every run; the notes and scope lines are curated
here (a JSON value alone doesn't carry its own unit or the season it was
computed for) and should be updated by hand if a model's output JSON gains
or renames a top-level key.

usage: uv run python infra/bigquery/make_contract.py [--nation cze]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
OUT_PATH = Path(__file__).resolve().parent / "model_outputs.md"

# File -> one-line scope: which nation/season(s) the JSON describes. All
# eight are produced by one NATION-scoped pipeline run (see src/render.py's
# `load_data()`); most don't carry their own season field, so this is
# curated from each module's docstring rather than introspected.
FILE_SCOPE = {
    "league_strength": (
        "home nation's movers, fit across the full processed season history "
        "(`config/seasons.yaml::history`); the out-of-sample check (`oos`) "
        "scores only the metrics season."
    ),
    "model_comparison": (
        "every nationality in the corpus, rolling-origin over the seasons in "
        "`origins` (this run's processed history)."
    ),
    "series_model": (
        "home nation's Big-5 season counts (full history) plus the two "
        "`series_contrast` peer countries; the one forecast targets the "
        "season after `current`."
    ),
    "youth_panel": (
        "the home nation's configured peer countries, two seasons per "
        "country (`previous` and `metrics`; `current` is partial and left out)."
    ),
    "gap_decomposition": (
        "home nation vs. each `compare` peer, metrics-season snapshot "
        "(cross-sectional, not a time series)."
    ),
    "goalkeepers": (
        "home nation vs. peer countries' goalkeepers, metrics season."
    ),
    "squad_lens": (
        "the squads named in the file's own `event`/`season` fields (below)."
    ),
    "pathways": (
        "home nation's exports vs. peer countries, metrics season plus "
        "career-history fields (export age, youth exposure) drawn from the "
        "full processed history."
    ),
}

# File -> {top-level key: short note (what it is, its unit)}. Curated from
# the module that writes each file (src/league_strength.py,
# src/model_comparison.py, src/series_model.py, src/youth_panel.py,
# src/gap_decomposition.py, src/goalkeepers.py, src/squad_lens.py,
# src/pathways.py) and the render.py builder that reads it back.
KEY_NOTES = {
    "league_strength": {
        "leagues": "one row per league: m_L (median posterior multiplier, Premier-League = 1.0), its 90% HDI, transition count, UEFA multiplier for comparison.",
        "diagnostics": "sampler diagnostics: max R-hat, minimum bulk ESS, divergent-transition count.",
        "ppc": "posterior predictive check: observed vs. replicated share-of-zeros/mean/90th-percentile of non-penalty goals + assists per player-season.",
        "oos": "out-of-sample refit: predicts each mover's first metrics-season row after a league change against naive/UEFA-ratio/model baselines (log predictive density, MAE, units: the per-90 rate).",
        "spearman": "rank correlation (rho, p, n) between the model's league medians and the UEFA multipliers.",
        "disagreements": "leagues where the model's rank vs. UEFA's rank disagree most, with both ranks and both multipliers.",
        "fit": "fit metadata: row/player/season counts and wall-clock runtime in seconds.",
    },
    "model_comparison": {
        "target": "the predicted quantity, as a formula string (units: league-adjusted npG+A per 90).",
        "origins": "the target seasons the rolling-origin evaluation iterated over.",
        "rows": "one row per (model, origin): RMSE and MAE (units: target's own per-90 scale), plus 90% coverage for the Bayesian model.",
        "pooled": "one row per model: RMSE/MAE pooled across every origin.",
        "winner_pooled": "the model key with the lowest pooled RMSE.",
        "notes": "free-text caveats surfaced by the fit (e.g. an origin with an empty training set).",
    },
    "series_model": {
        "break": "home nation's change-point posterior: top candidate break seasons with their probability, the level-change factor's median/90% HDI, the random walk's innovation scale sigma.",
        "contrast": "the same change-point fit, one entry per `series_contrast` peer country code.",
        "backtest": "one-step-ahead rolling-origin backtest rows (origin, forecast season, actual, model median + 90% interval, naive baseline) plus a pooled summary (MAE, coverage90).",
        "forecast": "the one forward forecast (next season) per country: median and 90% interval, units: player count.",
        "diagnostics": "sampler diagnostics for the change-point fit: max R-hat, minimum bulk ESS, divergent-transition count.",
    },
    "youth_panel": {
        "panel": "one row per (country, season): U21 share of domestic-league minutes (x) and top-9 players per million (y), the two panel axes.",
        "means": "one row per country: the two-season average of the panel's x/y, the between-country regression's actual input rows.",
        "n": "country-mean rows the between-country fit used (can be below the peer count -- a peer whose top flight FBref doesn't track is absent).",
        "n_countries": "distinct countries represented in `panel`.",
        "seasons_used": "the season codes pooled into `panel` (previous, metrics).",
        "between": "the country-mean Bayesian regression: beta_per_10pp (median/lo/hi, units: top-9-players-per-million per 10pp of U21 share), r2, n.",
        "within": "country-random-intercept fit on the full two-season panel (a stated check, not the headline -- see src/youth_panel.py).",
        "ols": "plain pooled least-squares slope on the full two-season panel (statsmodels-free numpy polyfit), same units as `between`.",
        "ols_means": "OLS slope on the country-mean rows only (`means`), for comparison with `between`.",
        "home": "the home nation's country code.",
    },
    "gap_decomposition": {
        "panel": "the ridge regression's input rows: one per (country, channel) predictor value.",
        "coefficients": "the fitted ridge model's per-channel coefficients (units: per-capita players-per-million per unit of the channel).",
        "contrasts": "one entry per home-vs-peer contrast: per-channel contribution, share of the gap, 90% bootstrap interval, and the residual.",
        "n": "peer countries the ridge fit used.",
        "home": "the home nation's country code.",
        "ridge_alpha": "the ridge regularisation strength (alpha) used for the fit.",
        "min_gap_for_share": "the minimum |gap| below which a channel's percentage share is suppressed (avoids a near-zero-denominator blow-up).",
    },
    "goalkeepers": {
        "min_minutes": "inclusion floor for a goalkeeper-season, in minutes.",
        "phantom_minutes": "the K=10 shrinkage prior expressed in minutes (same construction as the outfield features).",
        "per_million": "one row per country: goalkeepers per million population, same construction as the outfield `per_capita.parquet`.",
        "home_rank": "the home nation's rank in `per_million`.",
        "n_peers": "peer countries compared.",
        "export_age": "home vs. peer median age-at-first-export for goalkeepers.",
        "club_tier": "one row per country: share of goalkeeper-seasons in each club-league tier (domestic/stepping-stone/top-9/other).",
        "club_strength_proxy": "the label of the club-strength measure `club_tier`/`production` are keyed on.",
        "production": "GA/90 and saves/90, shrunk and (GA/90) quality-adjusted, home vs. peers.",
        "cards": "the goalkeeper showcase rows (same shape as the outfield showcase).",
    },
    "squad_lens": {
        "event": "the named squad event (e.g. a World Cup) this file's `countries` rows describe.",
        "season": "the season the squad tables were fetched for.",
        "countries": "one row per country: n named, matched-to-corpus count, share by league tier, cohort counts, median minutes/multiplier.",
    },
    "pathways": {
        "youth_exposure": "one row per (league, country): total U21/U23 minutes share in that league -- 'how much of a country's youth football happens at home'.",
        "export_route": "one row per country: exports observed/recent, median export age, share by destination-league tier, share still active (not yet exported, 'censored').",
        "fare": "one row per country: median minutes-share and median share of club goals+assists among exported players -- 'how they fare abroad'.",
        "profile": "one row per (tier, position group): home vs. peer median quality-adjusted production, by the club-league tier the player plays in.",
        "destinations": "home nation's exports bucketed by destination-league tier, with the median destination-league multiplier and named examples per bucket.",
    },
}

MODEL_JSONS = [
    "league_strength", "model_comparison", "series_model", "youth_panel",
    "gap_decomposition", "goalkeepers", "squad_lens", "pathways",
]


def _type_name(value: Any) -> str:
    if isinstance(value, list):
        return f"list[{len(value)}]"
    if isinstance(value, dict):
        return f"dict[{len(value)}]"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if value is None:
        return "null"
    return "str"


def _value_hint(value: Any) -> str:
    """A short literal for a scalar; empty for a list/dict (its size is the type)."""
    if isinstance(value, (list, dict)):
        return ""
    return f"`{value}`"


def contract_for(name: str, data: dict[str, Any]) -> str:
    scope = FILE_SCOPE.get(name, "")
    notes = KEY_NOTES.get(name, {})
    lines = [f"## `{name}.json`", "", f"Scope: {scope}", "", "| Key | Type | Value | Note |", "|---|---|---|---|"]
    for key, value in data.items():
        lines.append(f"| `{key}` | {_type_name(value)} | {_value_hint(value)} | {notes.get(key, '')} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nation", default="cze", help="NATION the JSONs were built for (default: cze)")
    args = ap.parse_args()

    processed = ROOT_DIR / "data" / "processed" / args.nation
    sections = []
    for name in MODEL_JSONS:
        path = processed / f"{name}.json"
        if not path.exists():
            print(f"skip {name}: {path} not found")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        sections.append(contract_for(name, data))

    header = (
        "# Model-output JSON contract\n\n"
        "Generated by `infra/bigquery/make_contract.py` from "
        f"`data/processed/{args.nation}/*.json` (`NATION={args.nation}`). One "
        "section per model-output JSON `src/render.py` reads (`load_data()`): "
        "its top-level keys, their types (list/dict sizes shown, scalars shown "
        "with their current value), a short note on units, and the "
        "season/nation the file as a whole describes. These JSONs are nested "
        "model summaries, not flat tables -- `infra/bigquery/load.sh` does not "
        "load them; read them directly, or flatten the table(s) you need "
        "before loading.\n\n"
        "Re-run after any change to a model module's output shape; do not "
        "hand-edit below this line.\n\n"
    )
    OUT_PATH.write_text(header + "\n".join(sections), encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT_DIR)} ({len(sections)} JSONs)")


if __name__ == "__main__":
    main()
