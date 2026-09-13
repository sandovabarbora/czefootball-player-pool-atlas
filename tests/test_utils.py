from types import SimpleNamespace

import pandas as pd

from src import utils


def test_cached_text_fetches_once_then_reads_from_cache(tmp_path, monkeypatch):
    calls = []

    def fake_http_get(url, *, headers=None, timeout=15.0, sleep_after=0.0):
        calls.append(url)
        return SimpleNamespace(text="hello world")

    monkeypatch.setattr(utils, "http_get", fake_http_get)
    cache_path = tmp_path / "nested" / "page.html"

    first = utils.cached_text("http://example.com/page", cache_path)
    assert first == "hello world"
    assert cache_path.read_text(encoding="utf-8") == "hello world"
    assert calls == ["http://example.com/page"]

    second = utils.cached_text("http://example.com/page", cache_path)
    assert second == "hello world"
    assert calls == ["http://example.com/page"]  # no second HTTP call


def test_cached_text_passes_through_headers_and_timeout(tmp_path, monkeypatch):
    seen = {}

    def fake_http_get(url, *, headers=None, timeout=15.0, sleep_after=0.0):
        seen["headers"] = headers
        seen["timeout"] = timeout
        return SimpleNamespace(text="ok")

    monkeypatch.setattr(utils, "http_get", fake_http_get)
    cache_path = tmp_path / "page.html"

    utils.cached_text("http://example.com", cache_path, headers={"User-Agent": "test"}, timeout=5.0)
    assert seen == {"headers": {"User-Agent": "test"}, "timeout": 5.0}


def test_collapse_player_seasons_sums_minutes_and_weights_rates():
    # A mid-season transfer: same player_key/season/pos_group, two league rows.
    df = pd.DataFrame({
        "player_key": ["x|2000", "x|2000", "y|1999"],
        "season": ["2024-2025", "2024-2025", "2024-2025"],
        "pos_group": ["FW", "FW", "FW"],
        "league": ["L1", "L2", "L3"],       # L2 has more minutes -> kept as "the" league
        "min": [600, 1800, 2000],
        "npg_ast_q": [1.0, 0.5, 0.3],       # weighted mean: (600*1 + 1800*0.5) / 2400 = 0.625
        "nt_flag": [True, True, False],
    })
    out = utils.collapse_player_seasons(df, rate_cols=["npg_ast_q"])

    assert len(out) == 2  # x's two rows collapsed into one; y untouched
    x = out[out.player_key == "x|2000"].iloc[0]
    assert x["min"] == 2400
    assert abs(x.npg_ast_q - 0.625) < 1e-9
    assert x.league == "L2"  # from the row with the most minutes
    y = out[out.player_key == "y|1999"].iloc[0]
    assert y["min"] == 2000 and abs(y.npg_ast_q - 0.3) < 1e-9


def test_collapse_player_seasons_is_a_no_op_when_no_duplicates():
    df = pd.DataFrame({
        "player_key": ["a", "b"], "season": ["2024-2025"] * 2, "pos_group": ["FW"] * 2,
        "league": ["L1", "L2"], "min": [1000, 2000], "npg_ast_q": [0.4, 0.6],
    })
    out = utils.collapse_player_seasons(df, rate_cols=["npg_ast_q"])
    pd.testing.assert_frame_equal(
        out.sort_values("player_key").reset_index(drop=True),
        df.sort_values("player_key").reset_index(drop=True),
        check_dtype=False,
    )
