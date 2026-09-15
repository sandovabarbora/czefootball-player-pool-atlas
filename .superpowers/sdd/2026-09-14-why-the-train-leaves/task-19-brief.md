# Task 19: When did the train leave — change point, backtest, one aggregate forecast (M4)

**Spec** §2 M4 + §4c (time series & forecasting). Data: `big5_series.json` (26 seasons,
per country `n` with ≥ 450 min and `per_million`). Slide 7 already shows the series; this
task adds the model behind the sentence "the break is dated to season Z (interval)" and the
report's *only* forecast — aggregate, backtested, labelled.

## Model (`src/series_model.py`) — PyMC, count series
- Observation: `n_t ~ Poisson(λ_t)` for the home nation, t = 2000/01 … 2025/26.
- **Local level with one change point in the level**:
  `log λ_t = μ_t`, `μ_t = μ_{t−1} + ε_t`, `ε_t ~ Normal(0, σ)`, `σ ~ HalfNormal(0.2)`, plus a
  step `δ` at an unknown time τ: `μ_t += δ · 1[t ≥ τ]`, `δ ~ Normal(0, 1)`,
  `τ ~ DiscreteUniform(3, T−3)`. Marginalise τ (PyMC `pm.Mixture`-free approach: loop over
  τ with `pm.Potential`/logsumexp, or use the standard "Bayesian change point" formulation
  — Adams and MacKay (2007) is the online reference; cite Gelman et al. (2013) for the
  discrete-parameter marginalisation). NUTS for the continuous part; report the posterior
  over τ (top-3 seasons with probabilities), δ (median, 90 % HDI, as a multiplicative
  factor exp δ), and σ. Fit the same model for the two `series_contrast` countries.
- **Rolling-origin backtest** (Hyndman and Athanasopoulos, 2021): origins 2010/11 →
  2024/25, one-step-ahead forecast of `n_{t+1}` from data ≤ t using the plain local level
  (no change point — the honest forecaster), scored by MAE and 90 % interval coverage;
  compare with the naive "same as last season". One table.
- **The one forecast**: next season's count for the home nation and the two contrast
  countries, median + 90 % interval, from the plain local level fitted on all seasons —
  labelled as a methods demonstration: "a count of players, not a statement about any
  player". Runtime target < 5 min total (T = 26, tiny).
- Outputs: `data/processed/<nation>/series_model.json` (`break: {top: [{season, prob}],
  delta_factor: {median, lo, hi}, sigma}`, `contrast: {code: {…}}`, `backtest: {rows,
  pooled: {mae_model, mae_naive, coverage90}}`, `forecast: {code: {season, median, lo, hi}}`,
  `diagnostics`) and figure `outputs/<nation>/series_model.svg`: the series with the
  posterior break probability as a bar strip under the x-axis, the fitted level with its
  band, and the forecast point with its interval at the right edge.

## Report
- Slide 7's answer sentence gains the break: "…; the break is dated to {break_season}
  ({break_prob} % posterior), a level change of ×{delta} ({lo}–{hi})." How-line adds the
  model in one clause and the citation.
- Chapter IV: new section `#series-model` "Dating the break and one forecast" after the
  model-comparison section: design (four sentences), the figure, the backtest table, the
  forecast table (home + contrasts) with the sentence that says what it is not, the
  diagnostics line. Validation & robustness list gains this model's headline. All EN + CS
  via placeholders. Cites: Adams and MacKay (2007) — verify arXiv URL; Durbin and Koopman
  (2012) — add to `refs.yaml` if verifiable (ISBN/publisher page), otherwise skip;
  Hyndman and Athanasopoulos (2021) already present.

## Tests
`tests/test_series_model.py`: synthetic series with a known step (level 20 → 10 at
t = 14) recovers τ within ±1 season as the posterior mode (short sampling); backtest split
never uses future seasons; forecast interval contains the true next value on a synthetic
random-walk series most of the time (coverage on 20 draws ≥ 0.7); JSON shape.

## Verify
`uv run pytest -q -p no:warnings`; `NATION=cze uv run python -m src.series_model`,
`NATION=eng` the same; render + build both; screenshot slide 7 + the new section (one
tab, close it). Commit plain message, no AI trailer; add src/config/templates/tests +
rebuilt docs + snapshots; never data/processed, outputs.
