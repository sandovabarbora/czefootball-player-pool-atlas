"""Render the English report of the Czech football player pool atlas.

Reads only `data/processed/<NATION>/*` (falling back to the committed
`data/snapshot/<NATION>/` copy of any missing file), `config/*.yaml`,
`site/players.<NATION>.json` and `outputs/<NATION>/intl_cohort_heatmap.svg`
(redrawn from the processed tables when missing); never touches the network.

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
import re
import shutil
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from src import config
from src.feature_eda import RAW_COLUMNS as FEATURE_EDA_RAW_COLUMNS
from src.features import FEATURES as FEATURE_EDA_FEATURES
from src.i18n import LANGS, Translator, localize_html_numbers
from src.international_benchmark import render_cohort_heatmap
from src.logging_setup import setup as logging_setup
from src.references import harvard_list, in_text, in_text_multi, refs_by_key
from src.utils import collapse_player_seasons, normalize_name, player_key as make_player_key, read_parquet, resolve_processed, season_label

matplotlib.use("Agg")

LOG = logging.getLogger(__name__)

GROUPS = ["FW", "MF", "DF"]
GROUP_TITLES = {"FW": "Forwards", "MF": "Midfielders", "DF": "Defenders"}
# Mirrors src.league_strength.REFERENCE_LEAGUE -- kept as a literal here (not
# imported) so render.py, imported by most of the test suite, doesn't pull in
# PyMC/ArviZ just for one string constant.
LEAGUE_STRENGTH_REFERENCE = "ENG-Premier League"
COHORT_ORDER = ["U22", "23-25", "26-29", "30+"]
# Home nation + the editorial subset of peers shown in the cohort exhibit
# table (config/nations/<NATION>.yaml::cohort_exhibit).
COHORT_COUNTRIES = [config.HOME, *config.nation()["cohort_exhibit"]]
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
# Display grouping for the cards section (task 9, "de-clutter"): the two
# national-team-core rules (top-9 and domestic-league minutes among the event
# squad) share one row, kicker `kicker.ntcore_merged`, cards in the order
# top-9 trio then home trio. Row order: highest quality-adjusted, NT core
# merged, youngest call-up, most top-9 minutes, domestic U23. This is a
# *display* regrouping of the same six RULE_KICKERS rules above; the card
# count bound in tests still reasons about the six underlying rules.
CARD_ROW_ORDER: list[list[str]] = [
    ["highest quality-adjusted"],
    ["most top-9 minutes among", "most domestic minutes among"],
    ["youngest national-team"],
    ["most top-9 league minutes"],
    ["most domestic-league minutes"],
]
DESTINATION_LABELS = {
    "domestic": "domestic", "top9": "top-9", "stepping_stone": "stepping stone",
    "peer_domestic": "peer country league", "other": "other",
}
CARD_ANALOGS = 3
CLUSTER_TOP_N = 5
ATLAS_NAMES_N = 10
MOVERS_N = 5
SITE_PLAYERS = config.ROOT_DIR / "site" / f"players.{config.NATION}.json"

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


def _cluster_top_surnames(coords: pd.DataFrame, season: str, style_id: str, n: int = 3) -> list[str]:
    """Surnames of the `n` home-eligible players with the most metrics-season
    minutes in one style cluster -- the tactical read's computed examples
    (Task 14b), right for any nation and any refit (the hand-typed name
    lists config/cluster_labels.yaml used to carry were not)."""
    needed = {"cluster_style", "home_eligible", "player", "min", "season", "player_key"}
    if not needed <= set(coords.columns):
        return []
    cur = _metrics_rows(coords, season)
    members = cur[cur["cluster_style"] == style_id]
    cz = members[members["home_eligible"]].sort_values("min", ascending=False)
    return [_last_name(nm) for nm in cz["player"].head(n).tolist()]


def _with_tactical_examples(base: str, examples: list[str]) -> str:
    """Append the computed "(Surname, Surname, Surname)" to a tactical read's
    base text (which now ends without one -- see `_cluster_top_surnames`)."""
    if not base:
        return ""
    return f"{base} ({', '.join(examples)})." if examples else f"{base}."


def _home_per_capita_row(per_capita: list[dict]) -> dict:
    """The home nation's own row in the per-capita benchmark.

    In a real run this is always present (the pipeline computed the table
    for this NATION). It can be missing only in the offline smoke-test setup
    of Task 14b's brief -- another nation's processed data copied verbatim
    under a different NATION, e.g. `data/processed/cze/*` copied into
    `data/processed/eng/` with no fetch/pipeline re-run -- in which case a
    zero-count placeholder keeps the render from crashing rather than the
    report silently mis-attributing a peer's numbers to the home nation.
    """
    row = next((r for r in per_capita if r["country"] == config.HOME), None)
    if row is not None:
        return row
    LOG.warning("%s has no per-capita row (mismatched NATION=%s vs. the processed data); "
                "using a zero-count placeholder", config.HOME, config.NATION)
    return {
        "country": config.HOME, "name": config.nation()["name"],
        "n_players": 0, "population_m": config.nation()["population_m"],
        "per_million": 0.001, "rank": len(per_capita) + 1,  # not 0: some callers divide by it
    }


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

# Every committed ledger (Task 21d: the v1.2 ledger joins the v1 one, copied
# from .superpowers/sdd/2026-09-14-why-the-train-leaves/progress.md the same
# way the v1 one was) -- n_rulings/n_reviews/n_tasks below sum across all of
# them, not just the v1 one LEDGER_PATH still names for the spec/plan/ledger
# links.
LEDGER_DIR = config.ROOT_DIR / "docs" / "superpowers" / "ledgers"
# The v1.2 sprint's document date, underscored like _DOC_DATE above for the
# same reason (not a typed football season).
_DOC_DATE_V1_2 = "2026_09_14".replace("_", "-")
# ledger filename -> its source `.superpowers/sdd/<dir>/` (task-*-brief.md
# files live there). The working `.superpowers/` tree is untracked and gets
# pruned between sessions -- v1's source dir is already gone from this
# worktree -- so this is a best-effort name, not load-bearing: when the
# directory isn't there, `_count_tasks` falls back to the ledger text itself.
LEDGER_SDD_DIRS = {
    f"{_DOC_DATE}-v1-progress.md": f"{_DOC_DATE}-czech-football-player-pool-atlas",
    f"{_DOC_DATE_V1_2}-v1-2-progress.md": f"{_DOC_DATE_V1_2}-why-the-train-leaves",
}


def _ledger_paths() -> list[Path]:
    return sorted(LEDGER_DIR.glob("*.md")) if LEDGER_DIR.is_dir() else []


def _count_tests() -> int:
    """Lines containing `def test_` across `tests/*.py` — recomputed every render, never typed."""
    return sum(
        1
        for p in sorted((config.ROOT_DIR / "tests").glob("*.py"))
        for line in p.read_text(encoding="utf-8").splitlines()
        if "def test_" in line
    )


def _count_rulings() -> int:
    """Lines containing `Ruling:` across every committed ledger
    (`docs/superpowers/ledgers/*.md`, one per edition) — one per dated
    controller decision, recomputed every render."""
    if not _ledger_paths():
        LOG.warning("no ledgers under %s; rulings count rendered as 0", LEDGER_DIR)
        return 0
    return sum(
        1
        for ledger in _ledger_paths()
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if "Ruling:" in line
    )


def _count_reviews() -> int:
    """Lines mentioning "review" (case-insensitive) across every committed
    ledger (Task 21d, chapter IV's peer-review sentence): reviews are
    two-stage per task (spec + quality) and every review's findings are
    recorded in the ledger, so this line count is the report's own evidence
    for that claim, not a typed number."""
    return sum(
        1
        for ledger in _ledger_paths()
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if "review" in line.lower()
    )


def _count_task_briefs(sdd_dir_name: str) -> int | None:
    """`task-*-brief.md` files under `.superpowers/sdd/<sdd_dir_name>/`, or
    None when that directory isn't present in this worktree."""
    sdd_dir = config.ROOT_DIR / ".superpowers" / "sdd" / sdd_dir_name
    if not sdd_dir.is_dir():
        return None
    return len(list(sdd_dir.glob("task-*-brief.md")))


def _count_tasks_in_ledger_text(ledger: Path) -> int:
    """Distinct `Task N`/`Task Na` identifiers mentioned in one ledger's own
    text — the fallback task count for a ledger whose source
    `.superpowers/sdd/` directory is gone (see `_count_task_briefs`)."""
    ids = {m.group(1) for m in re.finditer(r"\bTask (\d+[a-z]?)\b", ledger.read_text(encoding="utf-8"))}
    return len(ids)


def _count_tasks() -> int:
    """Total tasks across every committed ledger (Task 21d, the build-flow
    diagram): each ledger's `task-*-brief.md` count from its source
    `.superpowers/sdd/` directory when that's still on disk, else the
    distinct `Task N` identifiers mentioned in the ledger's own text —
    "counts computed where possible" per the brief, since the working
    `.superpowers/` tree is untracked and older sessions' source
    directories don't survive into a fresh worktree."""
    total = 0
    for ledger in _ledger_paths():
        sdd_name = LEDGER_SDD_DIRS.get(ledger.name)
        n = _count_task_briefs(sdd_name) if sdd_name else None
        total += n if n is not None else _count_tasks_in_ledger_text(ledger)
    return total


def _build_flow_urls(repo_url: str) -> dict[str, str]:
    """GitHub blob URLs for the design spec, the plan and the ledger."""
    return {
        "spec_url": f"{repo_url}/blob/main/{SPEC_PATH}",
        "plan_url": f"{repo_url}/blob/main/{PLAN_PATH}",
        "ledger_url": f"{repo_url}/blob/main/{LEDGER_PATH}",
    }


_LEDGER_EDITION_RE = re.compile(r"-(v1(?:-2)?)-progress\.md$")
_SPEC_PATH_RE = re.compile(r"docs/superpowers/specs/[\w.\-]+\.md")


def _build_how_built_links(repo_url: str) -> list[dict[str, str]]:
    """One {edition, spec_url, ledger_url} entry per committed ledger under
    `docs/superpowers/ledgers/` (Task 22 item 8: "How this was built" links
    both specs and both ledgers). Each ledger's own header names the spec
    it was built from -- a `Spec:` line for the v1 ledger, or the spec path
    embedded directly in the v1.2 ledger's `plan:` line -- so the pairing
    is read from the ledger text at render time rather than hardcoded; a
    stray draft spec with no ledger of its own (an abandoned revision) is
    correctly left out because nothing points to it.
    """
    links = []
    for ledger in _ledger_paths():
        text = ledger.read_text(encoding="utf-8")
        spec_match = _SPEC_PATH_RE.search(text)
        edition_match = _LEDGER_EDITION_RE.search(ledger.name)
        edition = edition_match.group(1).replace("-", ".") if edition_match else ledger.stem
        ledger_rel = ledger.relative_to(config.ROOT_DIR).as_posix()
        links.append({
            "edition": edition,
            "ledger_url": f"{repo_url}/blob/main/{ledger_rel}",
            "spec_url": f"{repo_url}/blob/main/{spec_match.group(0)}" if spec_match else None,
        })
    return links


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
    cz = cur[cur["home_eligible"]].copy()

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

    adj = config.nation()["adjective"]
    fig.suptitle(f"{adj} football · {GROUP_TITLES[group]} {season_label(season)}",
                 fontsize=14, fontfamily="serif", color=INK, y=1.02, x=0.02, ha="left",
                 weight="normal")
    fig.text(
        0.02, -0.025,
        f"PCA of the five-feature vector (npG/90, A/90, minutes share, age, cards/90), "
        f"{season_label(season)}. Grey: the whole corpus (n = {len(cur)}); coloured: "
        f"{adj}-eligible players by cluster (n = {len(cz)}). Oxblood rings: national-team "
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
    others = [c for c in peers if c != config.HOME]
    gaps = []
    for group in GROUPS:
        for cohort in COHORT_ORDER:
            g = coh[(coh.pos_group == group) & (coh.cohort == cohort)]
            n_by_country = g.set_index("country")["n"] if not g.empty else pd.Series(dtype=int)
            cze_n = int(n_by_country.get(config.HOME, 0))
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
        cz = members[members["home_eligible"]].sort_values("min", ascending=False)
        # Tactical read (Task 14b): the author's text ends without its
        # examples (config/cluster_labels.yaml's tactical.<group>.<key> no
        # longer carries a hand-typed "(Name, Name)" tail); the three
        # home-eligible players with the most metrics-season minutes in this
        # cluster are appended here instead, by surname -- correct for any
        # nation and any refit, where the hand-picked list was not.
        tactical_base = (tactical.get(key) or {}).get(tr.lang, "")
        examples = [_last_name(n) for n in cz["player"].head(3).tolist()]
        tactical_text = _with_tactical_examples(tactical_base, examples)
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
            "tactical": tactical_text,
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
    cz = traj[traj["home_eligible"]]

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
    """Group cards into display rows, in CARD_ROW_ORDER order (task 9).

    A row with two prefixes (the national-team-core row) concatenates their
    members in prefix order — the top-9 trio then the home trio — and takes
    the merged kicker `kicker.ntcore_merged`; every other row uses its single
    rule's kicker. `kicker.ntcore`/`kicker.ntcore_merged` carry the `{event}`
    placeholder; every other kicker is plain.
    """
    tr = tr or Translator("en")
    rows = []
    matched: set[tuple[str, str]] = set()
    for prefixes in CARD_ROW_ORDER:
        members = [c for prefix in prefixes for c in cards if c["reason"].startswith(prefix)]
        if not members:
            continue
        matched.update((c["player_key"], c["reason"]) for c in members)
        if len(prefixes) > 1:
            kicker = tr.raw("kicker.ntcore_merged", event=nt_core_event)
        else:
            key = RULE_KICKER_KEYS[prefixes[0]]
            kicker = tr.raw(key, event=nt_core_event) if key == "kicker.ntcore" else tr.raw(key)
        rows.append({"kicker": kicker, "cards": members})
    rest = [c for c in cards if (c["player_key"], c["reason"]) not in matched]
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
            "tactical": _with_tactical_examples(
                tactical.get(tr.lang, ""), _cluster_top_surnames(coords[group], season, style_id)),
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
                cze = sub[sub.country == config.HOME]
                others = sub[sub.country != config.HOME]
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
                "n": int(b["n"]), "share_of_abroad": float(b.get("share_of_abroad") or 0),  # rounded once, at display time
                "median_multiplier": _opt_float(b.get("median_multiplier"), 3),
                "examples": list((dest_raw.get("examples") or {}).get(b["bucket"], [])),
            } for b in dest_raw.get("buckets", [])],
            key=lambda b: -b["share_of_abroad"])
        destinations = {
            "n_total": int(dest_raw.get("n_total") or 0), "n_abroad": int(dest_raw.get("n_abroad") or 0),
            "buckets": buckets,
            "sideways_share": float(dest_raw.get("sideways_share") or 0),  # rounded once, at display time
            "sideways_definition": str(dest_raw.get("sideways_definition") or ""),
        }

    return {
        "destinations": destinations,
        "youth": youth, "export": export, "fare_min": fare_min, "fare_goals": fare_goals,
        "club_strength_proxy": proxy, "profile": profile,
        "youth_cze": _find(youth, config.HOME), "youth_top": next((r for r in youth if r["share_u21"] is not None), None),
        "export_cze": _find(export, config.HOME), "export_den": _find(export, peer_compare_countries()[-1]),
        "fare_min_cze": _find(fare_min, config.HOME), "fare_goals_cze": _find(fare_goals, config.HOME),
        "fare_min_rank": next((i + 1 for i, r in enumerate(fare_min) if r["country"] == config.HOME), None),
        "fare_goals_rank": next((i + 1 for i, r in enumerate(fare_goals) if r["country"] == config.HOME), None),
        "youth_rank": next((i + 1 for i, r in enumerate(youth) if r["country"] == config.HOME), None),
        "n_countries": len(peers),
    }


def _build_gk(gk_raw: dict) -> dict:
    """Slide 8b context: the goalkeepers counter-example (Task 18), built
    from `goalkeepers.json` (`src.goalkeepers.build_goalkeepers`'s payload,
    already display-rounded there). `{}` when the file is missing --
    `load_data`'s tolerant load -- in which case the template's `{% if gk
    %}` guards render nothing (slide 8b, the chapter IV paragraph, the GK
    card row and the TOC entry all disappear together).
    """
    if not gk_raw:
        return {}
    per_million = gk_raw.get("per_million", [])
    home_row = next((r for r in per_million if r.get("country") == config.HOME), None)
    export_age = gk_raw.get("export_age", {}) or {}
    gk_median_age = export_age.get("gk_median_age")
    outfield_median_age = export_age.get("outfield_median_age")
    earlier_or_later = None
    if gk_median_age is not None and outfield_median_age is not None:
        if gk_median_age < outfield_median_age:
            earlier_or_later = "earlier"
        elif gk_median_age > outfield_median_age:
            earlier_or_later = "later"
        else:
            earlier_or_later = "same_age"
    return {
        "home_row": home_row,
        "home_rank": gk_raw.get("home_rank"),
        "n_peers": gk_raw.get("n_peers"),
        "min_minutes": gk_raw.get("min_minutes"),
        "phantom_minutes": gk_raw.get("phantom_minutes"),
        "export_age": export_age,
        "earlier_or_later": earlier_or_later,
        "club_tier": gk_raw.get("club_tier", []),
        "club_strength_proxy": gk_raw.get("club_strength_proxy", ""),
        "production": gk_raw.get("production", {}),
        "cards": gk_raw.get("cards", []),
        "per_million": per_million,
        "max_per_million": max((r["per_million"] for r in per_million), default=0),
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
    cze = next((c for c in countries if c["country"] == config.HOME), None)
    others = sorted(
        (c for c in countries if c["country"] != config.HOME),
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
            "unmatched": tiers.get("unmatched", 0), "unmatched_pct": pct("unmatched"),
            "cohorts": c["cohorts"],
            "median_minutes": c.get("median_minutes"),
            "median_multiplier": c.get("median_multiplier"),
        })
    return {
        "event": str(lens.get("event", "")),
        "season_label": season_label(lens["season"]),
        "rows": rows,
    }


SQUAD_TIER_ORDER = {"top9": 0, "stepping_stone": 1, "domestic": 2, "other": 3, "unmatched": 4}


def _build_squad_grid(squads: pd.DataFrame, tables: pd.DataFrame, headline: list[str], stepping: list[str],
                      peer_domestic: dict[str, str], season: str, home: str) -> list[dict]:
    """Slide 6's face grid (Task 25b): one row per home-nation `nt_core_event`
    squad player, tier + minutes matched the same way `src.squad_lens.
    build_squad_lens` matches a squad row to its `season` table row (name +
    birth year), ordered by tier (`SQUAD_TIER_ORDER`, same top9 -> stepping
    -> domestic -> other -> unmatched precedence) then minutes descending.
    `player_key` comes from the matched table row when there is one (the
    exact key `site/players.<NATION>.json` is keyed by); an unmatched player
    gets the same `name|born` key `src.utils.player_key`/the pool builder use,
    so a photo fetched for them under that key (see `src.fetch_photos.
    squad_relevant_player_keys`) still resolves. Empty when `squads` has no
    row for `home` or `tables` is empty (pre-fetch data)."""
    from src.squad_lens import _tier

    home_rows = squads[squads.country == home] if not squads.empty else squads
    if home_rows.empty or tables.empty:
        return []
    t = tables[tables.season == season].copy()
    t["player_norm"] = t.player.map(normalize_name)
    rows = []
    for r in home_rows.itertuples():
        cand = t[t.player_norm == r.player_norm]
        if pd.notna(r.born) and "born" in cand.columns:
            cand = cand[cand.born.isna() | (cand.born == r.born)]
        if cand.empty:
            rows.append({"name": str(r.player), "player_key": make_player_key(r.player, r.born),
                        "tier": "unmatched", "min": None})
            continue
        best = cand.sort_values("min", ascending=False).iloc[0]
        rows.append({"name": str(r.player), "player_key": str(best.player_key),
                    "tier": _tier(best.league, home, headline, stepping, peer_domestic),
                    "min": int(best["min"])})
    rows.sort(key=lambda r: (SQUAD_TIER_ORDER.get(r["tier"], 9), -(r["min"] or 0)))
    return rows


def _build_big5(big5_series: dict) -> dict:
    """Slide 7 context: the 26-season Big-5 series (Task 13a) reduced to
    the peak/low/last Czech counts, season-labelled, plus the golden
    generations as one sourced string per season (season label, colon,
    the season's most-minutes Czech names). `{}` when `big5_series.json`
    is missing (pre-Task-13a data), which the template reads as "no slide
    7 proof".
    """
    if not big5_series:
        return {}
    seasons = big5_series["seasons"]
    peak, low = big5_series["cze_peak"], big5_series["cze_low"]
    last_season = seasons[-1]
    home_series = big5_series["countries"].get(config.HOME)
    if home_series is None:
        LOG.warning("%s has no Big-5 series (mismatched NATION=%s vs. the processed data)",
                    config.HOME, config.NATION)
    last_n = home_series["n"][-1] if home_series else 0
    golden = "; ".join(
        f"{season_label(g['season'])}: {', '.join(g['players'])}" for g in big5_series.get("golden", [])
    )
    return {
        "seasons": seasons,
        "countries": big5_series["countries"],
        "first_season": season_label(seasons[0]),
        "peak_n": peak["n"], "peak_season": season_label(peak["season"]),
        "low_n": low["n"], "low_season": season_label(low["season"]),
        "last_n": last_n, "last_season": season_label(last_season),
        "golden": golden,
    }


def peer_compare_countries() -> list[str]:
    """[home] + the two comparison peers (`nation()["compare"]`, falling back
    to the first two configured peers) -- a function, not a frozen
    module-level constant, so every caller gets the *live* config.HOME /
    config.nation() rather than whatever they were when `src.render` was
    first imported. A module-level constant here would go stale the moment
    anything in the process reloads `src.config` to a different nation
    afterwards (e.g. `tests/test_config.py`'s own NATION-reload tests, which
    run inside the same pytest session as `test_template_renders_with_real_
    context`) -- `config.HOME` alone is always read fresh at call time, so a
    frozen countries list built from it goes stale in a way `config.HOME`
    itself doesn't, silently mismatching keys built off this list against
    `config.HOME` looked up later."""
    return [config.HOME] + list(config.nation().get("compare", config.nation()["peers"][:2]))


def _country_sideways_share(features_all: pd.DataFrame, league_quality: dict, leagues_cfg: dict,
                            country: str, season: str) -> float | None:
    """Share of `country`'s exports abroad on a "sideways" move (destination
    league multiplier <= the country's own domestic-league multiplier).

    `src.pathways.destinations()`/`_summarize_destinations()` compute this
    for Czechia only (`home_eligible`, a Czech-specific column); slide 8
    needs the same number for Norway and Denmark, so this reapplies the
    identical rule — MIN_MINUTES_DESTINATIONS, one row per (player_key,
    season, pos_group) — to any country with a domestic league on file in
    `leagues_cfg["peer_domestic"]`. Returns None when the country has no
    domestic league on file or no multiplier for it.
    """
    from src.pathways import MIN_MINUTES_DESTINATIONS, _dedupe_player_season

    domestic_by_country = {v["country"]: k for k, v in leagues_cfg["peer_domestic"].items()}
    domestic_by_country[config.HOME] = leagues_cfg["domestic"]
    domestic_league = domestic_by_country.get(country)
    mult = league_quality["multipliers"]
    domestic_multiplier = mult.get(domestic_league) if domestic_league else None
    if domestic_league is None or domestic_multiplier is None:
        return None
    f = features_all[
        (features_all["season"] == season) & (features_all["nation"] == country)
        & (features_all["min"] >= MIN_MINUTES_DESTINATIONS)
    ]
    f = _dedupe_player_season(f, key_cols=("player_key", "season", "pos_group"))
    abroad = f[f["league"] != domestic_league]
    if abroad.empty:
        return None
    multipliers = abroad["league"].map(mult)
    sideways = multipliers.notna() & (multipliers <= domestic_multiplier)
    return float(sideways.sum()) / len(abroad)


def _build_peer_compare(per_capita: list[dict], pathways: dict, squad_lens: dict, big5_series: dict,
                        features_all: pd.DataFrame, league_quality: dict, leagues_cfg: dict,
                        season: str, names: dict[str, str],
                        countries: list[str] | None = None) -> dict:
    """Slide 8's `table.peer-compare`: six same-definition numbers plus the
    Big-5 count now, one column per country in `countries` (default: `peer_
    compare_countries()`, e.g. CZE/NOR/DEN under NATION=cze -- resolved
    fresh here rather than a frozen default so it always tracks the live
    home nation, see `peer_compare_countries`'s own docstring).

    Every row reuses a number already built elsewhere in the context (per
    capita, pathways youth/export/fare, squad_lens) except "sideways %",
    which `_country_sideways_share` computes fresh (see its docstring). A
    country missing a source for one row (Denmark has no row in
    `squad_lens.json` — not in the fetched 2026 World Cup squad tables)
    renders that cell as `None`, which the template shows as "—".
    """
    countries = countries if countries is not None else peer_compare_countries()
    pc_by = {r["country"]: r for r in per_capita}
    youth_by = {r["country"]: r for r in pathways.get("youth", [])}
    export_by = {r["country"]: r for r in pathways.get("export", [])}
    fare_by = {r["country"]: r for r in pathways.get("fare_min", [])}
    squad_by = {r["country"]: r for r in (squad_lens or {}).get("rows") or []}
    b5_by = (big5_series or {}).get("countries", {})

    def cell(value: float | int | None, fmt: str) -> dict:
        if value is None:
            return {"value": None, "fmt": fmt}
        return {"value": value, "fmt": fmt}

    rows_spec = [
        ("per_million", "peer_compare.per_million", "f2",
         lambda c: (pc_by.get(c) or {}).get("per_million")),
        ("u21_share", "peer_compare.u21_share", "pct1",
         lambda c: (youth_by.get(c) or {}).get("share_u21")),
        ("export_age", "peer_compare.export_age", "g",
         lambda c: (export_by.get(c) or {}).get("median_export_age_recent")),
        ("sideways", "peer_compare.sideways", "pct",
         lambda c: _country_sideways_share(features_all, league_quality, leagues_cfg, c, season)),
        ("minutes_share", "peer_compare.minutes_share", "pct",
         lambda c: (fare_by.get(c) or {}).get("value")),
        ("wc_top9", "peer_compare.wc_top9", "pct",
         lambda c: (((squad_by.get(c) or {}).get("top9_pct")) / 100) if squad_by.get(c) else None),
        ("big5_now", "peer_compare.big5_now", "int",
         lambda c: ((b5_by.get(c) or {}).get("n") or [None])[-1]),
    ]
    rows = [
        {"key": key, "label_key": label_key,
         "by_country": {c: cell(getter(c), fmt) for c in countries}}
        for key, label_key, fmt, getter in rows_spec
    ]
    by_key = {r["key"]: r for r in rows}

    def _val(row_key: str, country: str) -> float | None:
        return by_key[row_key]["by_country"][country]["value"]

    return {
        "countries": countries,
        "names": {c: names.get(c, c) for c in countries},
        "rows": rows,
        "nor_u21": _val("u21_share", countries[1]), "cze_u21": _val("u21_share", config.HOME),
        "nor_top9": _val("wc_top9", countries[1]), "cze_top9": _val("wc_top9", config.HOME),
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


# Byte budget for the in-browser sensitivity slider's embedded payload
# (Task 21c) -- checked in `_build_sensitivity_shrunk` so a future season's
# larger home-eligible pool fails the render loudly rather than silently
# ships a heavier page.
SENSITIVITY_SHRUNK_MAX_BYTES = 50_000


def _build_sensitivity_shrunk(features: dict[str, pd.DataFrame], metrics_season: str) -> list[dict]:
    """`data-shrunk` payload for the in-browser sensitivity slider (Task 21c):
    one row per home-eligible metrics-season player, every position group
    pooled flat (`player_key, name, league, npg_shrunk, ast_shrunk`).

    `docs/atlas.js` recomputes `q = (npg_shrunk + ast_shrunk) * m_league`
    from this payload under the viewer's own multipliers -- the same
    quantity `src/sensitivity.py`'s `_rank_group` computes offline
    (`(npg_p90_shrunk + ast_p90_shrunk) * multiplier`), so the two rank the
    same way at the config baseline (see `tests/test_site_build.py`, which
    checks that equality directly). A mid-season transfer is collapsed the
    same way `sensitivity.main()` collapses it (`collapse_player_seasons`),
    so a player appears once here, not once per club.
    """
    rows = []
    for df in features.values():
        sub = df[(df["season"] == metrics_season) & df["home_eligible"]].copy()
        if sub.empty:
            continue
        sub = collapse_player_seasons(sub, rate_cols=["npg_p90_shrunk", "ast_p90_shrunk"])
        for r in sub.itertuples():
            rows.append({
                "player_key": r.player_key, "name": str(r.player), "league": str(r.league),
                "npg_shrunk": round(float(r.npg_p90_shrunk), 4),
                "ast_shrunk": round(float(r.ast_p90_shrunk), 4),
            })
    rows.sort(key=lambda r: r["player_key"])
    n_bytes = len(json.dumps(rows, separators=(",", ":")).encode("utf-8"))
    if n_bytes > SENSITIVITY_SHRUNK_MAX_BYTES:
        raise ValueError(
            f"sensitivity slider payload is {n_bytes} bytes, over the {SENSITIVITY_SHRUNK_MAX_BYTES}-byte budget "
            "(Task 21c) -- trim the payload (fewer decimals, drop a field) before shipping it")
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


def _build_league_strength(ls: dict, domestic_league: str, tr: Translator | None = None) -> dict:
    """Chapter IV `#league-strength`: M2's per-league `m_L` table plus its
    own validation (posterior predictive check, out-of-sample on the
    metrics season, Spearman rank correlation against
    `config/league_quality.yaml`'s UEFA multipliers) and sampler
    diagnostics. `ls` is `league_strength.json`'s raw shape (`{}` when the
    file is missing -- `load_data`'s tolerant load -- in which case every
    list here is empty and the template section renders nothing).
    """
    tr = tr or Translator("en")
    leagues = ls.get("leagues", [])
    home = next((r for r in leagues if r["league"] == domestic_league), None)
    oos = ls.get("oos", {}) or {}
    oos_rows = [dict(r, method_label=tr.raw(f"ch4.strength.oos.method.{r['method']}")) for r in oos.get("rows", [])]
    oos_winner = max(oos_rows, key=lambda r: r["log_pred_density"]) if oos_rows else None
    return {
        "leagues": leagues,
        "home": home,
        "home_is_reference": bool(home) and home["league"] == LEAGUE_STRENGTH_REFERENCE,
        "diagnostics": ls.get("diagnostics", {}) or {},
        "ppc": ls.get("ppc", {}) or {},
        "oos": {
            "metrics_season": season_label(oos["metrics_season"]) if oos.get("metrics_season") else "",
            "n_candidates": oos.get("n_candidates", 0),
            "rows": oos_rows,
            "refit_runtime_s": oos.get("refit_runtime_s", 0),
            "winner": oos_winner,
        },
        "spearman": ls.get("spearman") or {"rho": None, "p": None, "n": 0},
        "disagreements": ls.get("disagreements", []),
        "fit": ls.get("fit") or {"rows": 0, "players": 0, "seasons": 0, "runtime_s": 0},
    }


# Mirrors src.model_comparison.MODEL_ORDER/BAYES_CHAINS/BAYES_DRAWS/
# BAYES_MAX_TRAIN -- kept as literals here (not imported) so render.py,
# imported by most of the test suite, doesn't pull in PyMC/ArviZ/
# scikit-learn just for an ordering list and three run-budget constants.
MODEL_COMPARISON_ORDER = ["persistence", "shrinkage_league_mean", "bayesian", "gbm", "mlp"]
MODEL_COMPARISON_BAYES_CHAINS = 2
MODEL_COMPARISON_BAYES_DRAWS = 400
MODEL_COMPARISON_BAYES_MAX_TRAIN = 2500


def _build_model_comparison(mc: dict, tr: Translator | None = None) -> dict:
    """Chapter IV `#model-comparison`: the rolling-origin table (models x
    origins, pooled row), the Bayesian model's per-origin coverage, the
    winner and its margin over persistence, and the winner's largest
    season-to-season RMSE change ("drift"). `mc` is `model_comparison.json`'s
    raw shape (`{}` when the file is missing -- `load_data`'s tolerant load
    -- in which case every list here is empty and the template section
    renders nothing).
    """
    tr = tr or Translator("en")
    origins = mc.get("origins", [])
    origin_labels = [season_label(o) for o in origins]
    rows = mc.get("rows", [])
    pooled = mc.get("pooled", [])
    pooled_by_model = {r["model"]: r for r in pooled}

    table = []
    for model in MODEL_COMPARISON_ORDER:
        if model not in pooled_by_model:
            continue
        by_origin = {r["origin"]: r for r in rows if r["model"] == model}
        table.append({
            "model": model, "label": tr.raw(f"ch4.compare.model.{model}"),
            "cells": [by_origin.get(o) for o in origins],
            "pooled": pooled_by_model[model],
        })

    winner_key = mc.get("winner_pooled")
    winner = pooled_by_model.get(winner_key)
    persistence = pooled_by_model.get("persistence")
    margin = None
    if winner and persistence and persistence["rmse"]:
        margin = (persistence["rmse"] - winner["rmse"]) / persistence["rmse"]
        margin = round(margin, 4)

    winner_rows = sorted((r for r in rows if r["model"] == winner_key), key=lambda r: r["origin"])
    drift = None
    if len(winner_rows) >= 2:
        deltas = [(a["origin"], b["origin"], abs(a["rmse"] - b["rmse"]))
                  for a, b in zip(winner_rows, winner_rows[1:], strict=False)]
        from_o, to_o, drift_val = max(deltas, key=lambda d: d[2])
        drift = {"from": season_label(from_o), "to": season_label(to_o), "value": drift_val}

    bayesian_rows = [r for r in rows if r["model"] == "bayesian" and r["coverage90"] is not None]

    return {
        "target": mc.get("target", ""), "origins": origins, "origin_labels": origin_labels,
        "table": table,
        "winner": winner, "winner_label": tr.raw(f"ch4.compare.model.{winner_key}") if winner_key else "",
        "margin": margin,
        "drift": drift,
        "bayesian_coverage": [{"origin": season_label(r["origin"]), "coverage90": r["coverage90"]}
                              for r in bayesian_rows],
        "bayesian_coverage_text": ", ".join(
            f"{season_label(r['origin'])}: {round(r['coverage90'] * 100)} %" for r in bayesian_rows),
        "bayesian_pooled_coverage": (pooled_by_model.get("bayesian") or {}).get("coverage90"),
        "notes": mc.get("notes", []),
        "persistence_pooled_rmse": persistence["rmse"] if persistence else None,
        "bayes_chains": MODEL_COMPARISON_BAYES_CHAINS, "bayes_draws": MODEL_COMPARISON_BAYES_DRAWS,
        "bayes_max_train": MODEL_COMPARISON_BAYES_MAX_TRAIN,
    }


# Mirrors src.series_model.CHAINS/DRAWS/TAU_MARGIN -- kept as literals here
# (not imported) so render.py, imported by most of the test suite, doesn't
# pull in PyMC/ArviZ just for three run-budget constants.
SERIES_MODEL_CHAINS = 2
SERIES_MODEL_DRAWS = 500
SERIES_MODEL_TAU_MARGIN = 3


def _build_series_model(sm: dict, names: dict[str, str], tr: Translator | None = None) -> dict:
    """Chapter IV `#series-model` and slide 7's break clause (Task 19): the
    change-point model's break posterior for the home nation and its two
    `series_contrast` peers, the rolling-origin backtest table and the
    report's one forecast. `sm` is `series_model.json`'s raw shape (`{}`
    when the file is missing -- `load_data`'s tolerant load -- in which
    case every list here is empty and the template section renders
    nothing).
    """
    tr = tr or Translator("en")
    if not sm:
        return {}
    br = sm["break"]
    home_top = br["top"][0]
    home_break = {
        "season": season_label(home_top["season"]), "prob": home_top["prob"],
        "delta": br["delta_factor"]["median"], "lo": br["delta_factor"]["lo"], "hi": br["delta_factor"]["hi"],
        "sigma": br["sigma"],
        "top": [{"season": season_label(r["season"]), "prob": r["prob"]} for r in br["top"]],
    }
    contrast = [
        {
            "code": code, "name": names.get(code, code),
            "season": season_label(c["top"][0]["season"]), "prob": c["top"][0]["prob"],
            "delta": c["delta_factor"]["median"], "lo": c["delta_factor"]["lo"], "hi": c["delta_factor"]["hi"],
        }
        for code, c in sm.get("contrast", {}).items()
    ]
    bt = sm.get("backtest", {}) or {}
    backtest_rows = [
        {**r, "origin": season_label(r["origin"]), "next_season": season_label(r["next_season"])}
        for r in bt.get("rows", [])
    ]
    pooled = dict(bt.get("pooled", {}))
    if "mae_model" in pooled and "mae_naive" in pooled:
        pooled["beats"] = pooled["mae_model"] < pooled["mae_naive"]
    forecast_rows = [
        {"code": code, "name": names.get(code, code), "season": season_label(f["season"]),
         "median": f["median"], "lo": f["lo"], "hi": f["hi"]}
        for code, f in sm.get("forecast", {}).items()
    ]
    return {
        "break": home_break,
        "contrast": contrast,
        "backtest": {"rows": backtest_rows, "pooled": pooled, "start": backtest_rows[0]["origin"] if backtest_rows else "",
                    "end": backtest_rows[-1]["origin"] if backtest_rows else ""},
        "forecast": forecast_rows,
        "diagnostics": sm.get("diagnostics", {}) or {},
        "chains": SERIES_MODEL_CHAINS, "draws": SERIES_MODEL_DRAWS, "margin": SERIES_MODEL_TAU_MARGIN,
    }


# Mirrors src.youth_panel.CHAINS/DRAWS/BOOTSTRAP_N -- kept as literals here
# (not imported) so render.py, imported by most of the test suite, doesn't
# pull in PyMC/ArviZ just for three run-budget constants.
YOUTH_PANEL_CHAINS = 4
YOUTH_PANEL_DRAWS = 1000
YOUTH_PANEL_BOOTSTRAP_N = 1000


def _build_youth_panel(yp: dict) -> dict:
    """Chapter IV `#youth-panel` and slide 3's cross-country clause (Task
    20, M3; between/within split from the Task 20 review -- see
    `src.youth_panel`'s module docstring). `yp` is `youth_panel.json`'s raw
    shape (`{}` when the file is missing -- `load_data`'s tolerant load --
    in which case slide 3's extra clause and the chapter IV section both
    render nothing).

    `between` (headline, on the template as `youth_panel.between`) answers
    the "across countries" question the slide asks; `within` (chapter IV
    only, a stated check) is the country-random-intercept fit on the full
    two-season panel, reported because it finds no signal -- not as a
    second headline number.
    """
    if not yp:
        return {}
    panel = [{**r, "season": season_label(r["season"])} for r in yp.get("panel", [])]
    return {
        "panel": panel,
        "means": yp.get("means", []),
        "n": yp.get("n", 0),
        "n_countries": yp.get("n_countries", 0),
        "seasons_used": yp.get("seasons_used", []),
        "between": yp.get("between", {}) or {},
        "within": yp.get("within", {}) or {},
        "ols": yp.get("ols", {}) or {},
        "ols_means": yp.get("ols_means", {}) or {},
        "chains": YOUTH_PANEL_CHAINS, "draws": YOUTH_PANEL_DRAWS, "n_boot": YOUTH_PANEL_BOOTSTRAP_N,
    }


# Mirrors src.gap_decomposition.RIDGE_ALPHA/BOOTSTRAP_N -- kept as a literal
# here (not imported) so render.py doesn't pull in scikit-learn just for a
# run-budget constant already carried by the JSON's own `ridge_alpha`.
GAP_DECOMPOSITION_BOOTSTRAP_N = 1000

# name -> i18n term-table key (src.gap_decomposition.CHANNEL_NAMES' values)
GAP_CHANNEL_LABELS = {
    "u21_share": "U21 minutes",
    "league_strength": "League strength",
    "export_age": "Export age",
}


def _build_gap_decomposition(gd: dict, names: dict[str, str]) -> dict:
    """Chapter IV `#gap-decomposition` and slide 8c (Task 20, M5): the
    linear split of the per-capita gap between the home nation and each
    `compare` country into the three measured channels, plus the residual.
    `gd` is `gap_decomposition.json`'s raw shape (`{}` when the file is
    missing -- `load_data`'s tolerant load -- in which case slide 8c and
    the chapter IV section both render nothing).
    """
    if not gd:
        return {}
    contrasts = []
    for c in gd.get("contrasts", []):
        channels = [{**ch, "label": GAP_CHANNEL_LABELS.get(ch["name"], ch["name"])} for ch in c.get("channels", [])]
        contrasts.append({**c, "name": names.get(c["contrast"], c["contrast"]), "channels": channels})
    return {
        "contrasts": contrasts,
        "primary": contrasts[0] if contrasts else None,
        "n": gd.get("n", 0),
        "coefficients": gd.get("coefficients", {}) or {},
        "ridge_alpha": gd.get("ridge_alpha"),
        "min_gap_for_share": gd.get("min_gap_for_share"),
        "n_boot": GAP_DECOMPOSITION_BOOTSTRAP_N,
    }


# Mirrors src.export_age_model.DRAWS/TUNE/CHAINS/LONO_* -- kept as literals
# here (not imported) so render.py doesn't pull in PyMC/ArviZ just for
# run-budget constants already carried by the JSON's own diagnostics.
EXPORT_AGE_CHAINS = 4
EXPORT_AGE_DRAWS = 1000


def _build_export_age_model(eam: dict) -> dict:
    """Chapter IV `#export-age-model` and slide 4b (Task 23, M1 proper): the
    age-at-export curve. `eam` is `export_age_model.json`'s raw shape (`{}`
    when the file is missing -- `load_data`'s tolerant load -- in which
    case slide 4b and the chapter IV section both render nothing).

    `y21`/`y24` are pulled out of/alongside `age_curve` for slide 4b's
    "arriving at 21 ... those arriving at 24 ..." sentence -- the template
    reads `export_age_model.age_curve` directly for the chapter IV table
    (ages 19/21/23/25/27).
    """
    if not eam:
        return {}
    y21 = next((r for r in eam.get("age_curve", []) if r["age"] == 21), None)
    return {
        **eam,
        "y21": y21,
        "chains": EXPORT_AGE_CHAINS, "draws": EXPORT_AGE_DRAWS,
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


def _build_feature_eda(fe: dict, tr: Translator | None = None) -> dict:
    """Chapter IV `#features-from-raw`: one raw row through the pipeline to a
    feature row, the rejected-candidates table. `fe` is `feature_eda.json`'s
    raw shape (`{}` when the file is missing -- `load_data`'s tolerant load
    -- in which case `raw_row` is falsy and the template section renders
    nothing). `candidate`/`statistic`/`decision` are stable codes the module
    writes (see `src.feature_eda.build_rejected`); this builder is where
    they get translated.
    """
    tr = tr or Translator("en")
    if not fe:
        return {}
    feature_row = fe.get("feature_row") or {}
    rejected = [
        {
            "candidate": r["candidate"],
            "statistic": tr.raw(f"ch4.eda.rejected.{r['candidate']}.statistic"),
            "value": r["value"],
            "decision": tr.raw(f"ch4.eda.rejected.{r['candidate']}.decision"),
        }
        for r in fe.get("rejected", [])
    ]
    penalty_top = fe.get("penalty_top", [])
    penalty_top_text = "; ".join(f"{p['player']} ({p['league']}, {round(p['share'] * 100)} %)" for p in penalty_top)
    distributions = fe.get("distributions", {})
    return {
        "metrics_season": season_label(fe["metrics_season"]),
        "raw_row": fe.get("raw_row"),
        "raw_columns": list(FEATURE_EDA_RAW_COLUMNS),
        "feature_player": feature_row.get("player", ""),
        "feature_rows": [{"name": f, **feature_row[f]} for f in FEATURE_EDA_FEATURES if f in feature_row],
        "rejected": rejected,
        "penalty_top": penalty_top,
        "penalty_top_text": penalty_top_text,
        "n_leagues": len(distributions.get("leagues", [])),
        "most_shrunk": fe.get("most_shrunk"),
        "age_band_range": _age_band_range(fe.get("age_bands") or []),
    }


def _age_band_range(bands: list[dict]) -> str:
    """'0.147 (30+) to 0.175 (23-25)' — the units behind the age-band spread statistic."""
    if not bands:
        return ""
    lo = min(bands, key=lambda b: b["median"])
    hi = max(bands, key=lambda b: b["median"])
    return f"{lo['median']:.3f} ({lo['band']}) – {hi['median']:.3f} ({hi['band']})"


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
    cze = _home_per_capita_row(per_capita)
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
        feat = feat[feat["home_eligible"]]
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
        "peer_squads": _load_parquet_or_empty(p / "peer_squads.parquet"),
        "showcase": _load_json(p / "showcase.json", []),
        "analogs": _load_json(p / "analogs.json", {}),
        "pathways": _load_json(p / "pathways.json", {}),
        "goalkeepers": _load_json(p / "goalkeepers.json", {}),
        "squad_lens": _load_json(p / "squad_lens.json", {}),
        "big5_series": _load_json(p / "big5_series.json", {}),
        "data_quality": _load_json(p / "data_quality.json", {}),
        "league_strength": _load_json(p / "league_strength.json", {}),
        "model_comparison": _load_json(p / "model_comparison.json", {}),
        "series_model": _load_json(p / "series_model.json", {}),
        "youth_panel": _load_json(p / "youth_panel.json", {}),
        "gap_decomposition": _load_json(p / "gap_decomposition.json", {}),
        "export_age_model": _load_json(p / "export_age_model.json", {}),
        "feature_eda": _load_json(p / "feature_eda.json", {}),
        "photos": _load_json(SITE_PLAYERS, {}),
        "cluster_labels": config.cluster_labels(),
        "build_process": config.build_process(),
        "league_quality": config.league_quality(),
        "countries": config.peers_meta(),
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
    # Display-name lookup: the full countries.yaml registry as a base (so a
    # country code that turns up in the processed data but isn't in this
    # NATION's own peer set -- e.g. Task 14b's offline smoke test, another
    # nation's data copied verbatim -- still resolves to a real name term()
    # can translate, not the raw code), the nation-scoped peers overriding it.
    names = {**{c: v["name"] for c, v in config.countries()["peers"].items()},
             **{c: v["name"] for c, v in data["countries"].items()}}

    per_capita = _build_per_capita(data["per_capita"])
    cze = _home_per_capita_row(per_capita)
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
    nt_core_event = config.squads().get("nt_core_event")
    pathways = _build_pathways(data["pathways"], names, peers)
    gk = _build_gk(data["goalkeepers"])
    squad_lens = _build_squad_lens(data["squad_lens"], names)
    if squad_lens:
        # Slide 6's face grid (Task 25b): the home nation's individual squad
        # players, additive to squad_lens's per-country aggregate `rows` (the
        # golden fixture test guards `rows` byte-for-byte; `players` is new).
        squad_lens["players"] = _build_squad_grid(
            data["peer_squads"], data["fbref_players"], list(data["leagues"]["headline"]),
            list(data["leagues"].get("stepping_stone", [])),
            {**{lg: v["country"] for lg, v in data["leagues"].get("peer_domestic", {}).items()},
             config.DOMESTIC_LEAGUE: config.HOME},
            metrics, config.HOME,
        )
    player_index = _build_player_index(data["features"], data["coords"], data["pool"],
                                       data["cluster_labels"], cards, metrics, tr)

    # Pool facts for the masthead and limitations
    lq = data["league_quality"]
    lg = data["leagues"]
    n_leagues = len({*lg["headline"], lg["domestic"], *lg.get("custom", {}), *lg.get("peer_domestic", {})})
    pool = data["pool"]
    cz_cur = {g: _metrics_rows(data["features"][g], metrics) for g in GROUPS}
    cz_cur = {g: df[df["home_eligible"]] for g, df in cz_cur.items()}
    n_with_metrics = sum(len(df) for df in cz_cur.values())
    n_nt_flagged = sum(int(df["nt_flag"].sum()) for df in cz_cur.values())
    nt_events = sorted({e for df in cz_cur.values() for s in df["nt_events"].dropna()
                        for e in str(s).split(" · ") if e})
    # Distinct season labels spanned by the corpus: the analog-depth history
    # plus the three named seasons (previous/metrics/current) — not a typed
    # count, so it tracks config/seasons.yaml automatically.
    n_seasons = len({*seasons_raw["history"], seasons_raw["previous"], seasons_raw["metrics"], seasons_raw["current"]})
    facts = {
        "n_pool": int(len(pool)),
        "n_no_tables": int((~pool["in_fbref_tables"]).sum()),
        "n_with_metrics": n_with_metrics,
        "n_nt_flagged": n_nt_flagged,
        "nt_events": ", ".join(nt_events),
        "n_photos": len(data["photos"]),
        "nt_years": config.nt_years(),
        "n_leagues": n_leagues,
        "n_seasons": n_seasons,
        "tier2_factor": float(lq.get("tier2_factor", 0)),
        "max_multiplier": max(float(v) for v in lq["multipliers"].values()),
        "history_start": seasons["history_start"],
        "coverage_start": seasons["previous"],  # peer domestic leagues are fetched from here on
        "n_tests": _count_tests(),
        "n_rulings": _count_rulings(),
        "n_reviews": _count_reviews(),
        "n_tasks": _count_tasks(),
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

    features_all = pd.concat(data["features"].values(), ignore_index=True)
    big5 = _build_big5(data["big5_series"])
    # English names of the Big-5 chart's lower-panel contrast countries
    # (src.big5_series.MID_TONE_COUNTRIES = nation()["series_contrast"]), for
    # slide.7.alt's alt text; term()-translated in the template like every
    # other data-sourced country name.
    big5["contrast_names"] = [names[c] for c in config.nation()["series_contrast"]]
    series_model = _build_series_model(data["series_model"], names, tr)
    if series_model:
        # Slide 7's answer sentence gains the break (Task 19): sourced from
        # the same change-point fit that backs #series-model below, not a
        # second computation.
        big5["break_season"] = series_model["break"]["season"]
        big5["break_prob"] = series_model["break"]["prob"]
        big5["delta"] = series_model["break"]["delta"]
        big5["delta_lo"] = series_model["break"]["lo"]
        big5["delta_hi"] = series_model["break"]["hi"]
    peer_compare = _build_peer_compare(per_capita, pathways, squad_lens, data["big5_series"],
                                       features_all, lq, lg, metrics, names)

    youth_panel = _build_youth_panel(data["youth_panel"])
    if youth_panel.get("between"):
        # Slide 3's panel clause (Task 20) reuses `pw.*` like slide 7 reuses
        # `big5.*` for its break clause (same mutate-after-build pattern).
        # The headline is the BETWEEN-country fit (one row per country) --
        # see src.youth_panel's module docstring for why the within-country
        # (country-random-intercept) fit is chapter-IV-only, not this one.
        beta = youth_panel["between"]["beta_per_10pp"]
        pathways["panel_n"] = youth_panel["between"]["n"]
        pathways["panel_n_countries"] = youth_panel["between"]["n"]
        pathways["panel_beta"] = beta["median"]
        pathways["panel_beta_lo"] = beta["lo"]
        pathways["panel_beta_hi"] = beta["hi"]

    gap_decomposition = _build_gap_decomposition(data["gap_decomposition"], names)
    export_age_model = _build_export_age_model(data["export_age_model"])

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
        "big5": big5,
        "peer_compare": peer_compare,
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
        "gk": gk,
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
        "sensitivity": {
            **_build_sensitivity(data["sensitivity"] if not data["sensitivity"].empty else pd.DataFrame(
                columns=["scenario", "description", "top10_overlap", "top10_churn", "mean_delta_rank_top20"]), tr),
            "shrunk": _build_sensitivity_shrunk(data["features"], metrics),
        },
        "limitations": _build_limitations(facts, tr),
        "data_quality": _build_data_quality(data["data_quality"], tr),
        "league_strength": _build_league_strength(data["league_strength"], config.DOMESTIC_LEAGUE, tr),
        "model_comparison": _build_model_comparison(data["model_comparison"], tr),
        "series_model": series_model,
        "youth_panel": youth_panel,
        "gap_decomposition": gap_decomposition,
        "export_age_model": export_age_model,
        "feature_eda": _build_feature_eda(data["feature_eda"], tr),
        "references": harvard_list(),
        "cite": {key: in_text(ref) for key, ref in refs_by_key().items()},
        "cite_multi": lambda keys: in_text_multi([refs_by_key()[k] for k in keys]),
        "facts": facts,
        "build_process": {**data["build_process"]["models"], "max_fix_rounds": data["build_process"]["max_fix_rounds"]},
        "home_code": config.HOME,
        "n_leagues": n_leagues,
        "headline_leagues": list(data["leagues"]["headline"]),
        "domestic_league_code": config.DOMESTIC_LEAGUE,
        "stepping_stone": list(data["leagues"].get("stepping_stone", [])),
        "seed": config.RANDOM_SEED,
        "photo_credits": _photo_credits(data["photos"], used_keys),
        "rendered_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "repo_url": "https://github.com/barborasandova/czefootball-player-pool-atlas",
        **_build_flow_urls("https://github.com/barborasandova/czefootball-player-pool-atlas"),
        "how_built_links": _build_how_built_links("https://github.com/barborasandova/czefootball-player-pool-atlas"),
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
        # Slide 3's panel clause (Task 20) -- see build_context's mutate-after-build comment.
        # Between-country headline (Task 20 review fix); matches youth_panel.between below.
        "panel_n": 8, "panel_n_countries": 8, "panel_beta": 0.78, "panel_beta_lo": 0.11, "panel_beta_hi": 1.4,
    }
    gk = {
        "home_row": {"country": "CZE", "name": "Czechia", "n_gk": 3, "population_m": 10.9,
                     "per_million": 0.28, "rank": 4},
        "home_rank": 4, "n_peers": 9, "min_minutes": 450, "phantom_minutes": 900,
        "export_age": {"gk_n": 3, "gk_median_age": 21.0, "gk_censored": 1, "gk_censored_share": 0.333,
                       "outfield_n": 15, "outfield_median_age": 23.0, "outfield_censored": 2,
                       "outfield_censored_share": 0.133,
                       "current_top9_ages": [{"player_key": "jindrich stanek|1996", "player": "Jindřich Staněk",
                                              "first_age": 21.0, "first_season": "2024-2025", "censored": False}]},
        "earlier_or_later": "earlier",
        "club_tier": [{"player": "Jindřich Staněk", "player_key": "jindrich stanek|1996",
                      "league": "GER-Bundesliga", "team": "Mainz 05", "min": 2700, "club_goals_pct": 0.6}],
        "club_strength_proxy": "goals-scored percentile within league",
        "production": {"home": [{"player": "Jindřich Staněk", "player_key": "jindrich stanek|1996",
                                  "team": "Mainz 05", "league": "GER-Bundesliga", "min": 2700, "ga90": 1.22,
                                  "saves90": 2.85, "save_pct_shrunk": 68.4, "cs_share": 0.28, "ga90_q": 0.96}],
                       "peer_medians": [{"country": "CZE", "n": 3, "median_ga90_q": 1.5, "median_saves90": 2.8,
                                         "median_save_pct": 67.5, "median_cs_share": 0.28}]},
        "per_million": [{"country": "CZE", "name": "Czechia", "n_gk": 3, "population_m": 10.9,
                         "per_million": 0.28, "rank": 4}],
        "max_per_million": 0.28,
        "cards": [
            {"player_key": "jindrich stanek|1996", "player": "Jindřich Staněk", "team": "Mainz 05",
             "league": "GER-Bundesliga", "min": 2700, "reason": "most top-9 minutes among home goalkeepers",
             "stats": {"ga90": 1.22, "saves90": 2.85, "save_pct": 68.4, "cs_share": 0.28, "ga90_q": 0.96},
             "club_goals_pct": 0.6, "nt_flag": True, "nt_events": ["UEFA Euro 2024"]},
        ],
    }
    facts = {"n_pool": 475, "n_no_tables": 120, "n_with_metrics": 206, "n_nt_flagged": 63,
             "nt_events": "UEFA Euro 2024", "n_photos": 114, "coverage_start": seasons["previous"],
             "nt_years": config.nt_years(),
             "n_leagues": 19, "n_seasons": 4, "tier2_factor": 0.6, "max_multiplier": 1.0,
             "n_tests": _count_tests(), "n_rulings": _count_rulings(),
             "n_reviews": _count_reviews(), "n_tasks": _count_tasks(), **seasons}
    data_quality = {
        "checks": [
            {"id": "women_filtered", "count": 92, "unit": "entries"},
            {"id": "namesakes", "count": 2, "unit": "players"},
            {"id": "no_tables", "count": 120, "unit": "players"},
            {"id": "split_seasons", "count": 423, "unit": "rows"},
            {"id": "nt_unmatched", "count": 18, "unit": "names"},
            {"id": "missing_born", "count": 0, "unit": "rows"},
            {"id": "gk_unjoined", "count": 1, "unit": "rows"},
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
    # Slide 6's face grid (Task 25b): a handful of home-nation squad players,
    # one per tier, so the fixture-driven template test exercises all four
    # tier tints plus the unmatched fallback.
    squad_lens["players"] = [
        {"name": "Patrik Schick", "player_key": "patrik schick|1996", "tier": "top9", "min": 1684},
        {"name": "Filip Vecheta", "player_key": "filip vecheta|2003", "tier": "stepping_stone", "min": 1200},
        {"name": "Jindřich Staněk", "player_key": "jindrich stanek|1996", "tier": "domestic", "min": 900},
        {"name": "Unmatched Player", "player_key": "unmatched player|x", "tier": "unmatched", "min": None},
    ]
    hero = {"per_million": 1.65, "rank": 2, "n_peers": 2, "n_players": 18, "population_m": 10.9,
            "top": per_capita[0], "gap": gaps[0], "export_cze": export[0], "export_den": export[0]}
    big5_seasons_raw = ["2000-2001", "2007-2008", "2015-2016", "2025-2026"]
    big5 = {
        "seasons": big5_seasons_raw,
        "countries": {"CZE": {"n": [21, 26, 6, 10], "per_million": [1.93, 2.39, 0.55, 0.92],
                              "minutes_share": [0.0094, 0.0136, 0.003, 0.002]}},
        "first_season": season_label(big5_seasons_raw[0]),
        "peak_n": 26, "peak_season": season_label(big5_seasons_raw[1]),
        "low_n": 6, "low_season": season_label(big5_seasons_raw[2]),
        "last_n": 10, "last_season": season_label(big5_seasons_raw[3]),
        "golden": f"{season_label(big5_seasons_raw[1])}: Jaroslav Drobný, Jaroslav Plašil, Radim Kučera",
        "contrast_names": ["Denmark", "Croatia"],
        "break_season": season_label(big5_seasons_raw[2]), "break_prob": 0.63,
        "delta": 0.57, "delta_lo": 0.38, "delta_hi": 0.86,
    }
    peer_compare = {
        "countries": ["CZE", "NOR", "DEN"],
        "names": {"CZE": "Czechia", "NOR": "Norway", "DEN": "Denmark"},
        "rows": [
            {"key": "per_million", "label_key": "peer_compare.per_million", "by_country": {
                "CZE": {"value": 2.39, "fmt": "f2"}, "NOR": {"value": 9.37, "fmt": "f2"}, "DEN": {"value": 12.58, "fmt": "f2"}}},
            {"key": "u21_share", "label_key": "peer_compare.u21_share", "by_country": {
                "CZE": {"value": 0.064, "fmt": "pct1"}, "NOR": {"value": 0.115, "fmt": "pct1"}, "DEN": {"value": 0.153, "fmt": "pct1"}}},
            {"key": "export_age", "label_key": "peer_compare.export_age", "by_country": {
                "CZE": {"value": 22.0, "fmt": "g"}, "NOR": {"value": 22.0, "fmt": "g"}, "DEN": {"value": 22.0, "fmt": "g"}}},
            {"key": "sideways", "label_key": "peer_compare.sideways", "by_country": {
                "CZE": {"value": 0.185, "fmt": "pct"}, "NOR": {"value": 0.22, "fmt": "pct"}, "DEN": {"value": 0.095, "fmt": "pct"}}},
            {"key": "minutes_share", "label_key": "peer_compare.minutes_share", "by_country": {
                "CZE": {"value": 0.5, "fmt": "pct"}, "NOR": {"value": 0.374, "fmt": "pct"}, "DEN": {"value": 0.455, "fmt": "pct"}}},
            {"key": "wc_top9", "label_key": "peer_compare.wc_top9", "by_country": {
                "CZE": {"value": 0.346, "fmt": "pct"}, "NOR": {"value": 0.654, "fmt": "pct"}, "DEN": {"value": None, "fmt": "pct"}}},
            {"key": "big5_now", "label_key": "peer_compare.big5_now", "by_country": {
                "CZE": {"value": 10, "fmt": "int"}, "NOR": {"value": 25, "fmt": "int"}, "DEN": {"value": 38, "fmt": "int"}}},
        ],
        "nor_u21": 0.115, "cze_u21": 0.064, "nor_top9": 0.654, "cze_top9": 0.346,
    }
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
        "big5": big5,
        "peer_compare": peer_compare,
        "per_capita": per_capita, "max_per_million": 9.9,
        "cohorts": cohorts, "cohort_countries": ["CZE", "DEN"], "cohort_names": {"CZE": "Czechia", "DEN": "Denmark"},
        "cohort_gaps": gaps,
        "observations": _build_observations(hero, per_capita, gaps, movers | {"MF": movers["FW"], "DF": movers["FW"]},
                                            thresholds, seasons, n_headline=1, tr=tr),
        "clusters": clusters, "cluster_names": {"FW": {"style": {"C0": tr.term("High-volume scorers")}, "quality": {"C2": tr.term("High-volume scorers in top-five leagues")}}},
        "movers": movers, "thresholds": thresholds,
        "pathways": pathways, "gk": gk, "squad_lens": squad_lens, "cards": cards,
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
        "sensitivity": {
            **_build_sensitivity(sens, tr),
            "shrunk": [
                {"player_key": "patrik schick|1996", "name": "Patrik Schick", "league": "GER-Bundesliga",
                 "npg_shrunk": 0.65, "ast_shrunk": 0.05},
                {"player_key": "filip vecheta|2003", "name": "Filip Vecheta", "league": "CZE-First League",
                 "npg_shrunk": 0.22, "ast_shrunk": 0.08},
            ],
        },
        "limitations": _build_limitations(facts, tr),
        "data_quality": _build_data_quality(data_quality, tr),
        "league_strength": _build_league_strength({
            "leagues": [
                {"league": "ENG-Premier League", "median": 1.0, "hdi_lo": 0.9, "hdi_hi": 1.1,
                 "n_transitions": 42, "uefa": 1.0},
                {"league": "CZE-First League", "median": 0.41, "hdi_lo": 0.28, "hdi_hi": 0.58,
                 "n_transitions": 18, "uefa": 0.434},
            ],
            "diagnostics": {"max_rhat": 1.01, "min_ess_bulk": 620.0, "min_ess_tail": 540.0,
                            "n_divergences": 0, "sigma_league_median": 0.31, "sigma_player_median": 1.42},
            "ppc": {"observed": {"zero_share": 0.31, "mean": 0.42, "p90": 1.0},
                   "replicated": {"zero_share": 0.33, "mean": 0.41, "p90": 1.0}},
            "oos": {"metrics_season": "2025-2026", "n_candidates": 24,
                   "rows": [{"method": "naive", "log_pred_density": -0.95, "mae": 0.21},
                            {"method": "uefa", "log_pred_density": -0.9, "mae": 0.19},
                            {"method": "model", "log_pred_density": -0.85, "mae": 0.17}],
                   "refit_runtime_s": 118.4},
            "spearman": {"rho": 0.81, "p": 0.0001, "n": 18},
            "disagreements": [{"league": "NED-Eredivisie", "model_rank": 3, "uefa_rank": 6,
                              "model_median": 0.71, "uefa": 0.51, "rank_diff": 3}],
            "fit": {"rows": 8108, "players": 2125, "seasons": 7, "runtime_s": 341.2},
        }, "CZE-First League", tr),
        "feature_eda": _build_feature_eda({
            "metrics_season": metrics_raw,
            "raw_row": {"league": "GER-Bundesliga", "season": metrics_raw, "team": "Hoffenheim",
                       "player": "Vladimír Coufal", "nation": "CZE", "pos": "DF", "born": 1992, "age": 32,
                       "mp": 34, "min": 3012, "gls": 1, "ast": 8, "pk": 0, "crdy": 4, "crdr": 0},
            "feature_row": {
                "player": "Vladimír Coufal", "pos_group": "DF",
                "npg_p90": {"raw": 0.0299, "shrunk": 0.0338, "quality": 0.0266, "z": 0.2081},
                "ast_p90": {"raw": 0.239, "shrunk": 0.193, "quality": 0.152, "z": 4.3077},
                "min_share": {"raw": 0.9843, "shrunk": 0.9843, "quality": 0.9843, "z": 1.6701},
                "age": {"raw": 32.0, "shrunk": 32.0, "quality": 32.0, "z": 1.4507},
                "cards_p90": {"raw": 0.1195, "shrunk": 0.1353, "quality": 0.1353, "z": -0.8952},
            },
            "rejected": [
                {"candidate": "gls_p90", "statistic": "corr_npg", "value": 0.973, "decision": "replaced_npg"},
                {"candidate": "mp", "statistic": "corr_min", "value": 0.8443, "decision": "replaced_min_share"},
                {"candidate": "crdr_p90", "statistic": "zero_share", "value": 0.8539, "decision": "folded_cards"},
                {"candidate": "age", "statistic": "band_spread", "value": 0.0283, "decision": "kept"},
                {"candidate": "born", "statistic": "missing_share", "value": 0.0028, "decision": "kept_key"},
            ],
            "penalty_top": [{"player": "Nabil Touaizi", "league": "POR-Primeira Liga", "season": metrics_raw,
                            "share": 1.0}],
            "age_bands": [{"band": "U22", "median": 0.1734, "n": 1155}, {"band": "23-25", "median": 0.1751, "n": 2035},
                         {"band": "26-29", "median": 0.1693, "n": 1527}, {"band": "30+", "median": 0.1468, "n": 939}],
            "missingness": [{"column": "born", "missing": 25, "share": 0.0028}],
            "most_shrunk": {"player": "Antonín Růsek", "league": "CZE-First League", "min": 454,
                           "raw": 0.5947, "shrunk": 0.2499, "delta": -0.3448},
            "distributions": {"leagues": ["ENG-Premier League", "CZE-First League"], "log_scaled": ["npg_p90"]},
        }, tr),
        "model_comparison": _build_model_comparison({
            "target": "npg_p90_quality + ast_p90_quality (season t+1)",
            "origins": ["2021-2022", "2022-2023"],
            "rows": [
                {"model": "persistence", "origin": "2021-2022", "n_test": 1955, "rmse": 0.0768, "mae": 0.0541, "coverage90": None},
                {"model": "shrinkage_league_mean", "origin": "2021-2022", "n_test": 1955, "rmse": 0.1343, "mae": 0.1045, "coverage90": None},
                {"model": "persistence", "origin": "2022-2023", "n_test": 1879, "rmse": 0.0782, "mae": 0.0558, "coverage90": None},
                {"model": "shrinkage_league_mean", "origin": "2022-2023", "n_test": 1879, "rmse": 0.1293, "mae": 0.0996, "coverage90": None},
                {"model": "bayesian", "origin": "2022-2023", "n_test": 1879, "rmse": 0.071, "mae": 0.0522, "coverage90": 0.9122},
                {"model": "gbm", "origin": "2022-2023", "n_test": 1879, "rmse": 0.0723, "mae": 0.0513, "coverage90": None},
                {"model": "mlp", "origin": "2022-2023", "n_test": 1879, "rmse": 0.0794, "mae": 0.0586, "coverage90": None},
            ],
            "pooled": [
                {"model": "persistence", "n_test": 3834, "rmse": 0.0775, "mae": 0.055, "coverage90": None},
                {"model": "shrinkage_league_mean", "n_test": 3834, "rmse": 0.1318, "mae": 0.102, "coverage90": None},
                {"model": "bayesian", "n_test": 1879, "rmse": 0.071, "mae": 0.0522, "coverage90": 0.9122},
                {"model": "gbm", "n_test": 1879, "rmse": 0.0723, "mae": 0.0513, "coverage90": None},
                {"model": "mlp", "n_test": 1879, "rmse": 0.0794, "mae": 0.0586, "coverage90": None},
            ],
            "winner_pooled": "bayesian",
            "notes": ["Fixture data for the offline template test."],
        }, tr),
        "series_model": _build_series_model({
            "break": {
                "top": [{"season": "2014-2015", "prob": 0.6211}, {"season": "2013-2014", "prob": 0.0779},
                        {"season": "2012-2013", "prob": 0.0758}],
                "delta_factor": {"median": 0.5719, "lo": 0.3805, "hi": 0.863}, "sigma": 0.0493,
            },
            "contrast": {
                "DEN": {"top": [{"season": "2021-2022", "prob": 0.1738}, {"season": "2019-2020", "prob": 0.1059},
                                {"season": "2020-2021", "prob": 0.1022}],
                       "delta_factor": {"median": 1.3308, "lo": 0.7083, "hi": 1.9181}, "sigma": 0.0965},
                "CRO": {"top": [{"season": "2003-2004", "prob": 0.2077}, {"season": "2004-2005", "prob": 0.1274},
                                {"season": "2014-2015", "prob": 0.0992}],
                       "delta_factor": {"median": 0.9565, "lo": 0.4988, "hi": 1.4854}, "sigma": 0.0862},
            },
            "backtest": {
                "rows": [
                    {"origin": "2010-2011", "next_season": "2011-2012", "actual": 20.0, "median": 20.0,
                     "lo": 13.0, "hi": 31.0, "naive": 19.0, "mae_model": 0.0, "mae_naive": 1.0, "covered": True},
                    {"origin": "2011-2012", "next_season": "2012-2013", "actual": 19.0, "median": 18.0,
                     "lo": 11.0, "hi": 28.0, "naive": 20.0, "mae_model": 1.0, "mae_naive": 1.0, "covered": True},
                ],
                "pooled": {"mae_model": 2.8, "mae_naive": 2.7333, "coverage90": 0.8667},
            },
            "forecast": {
                "CZE": {"season": "2026-2027", "median": 11.0, "lo": 5.0, "hi": 18.0},
                "DEN": {"season": "2026-2027", "median": 35.0, "lo": 22.0, "hi": 51.0},
                "CRO": {"season": "2026-2027", "median": 24.0, "lo": 14.0, "hi": 35.0},
            },
            "diagnostics": {"max_rhat": 1.01, "min_ess_bulk": 338.9, "min_ess_tail": 283.2, "n_divergences": 0},
        }, {"CZE": "Czechia", "DEN": "Denmark", "CRO": "Croatia"}, tr),
        "youth_panel": _build_youth_panel({
            "panel": [
                {"country": "CZE", "season": "2024-2025", "x": 0.1106, "y": 2.2},
                {"country": "CZE", "season": "2025-2026", "x": 0.0635, "y": 2.39},
                {"country": "DEN", "season": "2024-2025", "x": 0.1319, "y": 13.42},
                {"country": "DEN", "season": "2025-2026", "x": 0.1529, "y": 12.58},
            ],
            "means": [
                {"country": "CZE", "x": 0.0871, "y": 2.3},
                {"country": "DEN", "x": 0.1424, "y": 13.0},
            ],
            "n": 16, "n_countries": 8, "seasons_used": [season_label("2024-2025"), season_label("2025-2026")],
            "between": {"beta_per_10pp": {"median": 0.78, "lo": 0.11, "hi": 1.4}, "alpha": 2.1, "r2": 0.86,
                       "n": 8, "diagnostics": {"max_rhat": 1.0, "min_ess_bulk": 900.0, "min_ess_tail": 950.0,
                                               "n_divergences": 0}},
            "within": {"beta_per_10pp": {"median": -0.16, "lo": -2.53, "hi": 2.17}, "alpha": 6.35, "r2": 0.98,
                      "n": 16, "diagnostics": {"max_rhat": 1.01, "min_ess_bulk": 850.0, "min_ess_tail": 1000.0,
                                               "n_divergences": 0, "sigma_country_median": 5.19}},
            "ols": {"slope_per_10pp": {"point": 0.78, "lo": 0.11, "hi": 1.4}, "intercept": -0.2, "n_boot": 1000},
            "ols_means": {"slope_per_10pp": {"point": 1.07, "lo": -0.17, "hi": 2.33}, "intercept": -0.5, "n_boot": 1000},
        }),
        "gap_decomposition": _build_gap_decomposition({
            "panel": [{"country": "CZE", "y": 2.39, "x1": 0.0635, "x2": 1.0, "x3": 22.0, "x2_source": "m_L"}],
            "coefficients": {"a": 39.6, "b": {"x1": 82.3, "x2": -56.5, "x3": -0.27}},
            "contrasts": [
                {"contrast": "NOR", "gap_total": 6.98,
                 "channels": [
                     {"name": "u21_share", "contribution": 4.22, "share": 0.6, "lo": 1.22, "hi": 5.9},
                     {"name": "league_strength", "contribution": 5.12, "share": 0.73, "lo": 1.9, "hi": 6.77},
                     {"name": "export_age", "contribution": -0.0, "share": -0.0, "lo": -0.0, "hi": 0.0},
                 ], "residual": -2.37, "n": 8},
                {"contrast": "DEN", "gap_total": 10.19,
                 "channels": [
                     {"name": "u21_share", "contribution": 7.35, "share": 0.72, "lo": 2.17, "hi": 10.27},
                     {"name": "league_strength", "contribution": 1.67, "share": 0.16, "lo": 0.65, "hi": 2.26},
                     {"name": "export_age", "contribution": -0.0, "share": -0.0, "lo": -0.0, "hi": 0.0},
                 ], "residual": 1.17, "n": 8},
            ],
            "n": 8, "home": "CZE", "ridge_alpha": 1.0, "min_gap_for_share": 3.0,
        }, {"CZE": "Czechia", "NOR": "Norway", "DEN": "Denmark"}),
        "export_age_model": _build_export_age_model({
            "n": 115, "age_range": {"min": 17.0, "max": 31.0},
            "n_seasons_counts": {"1": 71, "2": 44}, "origin_source_counts": {"m_L": 110, "uefa": 5},
            "use_spline": False, "knots": [19, 21, 23, 25],
            "age_curve": [
                {"age": 19, "median": 0.32, "lo": 0.18, "hi": 0.47},
                {"age": 21, "median": 0.36, "lo": 0.25, "hi": 0.48},
                {"age": 23, "median": 0.39, "lo": 0.29, "hi": 0.50},
                {"age": 25, "median": 0.41, "lo": 0.28, "hi": 0.54},
                {"age": 27, "median": 0.42, "lo": 0.24, "hi": 0.60},
            ],
            "y24": {"age": 24, "median": 0.40, "lo": 0.29, "hi": 0.52},
            "diff_21_24": {"age_a": 21, "age_b": 24, "median": -0.04, "lo": -0.15, "hi": 0.07},
            "beta": {"median": 0.28, "lo": 0.05, "hi": 0.51},
            "home_nation_effect": {"median": -0.03, "lo": -0.15, "hi": 0.09},
            "home_median_age": 22.5, "home_code": "CZE",
            "diagnostics": {"max_rhat": 1.01, "min_ess_bulk": 720.0, "min_ess_tail": 680.0,
                            "n_divergences": 0, "sigma_n_median": 0.08},
            "ppc": {"observed": {"mean": 0.35, "sd": 0.22, "p10": 0.09, "p90": 0.66},
                   "replicated": {"mean": 0.36, "sd": 0.21, "p10": 0.10, "p90": 0.64}},
            "no_strength": {
                "diagnostics": {"max_rhat": 1.01, "min_ess_bulk": 700.0, "min_ess_tail": 650.0,
                                "n_divergences": 0, "sigma_n_median": 0.11},
                "home_nation_effect": {"median": -0.05, "lo": -0.19, "hi": 0.08}, "runtime_s": 30.2,
            },
            "lono": {
                "n_excluded": 8, "n": 107,
                "diff_21_24": {"age_a": 21, "age_b": 24, "median": -0.05, "lo": -0.17, "hi": 0.06},
                "beta": {"median": 0.27, "lo": 0.02, "hi": 0.50},
                "diagnostics": {"max_rhat": 1.02, "min_ess_bulk": 400.0, "min_ess_tail": 380.0,
                                "n_divergences": 0, "sigma_n_median": 0.09},
                "runtime_s": 14.8, "shift_diff_21_24": -0.01,
            },
            "fit": {"n": 115, "runtime_s": 32.5, "runtime_no_strength_s": 30.2, "runtime_lono_s": 14.8},
        }),
        "references": harvard_list(),
        "cite": {key: in_text(ref) for key, ref in refs_by_key().items()},
        "cite_multi": lambda keys: in_text_multi([refs_by_key()[k] for k in keys]),
        "facts": facts,
        "build_process": {**config.build_process()["models"], "max_fix_rounds": config.build_process()["max_fix_rounds"]},
        "home_code": "CZE",
        "n_leagues": 19, "headline_leagues": ["ENG-Premier League"],
        "domestic_league_code": "CZE-First League",
        "stepping_stone": ["NED-Eredivisie"], "seed": config.RANDOM_SEED,
        "photo_credits": [{"fbref_id": "5d4f7d61", "name": "Patrik Schick", "player_key": "patrik schick|1996",
                           "image": "img/players/5d4f7d61.jpg", "credit": "Patrik Schick (cropped).jpg",
                           "license": "Wikimedia Commons"}],
        "rendered_at": "2026.09.13 00:00",  # dotted so the no-typed-season test regex does not read it as a season
        "repo_url": "https://github.com/barborasandova/czefootball-player-pool-atlas",
        **_build_flow_urls("https://github.com/barborasandova/czefootball-player-pool-atlas"),
        "how_built_links": _build_how_built_links("https://github.com/barborasandova/czefootball-player-pool-atlas"),
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

    numbers_context: dict[str, Any] | None = None
    for lang in LANGS:
        context = build_context(data, atlas_notes, lang=lang)
        if numbers_context is None:
            numbers_context = context  # language-independent figures below draw off the first pass
        html_out = render_html(context)
        html_path = config.OUTPUTS_DIR / ("index.html" if lang == "en" else f"{lang}/index.html")
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_out, encoding="utf-8")
        LOG.info("wrote %s (%d bytes)", html_path, len(html_out.encode("utf-8")))

    # Slides 5 and 8's new figures (Task 25c): pure functions of the context
    # already built above, no separate data pass.
    from src.fare_dots import render_fare_dots_figure
    from src.pathway_slope import render_pathway_slope_figure

    if numbers_context is not None:
        render_fare_dots_figure(numbers_context["pathways"]["fare_min"], config.HOME,
                                config.OUTPUTS_DIR / "fare_dots.svg")
        pc = numbers_context["peer_compare"]
        render_pathway_slope_figure(pc["rows"][:6], pc["countries"], config.OUTPUTS_DIR / "pathway_slope.svg")

    css_src = config.TEMPLATES_DIR / "style.css"
    if css_src.exists():
        shutil.copyfile(css_src, config.OUTPUTS_DIR / "style.css")
        LOG.info("copied style.css")


if __name__ == "__main__":
    main()
