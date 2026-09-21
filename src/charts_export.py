"""Data for the page's interactive charts -> outputs/<nation>/charts/*.json.

The static SVG figures stay (they are the print fallback and what a reader
without scripts sees). This writes, from the same processed tables, the
compact JSON that `docs/charts.js` draws the interactive versions from:

    atlas_<FW|MF|DF>.json   every metrics-season player-season of the
                            position group: both projections' coordinates,
                            both cluster ids, and what a tooltip needs
    big5.json               the Big-5 series for every country, the dated
                            break and the forecast (from series_model.json)
    export_age.json         the age-at-export curve with its band, and the
                            home nation's exports as points
    changes.json            season_changes.json plus the full tier-to-tier
                            flows with names, for the Sankey
    clusters.json           the descriptive cluster labels per group and
                            projection, and each cluster's medians

Nothing here computes a statistic; every number is read from a table or a
JSON an earlier stage wrote.
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from src import config
from src.pool_table import _tier
from src.season_changes import GROUPS as CHANGE_GROUPS
from src.season_changes import classify
from src.utils import read_parquet

LOG = logging.getLogger(__name__)
GROUPS = ("FW", "MF", "DF")


def _r(x, nd=3):
    return None if x is None or pd.isna(x) else round(float(x), nd)


def atlas_points(coords: pd.DataFrame, feats: pd.DataFrame, season: str, cfg: dict) -> list[dict]:
    """One record per player-season row of the metrics season."""
    c = coords[coords.season == season].copy()
    f = feats[feats.season == season][["league", "team", "player_key", "age", "npg_p90_quality", "ast_p90_quality", "min_share"]]
    c = c.merge(f, on=["league", "team", "player_key"], how="left")
    headline, stepping, domestic = cfg["headline"], cfg["stepping_stone"], config.DOMESTIC_LEAGUE
    out = []
    for r in c.itertuples():
        out.append({
            "k": r.player_key, "n": r.player, "lg": r.league, "t": r.team,
            "x": _r(r.pc1_style), "y": _r(r.pc2_style), "qx": _r(r.pc1_quality), "qy": _r(r.pc2_quality),
            "c": r.cluster_style, "cq": r.cluster_quality,
            "h": int(bool(r.home_eligible)), "nt": int(bool(r.nt_flag)),
            "m": int(r.min), "a": None if pd.isna(r.age) else int(r.age),
            "q": _r((r.npg_p90_quality or 0) + (r.ast_p90_quality or 0)),
            "ms": _r(r.min_share, 2),
            "tier": _tier(r.league, headline, stepping, domestic),
        })
    return out


def clusters_payload(summary: pd.DataFrame, labels: dict) -> dict:
    out: dict = {}
    for r in summary.itertuples():
        out.setdefault(r.position, {}).setdefault(r.projection, {})[r.cluster] = {
            "label": labels.get(r.position, {}).get(r.projection, {}).get(r.cluster, r.cluster),
            "n": int(r.n), "top_leagues": r.top_leagues,
            "median_q": _r((r.median_npg_p90_quality or 0) + (r.median_ast_p90_quality or 0)),
            "median_min_share": _r(r.median_min_share, 2), "median_age": _r(r.median_age, 1),
        }
    return out


def big5_payload(big5: dict, series_model: dict, names: dict[str, str]) -> dict:
    return {
        "seasons": big5["seasons"],
        "countries": {c: {"name": names.get(c, c), "n": v["n"], "per_million": v["per_million"]}
                      for c, v in big5["countries"].items()},
        "home": config.HOME,
        "contrast": list(config.nation().get("series_contrast", [])),
        "break": (series_model.get("break") or {}).get("top", [])[:1],
        "forecast": series_model.get("forecast", {}),
    }


def export_age_payload(eam: dict, feats: pd.DataFrame, cfg: dict) -> dict:
    """The fitted curve and the home nation's own export points: each
    home-eligible player's first season in a headline league (age then, and
    his league-adjusted G+A per 90 over that season)."""
    headline = set(cfg["headline"])
    f = feats[feats.home_eligible & feats.league.isin(headline)].sort_values("season")
    first = f.drop_duplicates("player_key", keep="first")
    pts = [{"n": r.player, "k": r.player_key, "age": int(r.age), "q": _r((r.npg_p90_quality or 0) + (r.ast_p90_quality or 0)),
            "season": r.season, "lg": r.league}
           for r in first.itertuples() if not pd.isna(r.age)]
    return {"curve": eam.get("age_curve", []), "y21_24": {"y24": eam.get("y24"), "diff": eam.get("diff_21_24")},
            "points": pts, "home_median_age": eam.get("home_median_age"), "n": eam.get("n")}


def changes_payload(sc: dict, feats: pd.DataFrame, cfg: dict, seasons: dict) -> dict:
    moves = classify(feats, seasons["previous"], seasons["metrics"], config.features()["min_minutes"],
                     cfg["headline"], cfg["stepping_stone"], config.DOMESTIC_LEAGUE)
    moves["src"] = moves.tier_prev.fillna("entered")
    moves["dst"] = moves.tier_curr.fillna("left")
    flows = []
    for (src, dst), g in moves.groupby(["src", "dst"]):
        flows.append({"src": src, "dst": dst, "n": int(len(g)),
                      "names": sorted(g.player.tolist(), key=str.lower)})
    return sc | {"flows": flows}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p, cfg, seasons = config.PROCESSED_DIR, config.leagues(), config.seasons()
    out_dir = config.OUTPUTS_DIR / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    countries = config.countries()
    names = {c: v["name"] for section in countries.values() if isinstance(section, dict)
             for c, v in section.items() if isinstance(v, dict) and "name" in v}

    feats_all = pd.concat([read_parquet(p / f"features_{g}.parquet") for g in GROUPS], ignore_index=True)
    for g in GROUPS:
        coords = read_parquet(p / f"coords_{g}.parquet")
        feats = read_parquet(p / f"features_{g}.parquet")
        (out_dir / f"atlas_{g}.json").write_text(json.dumps(
            {"group": g, "season": seasons["metrics"], "points": atlas_points(coords, feats, seasons["metrics"], cfg)},
            separators=(",", ":"), ensure_ascii=False))
    (out_dir / "clusters.json").write_text(json.dumps(
        clusters_payload(read_parquet(p / "cluster_summary.parquet"), config.cluster_labels()), ensure_ascii=False))

    def load(name):
        f = p / name
        return json.loads(f.read_text()) if f.exists() else {}
    (out_dir / "big5.json").write_text(json.dumps(big5_payload(load("big5_series.json"), load("series_model.json"), names)))
    (out_dir / "export_age.json").write_text(json.dumps(export_age_payload(load("export_age_model.json"), feats_all, cfg), ensure_ascii=False))
    (out_dir / "changes.json").write_text(json.dumps(changes_payload(load("season_changes.json"), feats_all, cfg, seasons), ensure_ascii=False))
    LOG.info("charts written to %s", out_dir)


if __name__ == "__main__":
    main()
