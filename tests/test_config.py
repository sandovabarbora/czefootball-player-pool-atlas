from src import config


def test_headline_leagues_are_nine_and_exclude_peers():
    assert len(config.HEADLINE_LEAGUES) == 9
    peer_codes = set(config.countries()["peers"])
    assert not any(l.split("-")[0] in peer_codes for l in config.HEADLINE_LEAGUES)  # noqa: E741


def test_peer_countries_have_population():
    peers = config.countries()["peers"]
    assert set(peers) == {"CZE", "SVK", "AUT", "HUN", "POL", "CRO", "DEN", "SUI", "NOR"}
    assert all(v["population_m"] > 1 for v in peers.values())


def test_seasons_are_unambiguous():
    for s in config.seasons().values():
        assert len(s) == 9 and s[4] == "-"


def test_snapshot_dir_is_inside_data():
    assert config.SNAPSHOT_DIR.parent == config.DATA_DIR
