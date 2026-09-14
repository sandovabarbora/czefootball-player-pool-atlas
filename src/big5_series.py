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
from src.international_benchmark import CREAM, INK, MUTED, NAVY, OXBLOOD
from src.logging_setup import setup as logging_setup
from src.utils import read_parquet, season_label

LOG = logging.getLogger(__name__)

MID_TONE_COUNTRIES = ["DEN", "CRO"]


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

    cze_n = countries["CZE"]["n"]
    peak_idx = max(range(len(seasons)), key=lambda i: (cze_n[i], -i))
    low_idx = min(range(len(seasons)), key=lambda i: (cze_n[i], i))
    cze_peak = {"season": seasons[peak_idx], "n": cze_n[peak_idx]}
    cze_low = {"season": seasons[low_idx], "n": cze_n[low_idx]}

    golden_idx = sorted(range(len(seasons)), key=lambda i: (-cze_n[i], seasons[i]))[:3]
    golden = []
    for i in golden_idx:
        season = seasons[i]
        cze_season = history[(history["season"] == season) & (history["nation"] == "CZE")]
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
    """One matplotlib SVG: Czech `n` (thick navy, peak/low/last annotated)
    against the eight peers (thin grey, DEN/CRO mid-tone and labelled at the
    right edge) above a shared-x panel of `per_million` for CZE/DEN/CRO."""
    seasons = series["seasons"]
    years = [int(s[:4]) for s in seasons]
    countries = series["countries"]

    fig, (ax_n, ax_pm) = plt.subplots(
        2, 1, figsize=(11, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]},
    )
    fig.patch.set_facecolor(CREAM)

    for code, data in countries.items():
        if code == "CZE":
            continue
        color = MUTED if code in MID_TONE_COUNTRIES else "#d4cfc3"
        lw = 1.4 if code in MID_TONE_COUNTRIES else 1.0
        ax_n.plot(years, data["n"], color=color, lw=lw, zorder=2)
        if code in MID_TONE_COUNTRIES:
            ax_n.annotate(
                code, xy=(years[-1], data["n"][-1]), xytext=(6, 0),
                textcoords="offset points", fontsize=9, fontfamily="sans-serif",
                color=color, va="center",
            )

    cze_n = countries["CZE"]["n"]
    ax_n.plot(years, cze_n, color=NAVY, lw=2.6, zorder=5, label="Czechia")

    peak, low = series["cze_peak"], series["cze_low"]
    last_season, last_n = seasons[-1], cze_n[-1]
    for point, marker_color, dy in (
        (peak, OXBLOOD, 12),
        (low, OXBLOOD, -16),
        ({"season": last_season, "n": last_n}, NAVY, 12),
    ):
        x = int(point["season"][:4])
        ax_n.scatter([x], [point["n"]], color=marker_color, s=28, zorder=6)
        ax_n.annotate(
            f"{season_label(point['season'])}: {point['n']}", xy=(x, point["n"]),
            xytext=(0, dy), textcoords="offset points", ha="center",
            fontsize=9.5, fontfamily="sans-serif", color=INK, weight="medium",
        )

    ax_n.set_ylabel("Players (≥ 450 min)", fontsize=10, fontfamily="sans-serif", color=INK)
    ax_n.tick_params(axis="both", colors=INK, labelsize=9)
    for spine in ("top", "right"):
        ax_n.spines[spine].set_visible(False)

    for code in ("CZE", "DEN", "CRO"):
        if code not in countries:
            continue
        color = NAVY if code == "CZE" else MUTED
        lw = 2.2 if code == "CZE" else 1.4
        ax_pm.plot(years, countries[code]["per_million"], color=color, lw=lw, label=code)
        ax_pm.annotate(
            code, xy=(years[-1], countries[code]["per_million"][-1]), xytext=(6, 0),
            textcoords="offset points", fontsize=9, fontfamily="sans-serif",
            color=color, va="center",
        )

    ax_pm.set_ylabel("Per million population", fontsize=10, fontfamily="sans-serif", color=INK)
    ax_pm.set_xlabel("Season start year", fontsize=10, fontfamily="sans-serif", color=INK)
    ax_pm.tick_params(axis="both", colors=INK, labelsize=9)
    for spine in ("top", "right"):
        ax_pm.spines[spine].set_visible(False)

    fig.suptitle(
        f"Czech players in the Big-5 leagues, {season_label(seasons[0])} → {season_label(seasons[-1])}",
        fontsize=15, fontfamily="serif", color=INK, x=0.02, ha="left", y=0.98, weight="normal",
    )
    plt.subplots_adjust(top=0.92, hspace=0.12)
    plt.savefig(out_path, bbox_inches="tight", format="svg", facecolor=CREAM, edgecolor="none")
    plt.close(fig)
    LOG.info("wrote %s", out_path)


def main() -> None:
    logging_setup()
    config.ensure_dirs()

    history = read_parquet(config.PROCESSED_DIR / "big5_history.parquet")
    peers = config.countries()["peers"]
    series = build_series(history, peers)

    out_json = config.PROCESSED_DIR / "big5_series.json"
    out_json.write_text(json.dumps(series, ensure_ascii=False, indent=1), encoding="utf-8")
    LOG.info("wrote %s", out_json)

    render_series(series, config.OUTPUTS_DIR / "big5_series.svg")

    peak, low = series["cze_peak"], series["cze_low"]
    last_season = series["seasons"][-1]
    last_n = series["countries"]["CZE"]["n"][-1]
    LOG.info(
        "CZE peak %s (%d), low %s (%d), last %s (%d)",
        peak["season"], peak["n"], low["season"], low["n"], last_season, last_n,
    )


if __name__ == "__main__":
    main()
