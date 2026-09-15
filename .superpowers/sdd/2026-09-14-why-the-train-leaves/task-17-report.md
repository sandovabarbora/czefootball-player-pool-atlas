# Task 17 report — "From raw tables to a feature vector"

## Summary

Added `src/feature_eda.py`, wired it into the Makefile (`eda` target, ahead of
`data-quality`/`render` in `all`), and added a new report section
`#features-from-raw` (Chapter IV, right after "Data sources") in both
languages. The section shows one worked player-season end to end — raw FBref
row → per-90 → Bayesian-shrunk → league-quality-adjusted → z-score — the
cleaning ledger (linked to `#data-quality`, not recomputed), the five kept
features with a one-clause reason each, a five-row rejected-candidates table
computed from the corpus, and two new figures (`eda_distributions.svg`,
`eda_shrinkage.svg`).

Ran for both `cze` and `eng`, rendered + built both sites, screenshotted the
section in one browser tab (EN and CS), then closed it. Full test suite green
(201 tests), ruff clean.

## The raw row → feature row (NATION=cze, metrics season 2025/26)

Home player with the most metrics-season minutes among those who cleared the
inclusion floor: **Vladimír Coufal** (GER-Bundesliga, Hoffenheim, DF).

Raw FBref row:

| column | value |
|---|---|
| league | GER-Bundesliga |
| season | 2025-2026 |
| team | Hoffenheim |
| player | Vladimír Coufal |
| nation | CZE |
| pos | DF |
| born | 1992 |
| age | 32 |
| mp | 34 |
| min | 3012 |
| gls | 1 |
| ast | 8 |
| pk | 0 |
| crdy | 4 |
| crdr | 0 |

Feature row after the pipeline (raw → shrunk → quality-adjusted → z):

| feature | raw | shrunk | quality | z |
|---|---|---|---|---|
| npg_p90 | 0.0299 | 0.0338 | 0.0266 | 0.208 |
| ast_p90 | 0.239 | 0.193 | 0.152 | 4.308 |
| min_share | 0.9843 | 0.9843 | 0.9843 | 1.670 |
| age | 32.0 | 32.0 | 32.0 | 1.451 |
| cards_p90 | 0.1195 | 0.1353 | 0.1353 | -0.895 |

(`min_share`/`age` pass through shrinkage and quality unscaled, matching
`src/features.py`'s own design — only the two production rates get the
league multiplier.)

## Rejected-candidates table (cze, metrics season, corpus-wide — every
fetched nationality)

| candidate | statistic | value | decision |
|---|---|---|---|
| gls_p90 | corr(gls_p90, npg_p90) | 0.973 | replaced by npg_p90 |
| mp | corr(mp, min) | 0.844 | replaced by minutes share |
| crdr_p90 | share of player-seasons with zero red cards | 0.854 | folded into cards |
| age | spread of median production across age bands | 0.028 | kept |
| born | share of player-seasons missing a birth year | 0.003 | kept — required for the player key |

Supporting numbers behind the table:
- Top-3 penalty share (players who took the most of their team's penalties
  among their own goals): Nabil Touaizi (POR-Primeira Liga, 100%), Yohan
  Croizet (HUN-NB I, 100%), Luca Zuffi (SUI-Super League, 100%).
- Age-band medians (npg_p90 + ast_p90): U22 0.173 (n=1155), 23-25 0.175
  (n=2035), 26-29 0.169 (n=1527), 30+ 0.147 (n=939) — real but modest;
  called out honestly below.
- Most-shrunk home-eligible player: Antonín Růsek (CZE-First League, 454
  min, raw npG/90 0.595 → shrunk 0.250, Δ = -0.345) — annotated on the
  shrinkage figure.

## Figures

- `outputs/<nation>/eda_distributions.svg`: five small-multiple boxplots
  (one per raw feature) across the top leagues by row count plus the
  domestic league (always included, highlighted in oxblood). `npg_p90` and
  `ast_p90` are log1p-scaled for cze (skewness > 1.5, computed not typed).
- `outputs/<nation>/eda_shrinkage.svg`: raw vs. shrunk npG/90 against
  minutes for home-eligible players, connected by a thin segment per player,
  with the shrinkage weight curve `K / (minutes + K)` on a second axis
  (dashed, oxblood) and the most-shrunk player annotated.

Both render for `cze` and `eng` with different content (verified via md5:
`eda_shrinkage.svg` differs completely between nations; `eda_distributions.svg`
happens to be the same byte size but different content — the raw-feature
corpus it draws from is nation-independent, only the highlighted domestic
league differs).

## Files touched

- `src/feature_eda.py` (new, 425 lines)
- `tests/test_feature_eda.py` (new, 15 tests)
- `src/render.py` (`_build_feature_eda`, wired into `load_data`,
  `build_context`, `build_context_from_fixtures`)
- `src/i18n.py` / `config/i18n/cs.yaml` (39 new `ch4.eda.*` keys, EN + CS)
- `templates/report.html.j2` (new `#features-from-raw` section)
- `Makefile` (`eda` target; added to `.PHONY` and `all`; also folded in the
  pre-existing but undocumented `compare` target while touching those lines)
- `site/build.sh` (two new SVGs added to the required-file check and the
  copy list; **not** added to `site/svg_labels.py`'s Czech-translation
  pipeline — same choice already made for `league_strength*.svg` and
  `model_comparison.svg`, whose Czech pages also reference the English
  parent SVG rather than a locally-translated copy)
- `data/snapshot/{cze,eng}/feature_eda.json` (new)
- `docs/`, `docs/cs/`, `docs/eng/` (rebuilt; `atlas_*.svg` diffs are only the
  embedded generation-timestamp metadata + glyph-id renumbering matplotlib
  stamps on every render, not a content change)

## Self-review notes / concerns

- **Age effect is real but small.** The age-band spread (0.028) is the
  weakest of the five rejected-candidate numbers — I kept the feature per
  the brief (a genuinely non-flat curve), and said so plainly in copy
  ("real but modest"/kept as its own axis) rather than overstating it.
- **Czech translation of the two new SVGs' internal text was skipped.**
  `site/svg_labels.py` enforces "every non-numeric label longer than a
  surname must have an entry, or the build fails loudly" — my figures'
  subplot titles (`npg_p90 (log1p)`, etc.) aren't in its `KEEP` allow-list
  and would need new entries. I mirrored the existing, already-shipped
  precedent for `league_strength*.svg`/`model_comparison.svg`: added to
  `site/build.sh`'s copy list but not to `svg_labels.py`, so the Czech page
  shows the same (English-labelled) SVG as the English page — the
  surrounding prose and table are fully Czech either way. This is
  consistent with, not a regression from, what Tasks 15/16 already shipped.
- **Golden fixture untouched.** `tests/fixtures/context_cze_golden.json`
  only compares `hero`/`per_capita`/`cards`/`squad_lens_rows`/`peer_compare`
  — none of which this task's code path touches — so no update was needed
  there; the golden test still passes.
- **`data/snapshot/` diff is minimal.** `make snapshot` for both nations
  added only the two new `feature_eda.json` files; nothing else in
  `data/snapshot/` changed (verified via `git status`), confirming I didn't
  accidentally touch `model_comparison.json` or any other processed output.
