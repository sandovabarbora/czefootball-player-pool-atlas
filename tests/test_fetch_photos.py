import json
from pathlib import Path

import pandas as pd

from src.fetch_photos import match_images, sparql_for

FIX = json.loads((Path(__file__).parent / "fixtures" / "wikidata_sample.json").read_text())
BINDINGS = FIX["results"]["bindings"]


def test_sparql_embeds_names_and_czech_citizenship():
    q = sparql_for(["Patrik Schick"])
    assert '"Patrik Schick"@en' in q and "wd:Q213" in q


def test_match_by_name_and_birth_year():
    pool = pd.DataFrame({"fbref_id": ["x1"], "player": ["Patrik Schick"], "born": [1996]})
    out = match_images(BINDINGS, pool)
    assert len(out) == 1 and out.iloc[0].image_url.startswith("http")


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
