# Task 16: Model comparison and monitoring over time (spec §4b first bullet, M1 core)

**Question (football → analytical):** "What does a player's season tell us about the
next one, given where he plays, how old he is and — for exports — at what age he
moved?" → predict next-season league-adjusted production (`npg_p90_quality +
ast_p90_quality` of season t+1) from season t, for every player-season pair in the
corpus with ≥ 450 minutes in both seasons, all nationalities.

**Rolling-origin evaluation** (Hyndman and Athanasopoulos, 2021 — add to `refs.yaml`
with URL; verify): origins 2021/22 → 2025/26: for each target season T, train on pairs
whose target season < T, test on pairs with target season T. Report per origin season
and pooled: RMSE, MAE, and (for the Bayesian model) 90 % interval coverage. This table
*is* the "monitor performance over time" exhibit: drift is visible per season.

## Three models, same features, same splits
Features from season t: `npg_p90_shrunk, ast_p90_shrunk, min_share, age, cards_p90,
league (categorical), pos_group, league_multiplier`, plus for the Bayesian model the
M2 league effect `m_L` (from `league_strength.json`) as an offset option — report both
with and without it if cheap; otherwise with.
1. **Hierarchical Bayesian regression** (PyMC): target ~ Normal(μ, σ); μ = α + β·x
   (standardised numeric features) + γ_league (partial pooling) + δ_pos + u_player
   (partial pooling, σ_u ~ HalfNormal(0.5)); NUTS, 2 chains × 800 draws per origin
   (5 origins → keep runtime < 15 min total; reduce draws or subsample players if
   needed and say so). Coverage from the posterior predictive.
2. **Gradient boosting** (scikit-learn `HistGradientBoostingRegressor`, default-ish
   params with early stopping; `league`/`pos_group` as categorical). (Pedregosa et al.,
   2011 is already in refs.)
3. **Small neural player-season embedding** (PyTorch is NOT installed — use
   scikit-learn `MLPRegressor` on the same features plus a learned 8-dim league
   embedding is not possible in sklearn; instead: `MLPRegressor` on one-hot league +
   numeric features, 2 hidden layers (64, 32), early stopping). Call it what it is
   ("a small multilayer perceptron"), not an embedding model. If it does not beat GBM
   on pooled RMSE, the report says so and keeps the table.
Baseline 0: **persistence** (next = this season's value) and baseline 1: **shrinkage
to league mean** — both in the table.

## Outputs
`data/processed/<nation>/model_comparison.json`: `{"target": …, "origins": [T…],
"rows": [{"model", "origin", "n_test", "rmse", "mae", "coverage90"}], "pooled": [...],
"winner_pooled": "…", "notes": [...]}` and figure `outputs/<nation>/model_comparison.svg`:
RMSE per origin season, one line per model (palette), persistence dashed. Makefile
target `compare`; add to `all` before `render`; `render.load_data` tolerates a
missing JSON. The corpus is nation-independent: run once under cze, and for eng copy
the JSON (state it in the report).

## Report
Chapter IV, new section `#model-comparison` "Three models, one task, five seasons"
after the league-strength section: the question in both forms, the table (models ×
origins, pooled row), the figure, the coverage line for the Bayesian model, the winner
sentence with its margin, and a line on drift (largest season-to-season change in the
winner's RMSE, computed). Cites: (Hyndman and Athanasopoulos, 2021), (Gelman et al.,
2013), (Pedregosa et al., 2011). Extend the "Validation & robustness" list with this
model's headline. All i18n EN + CS, numbers via placeholders.

## Tests
`tests/test_model_comparison.py`: rolling-origin split correctness on a toy table (no
leakage: every test pair's target season equals T and every train pair's < T);
baselines' RMSE on a table with known values; JSON shape; a smoke test of the
Bayesian model with 2 chains × 100 draws on 200 synthetic rows (coverage between 0.6
and 1.0).

## Verify
`uv run pytest -q -p no:warnings`; `NATION=cze uv run python -m src.model_comparison`
(report runtime and the full table); copy for eng; render + build both; screenshot of
the section (one tab, close it). Commit plain message, no AI trailer; add
src/config/templates/tests + rebuilt docs + snapshots; never data/processed, outputs.
