# Cross-edition break models: refit protocol (30 September 2026)

Written and committed before any new estimate was looked at.

**Why a refit.** The cross-edition two-break fits on the nations page ran with the module defaults: 2 chains, 500
tuning steps and 500 draws. Some countries showed R-hat above 1.01 and divergent transitions.

**Model.** Unchanged for every country:

- `series_model.fit_change_point(y, n_breaks=2)`;
- a local level with non-centred innovations and two marginalised steps;
- the same priors;
- seed `config.RANDOM_SEED`.

**Sampler, stage 1 (all countries).** 4 chains, 2000 tuning steps, 2000 draws, target_accept 0.95.

**Sampler, stage 2.** Countries that fail the convergence rule in stage 1, and only they, are refitted once with
target_accept 0.99. All other settings stay the same. No other change is made to reach convergence.

**Convergence rule.** On `mu0`, `sigma`, `delta` and `z_eps`, all of the following must hold:

- max R-hat ≤ 1.01;
- min bulk ESS ≥ 400;
- min tail ESS ≥ 400;
- zero divergent transitions.

**Reporting.**

- The nations page shows every country's diagnostics: max R-hat, min bulk ESS, min tail ESS, divergences, the stage
  used, and pass or fail.
- A country that still fails after stage 2 has no dated steps on the page, and the page says so.
- Every dated step that changes against the published fit is logged in `config/journal.yaml` as old → new.
- Each edition's own series-model fit is a separate model and is not part of this refit.
