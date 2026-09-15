# Task 15 report: league strength from the transfer graph (M2) + references

## Status: done

Commit: `041ec4d` — "Task 15: league strength from the transfer graph (M2) + references" (branch `v1.2`, plain message, no AI trailer, per the hard rule).

## What was built

- `src/league_strength.py` — hierarchical Bayesian Poisson model (PyMC 5, non-centred
  parameterisation), identified from league movers. Public API: `build_movers`,
  `count_transitions`/`n_transitions_by_league`, `fit_model`, `league_strength_table`,
  `diagnostics_summary`, `ppc_summary`/`render_ppc_figure`, `score_predictions`
  (pure OOS scorer), `build_oos_candidates`/`attach_model_predictions`/`run_oos_validation`,
  `spearman_check`/`top_disagreements`, `render_strength_figure`, `assemble_output`, `main`.
- `src/references.py` + `config/refs.yaml` — Harvard formatter (`format_harvard`,
  `in_text`, `harvard_list`) over an 11-entry, hand-verified reference list.
- `tests/test_league_strength.py` — 13 tests: synthetic two-league recovery (2 chains ×
  300 draws, ~9 s), diagnostics/PPC shape, JSON-assembly shape, Spearman/disagreements on
  a synthetic table, the OOS scorer on a toy table, `build_oos_candidates`'
  landed-in-metrics-season filter, `build_movers`' filter/collapse/movers-only logic,
  `count_transitions`, and the refs.yaml/Harvard-formatter tests.
- `templates/report.html.j2` + `src/i18n.py` + `config/i18n/cs.yaml` — new `#league-strength`
  section (right after `#multipliers`), a `#validation-robustness` stub, a `#references`
  section (end of chapter IV), TOC entries for all three, and a one-line pointer from
  slide 4's and slide 5's how-lines. In-text citations added to the existing shrinkage
  paragraph (Efron and Morris) and cluster paragraph (Rousseeuw, Pedregosa) plus nine more
  placements inside the new section's own copy.
- `Makefile` — new `strength` target, added to `all` before `render`.
- `site/build.sh` / `site/svg_labels.py` — the two new figures added to the required-file
  list, the copy list, and (cze only) the Czech SVG-relabelling `FILES`/`T` dict, plus a
  small `KEEP` regex widening (league-code y-tick labels, single-digit "N+" bucket labels).
- `render.py`: `load_data` tolerates a missing `league_strength.json` (`_load_json` default
  `{}`); `build_context` adds `league_strength`, `references`, `cite` to the template
  context, including for the offline fixture context so the Czech-render test still covers
  the new copy.

## A bug found and fixed mid-task

The model's `m_L` is Premier-League-relative (`m_L = exp(beta_ENG - beta_L)`), so for the
`NATION=eng` run the home nation's own domestic league *is* the reference league. The first
draft's copy ("How much is a Premier League season worth in Premier League terms?" /
"a Premier League season converts to 1.00 of a Premier League one") was nonsensical for that
edition. Fixed with a `home_is_reference` flag (`render.py`, comparing the home row's league
against a literal `"ENG-Premier League"` — kept as a plain string rather than importing
`src.league_strength`'s constant, so `render.py`, pulled in by most of the test suite, doesn't
gain a PyMC/ArviZ import cost) and two new i18n keys (`ch4.strength.p1_is_ref` /
`ch4.strength.home_is_ref`) that flip the framing to "how much is *everyone else* worth in
Premier League terms" instead. Verified by screenshot on the `eng` build after the fix.

## The Czech run — headline numbers

- **m_L (CZE-First League): median 0.665, 90 % HDI [0.585, 0.749]**, 64 transitions touching
  it, UEFA multiplier 0.434 for comparison — the model puts Chance Liga meaningfully closer
  to Premier-League-equivalent than the UEFA coefficient does.
- **Spearman rho = 0.742** (n = 18 leagues in common, p = 0.00042).
- **OOS winner: the model**, by both metrics, decisively:

  | Method | Log predictive density | MAE (rate) |
  |---|---:|---:|
  | Same rate as before (naive) | −5.217 | 0.161 |
  | Rate × UEFA-multiplier ratio | −6.052 | 0.224 |
  | Model | **−2.174** | **0.127** |

  (863 OOS candidates: movers whose first 2025/26 row followed a league change.)
- Diagnostics: max R-hat 1.0028, min bulk ESS 1223.6, min tail ESS 1593.4, **0 divergences**.
  Main fit: 8108 rows, 2125 players, 7 seasons, **213.8 s**. OOS refit (2 chains × 500 draws,
  lighter budget, seasons < 2025/26 only): 84.5 s (that refit's own rhat/ESS warnings are
  expected and don't matter — only its posterior *medians* feed the OOS point predictions,
  not its own inference quality).
- PPC: observed vs. replicated — zero-share 15.44 % vs 13.87 %, mean 4.445 vs 4.4455 (near-exact),
  90th percentile 11.0 vs 10.85. Slightly under-dispersed at zero, otherwise a close match.
- Three largest disagreements with the UEFA ranking:
  1. **HUN-NB I**: model rank 6 vs UEFA rank 17 (m_L 0.743 vs multiplier 0.265) — only 35
     transitions, widest relative HDI of the low-transition leagues.
  2. **NED-Eredivisie**: model rank 15 vs UEFA rank 8 (m_L 0.597 vs multiplier 0.510).
  3. **NOR-Eliteserien**: model rank 18 vs UEFA rank 13 (m_L 0.574 vs multiplier 0.374).

Full `m_L` table (median, 90 % HDI, transitions, UEFA), sorted:

| League | m_L | 90 % HDI | Transitions | UEFA |
|---|---:|---:|---:|---:|
| ENG-Premier League | 1.000 | 1.000–1.000 | 588 | 1.000 |
| ITA-Serie A | 0.935 | 0.890–0.981 | 569 | 0.856 |
| ESP-La Liga | 0.908 | 0.859–0.953 | 435 | 0.807 |
| FRA-Ligue 1 | 0.810 | 0.772–0.848 | 672 | 0.666 |
| GER-Bundesliga | 0.777 | 0.741–0.814 | 588 | 0.788 |
| HUN-NB I | 0.743 | 0.625–0.864 | 35 | 0.265 |
| POR-Primeira Liga | 0.721 | 0.680–0.762 | 350 | 0.630 |
| BEL-Pro League | 0.671 | 0.637–0.710 | 474 | 0.573 |
| **CZE-First League** | **0.665** | **0.585–0.749** | **64** | **0.434** |
| TUR-Süper Lig | 0.660 | 0.625–0.696 | 472 | 0.484 |
| POL-Ekstraklasa | 0.659 | 0.599–0.729 | 131 | 0.438 |
| AUT-Bundesliga | 0.657 | 0.576–0.729 | 80 | 0.268 |
| DEN-Superliga | 0.636 | 0.576–0.702 | 117 | 0.371 |
| GER-2. Bundesliga | 0.600 | 0.555–0.645 | 230 | 0.473 |
| NED-Eredivisie | 0.597 | 0.567–0.632 | 387 | 0.510 |
| CRO-HNL | 0.597 | 0.525–0.671 | 64 | 0.249 |
| SUI-Super League | 0.597 | 0.538–0.649 | 128 | 0.293 |
| NOR-Eliteserien | 0.574 | 0.507–0.639 | 64 | 0.374 |

## The England run

`NATION=eng` was run for real (not copied) — `python -m src.league_strength` end to end,
main fit + OOS refit. **The resulting `league_strength.json` is byte-identical to the Czech
run's, except for the two wall-clock `runtime_s`/`refit_runtime_s` fields** (203.6 s /
82.4 s vs. Czech's 213.8 s / 84.5 s). This is a genuine finding, not an assumption: `diff`
on the two JSON files (pretty-printed) shows only those two numeric lines differ. The reason
is structural, not a bug — this model draws on `features_{FW,MF,DF}.parquet`, which (per
that file's own docstring convention) already carries every fetched nationality regardless
of home nation, and in the current repo state the `eng` and `cze` processed directories
happen to hold the same underlying player-season rows, so `build_movers` produces the exact
same 8108-row/2125-player/7-season corpus either way, and with the shared
`config.RANDOM_SEED = 42` the fit reproduces to the same posterior. So: **ran both, did not
copy, and they matched** — worth flagging to the coordinator in case the England-run's
processed data is expected to diverge from Czech's once its own fetch is truly independent
(peer-domestic leagues, etc.) — right now it evidently isn't, for this pipeline stage.

## References — verification log

All 11 candidates from the brief were kept; every one verified before being added to
`config/refs.yaml`:

| Key | Check | Result |
|---|---|---|
| efron_morris_1975 | `curl -sI https://doi.org/10.1080/01621459.1975.10479864` | 302 → tandfonline.com |
| gelman_et_al_2013 | `curl -sIL https://www.stat.columbia.edu/~gelman/book/` | 200 |
| hoffman_gelman_2014 | `curl -sI https://www.jmlr.org/papers/v15/hoffman14a.html` | 200 |
| vehtari_gelman_gabry_2017 | `curl -sI https://doi.org/10.1007/s11222-016-9696-4` | 302 → springer.com |
| abril_pla_et_al_2023 | `curl -sI https://doi.org/10.7717/peerj-cs.1516` | 302 → peerj.com |
| kumar_et_al_2019 | `curl -sI https://doi.org/10.21105/joss.01143` | 302 → joss.theoj.org |
| rousseeuw_1987 | `curl -sI https://doi.org/10.1016/0377-0427(87)90125-7` | 302 → elsevier.com |
| pedregosa_et_al_2011 | `curl -sI https://www.jmlr.org/papers/v12/pedregosa11a.html` | 200 |
| kharrat_mchale_pena_2020 | `curl -sI https://doi.org/10.1016/j.ejor.2019.11.026` | 302 → elsevier.com |
| hvattum_2019 | `curl -sI https://doi.org/10.2478/ijcss-2019-0001` | 302 → reference-global.com |
| poli_ravenel_besson_2024 | `curl -sI https://football-observatory.com/IMG/sites/mr/mr95/en/` | 200 |

The CIES entry is Monthly Report n°95 (May 2024), "Origins and destinations of football
expatriates (2020-2024)" — the most recent report on that theme I could locate with a
stable URL (the two more recent reports, n°97 and n°98, cover transfer-market economics and
scouting, not expatriates). Gelman et al.'s *Bayesian Data Analysis* has no DOI; I used the
author's own canonical book page (`stat.columbia.edu/~gelman/book/`, 200) rather than a
paywalled publisher page. Nothing was dropped — every candidate verified.

## Test summary

`uv run pytest -q -p no:warnings` (NATION=cze, the default): **174 passed**, ~22 s. Includes
the new `tests/test_league_strength.py` (13 tests, dominated by one ~9 s synthetic-fit
fixture) and updated `tests/test_render.py`/`tests/test_i18n.py` (new section ids, the
slide.4.how pointer text, added `league_strength`/`references`/`cite` to the offline fixture
context). The golden-fixture test (`test_context_matches_golden_fixture_for_cze`) still
passes unmodified — Task 15 only *adds* context keys, never touches `hero`/`per_capita`/
`cards`/`squad_lens`/`peer_compare`.

`NATION=eng uv run pytest` has 5 failures / 4 errors, all **pre-existing and unrelated** to
this task (confirmed by inspection): `CZE`-hardcoded assumptions in `_val`/benchmark/big5
helpers, `test_nation_defaults_to_cze`, and `test_site_build.py`'s CS-page assertions (the
England build is English-only by design, no `docs/eng/cs/`). None reference
`league_strength`/`references`/anything this task touched.

`uvx ruff check` clean on every new/hand-edited file except two **pre-existing** warnings I
left alone (`site/svg_labels.py`'s import-after-`sys.path.insert` pattern, and an ambiguous
`l` loop variable in a `test_render.py` test I didn't write) — neither introduced by this task.

## Verify steps run

- `uv run pytest -q -p no:warnings` → 174 passed.
- `NATION=cze uv run python -m src.league_strength` → full run, see numbers above.
- `NATION=eng uv run python -m src.league_strength` → full run, byte-identical output (see above).
- `NATION=cze uv run python -m src.render` + `NATION=cze ./site/build.sh` → `docs/index.html`,
  `docs/cs/index.html`.
- `NATION=eng uv run python -m src.render` + `NATION=eng ./site/build.sh docs/eng` →
  `docs/eng/index.html`.
- Screenshots: one Chrome tab per nation (via a local `python3 -m http.server` on `docs/`
  and `docs/eng/`, since `file://` URLs are blocked by the extension), scrolled through the
  full `#league-strength` section (question, design paragraph with in-text cites, figure,
  home-conversion line, table, OOS table, Spearman + disagreements, diagnostics line, PPC
  fold expanded to confirm the second figure, ranking statement), the `#validation-robustness`
  stub, and the `#references` list — both closed after. The England screenshot is what caught
  the `home_is_reference` bug above.

## Concerns / things worth a second look

1. **England and Czech runs currently share one corpus.** Not a bug in this task, but worth
   the coordinator's attention: if a later task expects the two nations' `league_strength.json`
   to diverge once England's fetch is more independent, that will only show up after a fresh
   `make fetch`/`make features` for `eng` — right now `data/processed/eng/features_*.parquet`
   evidently mirrors `cze`'s.
2. **`collapse_player_seasons(rate_cols=[])`** (used identically to every other caller in this
   codebase) sums `min` across a same-season multi-club split but takes `npg`/`ast` from the
   most-minutes club only, not summed — a known, pre-existing approximation (documented in
   `src/utils.py`'s docstring) that very rarely affects `y = npg + ast` for cross-league
   mid-season moves. Flagged in `league_strength.py`'s own docstring; not fixed here since it
   would mean changing a shared utility's contract for every other caller.
3. **Thin-transition leagues carry visibly wider HDIs** (HUN-NB I at 35 transitions: HDI width
   0.24, vs. FRA-Ligue 1 at 672 transitions: HDI width 0.076) — exactly as expected, and it's
   the leagues with the fewest transitions that produce the largest UEFA disagreements. The
   report's diagnostics line and the `n_transitions` column make this visible but don't call
   it out explicitly in prose; a future pass could add one sentence.
4. The OOS refit's own R-hat/ESS warnings (2 chains × 500 draws, expected with only 2 chains)
   are real PyMC warnings in the log — harmless here since only posterior medians are used for
   the OOS point predictions, but worth knowing they're there if anyone diffs the log later.
