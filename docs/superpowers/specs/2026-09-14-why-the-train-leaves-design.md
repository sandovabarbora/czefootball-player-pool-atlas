# Why the train leaves — v1.2 design

Date: 2026-09-14. Author: Barbora Šandová (with Claude). Status: draft for review.
Supersedes §2B–§2E of `2026-09-14-v1-1-portfolio-edition-design.md`; block A of that
spec is live. Builds on the v1 spec.

## 1. The question and the audience

v1 and block A describe *how big* the Czech pool is. The report's spine now becomes
one question — **why does the Czech pool fall behind peer countries of the same
size?** — answered as five mechanisms, each with an effect size, an interval and a
validation, and one counter-example (goalkeepers) where the same pipeline works.

The second audience is the FA insights panel. What they should be able to read off:
a football question turned into testable mechanisms; hierarchical Bayesian
modelling with honest uncertainty; a time series with a dated break; validation
against held-out data; and a method that transfers to England unchanged.

Stance stays descriptive: mechanisms are *associations in public data*, never
causal claims or recommendations. Every effect is reported with its interval and
with the sentence that says what it does not show.

## 2. The five mechanisms (chapter "Why the train leaves")

Each mechanism = one exhibit, one model or estimator, one validation, one footnoted
finding line. All on the corpus already fetched (17 leagues 2024/25–2026/27 + the
nine headline leagues back to 2020/21), unless stated.

### M1 · Late export
- Exhibit: age at first top-9 season, distribution per peer country (box/strip),
  Czech median 24 vs DEN/CRO 22 (already known); plus *what happens next*: the
  first-two-season top-9 production of exports by export age band.
- Model: hierarchical regression of quality-adjusted npG+A/90 in the first two top-9
  seasons ~ age at export (spline) + origin league effect + position, with country
  random effect; PyMC, NUTS. Output: expected production at export age 20 vs 24
  with 90 % interval; league-of-origin effects.
- Validation: posterior predictive check; out-of-sample on 2025/26 entrants (fit on
  ≤ 2024/25).
- Finding: "Exports who arrive at 21–22 produce X (a–b) in their first two top-9
  seasons; those arriving at 24+ produce Y (c–d)." plus the caveat that selection
  (better players leave earlier) is not separated from development.

### M2 · The domestic league as a ceiling
- Exhibit: estimated league strength with intervals, side by side with the UEFA
  coefficient multipliers used so far (validation exhibit from the old spec §2C).
- Model: player-season npG+A ~ Poisson(exposure = 90s) with log-rate = α +
  β_league + γ_position + f(age) + u_player, partial pooling on league and player;
  fitted on all nationalities, all fetched seasons. League effects scaled so the
  strongest = 1.00. Movers (same player in two leagues) identify β; report how many
  such transitions carry the Czech league's estimate.
- Validation: rank correlation with UEFA multipliers; predicted vs realised
  production of players who moved CZE → top-9 (calibration plot).
- Finding: "A Chance Liga season counts X (a–b) of a Bundesliga season; the UEFA
  coefficient implies 0.55." Which one the report's rankings should trust is
  stated in Limitations; rankings stay on UEFA for v1.2 (stability), the model
  effects are shown beside them.

### M3 · Minutes for the young at home
- Exhibit: exhibit A extended into a cross-country panel: U21 share of domestic
  minutes (2023/24–2025/26) against top-9 players per million, all nine peers,
  three seasons each — a scatter with a fitted line and its band.
- Estimator: Bayesian simple regression across country-seasons (n = 27) with the
  country random effect; report the slope with its interval and say plainly that
  n is small.
- Finding: "Countries that give U21 players X pp more of their domestic minutes have
  Y (a–b) more top-9 players per million; Czechia sits at …"

### M4 · When the train left
- Data: FBref Big-5 player tables 2000/01–2025/26 (130 pages, cached, headless).
- Exhibit: Czech players (and minutes share) in the Big-5 per season, 26 seasons,
  peer countries as thin lines; golden-generation seasons annotated *from the
  data* (the Czech players with the most Big-5 minutes each season).
- Model: local level model with a single structural break (or a change-point on
  the level), fitted on the Czech count series; report the break year with its
  interval; the same for DEN/CRO as contrast. Explicitly "smoothing and a break,
  not a forecast".
- Finding: "The Czech Big-5 presence fell from X (peak season) to Y; the break is
  dated to season Z (interval)."

### M5 · What the gap is made of
- Descriptive decomposition of the CZE–DEN (and CZE–NOR) difference in top-9
  players per million into: export age profile (M1), domestic league strength (M2),
  U21 minutes (M3), and a residual — Shapley-style over the fitted models, or a
  simpler Oaxaca-type split if the models do not compose cleanly. Reported as a
  bar with the residual shown honestly.
- Finding: "Of the gap of X players per million to Denmark, the export-age profile
  accounts for …, league strength …, youth minutes …, unexplained …"

## 3. The counter-example (chapter "Where it works: goalkeepers")

- Data: FBref keeper tables (`stat_type="keeper"`) for every fetched league-season;
  GK rows are already in the standard tables (minutes, born, nation).
- Exhibits: (i) GK per million in top-9 leagues by peer country; (ii) age at export
  of Czech GKs vs outfield exports vs peer GKs — the four Czech top-9 keepers were
  born 2000–03 and left at 18–21; (iii) the club tier they sit at (Tottenham, Ajax,
  PSV, Braga) and minutes; (iv) a short GK table (save %, GA/90, clean-sheet share,
  shrunk, quality-adjusted) with peer medians.
- Finding: "The one position where Czech exports leave at the peer age is the one
  where the pool's top-9 presence per million is at the peer median." Descriptive;
  the chapter says what differs in the pathway (academy moves at 18) without
  claiming cause.
- Cards: two GK cards by rule (most top-9 minutes; youngest top-9 keeper).

## 4. Validation & robustness (chapter IV addition)

- One section listing every model with: data, prior choices, convergence (R-hat,
  ESS, divergences), posterior predictive summary, out-of-sample check, and the
  sensitivity of its headline number to the shrinkage constant and the multiplier
  set. The existing sensitivity table stays.
- The findings tiles at the top become the five mechanism findings + the GK
  counter-example (six tiles), each with its interval.

## 4b. R&D evidence layer (the FA "Research & Development Data Scientist" brief)

The vacancy asks for: world-leading statistical/ML models validated with rigour;
novel methodology; evaluating emerging methods and literature; AI coding agents;
monitoring model performance over time; a peer-review culture; pipelines whose
outputs others can use (cloud, documented, professional code); visualisations and
web apps for stakeholders to explore model outputs; tracking/event-data
experience (strongly desirable); GCP, GitHub, deep learning (e.g. GNNs) beneficial.
Each item gets a visible, honest counterpart in the report:

- **Model comparison, not one model.** The M1 question ("what does a season predict
  about the next one, given export age, league and age?") is answered by three
  models on the same rolling-origin task — the hierarchical Bayesian model (M2
  effects), a gradient-boosted baseline, and a small neural player-season
  embedding — scored out of sample per season (2021/22 → 2025/26). One table, one
  chart, the honest winner named; the neural model is kept only if it earns its
  place. This is the "monitor performance over time" exhibit as well: the same
  scores per origin season, with drift called out.
- **Related methods** (chapter IV): a short annotated list — Efron–Morris shrinkage,
  plus-minus/RAPM-style player effects, league strength from transfers (the
  movers-identified design used in M2), Bayesian change-point (M4), Shapley/Oaxaca
  decompositions (M5), player embeddings / graph methods (the transfer network as a
  graph; GNN named as the natural next step, not claimed) — one sentence each on
  what was taken and what was left out and why.
- **Novel piece, stated as such:** league strength identified from the transfer
  graph with partial pooling, combined with the age-at-export curve — the pair
  turns "we export late" from an observation into an estimated cost with an
  interval.
- **Peer review culture:** the two-stage review per task and the ledger of
  rulings are shown as the project's peer review, with the counts; the ledger is
  in the repo.
- **Pipelines others can use:** `infra/bigquery/` with the parquet schemas and a
  `bq load` script; model outputs saved as parquet + JSON with a documented
  contract ("what the wider team would read"); the README's portability section
  points at it.
- **Stakeholder web app:** the interactive layers (atlas filters/tooltips,
  expandable cards, the sensitivity slider from the old §2E — reinstated as the
  last block) are the "explore model outputs" surface; vanilla JS, stated plainly
  (no React claimed).
- **Tracking-data readiness:** one paragraph with the concrete feature-vector
  extension (what columns an event/tracking feed would add and where in
  `features.py` they enter) plus the links to the author's tracking PoCs.
- **AI coding agents:** the "How this was built" section already documents the
  agentic workflow; add the model/tool split and the review gates as a diagram.

## 4c. The Senior Insights brief (the second vacancy) — what it adds

That brief stresses: translating football problems into well-defined analytical
questions; analytical products that shape selection/development/performance
decisions; wrangling, EDA and feature engineering on uncleaned data; visualisation
and web apps; stakeholder communication; GCP/BigQuery; time series & forecasting;
Bayesian inference/MCMC. On top of §4b:

- **Football question → analytical question, every time.** Each mechanism M1–M5
  and the GK chapter opens with two lines: the question as a technical director
  would ask it ("Do we sell our best 21-year-olds too late?") and the analytical
  formulation the report answers ("production in the first two top-9 seasons as a
  function of export age, given origin league and age, with a country effect").
  The findings list at the top carries the football-question phrasing.
- **Analytical products, named.** The squad lens (exhibit F) is presented as the
  selection-side product ("the squad by where its players play, next to the peers
  at the tournament"), the pathway exhibits as the development-side product, the
  cards and player index as the player-read product — each with a one-line "who
  would use it for what" that stays descriptive (no recommendation).
- **Wrangling, EDA and feature engineering shown, not claimed.** A chapter IV
  section "From raw tables to a feature vector": the raw FBref row, the cleaning
  steps (identity key, women's entries, split seasons, season guard — pointing at
  the data-quality log), the per-90 features and why exactly five, what was tried
  and rejected (e.g. cards/90 kept, minutes share vs. starts), and the EDA plots
  that decided it (distributions per league, shrinkage effect on low-minute
  players). Two figures, one table.
- **Time series with a backtested forecast.** M4's local-level model gets a
  rolling-origin backtest on the country-level Big-5 series (one-step-ahead, 2010
  → 2025) with coverage of its intervals; one forecast of the next season for the
  Czech and peer series shown *as a methods demonstration* with the interval and
  the sentence "a count of players, not a statement about any player". Ruling:
  this is the one forecast the stance allows — aggregate, backtested, labelled.
- **Bayesian/MCMC visible:** M1/M2 posterior plots, priors stated, convergence
  table, posterior predictive checks — in the validation section, not hidden.

## 5. Report structure after v1.2

Hero → six findings → **I. Why the train leaves** (M1–M5) → **II. Where it works:
goalkeepers** → III. The pool (benchmark, atlases, trajectories — today's chapter I,
shortened) → IV. Pathways exhibits A–F (today's chapter II, referenced from M1–M3) →
V. Cards and analogs → VI. Player index → VII. Methodology (models, validation,
data-quality log, how built, limitations, reproducibility).

## 6. Out of scope

Causal claims; recommendations; forecasts; event/tracking data (linked only);
the interactive sensitivity slider (deferred; may return as a last block).

## 6b. Definition of "world-leading" here

Public data, one country, one person: the claim the report makes is *rigour and
transferability*, not scale. Every model has an out-of-sample score, an interval,
a stated failure mode and a literature anchor; every number is recomputed on each
run; the whole thing runs for another nation by changing a code. That is the
standard the page holds itself to, and says so.

## 7. Order of work

1. M4 fetch (130 pages, headless, ~2 h, background) starts first — nothing depends
   on it until its exhibit.
2. M2 model (foundation: league effects reused by M1 and M5) → M1 → M3 → M5.
3. Goalkeepers chapter (independent; can run in parallel with M1–M3 on disjoint
   files).
4. M4 exhibit + break model.
5. Restructure the report (§5), findings tiles, validation chapter, deploy.

Each step: plan, subagent tasks, sonnet reviews, deploy after 2, 3 and 5.

## 8. Definition of done

Five mechanisms live with intervals and validation; GK chapter; restructured
report in both languages; models cached to `data/processed/model_*.nc`/parquet and
snapshotted; convergence diagnostics in the report; tests green; site deployed.

## 9. Deviations from the design

Written at Task 22 (the whole-branch fix wave), after the sprint shipped, so the
spec says what actually happened rather than only what was planned.

- **M3's n is 8 countries × 2 seasons (n = 16), not the 27 country-seasons this
  spec asked for (§2, "all nine peers, three seasons each").** Two independent
  narrowings, both stated in the shipped JSON's own `n`/`n_countries`/
  `seasons_used` fields rather than hidden: (1) the panel uses `{previous,
  metrics}` only, not `{previous, metrics, current}` — `current` is a season
  still in progress (partial data, see `config/seasons.yaml`) and is left out by
  design (`src/youth_panel.py`'s module docstring), so two seasons per country,
  not three; (2) Slovakia's own top flight (`SVK-Super Liga`) carries no FBref
  `comp_id` at all (`config/leagues.yaml`), so its U21-share is `None` in every
  season and its rows are dropped — 8 countries, not the 9 in `config.
  PEER_COUNTRIES`. 8 × 2 = 16. The between-country headline fit (Task 20's
  review-driven fix) then collapses that panel to one row per country, n = 8, for
  the actual slope estimate.
- **The goalkeeper counter-example's exhibit scope reached this spec's four
  exhibits (§3: (i) GK per million by country, (ii) export-age comparison, (iii)
  club tier, (iv) a production table with peer medians) in two stages, not one.**
  Task 18 shipped (ii) and (iii) as slide content and a single country's GK count
  in the slide answer; the whole-branch review (before Task 22) counted this as
  "2/4" because (i) and (iv) were computed in `goalkeepers.json`
  (`per_million`, `production`) but never rendered. Task 22 item 5 added both as
  folds under the existing club-tier table — (i) a per-country GK-per-million bar
  list reusing the `.capita` row markup, (iv) the GA/90, saves/90, save %,
  clean-sheet share and quality-adjusted GA/90 table with peer medians — closing
  the gap to 4/4 without a new data source; both were already computed by
  `src/goalkeepers.py`, just unused by the template.
- **M1 (the age-at-export production curve, §2) is still not built.** The
  whole-branch review's finding I6 ("M1 age-at-export curve never built") is real:
  nothing in the shipped pipeline fits the hierarchical regression of
  quality-adjusted npG+A/90 in the first two top-9 seasons on age at export
  (spline) + origin-league effect + position with a country random effect that
  this spec's §2 M1 describes. Ruling (whole-branch review): Task 22 is the fix
  wave for every other finding; M1 proper is Task 23, done after this fix wave,
  not folded into it.
- **The presentation restructure (§5, §7 step 5) ran first, not last.** §7's
  order of work put the report restructure after all five mechanisms (step 5, "M4
  exhibit + break model" then "Restructure the report"). The controller's actual
  ruling (v1.2 ledger, first entry) put it first instead: "presentation
  restructure ... goes first, before the models; eight question slides + Explore
  + Method" — the nine-slide question → answer → proof → how-line structure
  (Tasks 13a/13b) shipped and deployed before M2–M5 existed, so the mechanisms
  landed as slides in an already-restructured report rather than the other way
  round. Rationale recorded in the ledger: the user wanted the questions-then-
  evidence shape settled before spending model-fitting effort on content that
  would have to be re-framed into it anyway.
- **The England edition is additional scope, not in this spec.** §1 names
  "a method that transfers to England unchanged" as an audience-facing quality,
  not a deliverable; nothing in §2–§8 asks for a second nation's site. A ruling
  mid-sprint ("Run for England — pryč nebo ukázat i na ENG" → "show it") turned
  that quality into a concrete second run: `config/nations/eng.yaml`, `NATION=eng`,
  and a live `/eng/` site with an England-specific peer set, alongside the
  Czech-context golden test (`tests/test_render.py::
  test_context_matches_golden_fixture_for_cze`) that pins the Czech render so the
  nation-config refactor couldn't silently change it while adding the second one.
