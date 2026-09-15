"""Tests for src/gap_decomposition.py -- the Blinder-Oaxaca-style linear
gap decomposition (M5)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.gap_decomposition import (
    assemble_output,
    bootstrap_decomposition,
    build_channels,
    decompose,
    decompose_contrast,
    fit_ridge,
    predict_one,
)


def _toy_panel() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    countries = ["HOM", "NOR", "DEN", "AUT", "POL", "CRO", "SUI", "HUN"]
    x1 = rng.uniform(0.06, 0.16, size=len(countries))
    x2 = rng.uniform(0.4, 1.0, size=len(countries))
    x3 = rng.uniform(19, 25, size=len(countries))
    y = 2.0 + 30 * x1 + 5 * x2 - 0.3 * x3 + rng.normal(0, 0.4, size=len(countries))
    return pd.DataFrame({
        "country": countries, "y": y, "x1": x1, "x2": x2, "x3": x3,
        "x2_source": ["m_L"] * len(countries), "league": [f"{c}-Top" for c in countries],
    })


def test_build_channels_drops_missing_and_records_x2_source():
    per_capita_rows = [
        {"country": "AAA", "per_million": 3.0}, {"country": "BBB", "per_million": 9.0},
        {"country": "CCC", "per_million": 5.0},
    ]
    youth_rows = [
        {"country": "AAA", "share_u21": 0.10}, {"country": "BBB", "share_u21": 0.15},
        {"country": "CCC", "share_u21": None},  # untracked own top flight -> dropped
    ]
    export_rows = [
        {"country": "AAA", "median_export_age_recent": 22.0, "median_export_age": 23.0},
        {"country": "BBB", "median_export_age_recent": None, "median_export_age": 21.0},  # falls back
        {"country": "CCC", "median_export_age_recent": 24.0, "median_export_age": 24.0},
    ]
    league_strength_leagues = [{"league": "AAA-Top", "median": 0.8}]  # BBB-Top absent -> UEFA fallback
    uefa_multipliers = {"BBB-Top": 0.5}
    league_by_country = {"AAA": "AAA-Top", "BBB": "BBB-Top", "CCC": "CCC-Top"}

    panel = build_channels(per_capita_rows, youth_rows, export_rows, league_strength_leagues,
                           uefa_multipliers, league_by_country, ["AAA", "BBB", "CCC"])
    assert set(panel["country"]) == {"AAA", "BBB"}  # CCC dropped (no share_u21)
    aaa = panel[panel.country == "AAA"].iloc[0]
    assert aaa["x2_source"] == "m_L" and aaa["x2"] == 0.8
    bbb = panel[panel.country == "BBB"].iloc[0]
    assert bbb["x2_source"] == "uefa_multiplier" and bbb["x2"] == 0.5
    assert bbb["x3"] == 21.0  # fell back to the all-time median


def test_decompose_sums_exactly_to_fitted_gap():
    panel = _toy_panel()
    coeffs = fit_ridge(panel)
    by_country = {r["country"]: r for r in panel.to_dict("records")}
    home, contrast = by_country["HOM"], by_country["NOR"]
    result = decompose(home, contrast, coeffs)

    fitted_gap = predict_one(coeffs, contrast) - predict_one(coeffs, home)
    channel_sum = sum(c["contribution"] for c in result["channels"])
    assert abs(channel_sum - fitted_gap) < 1e-9
    # gap_total = fitted_gap + residual, exactly
    assert abs(result["gap_total"] - (fitted_gap + result["residual"])) < 1e-9
    assert abs(result["gap_total"] - (contrast["y"] - home["y"])) < 1e-9


def test_bootstrap_interval_contains_point_estimate():
    panel = _toy_panel()
    coeffs = fit_ridge(panel)
    by_country = {r["country"]: r for r in panel.to_dict("records")}
    home, contrast = by_country["HOM"], by_country["DEN"]
    point = decompose(home, contrast, coeffs)
    boot = bootstrap_decomposition(panel, home, contrast, n_boot=300, seed=7)
    for ch in point["channels"]:
        b = boot[ch["col"]]
        assert b["lo"] <= ch["contribution"] <= b["hi"] + 1e-9 or b["lo"] - 1e-9 <= ch["contribution"]


def test_decompose_contrast_json_shape():
    panel = _toy_panel()
    coeffs = fit_ridge(panel)
    result = decompose_contrast(panel, coeffs, "HOM", "NOR", n_boot=200, seed=1)
    assert set(result.keys()) == {"contrast", "gap_total", "channels", "residual", "n"}
    assert result["contrast"] == "NOR"
    assert result["n"] == len(panel)
    assert len(result["channels"]) == 3
    for ch in result["channels"]:
        assert set(ch.keys()) == {"name", "contribution", "share", "lo", "hi"}
        assert ch["lo"] <= ch["hi"]


def test_assemble_output_shape():
    panel = _toy_panel()
    coeffs = fit_ridge(panel)
    results = [decompose_contrast(panel, coeffs, "HOM", c, n_boot=100, seed=1) for c in ("NOR", "DEN")]
    out = assemble_output(panel, coeffs, results)
    assert out["n"] == len(panel)
    assert "home" in out  # config.HOME -- not this toy panel's "HOM" (assemble_output reads config directly)
    assert len(out["contrasts"]) == 2
    assert set(out["coefficients"]["b"].keys()) == {"x1", "x2", "x3"}
