import json
from pathlib import Path

import pandas as pd

import src.fetch_photos as fp
from src.fetch_photos import (
    _batch_cache_key,
    _fetch_batches,
    _parse_args,
    _resolve_only_with_metrics,
    match_images,
    sparql_for,
    squad_relevant_player_keys,
)

FIX = json.loads((Path(__file__).parent / "fixtures" / "wikidata_sample.json").read_text())
BINDINGS = FIX["results"]["bindings"]


def test_sparql_embeds_names_and_czech_citizenship():
    q = sparql_for(["Patrik Schick"])
    assert '"Patrik Schick"@en' in q and "wd:Q213" in q
    assert "wd:Q937857" in q  # association football player (occupation constraint)


def test_sparql_escapes_quotes_and_backslashes_in_names():
    q = sparql_for(['Jan "Honza" Novák', "back\\slash"])
    assert '"Jan \\"Honza\\" Novák"@en' in q
    assert '"back\\\\slash"@en' in q


def test_match_by_name_and_birth_year():
    pool = pd.DataFrame({"fbref_id": ["x1"], "player": ["Patrik Schick"], "born": [1996]})
    out = match_images(BINDINGS, pool)
    assert len(out) == 1 and out.iloc[0].image_url.startswith("http")


def test_squad_relevant_player_keys_matches_by_name_and_born_and_skips_unmatched():
    squads = pd.DataFrame({
        "country": ["CZE", "CZE", "CZE", "DEN"],
        "player": ["Matěj Kovář", "Jan Novák", "Ghost Player", "Peter Nielsen"],
        "player_norm": ["matej kovar", "jan novak", "ghost player", "peter nielsen"],
        "born": [2000, 1999, None, 1995],
    })
    pool = pd.DataFrame({
        "player": ["Matěj Kovář", "Jan Novák", "Jan Novák"],
        "player_key": ["matej kovar|2000", "jan novak|1999", "jan novak|1988"],
        "born": [2000, 1999, 1988],
    })
    keys = squad_relevant_player_keys(squads, pool, "CZE")
    # the birth year disambiguates the two "Jan Novák" pool rows; the DEN
    # player is out of scope and the unmatched "Ghost Player" is skipped
    assert keys == {"matej kovar|2000", "jan novak|1999"}


def test_squad_relevant_player_keys_empty_when_home_has_no_squad_rows():
    squads = pd.DataFrame({"country": ["DEN"], "player": ["Peter Nielsen"],
                           "player_norm": ["peter nielsen"], "born": [1995]})
    pool = pd.DataFrame({"player": ["Peter Nielsen"], "player_key": ["peter nielsen|1995"], "born": [1995]})
    assert squad_relevant_player_keys(squads, pool, "CZE") == set()


def test_no_match_when_birth_year_disagrees():
    pool = pd.DataFrame({"fbref_id": ["x1"], "player": ["Patrik Schick"], "born": [1990]})
    out = match_images(BINDINGS, pool)
    assert len(out) == 0


def test_unique_label_match_accepted_when_born_unknown():
    # "Jindřich Staněk" appears only once in the fixture, so with an unknown
    # birth year on our side, the unique label match is accepted.
    pool = pd.DataFrame(
        {"fbref_id": ["x2"], "player": ["Jindřich Staněk"], "born": pd.array([None], dtype="Int64")}
    )
    out = match_images(BINDINGS, pool)
    assert len(out) == 1
    assert out.iloc[0].fbref_id == "x2"


def test_ambiguous_label_skipped_when_born_unknown():
    # "Ladislav Krejčí" appears twice in the fixture (1992 and 1999), both
    # with images -- with no birth year to disambiguate, we must not guess.
    pool = pd.DataFrame(
        {"fbref_id": ["x3"], "player": ["Ladislav Krejčí"], "born": pd.array([None], dtype="Int64")}
    )
    out = match_images(BINDINGS, pool)
    assert len(out) == 0


def test_binding_without_img_is_ignored():
    # "Lukáš Provod" has no "img" key in the fixture.
    pool = pd.DataFrame({"fbref_id": ["x4"], "player": ["Lukáš Provod"], "born": [1996]})
    out = match_images(BINDINGS, pool)
    assert len(out) == 0


def test_batch_cache_key_is_order_independent_and_content_sensitive():
    assert _batch_cache_key(["Patrik Schick", "Tomáš Souček"]) == _batch_cache_key(
        ["Tomáš Souček", "Patrik Schick"]
    )
    assert _batch_cache_key(["Patrik Schick"]) != _batch_cache_key(["Tomáš Souček"])


def test_fetch_batches_caches_by_name_content_not_batch_position(tmp_path, monkeypatch):
    # A positional "batch_<i>.json" cache key would silently serve a stale
    # response after the pool changes -- the cache path must depend on the
    # batch's actual names instead.
    monkeypatch.setattr(fp, "WIKIDATA_CACHE_DIR", tmp_path)
    monkeypatch.setattr(fp.time, "sleep", lambda _seconds: None)

    seen_paths: list[Path] = []
    fetch_calls = []

    def fake_cached_text(url, cache_path, *, headers=None, timeout=15.0):
        seen_paths.append(cache_path)
        fetch_calls.append(url)
        return json.dumps({"results": {"bindings": []}})

    monkeypatch.setattr(fp, "cached_text", fake_cached_text)

    _fetch_batches(["Patrik Schick"])
    _fetch_batches(["Tomáš Souček"])

    assert len(seen_paths) == 2
    assert seen_paths[0] != seen_paths[1]  # different names -> different cache file
    assert all(p.parent == tmp_path for p in seen_paths)


def test_only_with_metrics_defaults_on_above_threshold_off_below():
    assert _resolve_only_with_metrics(None, fp.ONLY_WITH_METRICS_POOL_THRESHOLD + 1) is True
    assert _resolve_only_with_metrics(None, fp.ONLY_WITH_METRICS_POOL_THRESHOLD) is False
    assert _resolve_only_with_metrics(None, 10) is False


def test_only_with_metrics_explicit_flag_overrides_the_threshold():
    assert _resolve_only_with_metrics(False, fp.ONLY_WITH_METRICS_POOL_THRESHOLD + 1) is False
    assert _resolve_only_with_metrics(True, 10) is True


def test_only_with_metrics_cli_flags_parse():
    assert _parse_args(["--only-with-metrics"]).only_with_metrics is True
    assert _parse_args(["--no-only-with-metrics"]).only_with_metrics is False
    assert _parse_args([]).only_with_metrics is None


# --- Wikipedia page-image fallback -----------------------------------------
from src.fetch_photos import wikipedia_candidate


def _pages(**page):
    return {"query": {"pages": {"1": page}}}


def test_wikipedia_candidate_accepts_footballer_with_matching_birth_year():
    api = _pages(title="Pavel Šulc", original={"source": "https://upload.wikimedia.org/x/Pavel_Sulc.jpg"},
                 pageprops={"wikibase_item": "Q123"})
    entity = {"entities": {"Q123": {"claims": {
        "P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q937857"}}}}],
        "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+2000-12-19T00:00:00Z"}}}}]}}}}
    assert wikipedia_candidate(api, entity, born=2000) == ("https://upload.wikimedia.org/x/Pavel_Sulc.jpg", "Pavel_Sulc.jpg")


def test_wikipedia_candidate_rejects_other_occupation_or_wrong_year_or_disambiguation():
    api = _pages(title="X", original={"source": "https://u/x.jpg"}, pageprops={"wikibase_item": "Q1"})
    hockey = {"entities": {"Q1": {"claims": {"P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q11774891"}}}}]}}}}
    assert wikipedia_candidate(api, hockey, born=None) is None
    foot = {"entities": {"Q1": {"claims": {
        "P106": [{"mainsnak": {"datavalue": {"value": {"id": "Q937857"}}}}],
        "P569": [{"mainsnak": {"datavalue": {"value": {"time": "+1990-01-01T00:00:00Z"}}}}]}}}}
    assert wikipedia_candidate(api, foot, born=2000) is None
    assert wikipedia_candidate(api, foot, born=1990) is not None
    dis = _pages(title="X", original={"source": "https://u/x.jpg"}, pageprops={"wikibase_item": "Q1", "disambiguation": ""})
    assert wikipedia_candidate(dis, foot, born=1990) is None
    assert wikipedia_candidate(_pages(title="X", missing=""), foot, born=1990) is None
    assert wikipedia_candidate(_pages(title="X", pageprops={"wikibase_item": "Q1"}), foot, born=1990) is None
