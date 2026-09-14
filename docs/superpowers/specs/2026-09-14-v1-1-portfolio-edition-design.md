# Czech Football Player Pool Atlas — v1.1 "portfolio edition" design

Date: 2026-09-14. Author: Barbora Šandová (with Claude). Status: draft for review.
Builds on: `2026-09-12-czech-football-player-pool-atlas-design.md` (v1, implemented).

## 1. Purpose and audience

v1 answers "how big and how deep is the Czech pool" for a national-team
reader. v1.1 keeps every v1 finding and re-aims the report at a second
audience: an **insights hiring panel** (The FA, England Men's Insights Senior
Data Scientist, St George's Park). The panel reads for: a football problem
turned into an analytical question; validated, rigorous models; honest data
wrangling; stakeholder-grade communication; web delivery; and — explicitly in
the vacancy — Bayesian inference, time-series, and the use of AI coding agents.

The stance discipline stays: descriptive, public data, no predictions or
selection recommendations. Where v1.1 adds a model, the model *estimates
structure* (league effects, uncertainty, trend); it never says who to pick.

## 2. Scope

### A. Content additions (data already fetched)

- **Executive summary** at the top of the report: five one-line findings with
  the number, each ending in `*` with its footnote; one screen; both
  languages. Followed by a **"Method note — what transfers"** box: the same
  pipeline run for another country's pool (England's, say) needs only a
  nationality code and a peer set; nothing in the method is Czech-specific.
- **Fifth showcase rule — national-team core**: WC 2026 squad members with the
  most 2024/25 minutes in headline leagues, up to 3 per position group, skipping
  players already chosen (brings Šulc, Čvančara, Coufal by rule). Cards stay
  rule-based; a "Why these cards" note lists the five rules.
- **WC 2026 squad lens** (chapter II, exhibit F): the 26-man squad by league
  tier (top-9 / stepping stone / domestic / other), age cohort and 2024/25
  minutes, next to Croatia's and Denmark's WC 2026 squads (Wikipedia squad
  tables, same parser as v1). Descriptive.
- **Data-quality log** (chapter IV): the wrangling decisions as a table —
  name|born key, women's entries, mid-season transfers, Slovakia off FBref,
  country-page structure, ClubElo outage, photo occupation filter — with the
  count each one affected. Sourced from the ledger; numbers computed where
  possible.
- **How this was built** (chapter IV): spec → plan → subagent-driven tasks
  with two-stage reviews and a decisions ledger; links to the spec, plan and
  the v1 ledger (copied into `docs/superpowers/ledgers/` so it is in the
  repo); test count and build reproducibility. One paragraph and a small
  diagram.
- **Tracking credential**: Limitations state that no event/tracking/GPS data
  is used and link `tactical-cz` (broadcast tracking PoC for Czech football)
  and the hockey video PoC as the author's tracking work.

### B. Goalkeepers (new fetch, small)

- FBref `keeper` tables for every fetched league-season (soccerdata
  `stat_type="keeper"`; free tier: GA, saves, save %, clean sheets, minutes).
- GK pool: Czech-eligible keepers with ≥ 450 minutes; features per 90 (GA/90,
  saves/90, save %, clean-sheet share, age); shrinkage as for outfield; a
  **GK table** (not a PCA atlas — five keepers-per-club populations are too
  small for clusters) with peer-country cohort medians; cards for the
  rule-selected keepers (highest save % on ≥ 900 min; youngest NT keeper).
- Cohort heatmap gets a fourth panel (GK).

### C. Hierarchical Bayesian model (new module, runs alongside)

- `src/bayes_model.py` (PyMC): player-season npG+A count ~ Poisson with
  exposure = minutes/90 and rate = exp(α + β_league + γ_position +
  f(age) + u_player), partial pooling on league (β), position (γ) and player
  (u); f(age) a small spline or quadratic. Fitted on the full corpus (all
  nationalities, 2023/24–2024/25, ≥ 450 min), NUTS, 4 chains; convergence
  reported (R-hat, ESS, divergences).
- Outputs: **estimated league effects** with 90 % intervals, scaled so the
  strongest league = 1.00 — shown next to the UEFA-coefficient multipliers as a
  **validation exhibit** (rank correlation, biggest disagreements named);
  **player rating posteriors** (median + interval) on the twelve+ cards and
  in the player index; a **"what shrinkage does" figure** (raw vs posterior
  for low-minute players).
- The report's rankings keep using the UEFA multipliers (v1 stays stable);
  the model chapter is explicit that this is a method comparison, and the
  Limitations say which one the reader should trust for what. Runtime target
  < 15 min on a laptop; posterior summaries cached to `data/processed/
  bayes_*.parquet` and snapshotted.

### D. Twenty-five-year series (new fetch, larger)

- FBref standard player tables for the Big-5 leagues, seasons 2000/01 –
  2025/26 (5 × 26 = 130 pages, cached; ~2 h of Chrome once). For each
  season and peer country: number of players on rosters, minutes share, and
  the same for goalkeepers.
- Exhibit: **Czechs in the Big-5, 2000/01 → 2025/26**, per-million line with
  peer countries, markers for the golden generation's seasons (Nedvěd,
  Poborský, Koller, Rosický, Čech — named from the data, not typed). A
  descriptive trend with uncertainty (local level model or LOESS with a
  bootstrap band) — labelled as smoothing, not forecast.
- The series is also the place where the panel sees time-series handling.

### E. Web delivery

- **Interactive sensitivity**: a slider per league multiplier (±30 %) that
  recomputes the Czech quality ranking in the browser from the shrunk rates
  embedded in the page (no server); shows top-10 churn live. Exact port of
  the offline sensitivity analysis.
- Exec summary as the hero's first fold on phones; everything else as v1.

## 2b. Spikes before planning D and C

- **D — coverage spike (first):** fetch one 2000/01 page per Big-5 league and
  confirm FBref lists minutes and nationality for every player that far
  back. If a league starts later, the series starts where all five are
  covered and says so; if minutes are missing, the exhibit counts roster
  players only. The golden-generation markers are then whichever Czech
  players hold the most Big-5 minutes in each season — if the data names
  Nedvěd, Poborský, Koller, Rosický and Čech, the copy may say so with a
  footnote; if not, the copy names whoever the data names.
- **C — runtime spike:** fit the model on 2024/25 only (≈ 5 000
  player-seasons) and time it; if NUTS takes > 15 min, drop the player
  random effect to a two-level model (league, position) and say so.

## 3. Out of scope (still)

LLM briefs; event/tracking data (linked, not used); any selection
recommendation; a forecast.

## 4. Order of work and effort

1. A (content, ~1 day) → deploy.
2. B (GK, ~half a day incl. fetch) → deploy.
3. C (Bayesian model, ~1.5 days) → deploy.
4. D (25-year series, ~1 day incl. fetch) → deploy.
5. E (slider, ~half a day) → deploy.

Each step is a plan of its own with the same task/review discipline as v1;
the site is redeployed after each so the portfolio link is never broken.

## 5. Definition of done (v1.1)

- Exec summary + method note + data-quality log + "how it was built" live in
  both languages; five card rules; GK table and cards; Bayesian chapter with
  convergence diagnostics and the validation exhibit; 25-year series exhibit;
  sensitivity slider; tests green; snapshot updated; README updated;
  `football.datasimply.eu` serves it over HTTPS.
