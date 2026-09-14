"""Render the English report of the Czech football player pool atlas.

Reads only `data/processed/*` (falling back to the committed `data/snapshot/`
copy of any missing file), `config/*.yaml`, `site/players.json` and
`outputs/intl_cohort_heatmap.svg` (redrawn from the processed tables when
missing); never touches the network.

Output:
  outputs/atlas_FW.svg, outputs/atlas_MF.svg, outputs/atlas_DF.svg
  outputs/index.html          (full report, English)
  outputs/cs/index.html       (the same report in Czech; assets via ../)
  outputs/style.css           (copy of templates/style.css)

Languages: the template calls `t()` / `term()` from the context; both come
from src/i18n.py (English defaults + config/i18n/cs.yaml). Generated prose
(observations, limitations, kickers, sensitivity descriptions) is built
through the same translator, so one context per language is enough.

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
from markupsafe import Markup

from src import config
from src.i18n import LANGS, Translator, localize_html_numbers
from src.international_benchmark import render_cohort_heatmap
from src.logging_setup import setup as logging_setup
from src.utils import normalize_name, read_parquet, resolve_processed, season_label

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
NT_LABEL = f"NT {config.nt_years()}"
# showcase rule -> row kicker (descriptive; order = row order on the page)
RULE_KICKERS = [
    ("highest quality-adjusted", "Highest quality-adjusted production"),
    ("youngest national-team", "Youngest national-team call-up"),
    ("most top-9 minutes among", "National-team core"),   # row order = the order the rules are applied
    ("most domestic minutes among", "National-team core at home"),
    ("most top-9 league minutes", "Most top-9 minutes"),
    ("most domestic-league minutes", "Most domestic minutes under 23, no top-9 season yet"),
]
RULE_KICKER_KEYS = {
    "highest quality-adjusted": "kicker.highest",
    "youngest national-team": "kicker.youngest",
    "most top-9 league minutes": "kicker.top9",
    "most domestic-league minutes": "kicker.domestic",
    "most top-9 minutes among": "kicker.ntcore",
    "most domestic minutes among": "kicker.ntcore_home",
}
DESTINATION_LABELS = {
    "domestic": "domestic", "top9": "top-9", "stepping_stone": "stepping stone",
    "peer_domestic": "peer country league", "other": "other",
}
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


NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
                "ten", "eleven", "twelve"]


def number_word(n: int) -> str:
    """Spell small counts in prose ('eight peers'); digits beyond twelve."""
    return NUMBER_WORDS[n] if 0 <= n < len(NUMBER_WORDS) else str(n)


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


# Chapter IV "How this was built" — paths under the repo root, for both the
# n_tests / n_rulings counts and the spec/plan/ledger blob links. The v1
# sprint's document date, underscored here (not hyphenated) so it doesn't
# read as a typed football season to test_no_typed_season_in_render_or_i18n_module.
_DOC_DATE = "2026_09_12".replace("_", "-")
SPEC_PATH = f"docs/superpowers/specs/{_DOC_DATE}-czech-football-player-pool-atlas-design.md"
PLAN_PATH = f"docs/superpowers/plans/{_DOC_DATE}-czech-football-player-pool-atlas.md"
LEDGER_PATH = f"docs/superpowers/ledgers/{_DOC_DATE}-v1-progress.md"


def _count_tests() -> int:
    """Lines containing `def test_` across `tests/*.py` — recomputed every render, never typed."""
    return sum(
        1
        for p in sorted((config.ROOT_DIR / "tests").glob("*.py"))
        for line in p.read_text(encoding="utf-8").splitlines()
        if "def test_" in line
    )


def _count_rulings() -> int:
    """Lines containing `Ruling:` in the v1 pipeline ledger — one per dated controller decision."""
    ledger = config.ROOT_DIR / LEDGER_PATH
    if not ledger.exists():
        LOG.warning("ledger %s missing; rulings count rendered as 0", ledger)
        return 0
    return sum(1 for line in ledger.read_text(encoding="utf-8").splitlines() if "Ruling:" in line)


def _build_flow_urls(repo_url: str) -> dict[str, str]:
    """GitHub blob URLs for the design spec, the plan and the ledger."""
    return {
        "spec_url": f"{repo_url}/blob/main/{SPEC_PATH}",
        "plan_url": f"{repo_url}/blob/main/{PLAN_PATH}",
        "ledger_url": f"{repo_url}/blob/main/{LEDGER_PATH}",
    }


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

    The whole metrics-season corpus is drawn as a rasterised grey background; the
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
        f"call-up {config.nt_years()}.",
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
                    group: str, season: str, tr: Translator | None = None) -> list[dict]:
    """Style-projection cluster archetypes for one group."""
    tr = tr or Translator("en")
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
            "label": tr.term(style_labels[key]) if key in style_labels else f"Cluster {key}",
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
            "tactical": (tactical.get(key) or {}).get(tr.lang, ""),
            "top": cz["player"].head(CLUSTER_TOP_N).tolist(),
            "top_keys": cz["player_key"].head(CLUSTER_TOP_N).tolist(),
        })
    return rows


def _cluster_names(labels: dict, tr: Translator) -> dict[str, dict[str, dict[str, str]]]:
    """Cluster code -> translated label per group and projection, for the atlas tooltips."""
    return {
        g: {proj: {code: tr.term(label) for code, label in (labels.get(g, {}).get(proj) or {}).items()}
            for proj in ("style", "quality")}
        for g in GROUPS
    }


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


def _current_club(key: str, current_by_key: pd.DataFrame, pool_row: pd.Series | None,
                  current_label: str) -> tuple[str, str, str, str]:
    """(club, league, source, label) for the card's name line.

    The club comes from the current-season table row with the most minutes
    (label = the season, formatted through season_label()); a player without a current-season
    row falls back to the pool's country-page club, labelled "latest known"
    because that page carries no season.
    """
    if key in current_by_key.index:
        cur = current_by_key.loc[key]
        return str(cur["team"]), str(cur["league"]), "tables", current_label
    club = str(pool_row["club_current"]) if pool_row is not None and pool_row["club_current"] else ""
    return club, "", "country page", "latest known"


def _card_rows(cards: list[dict], tr: Translator | None = None,
               nt_core_event: str | None = None) -> list[dict]:
    """Group cards by showcase rule, one row per rule, in RULE_KICKERS order.

    The `kicker.ntcore` row carries the `{event}` placeholder (the national-team
    core rule names the event it was drawn from); every other kicker is plain.
    """
    tr = tr or Translator("en")
    rows = []
    for prefix, _kicker in RULE_KICKERS:
        members = [c for c in cards if c["reason"].startswith(prefix)]
        if members:
            key = RULE_KICKER_KEYS[prefix]
            kicker = tr.raw(key, event=nt_core_event) if key == "kicker.ntcore" else tr.raw(key)
            rows.append({"kicker": kicker, "cards": members})
    rest = [c for c in cards if not any(c["reason"].startswith(p) for p, _ in RULE_KICKERS)]
    if rest:
        rows.append({"kicker": tr.raw("kicker.other"), "cards": rest})
    return rows


def _build_cards(showcase: list[dict], analogs: dict, features: dict[str, pd.DataFrame],
                 coords: dict[str, pd.DataFrame], traj: dict[str, pd.DataFrame],
                 pool: pd.DataFrame, labels: dict, photos: dict, season: str,
                 current_season: str, tr: Translator | None = None,
                 current_table: pd.DataFrame | None = None) -> list[dict]:
    """One card per showcase player: stats, clusters, tactical read, trajectory, analogs.

    Stats come from `season` (metrics); the club on the meta line is the
    `current_season` club from `current_table` (the raw fbref_players rows,
    no minutes floor — the features frames drop players under 450 minutes,
    which early in a season is most of them), row with most minutes per
    player, falling back to the pool's country-page club.
    """
    tr = tr or Translator("en")
    pool_by_key = pool.drop_duplicates("player_key").set_index("player_key")
    photos_by_key = {v["player_key"]: dict(v, fbref_id=k) for k, v in photos.items()}
    source = current_table if current_table is not None else pd.concat(features.values(), ignore_index=True)
    current_by_key = _metrics_rows(source, current_season).set_index("player_key")
    current_year = int(current_season[:4])
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
        tj = traj[group]
        tj = tj[tj["player_key"] == key] if not tj.empty else tj
        trajectory = None
        if not tj.empty:
            r = tj.iloc[0]
            trajectory = {
                "delta": round(float(r["delta"]), 3), "direction": str(r["direction"]),
                "min_prev": int(r["min_prev"]), "min_curr": int(r["min_curr"]),
                "prev": round(float(r["npg_ast_quality_prev"]), 2),
                "curr": round(float(r["npg_ast_quality_curr"]), 2),
            }
        club_current, league_current, club_source, club_label = _current_club(
            key, current_by_key, p, season_label(current_season))
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
            "club_league": league_current,
            "club_source": club_source,
            "club_label": club_label,
            "age_current": current_year - int(f["born"]) if pd.notna(f["born"]) else None,
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
                "style": {"id": style_id, "label": tr.term(style_labels[style_id]) if style_id in style_labels else style_id},
                "quality": {"id": quality_id, "label": tr.term(quality_labels[quality_id]) if quality_id in quality_labels else quality_id},
            },
            "tactical": tactical.get(tr.lang, ""),
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

    dest_raw = pw.get("destinations")
    destinations = None
    if dest_raw:
        buckets = sorted(
            [{
                "bucket": b["bucket"], "label": DESTINATION_LABELS.get(b["bucket"], b["bucket"]),
                "n": int(b["n"]), "share_of_abroad": round(float(b.get("share_of_abroad") or 0), 3),
                "median_multiplier": _opt_float(b.get("median_multiplier"), 3),
                "examples": list((dest_raw.get("examples") or {}).get(b["bucket"], [])),
            } for b in dest_raw.get("buckets", [])],
            key=lambda b: -b["share_of_abroad"])
        destinations = {
            "n_total": int(dest_raw.get("n_total") or 0), "n_abroad": int(dest_raw.get("n_abroad") or 0),
            "buckets": buckets,
            "sideways_share": round(float(dest_raw.get("sideways_share") or 0), 3),
            "sideways_definition": str(dest_raw.get("sideways_definition") or ""),
        }

    return {
        "destinations": destinations,
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


def _build_squad_lens(lens: dict, names: dict[str, str]) -> dict:
    """Exhibit F context: `lens` (src.squad_lens.build_squad_lens's JSON shape) -> template rows.

    Rows are ordered CZE first, then the remaining countries by their top-9
    tier count descending. Empty/missing `lens` (squad_lens.json absent)
    returns `{}`, which the template reads as "no exhibit F".
    """
    countries = lens.get("countries") or []
    if not countries:
        return {}
    cze = next((c for c in countries if c["country"] == "CZE"), None)
    others = sorted(
        (c for c in countries if c["country"] != "CZE"),
        key=lambda c: -c["tiers"].get("top9", 0),
    )
    ordered = ([cze] if cze else []) + others
    rows = []
    for c in ordered:
        n, tiers = c["n"], c["tiers"]

        def pct(k: str, n: int = n, tiers: dict = tiers) -> float:
            return round(100 * tiers.get(k, 0) / n, 1) if n else 0.0

        rows.append({
            "country": c["country"], "name": names.get(c["country"], c["country"]),
            "n": n, "matched": c["matched"],
            "top9_pct": pct("top9"), "stepping_pct": pct("stepping_stone"),
            "domestic_pct": pct("domestic"), "other_pct": pct("other"),
            "unmatched": tiers.get("unmatched", 0),
            "cohorts": c["cohorts"],
            "median_minutes": c.get("median_minutes"),
            "median_multiplier": c.get("median_multiplier"),
        })
    return {
        "event": str(lens.get("event", "")),
        "season_label": season_label(lens["season"]),
        "rows": rows,
    }


def _build_findings(hero: dict, gaps: list[dict], pathways: dict, squad_lens: dict,
                    seasons: dict, tr: Translator) -> list[dict]:
    """Five one-line findings for the summary, each `{"text", "foot"}`.

    Every number traces to `hero`, `gaps`, `pathways` or `squad_lens` — all
    already built elsewhere in `build_context`. A finding whose source is
    missing is skipped rather than rendered with a placeholder number.
    """
    findings: list[dict] = []

    # (1) per-capita rank + density vs the leader
    top = hero.get("top")
    if top and hero.get("per_million"):
        findings.append({
            "text": tr.num(tr.raw(
                "finding.1", rank=tr.ordinal(hero["rank"]), n=hero["n_peers"],
                pm=f"{hero['per_million']:.2f}", top=tr.term(top["name"]),
                top_pm=f"{top['per_million']:.2f}",
                ratio=f"{top['per_million'] / hero['per_million']:.1f}",
            )),
            "foot": tr.raw("finding.1.foot", season=seasons["metrics"]),
        })

    # (2) largest cohort gap
    if gaps:
        g = gaps[0]
        findings.append({
            "text": tr.num(tr.raw(
                "finding.2", group=tr.term(g["group_title"]).lower(), cohort=g["cohort"],
                cze=g["cze_n"], s=("" if g["cze_n"] == 1 or tr.lang != "en" else "s"),
                peer=f"{g['peer_median_n']:g}",
            )),
            "foot": tr.raw("finding.2.foot"),
        })

    # (3) recent export age, CZE vs DEN
    export_cze, export_den = pathways.get("export_cze"), pathways.get("export_den")
    if (export_cze and export_den and export_cze.get("median_export_age_recent") is not None
            and export_den.get("median_export_age_recent") is not None):
        findings.append({
            "text": tr.num(tr.raw(
                "finding.3", cze=f"{export_cze['median_export_age_recent']:g}",
                den=f"{export_den['median_export_age_recent']:g}",
            )),
            "foot": tr.raw("finding.3.foot"),
        })

    # (4) exhibit C minutes share: CZE vs the peer whose share differs most
    fare_min, fare_cze = pathways.get("fare_min") or [], pathways.get("fare_min_cze")
    fare_others = [r for r in fare_min if r["country"] != "CZE"]
    if fare_cze and fare_others and pathways.get("fare_min_rank"):
        extreme = max(fare_others, key=lambda r: abs(r["value"] - fare_cze["value"]))
        findings.append({
            "text": tr.num(tr.raw(
                "finding.4", cze=f"{fare_cze['value'] * 100:.0f}",
                rank=tr.ordinal(pathways["fare_min_rank"]), n=len(fare_min),
                extreme=tr.term(extreme["name"]), extreme_value=f"{extreme['value'] * 100:.0f}",
            )),
            "foot": tr.raw("finding.4.foot"),
        })

    # (5) WC squad top-9 share, CZE vs peers; fallback: exhibit E sideways share
    rows = (squad_lens or {}).get("rows") or []
    cze_row = next((r for r in rows if r["country"] == "CZE"), None)
    peer_rows = [r for r in rows if r["country"] != "CZE"]
    if cze_row and peer_rows:
        top_peer = max(peer_rows, key=lambda r: r["top9_pct"])
        findings.append({
            "text": tr.num(tr.raw(
                "finding.5.squad", event=squad_lens["event"], cze=f"{cze_row['top9_pct']:.0f}",
                peer=tr.term(top_peer["name"]), peer_pct=f"{top_peer['top9_pct']:.0f}",
            )),
            "foot": tr.raw("finding.5.squad.foot", event=squad_lens["event"]),
        })
    else:
        dest = pathways.get("destinations")
        if dest and dest.get("sideways_share") is not None:
            findings.append({
                "text": tr.num(tr.raw("finding.5.sideways", share=f"{dest['sideways_share'] * 100:.0f}")),
                "foot": tr.raw("finding.5.sideways.foot"),
            })

    return findings


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


def _build_sensitivity(sens: pd.DataFrame, tr: Translator | None = None) -> dict:
    tr = tr or Translator("en")
    rows = [
        {"scenario": r.scenario, "description": tr.sensitivity(str(r.description)), "overlap": int(r.top10_overlap),
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


def _build_data_quality(dq: dict, tr: Translator | None = None) -> dict:
    """Chapter IV data-quality log: recomputed checks + recorded incidents.

    `dq` is `data_quality.json`'s raw shape (`{"checks": [...], "events":
    [...]}`, written by `src.data_quality`; `{}` when the file is missing --
    see `load_data`, which then leaves both lists empty and the template
    section renders nothing). Check labels/descriptions come from i18n
    (`dq.<id>.label` / `dq.<id>.what`); event text is already bilingual in
    the source yaml (one `en`/`cs` pair per event) and picked here by
    `tr.lang` -- counts and dates on events are recorded facts, not
    translated.
    """
    tr = tr or Translator("en")
    checks = [
        {"id": c["id"], "count": c["count"], "unit": tr.term(c["unit"]),
         "label": tr.raw(f"dq.{c['id']}.label"), "what": tr.raw(f"dq.{c['id']}.what")}
        for c in dq.get("checks", [])
    ]
    events = [
        {"date": e["date"], "text": e["cs"] if tr.lang == "cs" else e["en"],
         "recorded_count": e.get("recorded_count"),
         "unit": tr.term(e["unit"]) if e.get("unit") else None}
        for e in dq.get("events", [])
    ]
    return {"checks": checks, "events": events}


def _build_limitations(facts: dict, tr: Translator | None = None) -> list[dict]:
    """Limitations from spec §10 and the pipeline ledger; numbers from `facts`, copy from i18n."""
    tr = tr or Translator("en")
    params = dict(facts, max_multiplier=f"{facts['max_multiplier']:.2f}",
                  tier2_factor=f"{facts['tier2_factor']:g}")
    out = []
    for name in ("leagues", "features", "nt", "photos", "seasons", "multipliers", "origins",
                 "identity", "women", "scope", "tracking"):
        # Markup: lim.tracking.body carries <a> links (spec §10 copy is trusted, not
        # user input); without it Jinja's autoescape would print the tags as text.
        out.append({"title": tr.raw(f"lim.{name}.title"),
                    "body": Markup(tr.num(tr.raw(f"lim.{name}.body", **params)))})
    return out


def _build_observations(hero: dict, per_capita: list[dict], gaps: list[dict],
                        movers: dict[str, dict], thresholds: dict, seasons: dict,
                        n_headline: int, tr: Translator | None = None) -> list[dict]:
    """Three computed observations; every number and the titles come from the data."""
    tr = tr or Translator("en")
    top = per_capita[0]
    n_other_peers = len(per_capita) - 1
    cze = next(r for r in per_capita if r["country"] == "CZE")
    above = [r for r in per_capita if r["rank"] < cze["rank"]]
    below = [r for r in per_capita if r["rank"] > cze["rank"]]
    nearest_above = above[-1] if above else None
    obs1_body = tr.raw(
        "obs.1.body", cze_n=cze["n_players"], season=seasons["metrics"],
        topn=tr.number_word(n_headline, NUMBER_WORDS), pm=f"{cze['per_million']:.2f}",
        rank=cze["rank"], n=len(per_capita), top=tr.term(top["name"]), top_pm=f"{top['per_million']:.2f}",
        ratio=f"{top['per_million'] / cze['per_million']:.1f}",
    )
    if nearest_above:
        ratio = cze["population_m"] / nearest_above["population_m"]
        size = (tr.raw("obs.1.smaller", ratio=f"{ratio:.1f}") if ratio >= 1
                else tr.raw("obs.1.larger", ratio=f"{1 / ratio:.1f}"))
        obs1_body += tr.raw("obs.1.above", name=tr.term(nearest_above["name"]),
                            pm=f"{nearest_above['per_million']:.2f}",
                            players=nearest_above["n_players"], size=size)
    obs1_body += ". " + (
        tr.raw("obs.1.below", names=", ".join(tr.term(r["name"]) for r in below)) if below
        else tr.raw("obs.1.none_below")
    )

    g = gaps[:3]
    gap_text = "; ".join(
        tr.raw("obs.2.gap", group=tr.term(r["group_title"]).lower(), cohort=r["cohort"],
               cze=r["cze_n"], peer=f"{r['peer_median_n']:g}") for r in g
    )
    obs2_body = tr.raw(
        "obs.2.body", season=seasons["metrics"], topn=n_headline,
        peers=tr.number_word(n_other_peers, NUMBER_WORDS), s="s" if n_other_peers != 1 else "",
        k=tr.number_word(len(g), NUMBER_WORDS), plural="s are" if len(g) != 1 else " is",
        gaps=gap_text,
    )

    parts = []
    for group in GROUPS:
        m = movers[group]
        d = m["directions"]
        parts.append(tr.raw("obs.3.part", group=tr.term(GROUP_TITLES[group]).lower(), n=m["n_czech"],
                            up=d["improving"], stable=d["stable"], down=d["declining"]))
    n_total = sum(movers[g]["n_czech"] for g in GROUPS)
    n_stable = sum(movers[g]["directions"]["stable"] for g in GROUPS)
    stable_share = n_stable / n_total if n_total else 0.0
    traj_verdict = tr.raw("obs.3.stable") if stable_share >= 0.5 else tr.raw("obs.3.mixed")
    obs3_body = tr.raw(
        "obs.3.body", n=n_total, min=thresholds["min_minutes"], previous=seasons["previous"],
        metrics=seasons["metrics"], parts="; ".join(parts), band=f"{thresholds['direction']:.2f}",
        stable=n_stable,
    )
    return [
        {"title": tr.raw("obs.1.title", rank=cze["rank"], n=len(per_capita)), "body": tr.num(obs1_body)},
        {"title": (tr.raw("obs.2.title", group=tr.term(g[0]["group_title"]).lower(), cohort=g[0]["cohort"])
                   if g else tr.raw("obs.2.title_empty")),
         "body": tr.num(obs2_body)},
        {"title": tr.raw("obs.3.title", previous=seasons["previous"], metrics=seasons["metrics"],
                         verdict=traj_verdict), "body": tr.num(obs3_body)},
    ]


def _build_player_index(features: dict[str, pd.DataFrame], coords: dict[str, pd.DataFrame],
                        pool: pd.DataFrame, labels: dict, cards: list[dict], season: str,
                        tr: Translator | None = None) -> list[dict]:
    """Every Czech-eligible player with a `season` row: the numbers behind the atlases.

    One row per player (club with most minutes), sorted by surname; a player
    with a card carries its id so the index can link to it.
    """
    tr = tr or Translator("en")
    fbref_by_key = pool.drop_duplicates("player_key").set_index("player_key")["fbref_id"].to_dict()
    card_by_key = {c["player_key"]: c["fbref_id"] for c in cards}
    rows = []
    for group in GROUPS:
        feat = _metrics_rows(features[group], season)
        feat = feat[feat["czech_eligible"]]
        co = _metrics_rows(coords[group], season).set_index("player_key")
        style_labels = labels.get(group, {}).get("style", {})
        for r in feat.itertuples():
            style = str(co.loc[r.player_key, "cluster_style"]) if r.player_key in co.index else ""
            rows.append({
                "player_key": r.player_key,
                "fbref_id": str(fbref_by_key.get(r.player_key, "")),
                "card_id": card_by_key.get(r.player_key, ""),
                "player": str(r.player),
                "ascii_name": normalize_name(str(r.player)),
                "pos_group": group,
                "age": _opt_int(r.age),
                "league": str(r.league),
                "club": str(r.team),
                "min": int(r.min),
                "npg_ast_q": round(float(r.npg_p90_quality + r.ast_p90_quality), 2),
                "cluster_style": style,
                "cluster_label": tr.term(style_labels[style]) if style in style_labels else "",
                "nt_flag": bool(r.nt_flag),
            })
    return sorted(rows, key=lambda r: (_last_name(r["ascii_name"]), r["ascii_name"]))


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
    """Read a JSON file (snapshot fallback for processed files) or return `default`."""
    path = resolve_processed(path)
    if not path.exists():
        LOG.warning("missing %s", path)
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_parquet_or_empty(path: Path) -> pd.DataFrame:
    path = resolve_processed(path)
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
        "fbref_players": _load_parquet_or_empty(p / "fbref_players.parquet"),
        "showcase": _load_json(p / "showcase.json", []),
        "analogs": _load_json(p / "analogs.json", {}),
        "pathways": _load_json(p / "pathways.json", {}),
        "squad_lens": _load_json(p / "squad_lens.json", {}),
        "data_quality": _load_json(p / "data_quality.json", {}),
        "photos": _load_json(SITE_PLAYERS, {}),
        "cluster_labels": config.load_yaml("cluster_labels.yaml"),
        "league_quality": config.league_quality(),
        "countries": config.countries()["peers"],
        "seasons": config.seasons(),
        "feature_defs": config.features(),
        "leagues": config.leagues(),
    }


def _translator_context(tr: Translator) -> dict[str, Any]:
    """Language, asset prefix and the callables the template uses (`t`, `term` ...)."""
    return {
        "lang": tr.lang,
        "assets": "" if tr.lang == "en" else "../",
        "t": tr, "term": tr.term, "ordinal": tr.ordinal, "reason": tr.reason,
    }


def build_context(data: dict[str, Any], atlas_notes: dict[str, dict] | None = None,
                  lang: str = "en") -> dict[str, Any]:
    """Assemble the template context from loaded data, in one language."""
    from src.trajectory import DIRECTION_THRESHOLD, MIN_MINUTES

    tr = Translator(lang)

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

    clusters = {g: _build_clusters(data["coords"][g], data["features"][g], data["cluster_labels"], g, metrics, tr)
                for g in GROUPS}
    movers = {g: _build_movers(data["trajectory"][g]) for g in GROUPS}
    analog_blocks = _build_analog_blocks(data["showcase"], data["analogs"])
    cards = _build_cards(data["showcase"], data["analogs"], data["features"], data["coords"],
                         data["trajectory"], data["pool"], data["cluster_labels"], data["photos"], metrics,
                         seasons_raw["current"], tr,
                         current_table=data["fbref_players"] if not data["fbref_players"].empty else None)
    nt_core_event = config.load_yaml("squads.yaml").get("nt_core_event")
    pathways = _build_pathways(data["pathways"], names, peers)
    squad_lens = _build_squad_lens(data["squad_lens"], names)
    player_index = _build_player_index(data["features"], data["coords"], data["pool"],
                                       data["cluster_labels"], cards, metrics, tr)

    # Pool facts for the masthead and limitations
    lq = data["league_quality"]
    lg = data["leagues"]
    n_leagues = len({*lg["headline"], lg["domestic"], *lg.get("custom", {}), *lg.get("peer_domestic", {})})
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
        "nt_years": config.nt_years(),
        "n_leagues": n_leagues,
        "tier2_factor": float(lq.get("tier2_factor", 0)),
        "max_multiplier": max(float(v) for v in lq["multipliers"].values()),
        "history_start": seasons["history_start"],
        "coverage_start": seasons["previous"],  # peer domestic leagues are fetched from here on
        "n_tests": _count_tests(),
        "n_rulings": _count_rulings(),
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
    observations = _build_observations(hero, per_capita, gaps, movers, thresholds, seasons,
                                       len(data["leagues"]["headline"]), tr)
    findings = _build_findings(hero, gaps, pathways, squad_lens, seasons, tr)

    multipliers = sorted(
        [{"league": k, "value": float(v)} for k, v in lq["multipliers"].items()],
        key=lambda r: -r["value"])

    used_keys = {c["player_key"] for c in cards}
    for g in GROUPS:
        for c in clusters[g]:
            used_keys.update(c["top_keys"])
        used_keys.update(r["player_key"] for r in movers[g]["up"] + movers[g]["down"])

    return {
        **_translator_context(tr),
        "seasons": seasons,
        "groups": GROUPS,
        "group_titles": GROUP_TITLES,
        "hero": hero,
        "findings": findings,
        "per_capita": per_capita,
        "max_per_million": max(r["per_million"] for r in per_capita),
        "cohorts": cohorts,
        "cohort_countries": COHORT_COUNTRIES,
        "cohort_names": names,
        "cohort_gaps": gaps,
        "observations": observations,
        "clusters": clusters,
        "cluster_names": _cluster_names(data["cluster_labels"], tr),
        "movers": movers,
        "thresholds": thresholds,
        "pathways": pathways,
        "squad_lens": squad_lens,
        "cards": cards,
        "card_rows": _card_rows(cards, tr, nt_core_event=nt_core_event),
        "nt_core_event": nt_core_event,
        "player_index": player_index,
        "analog_blocks": analog_blocks,
        "atlas_notes": atlas_notes or {g: {"n_corpus": 0, "n_czech": 0, "n_nt": 0} for g in GROUPS},
        "multipliers": multipliers,
        "multiplier_source": str(lq.get("source", "")).strip(),
        "multiplier_method": str(lq.get("method", "")),
        "feature_defs": data["feature_defs"],
        "loadings": _build_loadings(data["loadings"]) if not data["loadings"].empty else [],
        "sensitivity": _build_sensitivity(data["sensitivity"] if not data["sensitivity"].empty else pd.DataFrame(
            columns=["scenario", "description", "top10_overlap", "top10_churn", "mean_delta_rank_top20"]), tr),
        "limitations": _build_limitations(facts, tr),
        "data_quality": _build_data_quality(data["data_quality"], tr),
        "facts": facts,
        "n_leagues": n_leagues,
        "headline_leagues": list(data["leagues"]["headline"]),
        "stepping_stone": list(data["leagues"].get("stepping_stone", [])),
        "seed": config.RANDOM_SEED,
        "photo_credits": _photo_credits(data["photos"], used_keys),
        "rendered_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "repo_url": "https://github.com/barborasandova/czefootball-player-pool-atlas",
        **_build_flow_urls("https://github.com/barborasandova/czefootball-player-pool-atlas"),
    }


def build_context_from_fixtures(lang: str = "en") -> dict[str, Any]:
    """Small hand-written context so the template renders offline in tests.

    Two countries, one position group (FW), one card, one analog block, one
    pathways row per exhibit. Shapes mirror `build_context()`.
    """
    tr = Translator(lang)
    metrics_raw, previous_raw, current_raw, history_raw = "2024-2025", "2023-2024", "2025-2026", "2020-2021"
    analog_raw, analog_next_raw = "2020-2021", "2021-2022"
    seasons = {"metrics": season_label(metrics_raw), "previous": season_label(previous_raw),
               "current": season_label(current_raw), "history_start": season_label(history_raw)}
    per_capita = [
        {"country": "DEN", "name": "Denmark", "n_players": 59, "population_m": 5.96, "per_million": 9.9, "rank": 1},
        {"country": "CZE", "name": "Czechia", "n_players": 18, "population_m": 10.9, "per_million": 1.65, "rank": 2},
    ]
    gaps = [{"pos_group": "DF", "group_title": "Defenders", "cohort": "26-29", "cze_n": 1,
             "peer_median_n": 5.5, "gap": -4.5}]
    cohorts = {"FW": [{"cohort": c, "cells": {"CZE": {"n": 1, "median": 0.33}, "DEN": {"n": 0, "median": None}}}
                      for c in COHORT_ORDER]}
    clusters = {"FW": [{
        "id": "C0", "label": tr.term("High-volume scorers"), "n": 3, "n_corpus": 314, "nt_pool": 1,
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
              "league": "ITA-Serie A", "season": season_label(analog_raw), "min": 2014, "npg_ast_q": 0.63,
              "distance": 0.7,
              "followed": [{"season": season_label(analog_next_raw), "league": "ITA-Serie A", "min": 2302,
                            "npg_ast_q": 0.4}]}
    cards = [{
        "player_key": "patrik schick|1996", "fbref_id": "5d4f7d61", "name": "Patrik Schick", "pos": "FW",
        "pos_title": "Forwards", "born": 1996, "age": 28, "league": "GER-Bundesliga", "club_season": "Leverkusen",
        "club": "Leverkusen", "club_league": "GER-Bundesliga", "club_source": "tables",
        "club_label": season_label(current_raw), "age_current": 29,
        "moved": False, "nt_flag": True, "nt_events": ["UEFA Euro 2024"],
        "reason": "highest quality-adjusted npG+A per 90 among FW",
        "stats": {"npg_ast_q": 0.68, "npg_p90": 0.8, "ast_p90": 0.06, "min": 1684, "min_share": 0.55, "npg": 15, "ast": 1},
        "clusters": {"style": {"id": "C0", "label": tr.term("High-volume scorers")},
                     "quality": {"id": "C2", "label": tr.term("High-volume scorers in top-five leagues")}},
        "tactical": "Primary scorers on starter minutes.",
        "trajectory": {"delta": 0.1, "direction": "improving", "min_prev": 1500, "min_curr": 1684, "prev": 0.58, "curr": 0.68},
        "analog_age": 29,
        "analogs": [analog],
        "photo": {"image": "img/players/5d4f7d61.jpg", "credit": "Patrik Schick (cropped).jpg", "license": "Wikimedia Commons"},
    }]
    analog_blocks = [{
        "player_key": "patrik schick|1996", "pos_group": "FW",
        "target": {"name": "Patrik Schick", "age": 29, "league": "GER-Bundesliga", "season": season_label(metrics_raw),
                   "min": 1684, "npg_ast_q": 0.68},
        "analogs": [analog],
    }]
    youth = [{"league": "CZE-First League", "country": "CZE", "name": "Czechia", "minutes_total": 544228,
              "share_u21": 0.111, "share_u23": 0.162}]
    export = [{"country": "CZE", "name": "Czechia", "n": 15, "n_recent": 6, "median_export_age": 23.0,
               "median_export_age_recent": 24.0,
               "origin": {"domestic": 0.667, "stepping_stone": 0.0, "other_top9": 0.0, "not_covered": 0.333},
               "censored_share": 0.2}]
    fare_min = [{"country": "DEN", "name": "Denmark", "n": 40, "value": 0.455},
                {"country": "CZE", "name": "Czechia", "n": 24, "value": 0.338}]
    fare_goals = [{"country": "DEN", "name": "Denmark", "n": 40, "value": 0.556},
                  {"country": "CZE", "name": "Czechia", "n": 24, "value": 0.513}]
    pathways = {
        "destinations": {
            "n_total": 199, "n_abroad": 40,
            "buckets": [{"bucket": "top9", "label": "top-9", "n": 18, "share_of_abroad": 0.45,
                         "median_multiplier": 0.788, "examples": ["Patrik Schick"]},
                        {"bucket": "peer_domestic", "label": "peer country league", "n": 10,
                         "share_of_abroad": 0.25, "median_multiplier": 0.268, "examples": ["Patrizio Stronati"]}],
            "sideways_share": 0.25,
            "sideways_definition": "destination league multiplier <= the domestic league's multiplier",
        },
        "youth": youth, "export": export, "fare_min": fare_min, "fare_goals": fare_goals,
        "club_strength_proxy": "goals-scored percentile within league",
        "profile": [{"tier": "top9", "tier_label": "top-9 league", "pos_group": "FW", "cze_n": 4,
                     "cze_median": 0.38, "peer_median_n": 6.0, "peer_median": 0.31, "peer_countries": 8}],
        "youth_cze": youth[0], "youth_top": youth[0], "export_cze": export[0], "export_den": export[0],
        "fare_min_cze": fare_min[1], "fare_goals_cze": fare_goals[1], "fare_min_rank": 2,
        "fare_goals_rank": 2, "youth_rank": 1, "n_countries": 2,
    }
    facts = {"n_pool": 475, "n_no_tables": 120, "n_with_metrics": 206, "n_nt_flagged": 63,
             "nt_events": "UEFA Euro 2024", "n_photos": 114, "coverage_start": seasons["previous"],
             "nt_years": config.nt_years(),
             "n_leagues": 19, "tier2_factor": 0.6, "max_multiplier": 1.0,
             "n_tests": _count_tests(), "n_rulings": _count_rulings(), **seasons}
    data_quality = {
        "checks": [
            {"id": "women_filtered", "count": 92, "unit": "entries"},
            {"id": "namesakes", "count": 2, "unit": "players"},
            {"id": "no_tables", "count": 120, "unit": "players"},
            {"id": "split_seasons", "count": 423, "unit": "rows"},
            {"id": "nt_unmatched", "count": 18, "unit": "names"},
            {"id": "missing_born", "count": 0, "unit": "rows"},
        ],
        "events": [
            # dotted dates so the no-typed-season regex test does not read them as seasons
            {"id": "season_index_stale", "date": "2026.09.14", "recorded_count": 9, "unit": "leagues",
             "en": "A stale FBref season index made soccerdata fetch the season-less URL.",
             "cs": "Zastaralý sezónní index FBref způsobil, že soccerdata stáhla URL bez sezóny."},
            {"id": "clubelo_down", "date": "2026.09.13",
             "en": "ClubElo's API answered 502 for the whole run.",
             "cs": "API ClubElo odpovídalo 502 po celou dobu běhu."},
        ],
    }
    squad_lens = _build_squad_lens({
        "event": "2026 FIFA World Cup", "season": metrics_raw,
        "countries": [
            {"country": "CZE", "n": 3, "matched": 2,
             "tiers": {"top9": 1, "stepping_stone": 0, "domestic": 1, "other": 0, "unmatched": 1},
             "cohorts": {"U22": 0, "23-25": 1, "26-29": 0, "30+": 2},
             "median_minutes": 1850.0, "median_multiplier": 0.434},
            {"country": "DEN", "n": 1, "matched": 1,
             "tiers": {"top9": 0, "stepping_stone": 0, "domestic": 1, "other": 0, "unmatched": 0},
             "cohorts": {"U22": 0, "23-25": 0, "26-29": 1, "30+": 0},
             "median_minutes": 900.0, "median_multiplier": 0.371},
        ],
    }, {"CZE": "Czechia", "DEN": "Denmark"})
    hero = {"per_million": 1.65, "rank": 2, "n_peers": 2, "n_players": 18, "population_m": 10.9,
            "top": per_capita[0], "gap": gaps[0], "export_cze": export[0], "export_den": export[0]}
    thresholds = {"min_minutes": 900, "direction": 0.05}
    sens = pd.DataFrame([{"scenario": "baseline", "description": "current multipliers from config/league_quality.yaml",
                          "top10_overlap": 29, "top10_churn": 0, "mean_delta_rank_top20": 0.0}])
    player_index = [{
        "player_key": "patrik schick|1996", "fbref_id": "5d4f7d61", "card_id": "5d4f7d61", "player": "Patrik Schick",
        "ascii_name": "patrik schick", "pos_group": "FW", "age": 28, "league": "GER-Bundesliga", "club": "Leverkusen",
        "min": 1684, "npg_ast_q": 0.68, "cluster_style": "C0", "cluster_label": tr.term("High-volume scorers"), "nt_flag": True,
    }, {
        "player_key": "filip vecheta|2003", "fbref_id": "0e5dcb3d", "card_id": "", "player": "Filip Vecheta",
        "ascii_name": "filip vecheta", "pos_group": "FW", "age": 21, "league": "CZE-First League", "club": "Slovácko",
        "min": 2100, "npg_ast_q": 0.33, "cluster_style": "C0", "cluster_label": tr.term("High-volume scorers"), "nt_flag": False,
    }]
    return {
        **_translator_context(tr), "seasons": seasons, "groups": ["FW"], "group_titles": GROUP_TITLES,
        "hero": hero,
        "findings": _build_findings(hero, gaps, pathways, squad_lens, seasons, tr),
        "per_capita": per_capita, "max_per_million": 9.9,
        "cohorts": cohorts, "cohort_countries": ["CZE", "DEN"], "cohort_names": {"CZE": "Czechia", "DEN": "Denmark"},
        "cohort_gaps": gaps,
        "observations": _build_observations(hero, per_capita, gaps, movers | {"MF": movers["FW"], "DF": movers["FW"]},
                                            thresholds, seasons, n_headline=1, tr=tr),
        "clusters": clusters, "cluster_names": {"FW": {"style": {"C0": tr.term("High-volume scorers")}, "quality": {"C2": tr.term("High-volume scorers in top-five leagues")}}},
        "movers": movers, "thresholds": thresholds,
        "pathways": pathways, "squad_lens": squad_lens, "cards": cards,
        "card_rows": _card_rows(cards, tr, nt_core_event="2026 FIFA World Cup"),
        "nt_core_event": "2026 FIFA World Cup",
        "player_index": player_index,
        "analog_blocks": analog_blocks,
        "atlas_notes": {"FW": {"n_corpus": 926, "n_czech": 39, "n_nt": 18}},
        "multipliers": [{"league": "ENG-Premier League", "value": 1.0}, {"league": "CZE-First League", "value": 0.434}],
        "multiplier_source": "", "multiplier_method": "uefa_coefficient",
        "feature_defs": {"features": ["npg_p90", "ast_p90", "min_share", "age", "cards_p90"],
                         "min_minutes": 450, "phantom_minutes": 900},
        "loadings": [{"position": "FW", "projection": "style", "pc": "PC1", "explained_pct": 26.8,
                      "npg_p90": 0.501, "ast_p90": 0.469, "min_share": 0.544, "age": 0.191, "cards_p90": -0.444}],
        "sensitivity": _build_sensitivity(sens, tr),
        "limitations": _build_limitations(facts, tr),
        "data_quality": _build_data_quality(data_quality, tr),
        "facts": facts,
        "n_leagues": 19, "headline_leagues": ["ENG-Premier League"],
        "stepping_stone": ["NED-Eredivisie"], "seed": config.RANDOM_SEED,
        "photo_credits": [{"fbref_id": "5d4f7d61", "name": "Patrik Schick", "player_key": "patrik schick|1996",
                           "image": "img/players/5d4f7d61.jpg", "credit": "Patrik Schick (cropped).jpg",
                           "license": "Wikimedia Commons"}],
        "rendered_at": "2026.09.13 00:00",  # dotted so the no-typed-season test regex does not read it as a season
        "repo_url": "https://github.com/barborasandova/czefootball-player-pool-atlas",
        **_build_flow_urls("https://github.com/barborasandova/czefootball-player-pool-atlas"),
    }


def render_html(context: dict[str, Any]) -> str:
    """Render one language; Czech pages get decimal commas in their text nodes."""
    env = Environment(loader=FileSystemLoader(str(config.TEMPLATES_DIR)), autoescape=True)
    html = env.get_template("report.html.j2").render(**context)
    return localize_html_numbers(html) if context.get("lang") == "cs" else html


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
        # outputs/*.svg is gitignored; the heatmap is a pure function of two
        # processed tables the report already loads, so redraw it here rather
        # than requiring a src.international_benchmark run (no network).
        LOG.info("%s missing; redrawing it from per_capita + cohorts", heatmap)
        render_cohort_heatmap(data["per_capita"], data["cohorts"], heatmap)

    for lang in LANGS:
        context = build_context(data, atlas_notes, lang=lang)
        html_out = render_html(context)
        html_path = config.OUTPUTS_DIR / ("index.html" if lang == "en" else f"{lang}/index.html")
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_out, encoding="utf-8")
        LOG.info("wrote %s (%d bytes)", html_path, len(html_out.encode("utf-8")))

    css_src = config.TEMPLATES_DIR / "style.css"
    if css_src.exists():
        shutil.copyfile(css_src, config.OUTPUTS_DIR / "style.css")
        LOG.info("copied style.css")


if __name__ == "__main__":
    main()
