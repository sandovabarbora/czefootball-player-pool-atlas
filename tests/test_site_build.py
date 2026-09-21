"""Site build: site/build.sh turns the two renders into docs/ (EN) and docs/cs/
(CS) with the site layer applied, the Czech figure labels and atlas_meta.json.

Runs the real build on the real outputs (a render must exist: `make render`)
into a temp dir, so the committed docs/ is never rewritten by the test suite;
the whole thing takes about a second.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

from src import config

ROOT = Path(__file__).resolve().parent.parent
# NATION resolved straight from the environment (like site/build.sh's own
# `NATION="${NATION:-cze}"`), NOT `config.NATION` -- `./site/build.sh` below
# runs in its own subprocess and always sees the real env var, but this
# process's `config` module can be left pointing at a different nation by
# the time this file runs (other test modules, e.g. tests/test_config.py,
# reload it mid-session); reading the env var directly keeps this file in
# sync with what the subprocess actually built regardless.
NATION = os.environ.get("NATION", "cze").lower()
RENDERED = ROOT / "outputs" / NATION / "index.html"
# site/build.sh only ships a Czech edition (docs/cs/) for the cze nation
# (the published site keeps its original, un-prefixed layout) -- see its own
# `if [ "$NATION" = "cze" ]` gates. Every cs-specific assertion below is
# skipped for a nation with no CS edition.
HAS_CS = False   # the Czech edition was retired on 2026-09-21; the site is English only
DOCS_DIR = ROOT / "docs" if NATION == "cze" else ROOT / "docs" / NATION

pytestmark = pytest.mark.skipif(not RENDERED.exists(), reason="no render in outputs/ (run `make render`)")


DOCS_PAGES = [DOCS_DIR / "index.html", DOCS_DIR / "atlas_meta.json"] + (
    [DOCS_DIR / "cs" / "index.html"] if HAS_CS else []
)


def _docs_fingerprint() -> list[tuple[bool, int, bytes]]:
    return [(p.exists(), p.stat().st_mtime_ns if p.exists() else 0, p.read_bytes() if p.exists() else b"")
            for p in DOCS_PAGES]


@pytest.fixture(scope="module")
def site_dir(tmp_path_factory) -> tuple[Path, bool]:
    out = tmp_path_factory.mktemp("site")
    before = _docs_fingerprint()
    subprocess.run(["./site/build.sh", str(out)], cwd=ROOT, check=True, capture_output=True)
    return out, _docs_fingerprint() == before


@pytest.fixture(scope="module")
def built(site_dir) -> dict[str, str]:
    out, _ = site_dir
    pages = {"en": (out / "index.html").read_text(encoding="utf-8")}
    if HAS_CS:
        pages["cs"] = (out / "cs" / "index.html").read_text(encoding="utf-8")
    return pages


def test_build_into_temp_dir_leaves_docs_untouched(site_dir):
    out, docs_unchanged = site_dir
    assert docs_unchanged, "site/build.sh <out> must not rewrite docs/"
    for asset in ("modern.css", "atlas.js", "style.css"):   # CNAME stays at the site root only
        assert (out / asset).exists(), asset


@pytest.mark.skipif(not HAS_CS, reason="no CS edition for this nation")
def test_build_produces_both_languages(built):
    en, cs = built["en"], built["cs"]
    assert '<html lang="en">' in en and '<html lang="cs">' in cs
    assert 'href="cs/"' in en and 'href="../"' in cs
    # no untranslated section headings in the Czech page
    for en_heading in re.findall(r"<h2[^>]*>([^<]+)</h2>", en):
        assert en_heading.strip() not in cs, en_heading


def test_site_layer_is_applied_to_both_pages(built):
    for lang, html in built.items():
        prefix = "" if lang == "en" else "../"
        assert '<nav class="topbar"' in html and 'class="lang-switch"' not in html
        assert f'href="{prefix}modern.css?v=' in html and f'src="{prefix}atlas.js?v=' in html
        assert 'hreflang="cs"' not in html
        # one card per position group per showcase rule (currently 5 rules, 3
        # groups); a rule can miss a group, so the count is a range.
        assert 12 <= html.count('class="cycle-card-visual') <= 18
        # task 10: one compact tile per card, first child, "Full card" toggle
        n_visuals = html.count('class="cycle-card-visual')
        assert html.count('class="cycle-tile"') == n_visuals
        assert html.count('class="tile-more"') == n_visuals
        assert '<article class="cycle-card"' in html
        assert html.index('class="cycle-tile"') < html.index('class="cycle-card-visual')
        assert 'class="hero-cutout"' in html
        # the masthead cast strip went in the distill pass (the faces live on
        # the cards); the page must not carry it any more
        assert 'class="cast"' not in html
        assert 'id="player-search"' in html and 'class="player-index-table"' in html
        assert html.count("<details class=\"cluster\">") >= 12
        assert "data-tex=" in html and "katex" in html
        assert "data-cluster-names=" in html




def test_player_atlas_page_is_built_with_portraits(site_dir):
    """site/build_atlas.py: the player atlas page next to the report, and the
    careers data it reads decorated with each player's portrait."""
    out, _ = site_dir
    page = (out / "atlas" / "index.html").read_text(encoding="utf-8")
    assert "data-atlas-app" in page and 'src="../atlas.app.js"' in page and '<nav class="topbar"' in page
    assert (out / "atlas.app.js").exists()
    data = json.loads((out / "charts" / "careers.json").read_text(encoding="utf-8"))
    assert data["players"] and data["seasons_covered"] and data["metrics_season"] in data["seasons_covered"]
    assert any(p.get("photo") for p in data["players"]), "no portrait made it into the careers data"
    # the report links every pool row to its career
    en = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="atlas/#p/' in en and 'href="atlas/"' in en


def test_atlas_meta_covers_three_atlases_and_the_heatmap(site_dir):
    out, _ = site_dir
    meta = json.loads((out / "atlas_meta.json").read_text(encoding="utf-8"))
    assert set(meta) == {"atlas_FW.svg", "atlas_MF.svg", "atlas_DF.svg", "intl_cohort_heatmap.svg"}
    for key in ("atlas_FW.svg", "atlas_MF.svg", "atlas_DF.svg"):
        panels = meta[key]["panels"]
        assert [p["proj"] for p in panels] == ["style", "quality"]
        for p in panels:
            assert p["clusters"] and p["ring"]["pts"] and "cx" in p and "cy" in p
            assert all("px" in n for n in p["names"]), "every name label sits on a point"
    hm = meta["intl_cohort_heatmap.svg"]["panels"]
    assert len(hm) == 3 and all(p["cells"] and p["rows"] and p["cols"] for p in hm)


def test_player_index_has_one_row_per_mapped_player(built):
    """One row per home-eligible player with a metrics-season feature row
    (`src.render._build_player_index`) -- the exact count is nation-specific
    (it tracks the size of that nation's own pool), so it's computed from
    `features_{FW,MF,DF}.parquet` directly rather than a hardcoded range
    calibrated to one nation's numbers."""
    from src.utils import read_parquet

    metrics_season = config.seasons()["metrics"]
    expected = 0
    for group in ("FW", "MF", "DF"):
        df = read_parquet(ROOT / "data" / "processed" / NATION / f"features_{group}.parquet")
        sub = df[(df["season"] == metrics_season) & df["home_eligible"]]
        expected += int(sub["player_key"].nunique())
    for html in built.values():
        rows = re.findall(r'<tr [^>]*data-name="', html)
        assert len(rows) == expected, (len(rows), expected)


def _rank_top10(rows: list[dict], multipliers: dict[str, float]) -> list[str]:
    """(player_key, q) sorted by q desc (ties broken by player_key, matching
    docs/atlas.js's own tie-break) -- the top-10 player_keys, same formula
    the slider and src/sensitivity.py both use: q = (npg + ast) * m_league.
    """
    scored = [
        (r["player_key"], (r["npg_shrunk"] + r["ast_shrunk"]) * multipliers.get(r["league"], 1.0))
        for r in rows
    ]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return [key for key, _ in scored[:10]]


def test_sensitivity_slider_payload_matches_offline_top10_at_defaults(built):
    """Task 21c: the `data-shrunk` payload embedded for the in-browser
    sensitivity slider parses, and -- with no JS involved -- ranking it by
    the slider's own formula at the config-default multipliers lands on the
    same top-10 player_keys as ranking `features_*.parquet` directly (the
    offline source), collapsed the same way `sensitivity.py` collapses a
    mid-season transfer.
    """
    from src.utils import collapse_player_seasons, read_parquet

    html = built["en"]
    m = re.search(r"data-shrunk='(\[.*?\])'", html, re.S)
    assert m, "no data-shrunk payload found on the page"
    shrunk = json.loads(m.group(1))
    assert shrunk, "empty sensitivity-slider payload"
    assert {"player_key", "name", "league", "npg_shrunk", "ast_shrunk"} <= set(shrunk[0])
    assert len(m.group(1).encode("utf-8")) <= 64_000

    multipliers = config.league_quality()["multipliers"]
    metrics_season = config.seasons()["metrics"]
    offline_rows = []
    for group in ("FW", "MF", "DF"):
        df = read_parquet(ROOT / "data" / "processed" / NATION / f"features_{group}.parquet")
        sub = df[(df["season"] == metrics_season) & df["home_eligible"]].copy()
        sub = collapse_player_seasons(sub, rate_cols=["npg_p90_shrunk", "ast_p90_shrunk"])
        offline_rows.extend(
            {"player_key": r.player_key, "league": r.league,
             "npg_shrunk": float(r.npg_p90_shrunk), "ast_shrunk": float(r.ast_p90_shrunk)}
            for r in sub.itertuples()
        )

    assert set(_rank_top10(shrunk, multipliers)) == set(_rank_top10(offline_rows, multipliers))

