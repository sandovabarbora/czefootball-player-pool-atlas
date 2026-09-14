import importlib

import pytest

from src import config


@pytest.mark.skipif(config.NATION != "cze", reason="Czechia-specific: its peers are mid-tier "
                    "nations chosen NOT to already play in the headline leagues; other home "
                    "nations (e.g. England) may deliberately pick peers that do.")
def test_headline_leagues_are_nine_and_exclude_peers():
    assert len(config.HEADLINE_LEAGUES) == 9
    peer_codes = set(config.nation()["peers"])
    assert not any(l.split("-")[0] in peer_codes for l in config.HEADLINE_LEAGUES)  # noqa: E741


def test_peer_countries_have_population():
    peers = config.countries()["peers"]
    assert set(config.PEER_COUNTRIES) <= set(peers)
    assert all(v["population_m"] > 1 for v in peers.values())


def test_peers_meta_is_restricted_to_and_ordered_by_peer_countries():
    meta = config.peers_meta()
    assert list(meta) == config.PEER_COUNTRIES
    assert set(meta) == set(config.PEER_COUNTRIES)


def test_seasons_are_unambiguous():
    def _check(s: str) -> None:
        assert len(s) == 9 and s[4] == "-"

    for v in config.seasons().values():
        if isinstance(v, list):
            for s in v:
                _check(s)
        else:
            _check(v)


def test_snapshot_dir_is_inside_data_under_the_nation_segment():
    assert config.SNAPSHOT_DIR.parent.parent == config.DATA_DIR
    assert config.SNAPSHOT_DIR.parent.name == "snapshot"
    assert config.SNAPSHOT_DIR.name == config.NATION


def test_processed_and_outputs_dirs_contain_the_nation_segment():
    assert config.PROCESSED_DIR.name == config.NATION
    assert config.OUTPUTS_DIR.name == config.NATION


def test_nt_years_span_from_nation_squads():
    years = [e["year"] for e in config.squads()["events"]]
    assert config.nt_years() == f"{min(years)}–{str(max(years))[-2:]}"


def test_nation_defaults_to_cze():
    assert config.NATION == "cze"
    assert config.HOME == "CZE"
    assert config.nation()["code"] == "CZE"
    assert config.nation()["name"] == "Czechia"


def test_nation_env_var_selects_the_config_file(monkeypatch):
    """NATION=eng picks config/nations/eng.yaml when the module is (re)loaded."""
    monkeypatch.setenv("NATION", "eng")
    try:
        eng_config = importlib.reload(config)
        assert eng_config.NATION == "eng"
        assert eng_config.HOME == "ENG"
        assert eng_config.nation()["name"] == "England"
        assert eng_config.nation()["domestic_league"] == "ENG-Premier League"
        assert eng_config.PROCESSED_DIR.name == "eng"
        assert eng_config.OUTPUTS_DIR.name == "eng"
        assert eng_config.SNAPSHOT_DIR.name == "eng"
    finally:
        monkeypatch.delenv("NATION", raising=False)
        importlib.reload(config)


def test_nation_carries_home_league_and_cs_forms():
    """Task 14b: every home nation config has an EN display name for its
    domestic league and a `cs` block of Czech-language nation-word forms."""
    for code in ("cze", "eng"):
        cfg = config.load_yaml(f"nations/{code}.yaml")
        assert cfg["home_league"]
        cs = cfg["cs"]
        for key in ("name", "gen", "adj_m", "adj_f", "adj_n", "adj_pl"):
            assert cs[key], (code, key)


def test_cluster_labels_defaults_to_the_shared_file():
    """config.cluster_labels() loads the shared config/cluster_labels.yaml
    unless nation() sets an override; cze/eng share one fit (Task 14b)."""
    assert "cluster_labels" not in config.nation()
    assert config.cluster_labels() == config.load_yaml("cluster_labels.yaml")


def test_unconfigured_nation_fails_loudly(monkeypatch):
    """config.HOME is resolved from nation() at import time, so a typo'd or
    unconfigured NATION fails loudly as soon as the module loads."""
    monkeypatch.setenv("NATION", "xyz")
    try:
        try:
            importlib.reload(config)
            raise AssertionError("expected FileNotFoundError for an unconfigured NATION")
        except FileNotFoundError:
            pass
    finally:
        monkeypatch.delenv("NATION", raising=False)
        importlib.reload(config)
