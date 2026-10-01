# Big-5 count fix and the leave-one-nation-out refit: protocol (1 October 2026)

Written and committed before any new estimate was looked at.

## 1. The Big-5 count

**Fault.** `src.big5_series.build_series` documents its count as players with at least 450 minutes summed across the
five leagues. The code applied the floor to each club stint instead. As a result, a player who moved between two
Big-5 clubs during a season, with fewer than 450 minutes at each, was left out. One example is England 2025/26:
Ethan Nwaneri played 171 minutes for Arsenal and 324 for Marseille. The Nations page sums the minutes, so it gave
128 where the edition gave 127.

**Fix.** Sum each player's minutes in a season across the five leagues, then apply the floor, as the docstring says.
This is the Nations page's definition. After the fix, the two pages must give the same count for every country and
season, and a test checks this.

**Consequence.** Each edition's series model is refitted on the corrected series, with the sampler, stages and
convergence rule of `design/edition-refit-protocol.md`. Changes against the published pages are logged in
`config/journal.yaml` as old → new.

## 2. The leave-one-nation-out fit (`export_age_model.run_lono`)

**Why.** It ran at 2 chains, 500 tuning steps and 500 draws. In every edition its minimum bulk ESS is 177–324,
below 400. Denmark's max R-hat is 1.023.

**Sampler.** The same settings as the model's main fit: 4 chains, 1000 tuning steps, 1000 draws, target_accept 0.9.
A fit that fails the rule is refitted once at target_accept 0.99. Nothing else changes.

**Rule.** The convergence rule of `design/edition-refit-protocol.md`, applied to the parameters that
`diagnostics_summary` already reports: max R-hat ≤ 1.01, bulk and tail ESS ≥ 400, no divergent transitions.

**Reporting.**

- The page reports the shift in the age-21-vs-24 difference as it does now.
- If the fit still fails, the page says that the check does not meet the rule, and draws nothing from it.
- The main fit and the fit without origin strength are rerun unchanged. They use the same seeds and settings, so any
  difference in them is reported.
