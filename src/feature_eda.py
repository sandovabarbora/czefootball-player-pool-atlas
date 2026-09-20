"""Task 17: "From raw tables to a feature vector" — wrangling, EDA and
feature engineering shown, not claimed (spec §4c).

Reads:  data/processed/<nation>/fbref_players.parquet, features_{FW,MF,DF}.parquet
Writes: data/processed/<nation>/feature_eda.json,
        outputs/<nation>/eda_distributions.svg, outputs/<nation>/eda_shrinkage.svg

Four things, one worked example:

1. One raw row: the home nation's player with the most metrics-season
   minutes, shown as its raw FBref columns (`pick_raw_and_feature_row`) next
   to the same player's feature row after per-90 -> Bayesian shrinkage ->
   league-quality projection -> z-score (`feature_row_dict`). The raw-row
   search is restricted to players who actually made it into the feature
   pipeline (min >= `feature_definitions.yaml::min_minutes`, a FW/MF/DF
   position), so a pairing always exists.

2. The cleaning ledger is not recomputed here — `data_quality.json` already
   carries it, and `render.py` links `#features-from-raw` to `#data-quality`
   rather than duplicating the counts.

3. Five kept features, five rejected candidates, corpus-wide (every fetched
   nationality) on the metrics-season feature-pipeline output — the same
   population every other chapter-IV number in this report describes:
     - `gls_p90` vs `npg_p90`: penalties inflate a few takers
       (`penalty_share_stat`) -> replaced by npg_p90.
     - `mp` (appearances) vs `min`: a start can be a substitute cameo
       (`starts_proxy_stat`) -> replaced by minutes share.
     - `crdr_p90` (red cards): most player-seasons have none
       (`red_card_zero_share_stat`) -> folded into cards (yellow + 2*red).
     - `age`: median production visibly differs by age band
       (`age_production_curve_stat`) -> kept as a feature.
     - `born` (raw column): occasionally missing corpus-wide
       (`missingness_stat`) -> kept anyway, since `player_key` (the
       cross-source join key, see `src.utils.player_key`) needs it.

4. Two EDA figures: `render_distributions_figure` (the five raw per-90
   features' distributions per league, the picture that motivates league
   adjustment) and `render_shrinkage_figure` (raw vs shrunk npG/90 against
   minutes, the picture that motivates shrinkage).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import skew

from src import config
from src.features import FEATURES
from src.figstyle import CREAM, INK, MUTED, NAVY, NAVY_DEEP, OXBLOOD, RULE, use_style
from src.logging_setup import setup as logging_setup
from src.utils import read_parquet

LOG = logging.getLogger(__name__)

GROUPS = ["FW", "MF", "DF"]
RAW_COLUMNS = ["league", "season", "team", "player", "nation", "pos", "born", "age",
               "mp", "min", "gls", "ast", "pk", "crdy", "crdr"]
_INT_RAW_COLUMNS = {"born", "age", "mp", "min", "gls", "ast", "pk", "crdy", "crdr"}
AGE_BAND_ORDER = ["U22", "23-25", "26-29", "30+"]

use_style()


# =============================================================================
# 1. The raw row and the feature row
# =============================================================================


def pick_raw_and_feature_row(
    tables: pd.DataFrame, features_by_group: dict[str, pd.DataFrame], metrics_season: str,
) -> tuple[pd.Series, pd.Series]:
    """The home nation's raw row with the most metrics-season minutes among
    players who also made it into the feature pipeline, plus that player's
    own feature row.

    Restricting to players present in some `features_{group}` frame (not
    every home-nation row in `fbref_players.parquet`) guarantees the second
    half of the pairing exists -- a raw row below the inclusion floor, at a
    goalkeeper position, or in a league without season tables would
    otherwise have no feature row to show next to it.
    """
    feat_all = pd.concat(features_by_group.values(), ignore_index=True) if features_by_group else pd.DataFrame()
    feat_metrics = feat_all[feat_all["season"] == metrics_season] if not feat_all.empty else feat_all
    eligible_keys = set(feat_metrics["player_key"]) if not feat_metrics.empty else set()

    home_rows = tables[
        (tables["nation"] == config.HOME) & (tables["season"] == metrics_season)
        & tables["player_key"].isin(eligible_keys)
    ]
    if home_rows.empty:
        raise ValueError(f"no {config.HOME} player with both a raw row and a feature row in {metrics_season}")
    raw = home_rows.sort_values("min", ascending=False).iloc[0]

    same_player = feat_metrics[feat_metrics["player_key"] == raw["player_key"]]
    same_team = same_player[same_player["team"] == raw["team"]]
    feat = (same_team if not same_team.empty else same_player).iloc[0]
    return raw, feat


def raw_row_dict(row: pd.Series) -> dict[str, Any]:
    """`row` (a `fbref_players.parquet` row) -> a plain dict over
    `RAW_COLUMNS`, in FBref's own column order, ints where FBref's own dtype
    is integer-like and `None` for a missing value (age/born can be NA)."""
    out: dict[str, Any] = {}
    for col in RAW_COLUMNS:
        v = row[col]
        if pd.isna(v):
            out[col] = None
        elif col in _INT_RAW_COLUMNS:
            out[col] = int(v)
        else:
            out[col] = str(v)
    return out


def feature_row_dict(row: pd.Series) -> dict[str, Any]:
    """`row` (a `features_{group}.parquet` row) -> `{player, pos_group,
    <feature>: {raw, shrunk, quality, z}}` for each of `src.features.FEATURES`
    -- the pipeline's four stages for that one player's season."""
    out: dict[str, Any] = {"player": str(row["player"]), "pos_group": str(row["pos_group"])}
    for f in FEATURES:
        stages = {"raw": row[f], "shrunk": row[f"{f}_shrunk"],
                  "quality": row[f"{f}_quality"], "z": row[f"{f}_quality_z"]}
        out[f] = {k: (round(float(v), 4) if pd.notna(v) else None) for k, v in stages.items()}
    return out


# =============================================================================
# 2. Why five features -- the rejected candidates, with the reason from the data
# =============================================================================


def penalty_share_stat(df: pd.DataFrame, n: int = 3) -> dict[str, Any]:
    """(i) corr(gls_p90, npg_p90) -- penalties inflate a few takers' raw goal
    count without being open-play production, hence npg_p90 over gls_p90 --
    plus the `n` player-seasons with the highest penalty share (pk / gls,
    among rows with at least one goal)."""
    d = df[df["min"] > 0].copy()
    d["gls_p90"] = d["gls"] / (d["min"] / 90.0)
    corr = float(d["gls_p90"].corr(d["npg_p90"])) if len(d) > 1 else None

    scored = df[df["gls"] > 0].copy()
    scored["penalty_share"] = scored["pk"] / scored["gls"]
    top = scored.sort_values("penalty_share", ascending=False).head(n)
    top_rows = [
        {"player": str(r.player), "league": str(r.league), "season": str(r.season),
         "share": round(float(r.penalty_share), 3)}
        for r in top.itertuples()
    ]
    return {"corr": round(corr, 4) if corr is not None else None, "top": top_rows}


def starts_proxy_stat(df: pd.DataFrame) -> dict[str, Any]:
    """(ii) corr(mp, min) -- an appearance (`mp`) can be a substitute cameo, so
    it is a noisier proxy for playing time than minutes share."""
    corr = float(df["mp"].corr(df["min"])) if len(df) > 1 else None
    return {"corr": round(corr, 4) if corr is not None else None}


def red_card_zero_share_stat(df: pd.DataFrame) -> dict[str, Any]:
    """(iii) share of player-seasons with zero red cards -- too sparse a
    signal on its own, hence folded into `cards_p90` (yellow + 2*red)."""
    share = float((df["crdr"] == 0).mean()) if len(df) else None
    return {"zero_share": round(share, 4) if share is not None else None}


def _age_band(age: object) -> str | None:
    if pd.isna(age):
        return None
    age = int(age)
    if age <= 21:
        return "U22"
    if age <= 25:
        return "23-25"
    if age <= 29:
        return "26-29"
    return "30+"


def age_production_curve_stat(df: pd.DataFrame) -> list[dict[str, Any]]:
    """(iv) median non-penalty production (npg_p90 + ast_p90) per age band --
    a visibly non-flat curve is the case for keeping age as a feature."""
    d = df.copy()
    d["band"] = d["age"].map(_age_band)
    d["prod"] = d["npg_p90"].fillna(0) + d["ast_p90"].fillna(0)
    rows = []
    for band in AGE_BAND_ORDER:
        sub = d[d["band"] == band]
        if sub.empty:
            continue
        rows.append({"band": band, "median": round(float(sub["prod"].median()), 4), "n": int(len(sub))})
    return rows


def missingness_stat(tables: pd.DataFrame) -> list[dict[str, Any]]:
    """(v) missing count/share per raw column -- `born` is the one the join
    key (`src.utils.player_key`) depends on."""
    n = len(tables)
    rows = []
    for c in RAW_COLUMNS:
        missing = int(tables[c].isna().sum())
        rows.append({"column": c, "missing": missing, "share": round(missing / n, 4) if n else 0.0})
    return rows


def build_rejected(
    penalty: dict[str, Any], starts: dict[str, Any], redcard: dict[str, Any],
    age_bands: list[dict[str, Any]], missingness: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """The five `{candidate, statistic, value, decision}` rows (brief §3):
    `candidate` and `decision` are stable codes the report's i18n layer
    translates (see `render._build_feature_eda`); `statistic` names what
    `value` is."""
    born_row = next((r for r in missingness if r["column"] == "born"), {"share": None})
    age_spread = (
        round(max(r["median"] for r in age_bands) - min(r["median"] for r in age_bands), 4)
        if age_bands else None
    )
    return [
        {"candidate": "gls_p90", "statistic": "corr_npg", "value": penalty["corr"], "decision": "replaced_npg"},
        {"candidate": "mp", "statistic": "corr_min", "value": starts["corr"], "decision": "replaced_min_share"},
        {"candidate": "crdr_p90", "statistic": "zero_share", "value": redcard["zero_share"], "decision": "folded_cards"},
        {"candidate": "age", "statistic": "band_spread", "value": age_spread, "decision": "kept"},
        {"candidate": "born", "statistic": "missing_share", "value": born_row["share"], "decision": "kept_key"},
    ]


# =============================================================================
# 3. Figures
# =============================================================================


def render_distributions_figure(
    features_all: pd.DataFrame, out_path: Path, top_n_leagues: int = 7,
) -> dict[str, Any]:
    """Small multiples: one panel per `src.features.FEATURES` raw value,
    boxplots per league (the `top_n_leagues` with the most rows, the
    domestic league always included), domestic league in oxblood. A panel's
    y-axis is log1p-scaled when its skewness (computed, not guessed) exceeds
    1.5 and every value is non-negative.
    """
    counts = features_all["league"].value_counts()
    leagues = list(counts.head(top_n_leagues).index)
    if config.DOMESTIC_LEAGUE in counts.index and config.DOMESTIC_LEAGUE not in leagues:
        leagues = [*leagues[:-1], config.DOMESTIC_LEAGUE]
    leagues = sorted(set(leagues), key=lambda lg: -counts.get(lg, 0))

    fig, axes = plt.subplots(1, len(FEATURES), figsize=(3.6 * len(FEATURES), 5.4))
    fig.patch.set_facecolor(CREAM)
    log_scaled = []
    for ax, feat in zip(axes, FEATURES, strict=True):
        vals = features_all[feat].dropna()
        sk = float(skew(vals)) if len(vals) > 2 else 0.0
        use_log = bool(sk > 1.5 and (vals >= 0).all())
        by_league = []
        for lg in leagues:
            v = features_all.loc[features_all["league"] == lg, feat].dropna()
            by_league.append(np.log1p(v) if use_log else v)
        bp = ax.boxplot(by_league, patch_artist=True, showfliers=False)
        for patch, lg in zip(bp["boxes"], leagues, strict=True):
            patch.set_facecolor(OXBLOOD if lg == config.DOMESTIC_LEAGUE else NAVY_DEEP)
            patch.set_alpha(0.75)
        for element in ("whiskers", "caps", "medians"):
            for line in bp[element]:
                line.set_color(INK)
        ax.set_xticks(range(1, len(leagues) + 1))
        ax.set_xticklabels(leagues, rotation=90, fontsize=9, fontfamily="sans-serif", color=INK)
        ax.set_title(feat + (" (log1p)" if use_log else ""), fontsize=10, fontfamily="sans-serif", color=INK)
        ax.set_facecolor(CREAM)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            ax.spines[spine].set_color(RULE)
        ax.tick_params(colors=INK)
        if use_log:
            log_scaled.append(feat)

    fig.suptitle("Raw per-90 feature distributions by league", fontsize=13, fontfamily="sans-serif",
                 color=INK, y=1.02, x=0.01, ha="left")
    plt.tight_layout()
    plt.savefig(out_path, format="svg", facecolor=CREAM, edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    LOG.info("wrote %s", out_path)
    return {"leagues": leagues, "log_scaled": log_scaled}


def render_shrinkage_figure(
    features_all: pd.DataFrame, phantom_minutes: int, out_path: Path,
) -> dict[str, Any] | None:
    """Raw vs shrunk npG/90 against minutes, home-nation-eligible rows only,
    connected by a thin segment per player; a dashed curve on a second axis
    is the shrinkage weight on the league median, `K / (minutes + K)`
    (`src.features.bayesian_shrink`'s own formula, `K` = `phantom_minutes`
    expressed in minutes). Returns the most-shrunk player (largest absolute
    `shrunk - raw` delta) or `None` when there is nothing to plot.
    """
    if features_all.empty or "home_eligible" not in features_all.columns:
        LOG.warning("no rows to plot; skipping %s", out_path)
        return None
    d = features_all[features_all["home_eligible"]].copy()
    d = d.dropna(subset=["min", "npg_p90", "npg_p90_shrunk"])
    if d.empty:
        LOG.warning("no home-eligible rows with npg_p90/npg_p90_shrunk; skipping %s", out_path)
        return None
    d["delta"] = d["npg_p90_shrunk"] - d["npg_p90"]
    most_shrunk = d.loc[d["delta"].abs().idxmax()]

    fig, ax = plt.subplots(figsize=(8.2, 5.4))
    fig.patch.set_facecolor(CREAM)
    ax.set_facecolor(CREAM)
    for _, r in d.iterrows():
        ax.plot([r["min"], r["min"]], [r["npg_p90"], r["npg_p90_shrunk"]], color=RULE, lw=0.6, zorder=1)
    ax.scatter(d["min"], d["npg_p90"], s=22, color=MUTED, alpha=0.6, zorder=2, label="raw npG/90")
    ax.scatter(d["min"], d["npg_p90_shrunk"], s=22, color=NAVY, alpha=0.9, zorder=3, label="shrunk npG/90")
    ax.annotate(str(most_shrunk["player"]).split()[-1], (most_shrunk["min"], most_shrunk["npg_p90_shrunk"]),
                xytext=(6, 6), textcoords="offset points", fontsize=8, color=INK, zorder=5)

    ax2 = ax.twinx()
    lo, hi = float(d["min"].min()), float(d["min"].max())
    grid = np.linspace(lo, hi if hi > lo else lo + 1, 200)
    weight = phantom_minutes / (grid + phantom_minutes)
    ax2.plot(grid, weight, color=OXBLOOD, lw=1.6, ls="--", zorder=2,
              label=f"weight on league median (K = {phantom_minutes} min)")
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel("weight on league median", fontsize=9.5, color=OXBLOOD, fontfamily="sans-serif")
    ax2.tick_params(colors=OXBLOOD)

    ax.set_xlabel("minutes", fontsize=10.5, color=INK, fontfamily="sans-serif")
    ax.set_ylabel("npG/90", fontsize=10.5, color=INK, fontfamily="sans-serif")
    ax.set_title("Shrinkage: raw vs shrunk npG/90 against minutes", fontsize=13, fontfamily="sans-serif",
                 color=INK, loc="left")
    ax.spines["top"].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(RULE)
    ax.tick_params(colors=INK)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, frameon=False, fontsize=8.5, loc="upper right")
    plt.tight_layout()
    plt.savefig(out_path, format="svg", facecolor=CREAM, edgecolor="none")
    plt.close(fig)
    LOG.info("wrote %s", out_path)

    return {
        "player": str(most_shrunk["player"]), "league": str(most_shrunk["league"]),
        "min": int(most_shrunk["min"]), "raw": round(float(most_shrunk["npg_p90"]), 4),
        "shrunk": round(float(most_shrunk["npg_p90_shrunk"]), 4), "delta": round(float(most_shrunk["delta"]), 4),
    }


# =============================================================================
# 4. Assembly / main
# =============================================================================


def assemble_output(
    metrics_season: str, raw_row: dict[str, Any], feature_row: dict[str, Any],
    rejected: list[dict[str, Any]], penalty: dict[str, Any], age_bands: list[dict[str, Any]],
    missingness: list[dict[str, Any]], most_shrunk: dict[str, Any] | None,
    distributions: dict[str, Any],
) -> dict[str, Any]:
    """Pure assembly of `feature_eda.json`'s shape; no I/O here, so this is
    testable on hand-built inputs (mirrors `league_strength.assemble_output`)."""
    return {
        "metrics_season": metrics_season,
        "raw_row": raw_row,
        "feature_row": feature_row,
        "rejected": rejected,
        "penalty_top": penalty["top"],
        "age_bands": age_bands,
        "missingness": missingness,
        "most_shrunk": most_shrunk,
        "distributions": distributions,
    }


def main() -> None:
    logging_setup()
    config.ensure_dirs()
    cfg = config.features()
    metrics_season = config.seasons()["metrics"]

    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    features_by_group = {g: read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in GROUPS}
    features_all = pd.concat(features_by_group.values(), ignore_index=True)
    feat_metrics = features_all[features_all["season"] == metrics_season]
    tables_metrics = tables[tables["season"] == metrics_season]

    raw, feat = pick_raw_and_feature_row(tables, features_by_group, metrics_season)
    raw_row = raw_row_dict(raw)
    feature_row = feature_row_dict(feat)
    LOG.info("raw/feature row: %s (%s), pos_group %s", raw_row["player"], raw_row["team"], feature_row["pos_group"])

    penalty = penalty_share_stat(feat_metrics)
    starts = starts_proxy_stat(feat_metrics)
    redcard = red_card_zero_share_stat(feat_metrics)
    age_bands = age_production_curve_stat(feat_metrics)
    missingness = missingness_stat(tables_metrics)
    rejected = build_rejected(penalty, starts, redcard, age_bands, missingness)
    LOG.info("rejected candidates: %s", [(r["candidate"], r["decision"]) for r in rejected])

    distributions = render_distributions_figure(feat_metrics, config.OUTPUTS_DIR / "eda_distributions.svg")
    most_shrunk = render_shrinkage_figure(feat_metrics, cfg["phantom_minutes"],
                                          config.OUTPUTS_DIR / "eda_shrinkage.svg")

    result = assemble_output(metrics_season, raw_row, feature_row, rejected, penalty, age_bands,
                             missingness, most_shrunk, distributions)
    out_json = config.PROCESSED_DIR / "feature_eda.json"
    out_json.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    LOG.info("wrote %s", out_json)


if __name__ == "__main__":
    main()
