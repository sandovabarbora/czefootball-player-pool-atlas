# Each edition's own series model: refit protocol (1 October 2026)

Written and committed before any new estimate was looked at. It extends `design/nations-refit-protocol.md`
(30 September 2026) to the model each edition's Big-5 page and findings rest on.

**Why a refit.** `src.series_model` ran with its module defaults: 2 chains, 500 tuning steps and 500 draws. At
those settings no edition's home fit meets the rule below. The minimum bulk ESS is 114–372. CZE has 2 divergent
transitions, DEN 3 and GER 16. The contrast fits and the local-level fits recorded no diagnostics at all.

**Models.** Unchanged:

- the home nation's two-break fit and each `series_contrast` peer's two-break fit
  (`fit_change_point(y, n_breaks=2)`);
- the local-level fits behind the live forecast and the rolling-origin backtest (`fit_local_level`);
- the same priors, seeds and backtest origins.

**Sampler, stage 1 (every fit).** 4 chains, 2000 tuning steps, 2000 draws, target_accept 0.95.

**Sampler, stage 2.** A fit that fails the convergence rule in stage 1, and only that fit, is refitted once with
target_accept 0.99. All other settings stay the same. No other change is made to reach convergence.

**Convergence rule.** Checked on `mu0`, `sigma` and `z_eps`, and also on `delta` for the change-point fits. All of
the following must hold:

- max R-hat ≤ 1.01;
- min bulk ESS ≥ 400;
- min tail ESS ≥ 400;
- zero divergent transitions.

**Reporting.**

- `series_model.json` carries the diagnostics of every fit: the stage used, and pass or fail.
- The Big-5 page's diagnostics sentence reports the home fit by this rule.
- If the home fit still fails after stage 2, the edition's Big-5 page dates no step, and the page and findings say so.
- A contrast peer whose fit fails is shown without dated steps.
- A live forecast whose fit fails is not shown.
- A backtest origin whose fit fails stays in the backtest, because the backtest scores the method as run. The
  page gives the number of origins that failed.
- The registered forecasts in `config/predictions.yaml` are not touched. If the live forecast moves, the page shows
  it beside the registered number, as `src.predictions` already does.
- Every dated step, interval or forecast that changes against the published pages is logged in
  `config/journal.yaml` as old → new.
- The other models (league strength, youth panel) are not part of this refit.
