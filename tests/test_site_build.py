"""Site build: site/build.sh turns the two renders into docs/ (EN) and docs/cs/
(CS) with the site layer applied, the Czech figure labels and atlas_meta.json.

Runs the real build on the real outputs (a render must exist: `make render`)
into a temp dir, so the committed docs/ is never rewritten by the test suite;
the whole thing takes about a second.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RENDERED = ROOT / "outputs" / "index.html"

pytestmark = pytest.mark.skipif(not RENDERED.exists(), reason="no render in outputs/ (run `make render`)")


DOCS_PAGES = [ROOT / "docs" / "index.html", ROOT / "docs" / "cs" / "index.html", ROOT / "docs" / "atlas_meta.json"]


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
    return {
        "en": (out / "index.html").read_text(encoding="utf-8"),
        "cs": (out / "cs" / "index.html").read_text(encoding="utf-8"),
    }


def test_build_into_temp_dir_leaves_docs_untouched(site_dir):
    out, docs_unchanged = site_dir
    assert docs_unchanged, "site/build.sh <out> must not rewrite docs/"
    for asset in ("modern.css", "atlas.js", "style.css", "CNAME"):
        assert (out / asset).exists(), asset


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
        assert '<nav class="topbar"' in html and 'class="lang-switch"' in html
        assert f'href="{prefix}modern.css?v=' in html and f'src="{prefix}atlas.js?v=' in html
        assert 'hreflang="cs" href="https://football.datasimply.eu/cs/"' in html
        # one card per position group per showcase rule (currently 5 rules, 3
        # groups); a rule can miss a group, so the count is a range.
        assert 12 <= html.count('class="cycle-card-visual') <= 18
        assert 'class="cast"' in html and 'class="hero-cutout"' in html
        assert 'id="player-search"' in html and 'class="player-index-table"' in html
        assert html.count("<details class=\"cluster\">") >= 12
        assert "data-tex=" in html and "katex" in html
        assert "data-cluster-names=" in html


def test_czech_page_points_at_czech_figures(built, site_dir):
    out, _ = site_dir
    cs = built["cs"]
    for name in ("atlas_FW.svg", "atlas_MF.svg", "atlas_DF.svg", "intl_cohort_heatmap.svg"):
        assert f'<img src="{name}"' in cs, name
        assert (out / "cs" / name).exists()
        svg = (out / "cs" / name).read_text(encoding="utf-8")
        assert "<text " in svg and ("Český fotbal" in svg or "Mezinárodní" in svg)
    for name in ("atlas_FW.svg", "intl_cohort_heatmap.svg"):
        assert f'<img src="{name}"' in built["en"]


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
    for html in built.values():
        rows = re.findall(r'<tr [^>]*data-name="', html)
        assert 150 <= len(rows) <= 260, len(rows)
