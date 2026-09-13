"""Sensitivity analysis for league quality multipliers (football corpus).

Locked decision: show how the quality-adjusted ranking of Czech-eligible
players in the metrics season changes when league multipliers are
perturbed. The metric is npg_p90_quality + ast_p90_quality, recomputed from
each player's `npg_p90_shrunk` / `ast_p90_shrunk` columns times the
scenario's (possibly perturbed) multiplier for that player's league --
not the canonical, baseline-multiplier `*_quality` columns already on the
features frame.

Scenarios: baseline, each individual league +/-20%, and every league
+/-20% at once (config/league_quality.yaml's `multipliers`).

Position groups (FW/MF/DF) score on very different scales for this metric
(forwards post far higher npG+A per 90 than defenders), so a single
cross-position ranking would just reproduce the position order every time.
Instead, ranking is done *within* each position group, and the three
ranked frames are then pooled into one sensitivity.parquet -- "top-10"
below means the union of each group's own top-10 (up to 30 players), and
"top-20" the union of each group's own top-20 (up to 60 players), not one
cross-position top-10/20 list.

Before ranking, `main()` runs `utils.collapse_player_seasons` on each
position group's metrics-season/Czech-eligible frame: a player transferred
mid-season has two rows in `fbref_players.parquet` (one per club) that
survive into `features_*.parquet`, and left uncollapsed those two rows
would (a) let one player occupy two ranks in the same group and (b) turn
`churn()`'s baseline/scenario merge into a cartesian join on the repeated
`player_key`, inflating `mean_delta_rank_top20`. The collapse sums `min`
and takes a minutes-weighted mean of `npg_p90_shrunk`/`ast_p90_shrunk`
across the duplicate rows before the scenario multiplier is even applied.
`churn()` additionally dedupes defensively (keeping each player's best
rank) before comparing, in case a caller passes in an unpooled or
uncollapsed frame.

Output: data/processed/sensitivity.parquet, columns
    scenario, description, top10_overlap, top10_churn, mean_delta_rank_top20
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from src import config
from src.utils import collapse_player_seasons, read_parquet, write_parquet

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Scenario:
    name: str
    multiplier_overrides: dict[str, float]
    description: str


def _build_scenarios(baseline: dict[str, float]) -> list[Scenario]:
    out = [Scenario("baseline", dict(baseline), "current multipliers from config/league_quality.yaml")]
    for league, mult in baseline.items():
        m_lo = dict(baseline)
        m_lo[league] = round(mult * 0.8, 4)
        out.append(Scenario(f"{league}_minus20", m_lo, f"{league} multiplier -20%"))
        m_hi = dict(baseline)
        m_hi[league] = round(mult * 1.2, 4)
        out.append(Scenario(f"{league}_plus20", m_hi, f"{league} multiplier +20%"))
    out.append(Scenario("all_minus20", {k: round(v * 0.8, 4) for k, v in baseline.items()},
                         "every league multiplier -20%"))
    out.append(Scenario("all_plus20", {k: round(v * 1.2, 4) for k, v in baseline.items()},
                         "every league multiplier +20%"))
    return out


def _rank_group(df: pd.DataFrame, multipliers: dict[str, float]) -> pd.DataFrame:
    """Recompute the metric for one position group under `multipliers`, rank within it."""
    out = df.copy()
    mult = out["league"].map(multipliers).astype(float)
    out["metric"] = (out["npg_p90_shrunk"] + out["ast_p90_shrunk"]) * mult
    out = out.sort_values("metric", ascending=False).reset_index(drop=True)
    out["rank"] = out.index + 1
    return out


def rank_pool(feats_by_group: dict[str, pd.DataFrame], multipliers: dict[str, float]) -> pd.DataFrame:
    """Rank players within each position group under `multipliers`, then pool the groups."""
    frames = []
    for group, df in feats_by_group.items():
        ranked = _rank_group(df, multipliers)
        ranked["pos_group"] = group
        frames.append(ranked[["player_key", "player", "pos_group", "metric", "rank"]])
    return pd.concat(frames, ignore_index=True)


def _dedup_by_best_rank(df: pd.DataFrame) -> pd.DataFrame:
    """Keep one row per (player_key, pos_group): the one with the best (lowest) rank.

    Defensive guard for `churn()`: a duplicate (player_key, pos_group) --
    normally prevented upstream by `collapse_player_seasons` in main() --
    would otherwise turn the baseline/scenario merge below into a cartesian
    join and inflate mean_delta_rank_top20.
    """
    return df.sort_values("rank").drop_duplicates(subset=["player_key", "pos_group"], keep="first")


def churn(baseline: pd.DataFrame, scenario: pd.DataFrame) -> dict:
    """Top-10 overlap/churn and mean |Δrank| over top-20, pooled across position groups.

    "top-10"/"top-20" = union of each group's own top-10/top-20 by `rank`
    (see module docstring); overlap/churn compare player_key set membership,
    mean_delta_rank_top20 compares each surviving player's rank number.
    """
    baseline = _dedup_by_best_rank(baseline)
    scenario = _dedup_by_best_rank(scenario)

    base_top10 = set(baseline.loc[baseline["rank"] <= 10, "player_key"])
    scen_top10 = set(scenario.loc[scenario["rank"] <= 10, "player_key"])
    overlap = len(base_top10 & scen_top10)
    churn_n = len(base_top10 - scen_top10)

    joined = baseline.merge(scenario, on=["player_key", "pos_group"], suffixes=("_base", "_scen"))
    top20 = joined[joined.rank_base <= 20]
    mean_delta = float((top20.rank_scen - top20.rank_base).abs().mean()) if len(top20) else 0.0

    return {"top10_overlap": overlap, "top10_churn": churn_n, "mean_delta_rank_top20": round(mean_delta, 3)}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = config.features()
    seasons_cfg = config.seasons()
    baseline_multipliers: dict[str, float] = config.league_quality()["multipliers"]

    feats_by_group = {}
    for g in cfg["groups"]:
        df = read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet")
        sub = df[(df.season == seasons_cfg["metrics"]) & df.czech_eligible].copy()
        n_before = len(sub)
        sub = collapse_player_seasons(sub, rate_cols=["npg_p90_shrunk", "ast_p90_shrunk"])
        if len(sub) != n_before:
            LOG.info("%s: collapsed %d mid-season-transfer duplicate rows", g, n_before - len(sub))
        feats_by_group[g] = sub
        LOG.info("%s: %d Czech-eligible players in %s", g, len(feats_by_group[g]), seasons_cfg["metrics"])

    scenarios = _build_scenarios(baseline_multipliers)
    baseline_ranked = rank_pool(feats_by_group, baseline_multipliers)

    rows = []
    for s in scenarios:
        scen_ranked = rank_pool(feats_by_group, s.multiplier_overrides)
        stats = churn(baseline_ranked, scen_ranked)
        rows.append({"scenario": s.name, "description": s.description, **stats})

    out = pd.DataFrame(rows)
    write_parquet(out, config.PROCESSED_DIR / "sensitivity.parquet")
    LOG.info("sensitivity: %d scenarios, max top10_churn=%d, max mean_delta_rank_top20=%.2f",
              len(out), int(out.top10_churn.max()), float(out.mean_delta_rank_top20.max()))


if __name__ == "__main__":
    main()
