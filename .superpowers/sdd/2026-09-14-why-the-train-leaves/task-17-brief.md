# Task 17: "From raw tables to a feature vector" — wrangling, EDA, feature engineering shown

**Spec §4c** (Senior Insights brief): "Wrangling, EDA and feature engineering shown, not
claimed." Chapter IV gets a section `#features-from-raw` placed right after "Data
sources": one raw row → the cleaning steps → the five features and why five → what was
tried and rejected → two EDA figures. Everything computed from the run; nothing typed.

## A. Module `src/feature_eda.py` → `data/processed/<nation>/feature_eda.json` + two SVGs
1. **The raw row**: pick the home nation's player with the most metrics-season minutes
   (from `fbref_players.parquet`), show his raw FBref columns as they arrive
   (`league, season, team, player, nation, pos, born, age, mp, min, gls, ast, pk, crdy,
   crdr`) and the same player's feature row after the pipeline
   (`npg_p90, ast_p90, min_share, age, cards_p90` → shrunk → quality-adjusted → z).
   Output as two small dicts.
2. **Cleaning ledger, counted**: reuse `data_quality.json` checks (women filtered,
   namesakes, split seasons, no-table players, season guard incidents) — link, do not
   recompute.
3. **Why five features — the rejected candidates, with the reason from the data**:
   compute for the metrics season, corpus-wide: (i) `gls_p90` vs `npg_p90` correlation
   (penalties inflate a few players — show the top-3 penalty share); (ii) `starts`
   proxy: `mp` vs `min` correlation (why minutes share, not appearances); (iii)
   `crdr_p90` (red cards) — share of player-seasons with zero (why it is folded into
   `cards`); (iv) `age` vs production curve (why age stays as a feature: median
   production by age band); (v) missingness per raw column (why `born` matters for the
   key). One table `rejected: [{candidate, statistic, value, decision}]` — decisions
   are descriptive ("folded into cards", "kept", "replaced by minutes share").
4. **EDA figure 1** `outputs/<nation>/eda_distributions.svg`: the five raw per-90
   features' distributions per league (small multiples, log-scaled where skewed;
   home league highlighted) — the picture that motivates shrinkage and league
   adjustment.
5. **EDA figure 2** `outputs/<nation>/eda_shrinkage.svg`: raw vs shrunk `npg_p90`
   against minutes (scatter with the K = {phantom_minutes} curve) — what shrinkage
   does to low-minute players; annotate the home nation's most-shrunk player
   (computed).
6. Makefile target `eda`; add to `all` before `render`; `render.load_data` tolerates
   a missing JSON.

## B. Report section (EN + CS, i18n)
- `h3` "From raw tables to a feature vector"; the raw row and the feature row as a
  two-column `table.kv` (label → value); one sentence per cleaning step with its
  count (from data_quality.json; link `#data-quality`); the "five features" paragraph
  as a list: feature → definition → why (one clause each); the rejected-candidates
  table; the two figures with one-sentence captions; cites: (Efron and Morris, 1975)
  at shrinkage, (Rousseeuw, 1987) is already at silhouette elsewhere. Mono only for the
  raw column names.
- Fold the raw/feature tables under `details.fold` if the section exceeds two screens
  at 1440 px.

## C. Tests
`tests/test_feature_eda.py`: rejected-candidates statistics on a toy corpus (penalty
share, mp–min correlation, red-card zero share); raw/feature row extraction picks the
most-minutes home player; JSON shape; figure smoke test (tmp_path).

## Verify
`uv run pytest -q -p no:warnings`; `NATION=cze uv run python -m src.feature_eda`,
`NATION=eng` the same (nation-specific: the raw row differs); render + build both;
screenshots (one tab, close it). Commit plain message, no AI trailer; add
src/config/templates/tests + rebuilt docs + snapshots; never data/processed, outputs.
