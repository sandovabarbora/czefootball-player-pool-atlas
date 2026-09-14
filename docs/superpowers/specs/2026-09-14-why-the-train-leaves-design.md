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

## 5. Report structure after v1.2

Hero → six findings → **I. Why the train leaves** (M1–M5) → **II. Where it works:
goalkeepers** → III. The pool (benchmark, atlases, trajectories — today's chapter I,
shortened) → IV. Pathways exhibits A–F (today's chapter II, referenced from M1–M3) →
V. Cards and analogs → VI. Player index → VII. Methodology (models, validation,
data-quality log, how built, limitations, reproducibility).

## 6. Out of scope

Causal claims; recommendations; forecasts; event/tracking data (linked only);
the interactive sensitivity slider (deferred; may return as a last block).

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
