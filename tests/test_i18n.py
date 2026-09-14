"""i18n: every English string and data label has a Czech entry, and the
Czech render of the fixture context is actually Czech."""

from __future__ import annotations

import re

import pytest
import yaml

from src import config
from src.i18n import (
    EN,
    TERMS_EN,
    Translator,
    check_complete,
    check_placeholders,
    load_cs,
    localize_html_numbers,
)
from src.render import build_context_from_fixtures, render_html


def test_cs_yaml_is_complete_and_has_no_stray_keys():
    cs = load_cs()
    check_complete(cs)  # raises on a missing string or term
    assert check_placeholders(cs) == []
    assert set(cs["strings"]) == set(EN)


def test_check_complete_fails_loudly():
    cs = load_cs()
    missing = {"strings": {k: v for k, v in cs["strings"].items() if k != "hero.h2"}, "terms": cs["terms"]}
    with pytest.raises(KeyError, match="hero.h2"):
        check_complete(missing)
    no_term = {"strings": cs["strings"], "terms": {k: v for k, v in cs["terms"].items() if k != "Forwards"}}
    with pytest.raises(KeyError, match="Forwards"):
        check_complete(no_term)
    stray = {"strings": dict(cs["strings"], **{"not.a.key": "x"}), "terms": cs["terms"]}
    with pytest.raises(KeyError, match="not.a.key"):
        check_complete(stray)


def test_every_cluster_label_has_a_czech_term():
    labels = yaml.safe_load((config.CONFIG_DIR / "cluster_labels.yaml").read_text(encoding="utf-8"))
    terms = load_cs()["terms"]
    wanted = {lab for grp in ("FW", "MF", "DF") for proj in ("style", "quality") for lab in labels[grp][proj].values()}
    assert wanted <= set(terms), sorted(wanted - set(terms))
    # every tactical read carries both languages
    for grp, reads in labels["tactical"].items():
        for cid, r in reads.items():
            assert r.get("en") and r.get("cs"), (grp, cid)


def test_translator_terms_reasons_and_numbers():
    en, cs = Translator("en"), Translator("cs")
    assert en.term("Forwards") == "Forwards" and cs.term("Forwards") == "Útočníci"
    with pytest.raises(KeyError):
        cs.term("no such label")
    assert cs.term_soft("no such label") == "no such label"
    for pattern in (p for p in TERMS_EN if "{pos}" in p):
        reason = pattern.format(pos="MF")
        assert en.reason(reason) == reason
        assert "MF" in cs.reason(reason) and cs.reason(reason) != reason
    assert (en.ordinal(1), en.ordinal(2), en.ordinal(3), en.ordinal(11), en.ordinal(22)) == ("1st", "2nd", "3rd", "11th", "22nd")
    assert cs.ordinal(2) == "2."
    assert cs.num("1.8 times, 2024/25, d = 0.70") == "1,8 times, 2024/25, d = 0,70"
    assert en.num("1.8") == "1.8"
    assert cs.sensitivity("GER-2. Bundesliga multiplier -20%") == "násobička GER-2. Bundesliga −20 %"
    assert cs.sensitivity("every league multiplier +20%") == "násobička každé ligy +20 %"
    assert en.sensitivity("every league multiplier +20%") == "every league multiplier +20%"


def test_t_escapes_parameters_but_trusts_the_string():
    cs = Translator("cs")
    out = cs("mast.pool_value", n="<b>")
    assert "<strong>" in out and "&lt;b&gt;" in out
    assert cs.raw("mast.pool_value", n="<b>") == "<strong><b></strong> hráčů"
    with pytest.raises(KeyError):
        cs("no.such.key")


def test_localize_html_numbers_touches_text_nodes_only():
    html = '<p style="--v: 1.5">1.65 and 2024/25</p><code>0.5</code><script>x = 1.5</script><span data-tex="a.b">0.70</span>'
    out = localize_html_numbers(html)
    assert '--v: 1.5' in out and "1,65 and 2024/25" in out and "<code>0.5</code>" in out
    assert "x = 1.5" in out and 'data-tex="a.b"' in out and ">0,70<" in out


def test_fixture_context_renders_in_czech():
    en = render_html(build_context_from_fixtures("en"))
    cs = render_html(build_context_from_fixtures("cs"))
    assert '<html lang="en">' in en and '<html lang="cs">' in cs
    for heading in re.findall(r"<h2[^>]*>([^<]+)</h2>", en):
        assert heading not in cs, heading
    assert 'href="../style.css"' in cs and 'src="../atlas_FW.svg"' in cs
    assert "Útočníci" in cs and "Střelci s vysokým objemem" in cs
    assert "zlepšení" in cs and "Vybrán jako: nejvyšší" in cs
    assert ">1,65<" in cs and ">1.65<" in en  # hero figure, decimal comma
    assert "{{" not in cs and "{%" not in cs
    assert "Nejvyšší kvalitou upravená produkce" in cs and "Highest quality-adjusted production" in en
    assert 'data-rule="highest quality-adjusted npG+A per 90 among FW"' in cs  # machine attribute stays English


def test_auto_injected_nation_words_fill_in_without_an_explicit_param():
    """Task 14b: nation, adj, Adj, code, home_league and every cs_* name come
    from config.nation() automatically -- a caller never passes them."""
    en, cs = Translator("en"), Translator("cs")
    assert en.raw("meta.title") == "Czech football · Player pool atlas"
    assert cs.raw("meta.title") == "Český fotbal · Atlas hráčského fondu"
    assert en.auto["nation"] == "Czechia" and en.auto["adj"] == "Czech" and en.auto["code"] == "CZE"
    assert en.auto["home_league"] == "Czech First League"
    assert cs.auto["cs_name"] == "Česko" and cs.auto["cs_adj_pl"] == "čeští" and cs.auto["cs_Adj_pl"] == "Čeští"
    # an explicit param still wins over an auto one of the same name
    assert en.raw("slide.4.how", season="2025/26", home_note="", adj="Overridden") == \
        "Destination league of every Overridden-eligible player's 2025/26 row; " \
        "sideways = destination multiplier ≤ Overridden league multiplier " \
        '(<a href="#league-strength">league strength: two estimates, § Methodology</a>).'


def test_check_placeholders_allows_auto_names_in_either_language_only():
    """cs.yaml may use a cs_* placeholder the English string never names (and
    vice versa for nation/adj/Adj/code/home_league) without tripping the
    subset check -- these are auto-injected, not part of the pair's contract."""
    cs = load_cs()
    assert check_placeholders(cs) == []
    # EN names {adj} (not {code}); CS names {cs_adj_m} and {cs_home_league}
    # (neither in EN) -- an auto name on either side, alone, is not a
    # mismatch: it is exempt from the subset check in both directions.
    probe_en = dict(EN, **{"__probe__": "needs {adj}"})
    probe_cs = dict(cs["strings"], **{"__probe__": "potřebuje {cs_adj_m} a {cs_home_league}"})
    import src.i18n as i18n_mod
    old_en = dict(i18n_mod.EN)
    try:
        i18n_mod.EN.update(probe_en)
        bad = check_placeholders({"strings": probe_cs, "terms": cs["terms"]})
        assert "__probe__" not in bad
    finally:
        i18n_mod.EN.clear()
        i18n_mod.EN.update(old_en)


def test_terms_cover_both_configured_nations_peer_countries():
    """TERMS_EN/cs.yaml's country terms cover cze's cohort (Czechia..Norway)
    and eng's (England..Belgium) -- either NATION can render in Czech."""
    cs_terms = load_cs()["terms"]
    for name in ("Czechia", "Norway", "England", "France", "Germany", "Spain",
                 "Italy", "Netherlands", "Portugal", "Belgium"):
        assert name in TERMS_EN and name in cs_terms


def test_every_template_key_has_an_english_default_and_a_czech_entry():
    template = (config.TEMPLATES_DIR / "report.html.j2").read_text(encoding="utf-8")
    used = set(re.findall(r"""\bt\(\s*['"]([a-z0-9_.]+)['"]""", template))
    assert used, "template calls no t()"
    assert used <= set(EN), sorted(used - set(EN))
    assert used <= set(load_cs()["strings"]), sorted(used - set(load_cs()["strings"]))
