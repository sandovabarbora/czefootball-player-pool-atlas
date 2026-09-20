"""The 26-season Big-5 series (M4 exhibit only -- the break model comes later).

For each peer country and each season 2000-2001 .. metrics, counts distinct
players (by `player_key`) with `min >= min_minutes` in the Big-5 leagues
(ENG/ITA/ESP/GER/FRA), per million population, and the country's share of
total Big-5 minutes that season. Also picks out the Czech peak/low season and
the three seasons with the most Czech players ("golden generations"), naming
their three highest-minutes Czech players -- computed from the data, never
typed.

Input:
    data/processed/big5_history.parquet (src.fetch_big5_history)

Output:
    data/processed/big5_series.json
    outputs/big5_series.svg
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src import config
from src.figstyle import (
    CORPUS,
    CREAM,
    INK,
    MUTED,
    OXBLOOD,
    annotate_point,
    label_right,
    season_axis,
    strip_chrome,
    use_style,
    y_grid_only,
)
from src.logging_setup import setup as logging_setup
from src.utils import read_parquet, season_label

LOG = logging.getLogger(__name__)
use_style()

MID_TONE_COUNTRIES = list(config.nation()["series_contrast"])


def build_series(history: pd.DataFrame, peers: dict[str, dict], min_minutes: int = 450) -> dict:
    """Per-peer, per-season player counts, per-capita rate and minutes share.

    `n` = distinct `player_key` with `min >= min_minutes` that season, summed
    across the five Big-5 leagues (a player transferred mid-season between
    two Big-5 clubs is counted once). `minutes_share` = the nation's total
    minutes that season (no floor -- every minute played counts) divided by
    all minutes played by anyone in the Big-5 that season.
    """
    seasons = sorted(history["season"].unique())
    season_totals = history.groupby("season")["min"].sum()

    countries: dict[str, dict] = {}
    for code, meta in peers.items():
        nation_rows = history[history["nation"] == code]
        n_list, per_million_list, minutes_share_list = [], [], []
        for season in seasons:
            season_nation = nation_rows[nation_rows["season"] == season]
            qualifying = season_nation[season_nation["min"] >= min_minutes]
            n = int(qualifying["player_key"].nunique())
            n_list.append(n)
            per_million_list.append(round(n / meta["population_m"], 2))
            total_min = float(season_totals.get(season, 0.0))
            nation_min = float(season_nation["min"].sum())
            minutes_share_list.append(round(nation_min / total_min, 4) if total_min > 0 else 0.0)
        countries[code] = {"n": n_list, "per_million": per_million_list, "minutes_share": minutes_share_list}

    cze_n = countries[config.HOME]["n"]
    peak_idx = max(range(len(seasons)), key=lambda i: (cze_n[i], -i))
    low_idx = min(range(len(seasons)), key=lambda i: (cze_n[i], i))
    cze_peak = {"season": seasons[peak_idx], "n": cze_n[peak_idx]}
    cze_low = {"season": seasons[low_idx], "n": cze_n[low_idx]}

    golden_idx = sorted(range(len(seasons)), key=lambda i: (-cze_n[i], seasons[i]))[:3]
    golden = []
    for i in golden_idx:
        season = seasons[i]
        cze_season = history[(history["season"] == season) & (history["nation"] == config.HOME)]
        by_player = (
            cze_season.groupby("player_key")
            .agg(player=("player", "first"), min=("min", "sum"))
            .sort_values("min", ascending=False)
        )
        players = by_player.head(3)["player"].tolist()
        golden.append({"season": season, "players": players})

    return {
        "seasons": seasons,
        "countries": countries,
        "cze_peak": cze_peak,
        "cze_low": cze_low,
        "golden": golden,
    }


def render_series(series: dict, out_path: Path) -> None:
    """One matplotlib SVG (Task 27B2): the home nation's `n` one thick
    oxblood line, peak/low/last each a small callout; every other country a
    thin grey line, the two `MID_TONE_COUNTRIES` labelled directly at the
    right edge (muted grey) and every other peer left unlabelled (`CORPUS`,
    the palest grey -- present for shape/context only). A `per_million`
    panel below shares the x-axis and carries no legend of its own, only
    the same direct right-edge labels."""
    seasons = series["seasons"]
    years = [int(s[:4]) for s in seasons]
    countries = series["countries"]

    fig, (ax_n, ax_pm) = plt.subplots(
        2, 1, figsize=(10.4, 7.4), sharex=True, gridspec_kw={"height_ratios": [2, 1]},
    )
    fig.patch.set_facecolor(CREAM)

    n_end_points = []
    for code, data in countries.items():
        if code == config.HOME:
            continue
        labelled = code in MID_TONE_COUNTRIES
        color = MUTED if labelled else CORPUS
        ax_n.plot(years, data["n"], color=color, lw=1.4 if labelled else 1.0, zorder=2)
        if labelled:
            n_end_points.append((years[-1], data["n"][-1], code, MUTED))

    cze_n = countries[config.HOME]["n"]
    ax_n.plot(years, cze_n, color=OXBLOOD, lw=2.6, zorder=5)
    label_right(ax_n, [*n_end_points, (years[-1], cze_n[-1], config.nation()["name"], OXBLOOD)])

    peak, low = series["cze_peak"], series["cze_low"]
    last_season, last_n = seasons[-1], cze_n[-1]
    for point, dy in ((peak, 14), (low, -18), ({"season": last_season, "n": last_n}, -18)):
        x = int(point["season"][:4])
        ax_n.scatter([x], [point["n"]], color=OXBLOOD, s=26, zorder=6, edgecolors=CREAM, linewidths=0.6)
        annotate_point(ax_n, x, point["n"], f"{season_label(point['season'])}: {point['n']}", dy=dy)

    ax_n.set_ylabel("Players (≥ 450 min)", fontsize=10, color=INK)
    ax_n.set_title(
        f"{config.nation()['adjective']} players in the Big-5 leagues", fontsize=13, color=INK, loc="left",
    )
    strip_chrome(ax_n)
    y_grid_only(ax_n)
    ax_n.margins(x=0.06)

    pm_end_points = []
    for code in [*MID_TONE_COUNTRIES]:
        if code not in countries:
            continue
        ax_pm.plot(years, countries[code]["per_million"], color=MUTED, lw=1.4, zorder=2)
        pm_end_points.append((years[-1], countries[code]["per_million"][-1], code, MUTED))
    ax_pm.plot(years, countries[config.HOME]["per_million"], color=OXBLOOD, lw=2.2, zorder=5)
    label_right(ax_pm, [*pm_end_points, (years[-1], countries[config.HOME]["per_million"][-1], config.HOME, OXBLOOD)])

    ax_pm.set_ylabel("Per million", fontsize=10, color=INK)
    season_axis(ax_pm, seasons, step=4)
    strip_chrome(ax_pm)
    y_grid_only(ax_pm)
    ax_pm.margins(x=0.06)

    plt.subplots_adjust(top=0.94, hspace=0.16, right=0.90)
    plt.savefig(out_path, format="svg")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    history = read_parquet(config.PROCESSED_DIR / "big5_history.parquet")
    peers = config.peers_meta()
    series = build_series(history, peers)

    out_json = config.PROCESSED_DIR / "big5_series.json"
    out_json.write_text(json.dumps(series, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.info("wrote %s", out_json)

    render_series(series, config.OUTPUTS_DIR / "big5_series.svg")

    peak, low = series["cze_peak"], series["cze_low"]
    last_season = series["seasons"][-1]
    last_n = series["countries"][config.HOME]["n"][-1]
    LOG.info(
        "%s peak %s (%d), low %s (%d), last %s (%d)",
        config.HOME, peak["season"], peak["n"], low["season"], low["n"], last_season, last_n,
    )


if __name__ == "__main__":
    main()
