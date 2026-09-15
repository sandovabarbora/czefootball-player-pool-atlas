# Task 15: League strength from the transfer graph (M2) + references

**Spec:** `docs/superpowers/specs/2026-09-14-why-the-train-leaves-design.md` §2 M2, §4, §4b.
**Spike facts (controller, 2026-09-14):** corpus ≥ 450 min, all nationalities, 7 seasons
(2020/21 → 2026/27, headline leagues from 2020/21, the rest from 2024/25): 24 912
player-seasons, 10 256 players; **2 125 movers** (players with ≥ 2 leagues), 8 108 of
their player-seasons, 2 731 league transitions across 240 league pairs; the Czech league
sits in ~60 transitions (POL↔CZE 15, BEL→CZE 11, NED→CZE 6, TUR↔CZE 7, GER→CZE 4, …).
A naive hierarchical Poisson on *all* players (controller spike) recovers league goal
environments (Eredivisie highest, Serie A lowest), not strength — the player effects are
shrunk toward one mean, so league effects absorb the league's talent mix. Identification
must come from within-player contrasts, i.e. movers.

## Model (`src/league_strength.py`)
- Data: `features_{FW,MF,DF}.parquet` (nation dir), `min ≥ 450`, `born` known,
  `collapse_player_seasons` applied; **movers only** (≥ 2 distinct leagues); response
  `y = npg + ast` (non-penalty goals + assists, integers), exposure `min/90`.
- `y ~ Poisson(exp(α + β_league + γ_pos + f(age) + u_player) · exposure)`,
  `f(age)` quadratic on `(age − 26)/5`; `u_player ~ Normal(0, σ_u)` with **σ_u ~ HalfNormal(2)**
  (wide: player effects essentially unpooled — the within-player contrast is the point);
  `β_league ~ Normal(0, σ_L)`, `σ_L ~ HalfNormal(0.5)`, non-centred; `γ_pos ~ Normal(0, 1)`.
  PyMC 5, NUTS, 4 chains × 1 000 draws after 1 000 tune, `target_accept 0.9`,
  `random_seed = config.RANDOM_SEED`. Runtime target < 10 min (spike: 3 min on 10 k rows).
- **Strength scale:** `m_L = exp(β_ENG − β_L)` (a rate in league L converted to a
  Premier-League-equivalent rate; `m_ENG = 1`). Report median and 90 % HDI per league,
  the number of transitions touching the league, and R-hat/ESS/divergences.
- **Validation (three, all in the JSON):**
  1. posterior predictive check: observed vs replicated `y` distribution (one summary
     statistic: share of zeros, mean, 90th percentile) and a PPC figure;
  2. **out-of-sample on the last season**: refit on seasons < metrics season, predict each
     mover's first season after a league change in the metrics season; score log
     predictive density and MAE against (a) "same rate as before" naive, (b) rate × UEFA
     multiplier ratio, (c) the model; one table;
  3. rank correlation (Spearman) between model medians and `config/league_quality.yaml`
     multipliers; the three largest disagreements named.
- Output `data/processed/<nation>/league_strength.json`
  (`leagues: [{league, median, hdi_lo, hdi_hi, n_transitions, uefa}]`, `diagnostics`,
  `ppc`, `oos`, `spearman`, `disagreements`, `fit: {rows, players, seasons, runtime_s}`)
  and figures `outputs/<nation>/league_strength.svg` (dot + interval per league, sorted,
  UEFA multiplier as a hollow marker; palette from `international_benchmark`) and
  `outputs/<nation>/league_strength_ppc.svg`. Makefile target `strength`; add to `all`
  before `render`; `render.load_data` tolerates a missing JSON.
- The model is nation-independent (all nationalities) — it runs under each nation dir
  (fast enough); no sharing needed.

## Report (chapter IV, EN + CS, all through i18n)
New section `#league-strength` "League strength: two estimates" right after "League
multipliers": the question ("How much is a Chance Liga season worth in Premier League
terms?"), the design in three sentences (movers, within-player contrasts, partial
pooling), the figure, the OOS table, the Spearman number and the three disagreements,
the diagnostics line, and a plain statement of which estimate the rankings use (UEFA,
unchanged) and why the model estimate is shown beside it (the report's own check on
its assumption). Add a one-line pointer from slide 4's and slide 5's how-lines
("league strength: two estimates, § Methodology") and a **Validation & robustness**
subsection stub that lists this model's diagnostics (later tasks add M1/M4).
Numbers via placeholders; nothing typed.

## References (Harvard) — `config/refs.yaml` + section `#references`
`refs.yaml`: `key, authors, year, title, container, volume, issue, pages, doi|url`.
Render an alphabetical list in Harvard style in a new final methodology section
"References", and in-text author–date cites "(Efron and Morris, 1975)" placed by the
template where the method is described (shrinkage, hierarchical model, NUTS, LOO/PPC,
silhouette, PyMC, ArviZ, plus-minus/RAPM lineage, expatriate-player reports). Candidate
list — **include only after verifying each DOI/URL resolves (`curl -sI https://doi.org/<doi>`
→ 30x) and the bibliographic fields are right; drop any you cannot verify, never invent**:
- Efron, B. and Morris, C. (1975) 'Data analysis using Stein's estimator and its
  generalizations', Journal of the American Statistical Association, 70(350), pp. 311–319. doi:10.1080/01621459.1975.10479864
- Gelman, A., Carlin, J.B., Stern, H.S., Dunson, D.B., Vehtari, A. and Rubin, D.B. (2013) Bayesian Data Analysis. 3rd edn. Boca Raton: CRC Press.
- Hoffman, M.D. and Gelman, A. (2014) 'The No-U-Turn Sampler: adaptively setting path lengths in Hamiltonian Monte Carlo', Journal of Machine Learning Research, 15, pp. 1593–1623.
- Vehtari, A., Gelman, A. and Gabry, J. (2017) 'Practical Bayesian model evaluation using leave-one-out cross-validation and WAIC', Statistics and Computing, 27(5), pp. 1413–1432. doi:10.1007/s11222-016-9696-4
- Abril-Pla, O. et al. (2023) 'PyMC: a modern, and comprehensive probabilistic programming framework in Python', PeerJ Computer Science, 9, e1516. doi:10.7717/peerj-cs.1516
- Kumar, R., Carroll, C., Hartikainen, A. and Martin, O. (2019) 'ArviZ a unified library for exploratory analysis of Bayesian models in Python', Journal of Open Source Software, 4(33), 1143. doi:10.21105/joss.01143
- Rousseeuw, P.J. (1987) 'Silhouettes: a graphical aid to the interpretation and validation of cluster analysis', Journal of Computational and Applied Mathematics, 20, pp. 53–65. doi:10.1016/0377-0427(87)90125-7
- Pedregosa, F. et al. (2011) 'Scikit-learn: machine learning in Python', Journal of Machine Learning Research, 12, pp. 2825–2830.
- Kharrat, T., McHale, I.G. and Peña, J.L. (2020) 'Plus–minus player ratings for soccer', European Journal of Operational Research, 283(2), pp. 726–736. doi:10.1016/j.ejor.2019.11.026
- Hvattum, L.M. (2019) 'A comprehensive review of plus-minus ratings for evaluating individual players in team sports', International Journal of Computer Science in Sport, 18(1), pp. 1–23. doi:10.2478/ijcss-2019-0001
- Poli, R., Ravenel, L. and Besson, R. (CIES Football Observatory) — the most recent
  'Expatriate footballers' monthly report you can locate with a stable URL (cite year and
  report number as on the page).
Place the citations where the text already describes the method; do not add prose to
make room for a cite.

## Tests
`tests/test_league_strength.py`: (1) synthetic movers with known league effects (two
leagues, 300 players, Poisson draws with a fixed seed) → the recovered `m_L` ordering and
magnitude within a tolerance (short sampling: 2 chains × 300 draws in the test); (2) the
OOS scorer on a toy table; (3) the JSON shape; (4) `refs.yaml` loads, every entry has
year/title and a doi or url, and the Harvard formatter produces
"Efron, B. and Morris, C. (1975) 'Data analysis…', Journal of the American Statistical
Association, 70(350), pp. 311–319." for the fixture.

## Verify
`uv run pytest -q -p no:warnings`; `NATION=cze uv run python -m src.league_strength`
(report runtime, diagnostics, the m_L table, OOS table, Spearman, disagreements);
`NATION=eng` the same (or copy the JSON if identical inputs — say which); render + build
both nations; screenshots of the new section (one tab, close it). Commit plain message,
no AI trailer; add src/config/templates/tests/site + rebuilt docs + snapshots; never
`data/processed`, `outputs`.
