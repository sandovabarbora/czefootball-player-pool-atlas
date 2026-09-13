"""Render the English report of the Czech football player pool atlas.

Reads only `data/processed/*`, `config/*.yaml`, `site/players.json` and
`outputs/intl_cohort_heatmap.svg` (Task 8); never touches the network.

Output:
  outputs/atlas_FW.svg, outputs/atlas_MF.svg, outputs/atlas_DF.svg
  outputs/index.html          (full report, English)
  outputs/style.css           (copy of templates/style.css)

Every number in the report comes from the template context built here;
the template types only years, K = 10 and the ±20 % of the sensitivity
scenarios. `build_context_from_fixtures()` returns a small hand-written
context so the template test runs offline.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import shutil
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Environment, FileSystemLoader

from src import config
from src.logging_setup import setup as logging_setup
from src.utils import normalize_name, read_parquet

matplotlib.use("Agg")

LOG = logging.getLogger(__name__)

GROUPS = ["FW", "MF", "DF"]
GROUP_TITLES = {"FW": "Forwards", "MF": "Midfielders", "DF": "Defenders"}
COHORT_ORDER = ["U22", "23-25", "26-29", "30+"]
COHORT_COUNTRIES = ["CZE", "DEN", "CRO", "AUT", "SUI"]
TIER_ORDER = ["domestic", "stepping_stone", "top9", "other"]
TIER_LABELS = {
    "domestic": "domestic league",
    "stepping_stone": "stepping-stone league",
    "top9": "top-9 league",
    "other": "other covered league",
}
ORIGIN_LABELS = {
    "domestic": "domestic",
    "stepping_stone": "stepping stone",
    "other_top9": "other top-9",
    "not_covered": "not covered",
}
ORIGIN_ORDER = ["domestic", "stepping_stone", "other_top9", "not_covered"]
NT_LABEL = "NT 2024–26"
CARD_ANALOGS = 3
CLUSTER_TOP_N = 5
ATLAS_NAMES_N = 10
MOVERS_N = 5
SITE_PLAYERS = config.ROOT_DIR / "site" / "players.json"

# Palette aligned with templates/style.css (OKLCH tokens converted to sRGB hex
# for matplotlib). Navy load-bearing, oxblood for highlights, warm neutrals.
NAVY = "#1f3a5f"
NAVY_SOFT = "#7e8eaa"
OXBLOOD = "#9c3a2a"
INK = "#2a261f"
MUTED = "#8a857b"
RULE = "#c8c2b7"
CREAM = "#fdfbf6"

# Curated cluster palette: navy variants + warm earth tones. OXBLOOD is
# reserved for NT rings and the CZE row highlight.
CLUSTER_PALETTE = [
    NAVY,
    NAVY_SOFT,
    "#b08968",  # warm tan
    "#7a5c63",  # rose brown
    "#5e7e64",  # sage mute
    "#7e6678",  # plum mute
    "#3d6b6e",  # deep teal
    "#806b53",  # umber dark
]

plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Spectral", "Cambria", "Georgia", "Times New Roman", "DejaVu Serif"]
plt.rcParams["font.sans-serif"] = ["Bricolage Grotesque", "Helvetica Neue", "Arial", "DejaVu Sans"]
plt.rcParams["axes.edgecolor"] = RULE
plt.rcParams["axes.labelcolor"] = MUTED
plt.rcParams["xtick.color"] = MUTED
plt.rcParams["ytick.color"] = MUTED
plt.rcParams["text.color"] = INK


# =============================================================================
# Small helpers
# =============================================================================


def season_label(season: str) -> str:
    """'2024-2025' -> '2024/25'."""
    start, end = season.split("-")
    return f"{start}/{end[-2:]}"


def _last_name(name: str) -> str:
    return str(name).split()[-1] if str(name).strip() else ""


def _cluster_id(label: object) -> int:
    """'C3' -> 3; -1 when missing."""
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return -1
    return int(str(label).lstrip("C"))


def _opt_float(value: object, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _opt_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _same_club(a: str, b: str) -> bool:
    """FBref's table and country-page club names differ in suffixes ('West Ham' vs
    'West Ham United'); treat one containing the other as the same club."""
    x, y = normalize_name(a), normalize_name(b)
    return bool(x) and bool(y) and (x in y or y in x)


def _metrics_rows(frame: pd.DataFrame, season: str) -> pd.DataFrame:
    """One row per player in `season`: the club where they played most.

    Works for the features and the coords frames alike (both carry
    `player_key`, `season`, `min`); a mid-season transfer otherwise appears
    twice on the atlas and in the cluster lists.
    """
    cur = frame[frame["season"] == season]
    return cur.sort_values("min", ascending=False).drop_duplicates("player_key")


# =============================================================================
# Figures
# =============================================================================


def _render_atlas(coords: pd.DataFrame, features: pd.DataFrame, group: str,
                  season: str, out_path: Path) -> dict[str, int]:
    """Two-panel atlas (style / quality) for one position group.

    The whole 2024/25 corpus is drawn as a rasterised grey background; the
    Czech-eligible players are vector points coloured by cluster, with
    oxblood rings for the national-team flag and the top Czech names by
    quality-adjusted npG+A per 90 annotated. Returns counts for the caption.
    """
    cur = _metrics_rows(coords, season).copy()
    feat = _metrics_rows(features, season)[
        ["player_key", "npg_p90_quality", "ast_p90_quality"]
    ]
    cur = cur.merge(feat, on="player_key", how="left")
    cur["q"] = cur["npg_p90_quality"].fillna(0) + cur["ast_p90_quality"].fillna(0)
    cz = cur[cur["czech_eligible"]].copy()

    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(13, 6.5))
    fig.patch.set_facecolor(CREAM)
    for ax, proj, title in (
        (ax_left, "style", "Style map (no league multipliers)"),
        (ax_right, "quality", "Quality-adjusted map"),
    ):
        x_col, y_col, c_col = f"pc1_{proj}", f"pc2_{proj}", f"cluster_{proj}"
        bg = cur.dropna(subset=[x_col, y_col])
        ax.scatter(bg[x_col], bg[y_col], s=7, c=MUTED, alpha=0.28, linewidths=0,
                   rasterized=True, zorder=1, label="corpus")
        sub = cz.dropna(subset=[x_col, y_col]).copy()
        sub["cid"] = sub[c_col].map(_cluster_id)
        for cid in sorted(sub["cid"].unique()):
            color = CLUSTER_PALETTE[cid % len(CLUSTER_PALETTE)] if cid >= 0 else MUTED
            m = sub["cid"] == cid
            coll = ax.scatter(sub.loc[m, x_col], sub.loc[m, y_col], s=26, c=color, alpha=0.9,
                              edgecolors=CREAM, linewidths=0.55, zorder=4,
                              label=f"C{cid}" if cid >= 0 else "—")
            coll.set_gid(f"{group}-{proj}-C{cid}")
        nt = sub[sub["nt_flag"]]
        ring = ax.scatter(nt[x_col], nt[y_col], s=95, facecolors="none", edgecolors=OXBLOOD,
                          linewidths=1.35, alpha=0.9, zorder=5, label=NT_LABEL)
        ring.set_gid(f"{group}-{proj}-nt")
        for _, row in sub.nlargest(ATLAS_NAMES_N, "q").iterrows():
            ax.annotate(_last_name(row["player"]), (row[x_col], row[y_col]),
                        xytext=(3, 3), textcoords="offset points", fontsize=7,
                        color=INK, zorder=10)
        ax.set_title(title, fontsize=11.5, fontfamily="serif", color=INK, pad=12, loc="left")
        ax.set_xlabel("PC1", fontsize=8.5, color=MUTED, fontfamily="sans-serif")
        ax.set_ylabel("PC2", fontsize=8.5, color=MUTED, fontfamily="sans-serif")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(RULE)
        ax.tick_params(colors=MUTED, labelsize=8)
        ax.set_facecolor(CREAM)
        leg = ax.legend(loc="lower right", fontsize=7.5, frameon=False, labelcolor=INK)
        for txt in leg.get_texts():
            txt.set_fontfamily("sans-serif")

    fig.suptitle(f"Czech football · {GROUP_TITLES[group]} {season_label(season)}",
                 fontsize=14, fontfamily="serif", color=INK, y=1.02, x=0.02, ha="left",
                 weight="normal")
    fig.text(
        0.02, -0.025,
        f"PCA of the five-feature vector (npG/90, A/90, minutes share, age, cards/90), "
        f"{season_label(season)}. Grey: the whole corpus (n = {len(cur)}); coloured: "
        f"Czech-eligible players by cluster (n = {len(cz)}). Oxblood rings: national-team "
        f"call-up 2024–26.",
        ha="left", fontsize=8.2, color=MUTED, fontfamily="sans-serif",
    )
    plt.tight_layout()
    plt.savefig(out_path, bbox_inches="tight", format="svg", dpi=160)
    plt.close(fig)
    LOG.info("wrote %s", out_path)
    return {"n_corpus": int(len(cur)), "n_czech": int(len(cz)),
            "n_nt": int(cz["nt_flag"].sum())}


# =============================================================================
# Context builders (pure functions over the loaded frames)
# =============================================================================


def _build_per_capita(pc: pd.DataFrame) -> list[dict]:
    return [
        {
            "country": r.country, "name": r.name, "n_players": int(r.n_players),
            "population_m": float(r.population_m), "per_million": float(r.per_million),
            "rank": int(r.rank),
        }
        for r in pc.sort_values("rank").itertuples()
    ]


def _build_cohorts(coh: pd.DataFrame, countries: list[str]) -> dict[str, list[dict]]:
    """group -> [{cohort, cells: {country: {n, median}}}] for the shown countries."""
    out: dict[str, list[dict]] = {}
    for group in GROUPS:
        rows = []
        for cohort in COHORT_ORDER:
            cells: dict[str, dict] = {}
            for country in countries:
                cell = coh[(coh.country == country) & (coh.pos_group == group) & (coh.cohort == cohort)]
                if cell.empty:
                    cells[country] = {"n": 0, "median": None}
                else:
                    cells[country] = {"n": int(cell.iloc[0]["n"]),
                                      "median": float(cell.iloc[0]["median_npg_ast_p90"])}
            rows.append({"cohort": cohort, "cells": cells})
        out[group] = rows
    return out


def _cohort_gaps(coh: pd.DataFrame, peers: list[str]) -> list[dict]:
    """CZE n minus the median n of the other peers per (group, cohort); largest shortfall first.

    Same zero-filling rule as international_benchmark.build_narrative: a peer
    without a row in a cohort has 0 qualifying players there.
    """
    others = [c for c in peers if c != "CZE"]
    gaps = []
    for group in GROUPS:
        for cohort in COHORT_ORDER:
            g = coh[(coh.pos_group == group) & (coh.cohort == cohort)]
            n_by_country = g.set_index("country")["n"] if not g.empty else pd.Series(dtype=int)
            cze_n = int(n_by_country.get("CZE", 0))
            peer_median = float(pd.Series([int(n_by_country.get(c, 0)) for c in others]).median())
            gaps.append({
                "pos_group": group, "group_title": GROUP_TITLES[group], "cohort": cohort,
                "cze_n": cze_n, "peer_median_n": peer_median, "gap": cze_n - peer_median,
            })
    return sorted(gaps, key=lambda r: (r["gap"], r["pos_group"], r["cohort"]))


def _build_clusters(coords: pd.DataFrame, features: pd.DataFrame, labels: dict,
                    group: str, season: str) -> list[dict]:
    """Style-projection cluster archetypes for one group."""
    cur = _metrics_rows(coords, season).copy()
    feat = _metrics_rows(features, season)[
        ["player_key", "npg_p90_shrunk", "ast_p90_shrunk", "min_share", "age", "cards_p90_shrunk"]
    ]
    cur = cur.merge(feat, on="player_key", how="left")
    style_labels = labels.get(group, {}).get("style", {})
    tactical = labels.get("tactical", {}).get(group, {})
    rows = []
    for cid in sorted(cur["cluster_style"].dropna().map(_cluster_id).unique()):
        key = f"C{cid}"
        members = cur[cur["cluster_style"] == key]
        cz = members[members["czech_eligible"]].sort_values("min", ascending=False)
        rows.append({
            "id": key,
            "label": style_labels.get(key, f"Cluster {key}"),
            "n": int(len(cz)),
            "n_corpus": int(len(members)),
            "nt_pool": int(cz["nt_flag"].sum()),
            "median_born": _opt_int(cz["born"].median()) if len(cz) else None,
            "medians": {
                "npg_p90": _opt_float(members["npg_p90_shrunk"].median()),
                "ast_p90": _opt_float(members["ast_p90_shrunk"].median()),
                "min_share": _opt_float(members["min_share"].median(), 3),
                "age": _opt_float(members["age"].median(), 0),
                "cards_p90": _opt_float(members["cards_p90_shrunk"].median()),
            },
            "tactical": (tactical.get(key) or {}).get("en", ""),
            "top": cz["player"].head(CLUSTER_TOP_N).tolist(),
            "top_keys": cz["player_key"].head(CLUSTER_TOP_N).tolist(),
        })
    return rows


def _build_movers(traj: pd.DataFrame, n: int = MOVERS_N) -> dict[str, list[dict]]:
    """Czech-eligible movers up / down by quality-adjusted npG+A per 90 delta."""
    if traj.empty:
        return {"up": [], "down": [], "n_czech": 0, "directions": {}}
    cz = traj[traj["czech_eligible"]]

    def _row(r) -> dict:
        return {
            "player_key": r.player_key, "name": r.player, "league": r.league,
            "min_prev": int(r.min_prev), "min_curr": int(r.min_curr),
            "prev": round(float(r.npg_ast_quality_prev), 3),
            "curr": round(float(r.npg_ast_quality_curr), 3),
            "delta": round(float(r.delta), 3), "direction": r.direction,
        }

    up = cz[cz["direction"] == "improving"].nlargest(n, "delta")
    down = cz[cz["direction"] == "declining"].nsmallest(n, "delta")
    directions = {k: int(v) for k, v in cz["direction"].value_counts().items()}
    return {
        "up": [_row(r) for r in up.itertuples()],
        "down": [_row(r) for r in down.itertuples()],
        "n_czech": int(len(cz)),
        "directions": {d: directions.get(d, 0) for d in ("improving", "stable", "declining")},
    }


def _analog_row(a: dict) -> dict:
    return {
        "rank": int(a["rank"]), "player_key": a["player_key"], "name": a["player"],
        "nation": a["nation"], "league": a["league"], "season": season_label(a["season"]),
        "min": int(a["min"]), "npg_ast_q": round(float(a["npg_ast_q"]), 2),
        "distance": round(float(a["distance"]), 2),
        "followed": [
            {"season": season_label(f["season"]), "league": f["league"], "min": int(f["min"]),
             "npg_ast_q": round(float(f["npg_ast_q"]), 2)}
            for f in a.get("followed", [])
        ],
    }


def _build_analog_blocks(showcase: list[dict], analogs: dict) -> list[dict]:
    blocks = []
    for s in showcase:
        block = analogs.get(s["player_key"])
        if not block:
            continue
        t = block["target"]
        blocks.append({
            "player_key": s["player_key"], "pos_group": s["pos_group"],
            "target": {
                "name": t["name"], "age": int(t["age"]), "league": t["league"],
                "season": season_label(t["season"]), "min": int(t["min"]),
                "npg_ast_q": round(float(t["npg_ast_q"]), 2),
            },
            "analogs": [_analog_row(a) for a in block["analogs"]],
        })
    return blocks


def _build_cards(showcase: list[dict], analogs: dict, features: dict[str, pd.DataFrame],
                 coords: dict[str, pd.DataFrame], traj: dict[str, pd.DataFrame],
                 pool: pd.DataFrame, labels: dict, photos: dict, season: str) -> list[dict]:
    """One card per showcase player: stats, clusters, tactical read, trajectory, analogs."""
    pool_by_key = pool.drop_duplicates("player_key").set_index("player_key")
    photos_by_key = {v["player_key"]: dict(v, fbref_id=k) for k, v in photos.items()}
    cards = []
    for s in showcase:
        key, group = s["player_key"], s["pos_group"]
        feat = _metrics_rows(features[group], season)
        feat = feat[feat["player_key"] == key]
        co = _metrics_rows(coords[group], season)
        co = co[co["player_key"] == key]
        if feat.empty or co.empty:
            LOG.warning("card: missing data for %s", s["player"])
            continue
        f, c = feat.iloc[0], co.iloc[0]
        p = pool_by_key.loc[key] if key in pool_by_key.index else None
        style_id, quality_id = str(c["cluster_style"]), str(c["cluster_quality"])
        style_labels = labels.get(group, {}).get("style", {})
        quality_labels = labels.get(group, {}).get("quality", {})
        tactical = labels.get("tactical", {}).get(group, {}).get(style_id) or {}
        tr = traj[group]
        tr = tr[tr["player_key"] == key] if not tr.empty else tr
        trajectory = None
        if not tr.empty:
            r = tr.iloc[0]
            trajectory = {
                "delta": round(float(r["delta"]), 3), "direction": str(r["direction"]),
                "min_prev": int(r["min_prev"]), "min_curr": int(r["min_curr"]),
                "prev": round(float(r["npg_ast_quality_prev"]), 2),
                "curr": round(float(r["npg_ast_quality_curr"]), 2),
            }
        club_current = str(p["club_current"]) if p is not None and p["club_current"] else ""
        block = analogs.get(key) or {}
        analog_age = _opt_int((block.get("target") or {}).get("age"))
        nt_events = [e for e in str(f.get("nt_events") or "").split(" · ") if e]
        photo = photos_by_key.get(key)
        cards.append({
            "player_key": key,
            "fbref_id": str(p["fbref_id"]) if p is not None else "",
            "name": str(f["player"]),
            "pos": group,
            "pos_title": GROUP_TITLES[group],
            "born": _opt_int(f["born"]),
            "age": _opt_int(f["age"]),
            "league": str(f["league"]),
            "club_season": str(f["team"]),
            "club": club_current,
            "moved": bool(club_current) and not _same_club(str(f["team"]), club_current),
            "nt_flag": bool(f["nt_flag"]),
            "nt_events": nt_events,
            "reason": s["reason"],
            "stats": {
                "npg_ast_q": round(float(f["npg_p90_quality"] + f["ast_p90_quality"]), 2),
                "npg_p90": round(float(f["npg_p90"]), 2),
                "ast_p90": round(float(f["ast_p90"]), 2),
                "min": int(f["min"]),
                "min_share": round(float(f["min_share"]), 2),
                "npg": int(f["npg"]),
                "ast": int(f["ast"]),
            },
            "clusters": {
                "style": {"id": style_id, "label": style_labels.get(style_id, style_id)},
                "quality": {"id": quality_id, "label": quality_labels.get(quality_id, quality_id)},
            },
            "tactical": tactical.get("en", ""),
            "trajectory": trajectory,
            "analog_age": analog_age,
            "analogs": [_analog_row(a) for a in block.get("analogs", [])[:CARD_ANALOGS]],
            "photo": ({"image": photo["image"], "credit": photo["credit"],
                       "license": photo["license"]} if photo else None),
        })
    return cards


def _build_pathways(pw: dict, names: dict[str, str], peers: list[str]) -> dict:
    youth = []
    for r in pw.get("youth_exposure", []):
        has = r.get("share_u21") is not None
        youth.append({
            "league": r["league"], "country": r["country"], "name": names.get(r["country"], r["country"]),
            "minutes_total": int(r.get("minutes_total") or 0),
            "share_u21": round(float(r["share_u21"]), 3) if has else None,
            "share_u23": round(float(r["share_u23"]), 3) if r.get("share_u23") is not None else None,
        })
    youth.sort(key=lambda r: (r["share_u21"] is None, -(r["share_u21"] or 0)))

    export = []
    for r in pw.get("export_route", []):
        shares = r.get("origin_shares", {})
        export.append({
            "country": r["country"], "name": names.get(r["country"], r["country"]),
            "n": int(r["n"]), "n_recent": int(r["n_recent"]),
            "median_export_age": _opt_float(r.get("median_export_age"), 1),
            "median_export_age_recent": _opt_float(r.get("median_export_age_recent"), 1),
            "origin": {k: round(float(shares.get(k) or 0), 3) for k in ORIGIN_ORDER},
            "censored_share": round(float(r.get("censored_share") or 0), 3),
        })
    rank = {c: i for i, c in enumerate(peers)}
    export.sort(key=lambda r: rank.get(r["country"], 99))

    fare_rows = pw.get("fare", [])
    fare_min = sorted(
        [{"country": r["country"], "name": names.get(r["country"], r["country"]), "n": int(r["n"]),
          "value": round(float(r["median_min_share"]), 3)} for r in fare_rows],
        key=lambda r: -r["value"])
    fare_goals = sorted(
        [{"country": r["country"], "name": names.get(r["country"], r["country"]), "n": int(r["n"]),
          "value": round(float(r["median_club_goals_pct"]), 3)} for r in fare_rows],
        key=lambda r: -r["value"])
    proxy = fare_rows[0]["club_strength_proxy"] if fare_rows else ""

    prof = pd.DataFrame(pw.get("profile", []))
    profile = []
    if not prof.empty:
        for tier in TIER_ORDER:
            for group in GROUPS:
                sub = prof[(prof.tier == tier) & (prof.pos_group == group)]
                if sub.empty:
                    continue
                cze = sub[sub.country == "CZE"]
                others = sub[sub.country != "CZE"]
                profile.append({
                    "tier": tier, "tier_label": TIER_LABELS.get(tier, tier), "pos_group": group,
                    "cze_n": int(cze.iloc[0]["n"]) if not cze.empty else 0,
                    "cze_median": _opt_float(cze.iloc[0]["median_npg_ast_q"]) if not cze.empty else None,
                    "peer_median_n": _opt_float(others["n"].median(), 1) if not others.empty else None,
                    "peer_median": _opt_float(others["median_npg_ast_q"].median()) if not others.empty else None,
                    "peer_countries": int(others["country"].nunique()),
                })

    def _find(rows: list[dict], country: str) -> dict | None:
        return next((r for r in rows if r["country"] == country), None)

    return {
        "youth": youth, "export": export, "fare_min": fare_min, "fare_goals": fare_goals,
        "club_strength_proxy": proxy, "profile": profile,
        "youth_cze": _find(youth, "CZE"), "youth_top": next((r for r in youth if r["share_u21"] is not None), None),
        "export_cze": _find(export, "CZE"), "export_den": _find(export, "DEN"),
        "fare_min_cze": _find(fare_min, "CZE"), "fare_goals_cze": _find(fare_goals, "CZE"),
        "fare_min_rank": next((i + 1 for i, r in enumerate(fare_min) if r["country"] == "CZE"), None),
        "fare_goals_rank": next((i + 1 for i, r in enumerate(fare_goals) if r["country"] == "CZE"), None),
        "youth_rank": next((i + 1 for i, r in enumerate(youth) if r["country"] == "CZE"), None),
        "n_countries": len(peers),
    }


def _build_loadings(loadings: pd.DataFrame) -> list[dict]:
    rows = []
    for r in loadings.itertuples():
        rows.append({
            "position": r.position, "projection": r.projection, "pc": r.pc,
            "explained_pct": round(float(r.explained_variance) * 100, 1),
            "npg_p90": round(float(r.npg_p90), 3), "ast_p90": round(float(r.ast_p90), 3),
            "min_share": round(float(r.min_share), 3), "age": round(float(r.age), 3),
            "cards_p90": round(float(r.cards_p90), 3),
        })
    order = {g: i for i, g in enumerate(GROUPS)}
    rows.sort(key=lambda r: (order.get(r["position"], 9), r["projection"] != "style", r["pc"]))
    return rows


def _build_sensitivity(sens: pd.DataFrame) -> dict:
    rows = [
        {"scenario": r.scenario, "description": r.description, "overlap": int(r.top10_overlap),
         "churn": int(r.top10_churn), "mean_delta": round(float(r.mean_delta_rank_top20), 2)}
        for r in sens.itertuples()
    ]
    base = next((r for r in rows if r["scenario"] == "baseline"), rows[0] if rows else None)
    worst = max(rows, key=lambda r: (r["churn"], r["mean_delta"])) if rows else None
    return {
        "rows": rows,
        "n_scenarios": len(rows),
        "baseline_top10": base["overlap"] if base else 0,
        "n_zero_churn": sum(1 for r in rows if r["churn"] == 0),
        "max_churn": worst["churn"] if worst else 0,
        "worst": worst,
    }


def _build_limitations(facts: dict) -> list[dict]:
    """Limitations from spec §10 and the pipeline ledger; numbers from `facts`."""
    f = facts
    return [
        {"title": "Leagues without metrics",
         "body": (f"FBref covers about forty competitions; the Czech second tier and the Slovak top "
                  f"flight are not among them. {f['n_no_tables']} of the {f['n_pool']} Czech "
                  f"professionals found on FBref's country page play in a league without season "
                  f"tables and carry no metrics; they are listed by name and club only. Slovakia's "
                  f"exhibits in chapter II therefore rest on its players abroad.")},
        {"title": "Free-tier feature set",
         "body": ("The feature vector is five basic columns per 90 minutes: non-penalty goals, "
                  "assists, minutes share, age and cards. No expected goals, no progressive passes, "
                  "no tackles — the rule was one identical vector across every league in the corpus, "
                  "and only the basic table is available for all of them. Defensive and creative "
                  "contributions beyond assists are invisible to the map.")},
        {"title": "National-team flag source",
         "body": (f"The flag \"called up since 2024\" is parsed from Wikipedia squad tables "
                  f"({f['nt_events']}) and matched on normalised name plus birth year. "
                  f"{f['n_nt_flagged']} of the {f['n_with_metrics']} mapped players carry it. A squad "
                  f"table edit or a name variant can drop a call-up; the flag is a tag, not a cap count.")},
        {"title": "Photo coverage",
         "body": (f"{f['n_photos']} of the {f['n_pool']} pool players have a Wikimedia Commons "
                  f"portrait (Wikidata P18, matched on name, citizenship and birth date, occupation "
                  f"filtered to association football player). Players without a photo show initials.")},
        {"title": "Season split",
         "body": (f"The headline per-capita count uses {f['current']} rosters; every metric, cohort "
                  f"table and atlas uses the complete {f['metrics']} season; trajectories run "
                  f"{f['previous']} → {f['metrics']}; the club on a card is the {f['current']} club. "
                  f"A player who moved in summer therefore appears with last season's numbers and this "
                  f"season's club.")},
        {"title": "League multipliers",
         "body": ("ClubElo was unreachable at run time, so the multipliers are UEFA association "
                  "coefficients scaled to the strongest league = 1.00, and second-tier leagues are "
                  "set to 0.6 × the first tier of the same country by assumption. The club-strength "
                  "proxy in chapter II is the club's goals-scored percentile within its league, not "
                  "an Elo rating. The sensitivity table shows how far a ±20 % error in any one "
                  "multiplier moves the Czech ranking.")},
        {"title": "Export origins from recent entrants only",
         "body": (f"The origin league of an export is known only when the season before the first "
                  f"top-9 season was fetched: {f['history_start']} onwards for the headline leagues, "
                  f"{f['coverage_start']} onwards for the peer domestic leagues. Origin shares and the "
                  f"recent export age are therefore computed over players whose first top-9 season is "
                  f"{f['metrics']} or {f['current']}; earlier entrants count towards the full export "
                  f"age but not the origin mix, and a first appearance already in {f['history_start']} "
                  f"is censored (the censored share is shown).")},
        {"title": "Player identity",
         "body": ("FBref's season tables carry no player id, so players are joined on normalised "
                  "name plus birth year across leagues and seasons; two players sharing both would "
                  "collapse into one. A mid-season transfer produces two club rows that are collapsed "
                  "into one minutes-weighted row before ranking.")},
        {"title": "Women's entries and the -ová heuristic",
         "body": ("FBref's country page mixes men's and women's competitions. Entries whose surname "
                  "ends in -ová were dropped from the pool; a woman with a different surname ending "
                  "would survive the filter, and a man with that ending would not.")},
        {"title": "No market values, no scouting",
         "body": ("Transfer fees, market values, video and scouting reports are outside the public "
                  "sources used here. The map describes statistical footprints and counts; selection "
                  "and development decisions require the federation's own data and expertise, which "
                  "this method does not have.")},
    ]


def _build_observations(hero: dict, per_capita: list[dict], gaps: list[dict],
                        movers: dict[str, dict], thresholds: dict, seasons: dict) -> list[dict]:
    """Three computed observations; every number comes from the data."""
    top = per_capita[0]
    cze = next(r for r in per_capita if r["country"] == "CZE")
    above = [r for r in per_capita if r["rank"] < cze["rank"]]
    below = [r for r in per_capita if r["rank"] > cze["rank"]]
    nearest_above = above[-1] if above else None
    obs1_body = (
        f"{cze['n_players']} Czech players on {seasons['current']} rosters of the nine strongest "
        f"leagues give {cze['per_million']:.2f} per million inhabitants, rank {cze['rank']} of "
        f"{len(per_capita)}. {top['name']} leads with {top['per_million']:.2f}, "
        f"{top['per_million'] / cze['per_million']:.1f} times the Czech density"
    )
    if nearest_above:
        obs1_body += (
            f"; {nearest_above['name']} sits one place above with {nearest_above['per_million']:.2f} "
            f"from {nearest_above['n_players']} players and a population "
            f"{cze['population_m'] / nearest_above['population_m']:.1f} times smaller"
        )
    obs1_body += ". " + (
        f"Below Czechia: {', '.join(r['name'] for r in below)}." if below else "No peer sits below."
    )

    g = gaps[:3]
    gap_text = "; ".join(
        f"{r['group_title'].lower()} {r['cohort']} — {r['cze_n']} Czech against a peer median of "
        f"{r['peer_median_n']:g}" for r in g
    )
    obs2_body = (
        f"Counting {seasons['metrics']} top-9 players by position group and age cohort and comparing "
        f"the Czech count with the median of the other eight peers, the three largest shortfalls are "
        f"{gap_text}. The cohort tables above show the medians behind the counts."
    )

    parts = []
    for group in GROUPS:
        m = movers[group]
        d = m["directions"]
        parts.append(f"{GROUP_TITLES[group].lower()} {m['n_czech']} ({d['improving']} up, "
                     f"{d['stable']} stable, {d['declining']} down)")
    n_total = sum(movers[g]["n_czech"] for g in GROUPS)
    n_stable = sum(movers[g]["directions"]["stable"] for g in GROUPS)
    obs3_body = (
        f"{n_total} Czech-eligible players had at least {thresholds['min_minutes']} minutes in both "
        f"{seasons['previous']} and {seasons['metrics']}: {'; '.join(parts)}. A move counts as up or "
        f"down when quality-adjusted npG+A per 90 changed by more than "
        f"{thresholds['direction']:.2f}; {n_stable} of {n_total} stayed within that band. These are "
        f"season-over-season deltas, not projections."
    )
    return [
        {"title": f"Per capita: rank {cze['rank']} of {len(per_capita)}", "body": obs1_body},
        {"title": f"The largest cohort gap: {g[0]['group_title'].lower()} {g[0]['cohort']}" if g else "Cohort gaps",
         "body": obs2_body},
        {"title": f"Trajectories {seasons['previous']} → {seasons['metrics']}: mostly stable", "body": obs3_body},
    ]


def _photo_credits(photos: dict, used_keys: set[str]) -> list[dict]:
    rows = [
        {"fbref_id": fid, "name": v["name"], "player_key": v["player_key"],
         "image": v["image"], "credit": v["credit"], "license": v["license"]}
        for fid, v in photos.items() if v["player_key"] in used_keys
    ]
    return sorted(rows, key=lambda r: _last_name(r["name"]).lower())


# =============================================================================
# Loading and orchestration
# =============================================================================


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        LOG.warning("missing %s", path)
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_parquet_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        LOG.warning("missing %s", path)
        return pd.DataFrame()
    return read_parquet(path)


def load_data() -> dict[str, Any]:
    """Load every processed input the report needs (no network)."""
    p = config.PROCESSED_DIR
    return {
        "per_capita": read_parquet(p / "per_capita.parquet"),
        "cohorts": read_parquet(p / "cohorts.parquet"),
        "features": {g: read_parquet(p / f"features_{g}.parquet") for g in GROUPS},
        "coords": {g: read_parquet(p / f"coords_{g}.parquet") for g in GROUPS},
        "trajectory": {g: _load_parquet_or_empty(p / f"trajectory_{g}.parquet") for g in GROUPS},
        "loadings": _load_parquet_or_empty(p / "pca_loadings.parquet"),
        "sensitivity": _load_parquet_or_empty(p / "sensitivity.parquet"),
        "pool": read_parquet(p / "pool.parquet"),
        "showcase": _load_json(p / "showcase.json", []),
        "analogs": _load_json(p / "analogs.json", {}),
        "pathways": _load_json(p / "pathways.json", {}),
        "photos": _load_json(SITE_PLAYERS, {}),
        "cluster_labels": config.load_yaml("cluster_labels.yaml"),
        "league_quality": config.league_quality(),
        "countries": config.countries()["peers"],
        "seasons": config.seasons(),
        "feature_defs": config.features(),
        "leagues": config.leagues(),
    }


def build_context(data: dict[str, Any], atlas_notes: dict[str, dict] | None = None) -> dict[str, Any]:
    """Assemble the template context from loaded data."""
    from src.trajectory import DIRECTION_THRESHOLD, MIN_MINUTES

    seasons_raw = data["seasons"]
    seasons = {
        "metrics": season_label(seasons_raw["metrics"]),
        "previous": season_label(seasons_raw["previous"]),
        "current": season_label(seasons_raw["current"]),
        "history_start": season_label(seasons_raw["history"][0]),
    }
    metrics = seasons_raw["metrics"]
    peers = list(data["countries"])
    names = {c: v["name"] for c, v in data["countries"].items()}

    per_capita = _build_per_capita(data["per_capita"])
    cze = next(r for r in per_capita if r["country"] == "CZE")
    cohorts = _build_cohorts(data["cohorts"], COHORT_COUNTRIES)
    gaps = _cohort_gaps(data["cohorts"], peers)

    clusters = {g: _build_clusters(data["coords"][g], data["features"][g], data["cluster_labels"], g, metrics)
                for g in GROUPS}
    movers = {g: _build_movers(data["trajectory"][g]) for g in GROUPS}
    analog_blocks = _build_analog_blocks(data["showcase"], data["analogs"])
    cards = _build_cards(data["showcase"], data["analogs"], data["features"], data["coords"],
                         data["trajectory"], data["pool"], data["cluster_labels"], data["photos"], metrics)
    pathways = _build_pathways(data["pathways"], names, peers)

    # Pool facts for the masthead and limitations
    pool = data["pool"]
    cz_cur = {g: _metrics_rows(data["features"][g], metrics) for g in GROUPS}
    cz_cur = {g: df[df["czech_eligible"]] for g, df in cz_cur.items()}
    n_with_metrics = sum(len(df) for df in cz_cur.values())
    n_nt_flagged = sum(int(df["nt_flag"].sum()) for df in cz_cur.values())
    nt_events = sorted({e for df in cz_cur.values() for s in df["nt_events"].dropna()
                        for e in str(s).split(" · ") if e})
    facts = {
        "n_pool": int(len(pool)),
        "n_no_tables": int((~pool["in_fbref_tables"]).sum()),
        "n_with_metrics": n_with_metrics,
        "n_nt_flagged": n_nt_flagged,
        "nt_events": ", ".join(nt_events),
        "n_photos": len(data["photos"]),
        "history_start": seasons["history_start"],
        "coverage_start": seasons["previous"],  # peer domestic leagues are fetched from here on
        **seasons,
    }

    thresholds = {"min_minutes": MIN_MINUTES, "direction": DIRECTION_THRESHOLD}
    hero = {
        "per_million": cze["per_million"], "rank": cze["rank"], "n_peers": len(per_capita),
        "n_players": cze["n_players"], "population_m": cze["population_m"],
        "top": per_capita[0],
        "gap": gaps[0] if gaps else None,
        "export_cze": pathways["export_cze"], "export_den": pathways["export_den"],
    }
    observations = _build_observations(hero, per_capita, gaps, movers, thresholds, seasons)

    lq = data["league_quality"]
    multipliers = sorted(
        [{"league": k, "value": float(v)} for k, v in lq["multipliers"].items()],
        key=lambda r: -r["value"])

    used_keys = {c["player_key"] for c in cards}
    for g in GROUPS:
        for c in clusters[g]:
            used_keys.update(c["top_keys"])
        used_keys.update(r["player_key"] for r in movers[g]["up"] + movers[g]["down"])

    return {
        "lang": "en",
        "seasons": seasons,
        "groups": GROUPS,
        "group_titles": GROUP_TITLES,
        "hero": hero,
        "per_capita": per_capita,
        "max_per_million": max(r["per_million"] for r in per_capita),
        "cohorts": cohorts,
        "cohort_countries": COHORT_COUNTRIES,
        "cohort_names": names,
        "cohort_gaps": gaps,
        "observations": observations,
        "clusters": clusters,
        "movers": movers,
        "thresholds": thresholds,
        "pathways": pathways,
        "cards": cards,
        "analog_blocks": analog_blocks,
        "atlas_notes": atlas_notes or {g: {"n_corpus": 0, "n_czech": 0, "n_nt": 0} for g in GROUPS},
        "multipliers": multipliers,
        "multiplier_source": str(lq.get("source", "")).strip(),
        "multiplier_method": str(lq.get("method", "")),
        "feature_defs": data["feature_defs"],
        "loadings": _build_loadings(data["loadings"]) if not data["loadings"].empty else [],
        "sensitivity": _build_sensitivity(data["sensitivity"]) if not data["sensitivity"].empty else _build_sensitivity(pd.DataFrame(columns=["scenario", "description", "top10_overlap", "top10_churn", "mean_delta_rank_top20"])),
        "limitations": _build_limitations(facts),
        "facts": facts,
        "n_leagues": len(data["leagues"]["headline"]) + 1 + len(data["leagues"]["peer_domestic"]) + 1,
        "headline_leagues": list(data["leagues"]["headline"]),
        "stepping_stone": list(data["leagues"].get("stepping_stone", [])),
        "seed": config.RANDOM_SEED,
        "photo_credits": _photo_credits(data["photos"], used_keys),
        "rendered_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "repo_url": "https://github.com/barborasandova/czefootball-player-pool-atlas",
    }


def build_context_from_fixtures() -> dict[str, Any]:
    """Small hand-written context so the template renders offline in tests.

    Two countries, one position group (FW), one card, one analog block, one
    pathways row per exhibit. Shapes mirror `build_context()`.
    """
    seasons = {"metrics": "2024/25", "previous": "2023/24", "current": "2025/26", "history_start": "2020/21"}
    per_capita = [
        {"country": "DEN", "name": "Denmark", "n_players": 59, "population_m": 5.96, "per_million": 9.9, "rank": 1},
        {"country": "CZE", "name": "Czechia", "n_players": 18, "population_m": 10.9, "per_million": 1.65, "rank": 2},
    ]
    gaps = [{"pos_group": "DF", "group_title": "Defenders", "cohort": "26-29", "cze_n": 1,
             "peer_median_n": 5.5, "gap": -4.5}]
    cohorts = {"FW": [{"cohort": c, "cells": {"CZE": {"n": 1, "median": 0.33}, "DEN": {"n": 0, "median": None}}}
                      for c in COHORT_ORDER]}
    clusters = {"FW": [{
        "id": "C0", "label": "High-volume scorers", "n": 3, "n_corpus": 314, "nt_pool": 1,
        "median_born": 1999,
        "medians": {"npg_p90": 0.26, "ast_p90": 0.06, "min_share": 0.601, "age": 25.0, "cards_p90": 0.14},
        "tactical": "Primary scorers on starter minutes.",
        "top": ["Patrik Schick", "Filip Vecheta"], "top_keys": ["patrik schick|1996", "filip vecheta|2003"],
    }]}
    movers = {"FW": {
        "up": [{"player_key": "filip vecheta|2003", "name": "Filip Vecheta", "league": "CZE-First League",
                "min_prev": 1200, "min_curr": 2100, "prev": 0.21, "curr": 0.33, "delta": 0.12, "direction": "improving"}],
        "down": [], "n_czech": 1, "directions": {"improving": 1, "stable": 0, "declining": 0},
    }}
    analog = {"rank": 1, "player_key": "alvaro morata|1992", "name": "Álvaro Morata", "nation": "ESP",
              "league": "ITA-Serie A", "season": "2020/21", "min": 2014, "npg_ast_q": 0.63, "distance": 0.7,
              "followed": [{"season": "2021/22", "league": "ITA-Serie A", "min": 2302, "npg_ast_q": 0.4}]}
    cards = [{
        "player_key": "patrik schick|1996", "fbref_id": "5d4f7d61", "name": "Patrik Schick", "pos": "FW",
        "pos_title": "Forwards", "born": 1996, "age": 28, "league": "GER-Bundesliga", "club_season": "Leverkusen",
        "club": "Leverkusen", "moved": False, "nt_flag": True, "nt_events": ["UEFA Euro 2024"],
        "reason": "highest quality-adjusted npG+A per 90 among FW",
        "stats": {"npg_ast_q": 0.68, "npg_p90": 0.8, "ast_p90": 0.06, "min": 1684, "min_share": 0.55, "npg": 15, "ast": 1},
        "clusters": {"style": {"id": "C0", "label": "High-volume scorers"},
                     "quality": {"id": "C2", "label": "High-volume scorers in top-five leagues"}},
        "tactical": "Primary scorers on starter minutes.",
        "trajectory": {"delta": 0.1, "direction": "improving", "min_prev": 1500, "min_curr": 1684, "prev": 0.58, "curr": 0.68},
        "analog_age": 29,
        "analogs": [analog],
        "photo": {"image": "img/players/5d4f7d61.jpg", "credit": "Patrik Schick (cropped).jpg", "license": "Wikimedia Commons"},
    }]
    analog_blocks = [{
        "player_key": "patrik schick|1996", "pos_group": "FW",
        "target": {"name": "Patrik Schick", "age": 29, "league": "GER-Bundesliga", "season": "2024/25",
                   "min": 1684, "npg_ast_q": 0.68},
        "analogs": [analog],
    }]
    youth = [{"league": "CZE-First League", "country": "CZE", "name": "Czechia", "minutes_total": 544228,
              "share_u21": 0.111, "share_u23": 0.162}]
    export = [{"country": "CZE", "name": "Czechia", "n": 15, "n_recent": 6, "median_export_age": 23.0,
               "median_export_age_recent": 24.0,
               "origin": {"domestic": 0.667, "stepping_stone": 0.0, "other_top9": 0.0, "not_covered": 0.333},
               "censored_share": 0.2}]
    fare_min = [{"country": "CZE", "name": "Czechia", "n": 24, "value": 0.338}]
    fare_goals = [{"country": "CZE", "name": "Czechia", "n": 24, "value": 0.513}]
    pathways = {
        "youth": youth, "export": export, "fare_min": fare_min, "fare_goals": fare_goals,
        "club_strength_proxy": "goals-scored percentile within league",
        "profile": [{"tier": "top9", "tier_label": "top-9 league", "pos_group": "FW", "cze_n": 4,
                     "cze_median": 0.38, "peer_median_n": 6.0, "peer_median": 0.31, "peer_countries": 8}],
        "youth_cze": youth[0], "youth_top": youth[0], "export_cze": export[0], "export_den": export[0],
        "fare_min_cze": fare_min[0], "fare_goals_cze": fare_goals[0], "fare_min_rank": 1,
        "fare_goals_rank": 1, "youth_rank": 1, "n_countries": 2,
    }
    facts = {"n_pool": 475, "n_no_tables": 120, "n_with_metrics": 206, "n_nt_flagged": 63,
             "nt_events": "UEFA Euro 2024", "n_photos": 114, "coverage_start": "2023/24", **seasons}
    hero = {"per_million": 1.65, "rank": 2, "n_peers": 2, "n_players": 18, "population_m": 10.9,
            "top": per_capita[0], "gap": gaps[0], "export_cze": export[0], "export_den": export[0]}
    thresholds = {"min_minutes": 900, "direction": 0.05}
    sens = pd.DataFrame([{"scenario": "baseline", "description": "current multipliers",
                          "top10_overlap": 29, "top10_churn": 0, "mean_delta_rank_top20": 0.0}])
    return {
        "lang": "en", "seasons": seasons, "groups": ["FW"], "group_titles": GROUP_TITLES,
        "hero": hero, "per_capita": per_capita, "max_per_million": 9.9,
        "cohorts": cohorts, "cohort_countries": ["CZE", "DEN"], "cohort_names": {"CZE": "Czechia", "DEN": "Denmark"},
        "cohort_gaps": gaps,
        "observations": _build_observations(hero, per_capita, gaps, movers | {"MF": movers["FW"], "DF": movers["FW"]},
                                            thresholds, seasons),
        "clusters": clusters, "movers": movers, "thresholds": thresholds,
        "pathways": pathways, "cards": cards, "analog_blocks": analog_blocks,
        "atlas_notes": {"FW": {"n_corpus": 926, "n_czech": 39, "n_nt": 18}},
        "multipliers": [{"league": "ENG-Premier League", "value": 1.0}, {"league": "CZE-First League", "value": 0.434}],
        "multiplier_source": "UEFA coefficient fallback.", "multiplier_method": "uefa_coefficient",
        "feature_defs": {"features": ["npg_p90", "ast_p90", "min_share", "age", "cards_p90"],
                         "min_minutes": 450, "phantom_minutes": 900},
        "loadings": [{"position": "FW", "projection": "style", "pc": "PC1", "explained_pct": 26.8,
                      "npg_p90": 0.501, "ast_p90": 0.469, "min_share": 0.544, "age": 0.191, "cards_p90": -0.444}],
        "sensitivity": _build_sensitivity(sens),
        "limitations": _build_limitations(facts), "facts": facts,
        "n_leagues": 19, "headline_leagues": ["ENG-Premier League"],
        "stepping_stone": ["NED-Eredivisie"], "seed": config.RANDOM_SEED,
        "photo_credits": [{"fbref_id": "5d4f7d61", "name": "Patrik Schick", "player_key": "patrik schick|1996",
                           "image": "img/players/5d4f7d61.jpg", "credit": "Patrik Schick (cropped).jpg",
                           "license": "Wikimedia Commons"}],
        "rendered_at": "2026-09-13 00:00",
        "repo_url": "https://github.com/barborasandova/czefootball-player-pool-atlas",
    }


def render_html(context: dict[str, Any]) -> str:
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATES_DIR)), autoescape=True)
    return env.get_template("report.html.j2").render(**context)


def main() -> None:
    logging_setup()
    config.ensure_dirs()
    data = load_data()
    metrics = data["seasons"]["metrics"]

    atlas_notes = {
        g: _render_atlas(data["coords"][g], data["features"][g], g, metrics,
                         config.OUTPUTS_DIR / f"atlas_{g}.svg")
        for g in GROUPS
    }
    heatmap = config.OUTPUTS_DIR / "intl_cohort_heatmap.svg"
    if not heatmap.exists():
        LOG.warning("%s missing — run src.international_benchmark first", heatmap)

    context = build_context(data, atlas_notes)
    html_out = render_html(context)
    html_path = config.OUTPUTS_DIR / "index.html"
    html_path.write_text(html_out, encoding="utf-8")
    LOG.info("wrote %s (%d bytes)", html_path, len(html_out.encode("utf-8")))

    css_src = config.TEMPLATES_DIR / "style.css"
    if css_src.exists():
        shutil.copyfile(css_src, config.OUTPUTS_DIR / "style.css")
        LOG.info("copied style.css")


if __name__ == "__main__":
    main()
