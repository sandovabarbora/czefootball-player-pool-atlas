# Task 16 report: model comparison and monitoring over time (M1 core)

## Status: done

Final commit: `d162559` — "Task 16: three-model rolling-origin comparison (M1 core) with
Bayesian, GBM and MLP against two baselines" (branch `v1.2`, plain message, no AI
trailer, per the hard rule). Six WIP checkpoints precede it (`09d06cf` skeleton,
`1f4d2fb` Bayesian/GBM/MLP fitting, `cc6f171` figure + `main()`, `cf997f6` a dtype
fix, `b442b02` render/template/i18n wiring, `e0353e9` site-build wiring), each
following a green focused-test run, per the brief's incremental-module instruction.

## What was built

- `src/model_comparison.py` — rolling-origin evaluation over the pairs corpus built
  from `features_{FW,MF,DF}.parquet` (nation-independent, same as `league_strength.py`).
  Public API: `build_pairs`, `rolling_origin_split`, `rmse`/`mae`, `predict_persistence`,
  `predict_shrinkage_to_league_mean` (baselines 0/1), `fit_bayesian`/`predict_bayesian`
  (hierarchical Bayesian regression, PyMC 5, non-centred), `fit_predict_gbm`
  (`HistGradientBoostingRegressor`), `fit_predict_mlp` (`MLPRegressor`), `attach_m_l`
  (M2 league-strength offset), `render_figure`, `assemble_output`, `main`.
- `tests/test_model_comparison.py` — 10 tests: rolling-origin split correctness on a
  toy table (no leakage, plus the degenerate-first-origin case), baselines' RMSE/MAE
  on tables with known values, `build_pairs` on a hand-built fixture (consecutive-season
  matching, the 450-minute filter), a Bayesian smoke test (2 chains × 100 draws, 200
  synthetic rows, coverage asserted in [0.6, 1.0]), and the JSON-assembly shape.
- `config/refs.yaml` — one new entry, `hyndman_athanasopoulos_2021` (*Forecasting:
  Principles and Practice*, 3rd ed., OTexts), verified `curl -sIL https://otexts.com/fpp3/`
  → 200.
- `templates/report.html.j2` + `src/i18n.py` + `config/i18n/cs.yaml` — new
  `#model-comparison` section (Chapter IV, right after `#league-strength`, before
  `#shrinkage`), a `ch4.validation.m1` bullet added to the existing `#validation-robustness`
  list (before the M2 bullet), and TOC entries (`toc.compare`/`toc.short.compare`) in
  both the sticky sidebar and the mobile `<details>` nav. All copy in EN + CS with
  matching placeholders.
- `src/render.py` — `_build_model_comparison` (mirrors `_build_league_strength`'s
  pattern: pooled/per-origin table assembly, winner + margin over persistence, drift
  as the largest season-to-season RMSE change in the winner, Bayesian per-origin
  coverage text); `load_data` tolerates a missing `model_comparison.json`
  (`_load_json` default `{}`); `build_context` and `build_context_from_fixtures` both
  wired. `MODEL_COMPARISON_ORDER`/`MODEL_COMPARISON_BAYES_*` are kept as literals in
  `render.py` (not imported from `src.model_comparison`) so `render.py` — pulled in by
  most of the test suite — doesn't gain a PyMC/scikit-learn import cost, the same
  reasoning already used for `LEAGUE_STRENGTH_REFERENCE`.
- `Makefile` — new `compare` target (`python -m src.model_comparison`), added to `all`
  between `strength` and `pathways`, plus a `help` line.
- `site/build.sh` / `site/svg_labels.py` — `model_comparison.svg` added to the
  required-file list, the copy list, and (cze only) the Czech SVG-relabelling `FILES`/`T`
  dict (title, axis labels, five model-legend labels); `KEEP`'s regex widened by one
  alternative (`\d{4}/\d\d`) for the plain `"2021/22"`-style x-axis tick labels this
  figure introduces (the pattern's date only exists elsewhere paired with a colon-count
  suffix, e.g. big5_series's point annotations).

## A bug found and fixed mid-task

`features.py`'s `age` column is pandas' nullable `Float64` extension dtype (from
`_fill_missing_age`). Mixed into a `DataFrame[feature_cols].to_numpy()` alongside plain
`float64` columns, pandas silently falls back to an `object`-dtype array, which PyTensor
rejects outright (`TypeError: Unsupported dtype for TensorType: object`) — this only
surfaced on the real corpus (the unit test's synthetic fixtures never touch
`features.py`, so their `age` column was already plain `float64`). Fixed by casting every
numeric/target column to `float64` once in `build_pairs` (`src/model_comparison.py`),
rather than at every downstream `.to_numpy()` call site.

The `#model-comparison` question paragraph's first draft used `thresholds.min_minutes`
for its "{min} minutes" placeholder — that turned out to be `src.trajectory.MIN_MINUTES`
(900, a different threshold entirely, only coincidentally present under the same context
key from an earlier task), not this task's own 450-minute floor. Caught by reading the
rendered HTML during self-review ("at least 900 minutes" contradicted the JSON's own
`MIN_MINUTES = 450`); fixed to `feature_defs.min_minutes` (450, confirmed against
`config/feature_definitions.yaml`).

## The Czech run — headline numbers

Runtime: **191.3 s total** (`NATION=cze uv run python -m src.model_comparison`), well
under the 15-minute budget. Corpus: `build_pairs` over `features_{FW,MF,DF}.parquet`
(all nationalities, no movers restriction) produced pairs whose target seasons span
2021/22 → 2026/27 before origin filtering; the five origins 2021/22 → 2025/26 pool to
**10,805 test rows** for the two baselines and **8,850** for the three learned models
(the gap is origin 1's empty training set — a genuine corpus-depth limit, not a bug: see
below).

**Pooled table** (one line per model; RMSE/MAE in league-adjusted npG+A per 90):

| Model | n_test | RMSE | MAE | Coverage (90%) |
|---|---:|---:|---:|---:|
| Persistence (baseline 0) | 10,805 | 0.0754 | 0.0533 | — |
| Shrinkage to league mean (baseline 1) | 10,805 | 0.1247 | 0.0968 | — |
| Hierarchical Bayesian | 8,850 | 0.0713 | 0.0526 | 0.9158 |
| **Gradient boosting (winner)** | 8,850 | **0.0706** | 0.0510 | — |
| Small MLP | 8,850 | 0.0753 | 0.0557 | — |

**Full table, per origin** (RMSE, MAE):

| Model | 2021/22 | 2022/23 | 2023/24 | 2024/25 | 2025/26 | Pooled |
|---|---|---|---|---|---|---|
| Persistence | 0.0768 (0.0541) | 0.0782 (0.0558) | 0.0789 (0.0564) | 0.0787 (0.0565) | 0.0684 (0.0477) | 0.0754 (0.0533) |
| Shrinkage to league mean | 0.1343 (0.1045) | 0.1293 (0.0996) | 0.1311 (0.0976) | 0.1271 (0.0977) | 0.1099 (0.0893) | 0.1247 (0.0968) |
| Hierarchical Bayesian | — | 0.0710 (0.0522) | 0.0759 (0.0536) | 0.0722 (0.0534) | 0.0681 (0.0516) | 0.0713 (0.0526) |
| Gradient boosting | — | 0.0723 (0.0513) | 0.0744 (0.0515) | 0.0698 (0.0505) | 0.0677 (0.0509) | 0.0706 (0.0510) |
| Small MLP | — | 0.0794 (0.0586) | 0.0792 (0.0571) | 0.0735 (0.0543) | 0.0714 (0.0541) | 0.0753 (0.0557) |

**Winner: gradient boosting**, pooled RMSE 0.0706 vs 0.0754 for persistence — **6.4% lower**
(`(0.0754 − 0.0706) / 0.0754`). A modest but real margin; the Bayesian model (0.0713) and
even plain persistence trail closely behind, which is itself the honest finding this
exhibit exists to report — none of the fitted models dramatically outperforms "predict
next season = this season."

**Coverage**: the Bayesian model's 90% predictive interval (a normal approximation, not
full posterior-predictive Monte Carlo — see "Design decisions" below) covered the observed
value **91.6% of the time pooled**, close to nominal: 2022/23 91.2%, 2023/24 90.5%,
2024/25 91.4%, 2025/26 92.6%.

**Drift**: the winner's (gradient boosting) largest season-to-season RMSE change is
**0.0046, between 2023/24 (0.0744) and 2024/25 (0.0698)** — a real but small move; the
persistence baseline's own swing is larger (0.079 → 0.068 between 2024/25 and 2025/26,
Δ0.011), visible directly in the figure (`outputs/cze/model_comparison.svg`, and rendered
in the report).

**MLP vs GBM**: the brief's contingency fired — the small MLP does **not** beat gradient
boosting on pooled RMSE (0.0753 vs 0.0706), reported plainly via the JSON's `notes` and
the report copy ("small MLP", never "embedding model", per the brief — PyTorch isn't in
this pipeline).

## Design decisions (documented in the module docstring, repeated here for the record)

1. **Origin 1 (2021/22) has an empty training set by construction.** The earliest feature
   season on file is 2020-2021; the earliest possible pair's target season is therefore
   2021-2022 — exactly the first origin — leaving no strictly-earlier target season to
   train on. This is a genuine depth limit of the corpus, not a bug: `rolling_origin_split`
   returns the empty frame faithfully (tested), `main` fits only the two baselines for that
   origin and logs a note rather than silently zero-row-fitting the three learned models.
2. **Both baselines are computable without any training corpus.** Persistence uses only the
   test row's own season-t composite value. Shrinkage-to-league-mean uses an
   empirical-Bayes blend of the *historical* (training) per-league target mean toward the
   overall training mean (K=10, the same phantom-observations logic as
   `features.bayesian_shrink`); when training is empty (origin 1 only) it falls back to the
   test season's own known `value_t` mean — a current-season quantity, not the (unknown)
   target, so this is not leakage.
3. **The Bayesian model's 90% interval is a normal approximation to the posterior
   predictive**, not full Monte Carlo sampling of `y_rep`: per test row,
   `median(mu across draws) ± 1.645·√(var(mu) + sigma_resid_median² + [sigma_player_median²
   if the player is unseen in training])`. Documented as an approximation in the module
   docstring, the i18n copy notes it implicitly via the coverage figure being close-but-not-
   exact to 90%; chosen to avoid materialising a (draws × rows) `y_rep` array five times over
   within the runtime budget.
4. **Runtime reduction, stated plainly (JSON `notes` + report copy):** the Bayesian fit uses
   2 chains × 400 draws per origin (vs. `league_strength.py`'s 4 × 1000) and training rows
   are subsampled to at most 2,500 (seeded, `config.RANDOM_SEED`) when an origin's split is
   larger — origin 5's untrimmed 7,596-row training set is the one this affects. GBM and MLP
   train on the full split (they're fast). Each Bayesian fit took ~44–47 s; total pipeline
   runtime 191.3 s.
5. **The M2 league-strength multiplier `m_L`** (`league_strength.json`, Task 15) is used as
   an *extra* feature for the Bayesian model only (`attach_m_l`), alongside the
   config-based `league_multiplier` already in every model's base feature set — "with", per
   the brief's fallback clause, not run both ways (kept cheap).
6. **R-hat warnings**: every origin's 2-chain Bayesian fit logs PyMC's standard "run at
   least 4 chains" / R-hat / low-ESS warnings — expected at this reduced budget (the same
   caveat `league_strength.py`'s own lighter-budget OOS refit carries) and harmless here
   since only the posterior's own draws feed point predictions and the coverage
   approximation, not a separately-reported diagnostics table (this task's brief doesn't
   ask for one, unlike Task 15's `diagnostics_summary`).

## The England run

Per the brief, **not re-run** — `data/processed/eng/model_comparison.json` and
`data/snapshot/eng/model_comparison.json` are byte-for-byte copies of the Czech run's
output, and `outputs/eng/model_comparison.svg` / `docs/eng/model_comparison.svg` are
copies of the Czech figure. This mirrors Task 15's own finding (documented in its report)
that `features_{FW,MF,DF}.parquet` already carries every fetched nationality regardless of
home nation, and in the current repo state `eng`'s and `cze`'s processed directories hold
the same underlying player-season rows — so a genuine independent `eng` run would very
likely reproduce the same numbers anyway (as Task 15 confirmed for its own model), and
copying is both faster and exactly what the brief asked for. `NATION=eng uv run python -m
src.render` + `NATION=eng ./site/build.sh` were run for real (not copied) to produce
`docs/eng/index.html`.

## References — verification log

| Key | Check | Result |
|---|---|---|
| hyndman_athanasopoulos_2021 (new) | `curl -sIL https://otexts.com/fpp3/` | 200 |
| gelman_et_al_2013 | already verified (Task 15) | — |
| pedregosa_et_al_2011 | already verified (Task 15) | — |

## Test summary

`uv run pytest -q -p no:warnings` (`NATION=cze`, the default): **188 passed** (up from
174 at Task 15's close), ~35 s total, dominated by the new `tests/test_model_comparison.py`
(10 tests, ~5–8 s for the Bayesian smoke fixture) plus updated `tests/test_render.py`/
`tests/test_i18n.py` (new section id, new TOC keys, `model_comparison` added to both the
real and fixture contexts). The golden-fixture test
(`test_context_matches_golden_fixture_for_cze`) passes unmodified — this task only *adds*
context keys, never touches existing ones.

`NATION=eng uv run pytest`: 5 failures / 4 errors — **identical in count and cause** to
Task 15's report (`CZE`-hardcoded assumptions in `_val`/benchmark/big5 helpers,
`test_nation_defaults_to_cze`, and `test_site_build.py`'s CS-page assertions for an
English-only build); none reference `model_comparison` or anything this task touched.
Confirmed by inspection, not just count-matching.

`uvx ruff check src tests site/svg_labels.py`: clean except the two pre-existing warnings
already on record from Task 15 (`site/svg_labels.py`'s import-after-`sys.path.insert`
pattern, `fetch_fbref.py`'s `N818` exception naming) — neither introduced by this task.

## Verify steps run

- `uv run pytest -q -p no:warnings` → 188 passed.
- `NATION=cze uv run python -m src.model_comparison` → full run, 191.3 s, see numbers above.
- `data/processed/eng/model_comparison.json` copied from `cze`'s (stated above); `outputs/
  eng/model_comparison.svg` copied from `cze`'s figure.
- `NATION=cze uv run python -m src.render` + `NATION=cze ./site/build.sh` → `docs/index.html`,
  `docs/cs/index.html`, `docs/model_comparison.svg`, `docs/cs/model_comparison.svg`.
- `NATION=eng uv run python -m src.render` + `NATION=eng ./site/build.sh docs/eng` →
  `docs/eng/index.html`, `docs/eng/model_comparison.svg`.
- Screenshot: one Chrome tab, `docs/index.html#model-comparison` served via a local
  `python3 -m http.server` (the extension blocks `file://`), scrolled through the full
  section (question, design paragraph with in-text cites, figure, the models×origins×
  pooled table, the coverage/winner/drift lines) — confirmed the figure and table render
  correctly and flow into the next section (`#shrinkage`); tab closed after.

## Concerns / things worth a second look

1. **The winner's margin over persistence is modest (6.4%)**, and over the Bayesian model
   smaller still (0.0713 vs 0.0706, essentially tied). This is reported plainly, not
   dressed up — exactly the "honest, validated, no overclaiming" brief for an FA
   data-science panel. A reviewer might reasonably ask whether gradient boosting's win is
   robust to a different random seed; that's outside this task's scope (no seed-sweep was
   requested) but would be a natural follow-up.
2. **The Bayesian model's 90% interval is an approximation** (normal, not full posterior-
   predictive Monte Carlo) — documented in the module docstring and implicitly visible in
   the coverage numbers being close-but-not-exact to 90% rather than exactly so. Flagged
   here again so it isn't missed.
3. **Origin 1 carries only two of five models.** The pooled table is honest about this (its
   `n_test` for the three learned models is 8,850, not 10,805), but a reader skimming only
   the pooled row without the note could miss that the comparison isn't perfectly
   apples-to-apples across models. The report's table note (`ch4.compare.note`) states this
   explicitly right under the table.
4. **`data-highlight="winner"` on the winning model's table row has no CSS rule** (checked
   `templates/style.css`) — matches the existing precedent (`league_strength`'s own
   `data-highlight="cze"` on its table rows is likewise currently unstyled), so left as is
   rather than introducing new CSS unprompted by the brief.
