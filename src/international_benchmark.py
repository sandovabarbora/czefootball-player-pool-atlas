"""Per-capita benchmark and cohort gaps for the nine peer countries.

Two independent deliverables:

    per-capita: distinct players (by `player_key`) with `nation` == peer on
    `current`-season rosters of the UEFA top-9 headline leagues, divided by
    population (millions). Answers "how many top-9-league players does each
    peer country field, relative to its population".

    cohorts: for the `metrics` season, median non-penalty-goals + assists per
    90 (quality-adjusted) by country x position group (FW/MF/DF) x age
    cohort, restricted to players with >= min_minutes in headline leagues.
    Answers "at which age cohort is each country's pool thin or deep".

Inputs:
    data/processed/fbref_players.parquet   (all rosters, all nations/leagues)
    data/processed/features_{FW,MF,DF}.parquet (quality-adjusted per-90 rates)

Outputs:
    data/processed/per_capita.parquet
    data/processed/cohorts.parquet
    outputs/intl_cohort_heatmap.svg
    outputs/benchmark_narrative.md

This module reports counts and medians only. It makes no player-selection
recommendation.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from src import config
from src.logging_setup import setup as logging_setup
from src.utils import read_parquet, write_parquet

LOG = logging.getLogger(__name__)

# --- Palette (kept from the hockey module's styling) -------------------------

NAVY        = "#1f3a5f"
NAVY_DEEP   = "#162a44"
OXBLOOD     = "#9c3a2a"
INK         = "#2a261f"
MUTED       = "#8a857b"
RULE        = "#c8c2b7"
CREAM       = "#fdfbf6"
CREAM_TINT  = "#efe9dc"

# Sequential ramp cream -> navy. Reads as "more production = more visual
# weight" without the YlGnBu green-teal SaaS-dashboard vocabulary.
CMAP_NAVY = LinearSegmentedColormap.from_list(
    "cream_to_navy",
    [
        (0.00, CREAM_TINT),
        (0.30, "#c4c3bc"),
        (0.55, "#7e8eaa"),
        (0.80, NAVY),
        (1.00, NAVY_DEEP),
    ],
    N=256,
)

# Matplotlib font defaults, shared with render.py.
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = [
    "Spectral", "Cambria", "Georgia", "Times New Roman", "DejaVu Serif",
]
plt.rcParams["font.sans-serif"] = [
    "Bricolage Grotesque", "Helvetica Neue", "Arial", "DejaVu Sans",
]
plt.rcParams["text.color"] = INK

COHORTS = [("U22", 0, 21), ("23-25", 23, 25), ("26-29", 26, 29), ("30+", 30, 99)]
POS_GROUPS = ["FW", "MF", "DF"]
POS_GROUP_TITLES = {
    "FW": "Forwards",
    "MF": "Midfielders",
    "DF": "Defenders",
}


def assign_cohort(born: int, season: str) -> str | None:
    """Age cohort at the season's calendar turn (as in the hockey module).

    age = year the season turns into (season[:4] + 1) - birth year.
    """
    age = int(season[:4]) + 1 - born
    if age <= 22:
        return "U22"
    for label, lo, hi in COHORTS[1:]:
        if lo <= age <= hi:
            return label
    return None


def per_capita(
    tables: pd.DataFrame, peers: dict, headline_leagues: list[str], season: str
) -> pd.DataFrame:
    """Distinct headline-league players per peer country, per million population."""
    sub = tables[
        (tables.season == season)
        & tables.league.isin(headline_leagues)
        & tables.nation.isin(peers)
    ]
    n = sub.groupby("nation")["player_key"].nunique()
    rows = []
    for code, meta in peers.items():
        cnt = int(n.get(code, 0))
        rows.append({
            "country": code,
            "name": meta["name"],
            "n_players": cnt,
            "population_m": meta["population_m"],
            "per_million": round(cnt / meta["population_m"], 2),
        })
    # Tie-break: on equal per-capita rate, the smaller-population country
    # ranks first (a given rate reflects a thinner population base).
    out = (
        pd.DataFrame(rows)
        .sort_values(["per_million", "population_m"], ascending=[False, True])
        .reset_index(drop=True)
    )
    out["rank"] = range(1, len(out) + 1)
    return out


def cohort_table(features_by_group: dict[str, pd.DataFrame], peers: dict) -> pd.DataFrame:
    """Median quality-adjusted npG+A per 90 by country x position group x cohort.

    Restricted to the metrics season, headline leagues, and players with
    >= min_minutes.
    """
    season = config.seasons()["metrics"]
    min_minutes = config.features()["min_minutes"]
    rows = []
    for group, df in features_by_group.items():
        d = df[
            (df.season == season)
            & df.nation.isin(peers)
            & df.league.isin(config.HEADLINE_LEAGUES)
            & (df["min"] >= min_minutes)
        ].copy()
        if d.empty:
            continue
        d["cohort"] = d["born"].map(lambda b: assign_cohort(int(b), season))
        d["npg_ast_q"] = d["npg_p90_quality"] + d["ast_p90_quality"]
        for (country, cohort), g in d.groupby(["nation", "cohort"]):
            rows.append({
                "country": country,
                "pos_group": group,
                "cohort": cohort,
                "n": len(g),
                "median_npg_ast_p90": round(float(g["npg_ast_q"].median()), 2),
            })
    return pd.DataFrame(rows)


# --- Visualization -----------------------------------------------------------


def render_cohort_heatmap(per_capita_table: pd.DataFrame, cohorts: pd.DataFrame, out_path: Path) -> None:
    """Three-panel heatmap: FW / MF / DF. Rows = countries ordered by
    per-capita rank (top first); cols = age cohorts. Cell color = median
    npG+A per 90 (cream -> navy ramp); cell annotation = n over median. The
    CZE row is highlighted with an oxblood outline."""
    country_order = per_capita_table.sort_values("rank")["country"].tolist()
    cohort_order = [c[0] for c in COHORTS]
    n_countries = len(country_order)
    n_cohorts = len(cohort_order)

    fig, axes = plt.subplots(1, 3, figsize=(16.5, 5.4), sharey=True)
    fig.patch.set_facecolor(CREAM)

    vmax = float(cohorts["median_npg_ast_p90"].max()) if not cohorts.empty else 1.0

    for ax, group in zip(axes, POS_GROUPS, strict=True):
        sub = cohorts[cohorts["pos_group"] == group]
        matrix = np.full((n_countries, n_cohorts), np.nan)
        n_matrix = np.zeros((n_countries, n_cohorts), dtype=int)
        for i, country in enumerate(country_order):
            for j, cohort in enumerate(cohort_order):
                row = sub[(sub["country"] == country) & (sub["cohort"] == cohort)]
                if not row.empty:
                    matrix[i, j] = row.iloc[0]["median_npg_ast_p90"]
                    n_matrix[i, j] = int(row.iloc[0]["n"])

        ax.imshow(matrix, cmap=CMAP_NAVY, aspect="auto", vmin=0.0, vmax=vmax)
        ax.set_xticks(range(n_cohorts))
        ax.set_xticklabels(cohort_order, fontsize=9.5, fontfamily="sans-serif", color=INK)
        ax.set_yticks(range(n_countries))
        ax.set_yticklabels(country_order, fontsize=9.5, fontfamily="sans-serif",
                            color=INK, weight="medium")
        ax.set_title(
            f"{POS_GROUP_TITLES[group]}  ·  median npG+A per 90 (quality-adjusted)",
            fontsize=11, fontfamily="serif", color=INK, pad=12, loc="left", weight="normal",
        )
        ax.tick_params(axis="both", which="both", length=0, colors=INK, pad=6)
        for spine in ax.spines.values():
            spine.set_visible(False)

        for i in range(n_countries):
            for j in range(n_cohorts):
                n = n_matrix[i, j]
                if n == 0:
                    ax.text(j, i, "—", ha="center", va="center",
                            fontsize=10, color=MUTED, fontfamily="serif")
                else:
                    val = matrix[i, j]
                    text_color = CREAM if (vmax and val > 0.55 * vmax) else INK
                    ax.text(j, i - 0.10, f"n={n}", ha="center", va="center",
                            fontsize=8.5, color=text_color, fontfamily="sans-serif",
                            weight="medium")
                    ax.text(j, i + 0.20, f"{val:.2f}", ha="center", va="center",
                            fontsize=9, color=text_color, fontfamily="serif", weight="normal")

        cz_idx = country_order.index("CZE") if "CZE" in country_order else None
        if cz_idx is not None:
            ax.add_patch(plt.Rectangle(
                (-0.5, cz_idx - 0.5), n_cohorts, 1,
                fill=False, edgecolor=OXBLOOD, lw=2.2, zorder=8,
            ))

    fig.canvas.draw()
    if "CZE" in country_order:
        cz_idx = country_order.index("CZE")
        for ax in axes:
            labels = ax.get_yticklabels()
            if cz_idx < len(labels):
                labels[cz_idx].set_color(OXBLOOD)
                labels[cz_idx].set_weight("bold")

    fig.suptitle(
        "International cohort benchmark  ·  UEFA top-9 leagues 2024/25",
        fontsize=14, fontfamily="serif", color=INK, x=0.02, ha="left", y=1.04, weight="normal",
    )
    fig.text(
        0.02, 0.985,
        "Cell: player count and median npG+A per 90. Rows ordered by per-capita rank "
        "(top first); highlighted row = CZE.",
        ha="left", fontsize=9, color=MUTED, fontfamily="sans-serif",
    )
    plt.subplots_adjust(top=0.86, wspace=0.08)
    plt.savefig(out_path, bbox_inches="tight", format="svg", facecolor=CREAM, edgecolor="none")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


# --- Narrative -----------------------------------------------------------


def build_narrative(pc: pd.DataFrame, coh: pd.DataFrame) -> str:
    """Factual, non-evaluative summary: per-capita ranking, CZE rank, and the
    top-3 cohort gaps where CZE's player count is lowest relative to the
    peer median for that cohort."""
    lines = [
        "# International cohort benchmark",
        "",
        f"UEFA top-9 leagues, {config.seasons()['current']} rosters "
        f"(per-capita) and {config.seasons()['metrics']} season (cohorts).",
        "",
        "## Per-capita ranking (headline-league players per million population)",
        "",
        "| Rank | Country | Players | Population (M) | Per million |",
        "|---:|---|---:|---:|---:|",
    ]
    for _, r in pc.sort_values("rank").iterrows():
        lines.append(
            f"| {int(r['rank'])} | {r['name']} ({r['country']}) | {int(r['n_players'])} | "
            f"{r['population_m']:.2f} | {r['per_million']:.2f} |"
        )
    lines.append("")

    cze_row = pc[pc.country == "CZE"]
    if not cze_row.empty:
        r = cze_row.iloc[0]
        lines.append(
            f"CZE ranks {int(r['rank'])} of {len(pc)} peer countries, with "
            f"{int(r['n_players'])} players ({r['per_million']:.2f} per million)."
        )
        lines.append("")

    lines.append("## Cohort gaps")
    lines.append("")
    lines.append(
        "For each position group x age cohort, CZE's player count (n) compared "
        "with the median n across the other peer countries in that cohort. The "
        "three cohorts with the largest shortfall (CZE n minus peer median n) "
        "are listed below."
    )
    lines.append("")

    if not coh.empty:
        gaps = []
        for (group, cohort), g in coh.groupby(["pos_group", "cohort"]):
            cze_n = g[g.country == "CZE"]["n"]
            cze_n_val = int(cze_n.iloc[0]) if not cze_n.empty else 0
            peer_n = g[g.country != "CZE"]["n"]
            if peer_n.empty:
                continue
            peer_median_n = float(peer_n.median())
            gaps.append({
                "pos_group": group,
                "cohort": cohort,
                "cze_n": cze_n_val,
                "peer_median_n": peer_median_n,
                "gap": cze_n_val - peer_median_n,
            })
        gaps_df = pd.DataFrame(gaps).sort_values("gap")
        lines.append("| Position | Cohort | CZE n | Peer median n | Gap |")
        lines.append("|---|---|---:|---:|---:|")
        for _, r in gaps_df.head(3).iterrows():
            lines.append(
                f"| {POS_GROUP_TITLES[r['pos_group']]} | {r['cohort']} | {int(r['cze_n'])} | "
                f"{r['peer_median_n']:.1f} | {r['gap']:.1f} |"
            )
        lines.append("")

    lines.append(
        "Numbers only; this is not a player-selection recommendation."
    )
    return "\n".join(lines)


# --- Main ---


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    peers = config.countries()["peers"]
    tables = read_parquet(config.PROCESSED_DIR / "fbref_players.parquet")
    pc = per_capita(tables, peers, config.HEADLINE_LEAGUES, config.seasons()["current"])
    write_parquet(pc, config.PROCESSED_DIR / "per_capita.parquet")

    feats = {g: read_parquet(config.PROCESSED_DIR / f"features_{g}.parquet") for g in config.features()["groups"]}
    coh = cohort_table(feats, peers)
    write_parquet(coh, config.PROCESSED_DIR / "cohorts.parquet")

    render_cohort_heatmap(pc, coh, config.OUTPUTS_DIR / "intl_cohort_heatmap.svg")

    narrative = build_narrative(pc, coh)
    narrative_path = config.OUTPUTS_DIR / "benchmark_narrative.md"
    narrative_path.write_text(narrative, encoding="utf-8")
    LOG.info("wrote %s", narrative_path)

    LOG.info("per capita:\n%s", pc.to_string(index=False))


if __name__ == "__main__":
    main()
