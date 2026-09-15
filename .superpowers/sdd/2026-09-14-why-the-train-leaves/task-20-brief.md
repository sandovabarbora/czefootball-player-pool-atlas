# Task 20: M3 (youth minutes across countries) + M5 (what the gap is made of)

**Spec** §2 M3, M5. Both descriptive; both with intervals; both honest about n.

## M3 — `src/youth_panel.py` → `youth_panel.json` + `youth_panel.svg`
- Panel: for every peer country + home nation, for each of the three fetched seasons
  (previous, metrics, current — the current season is partial: **use previous and
  metrics only**, say so), the U21 share of its top flight's minutes (reuse
  `pathways.youth_exposure` logic per season) and the country's top-9 players per million
  in the *following* season's… no — keep it contemporaneous and simple: `x` = U21 share of
  domestic minutes in season s, `y` = top-9 players per million in season s (per_capita
  rule). n = countries × 2 seasons (cze: 9 × 2 = 18; eng: 8 × 2 = 16).
- Model: Bayesian simple regression `y ~ Normal(α + β·x, σ)` with a country random
  intercept (partial pooling; two seasons per country make the intercept weakly
  identified — say so), PyMC, 4 chains × 1 000. Report β (per 10 percentage points of
  U21 share) with 90 % HDI, R², and the sentence "n = {n}; the interval is wide because the
  panel is small". Compare with a plain OLS slope (statsmodels not installed → numpy
  polyfit + bootstrap 1 000 for a CI) so the reader sees the two agree.
- Figure: scatter (country codes as labels, two seasons connected per country), the
  fitted line with its band, home nation highlighted.

## M5 — `src/gap_decomposition.py` → `gap_decomposition.json` + `gap_decomposition.svg`
- Question: of the difference in top-9 players per million between the home nation and
  each `compare` country (cze: NOR, DEN; eng: FRA, ESP), how much goes with each measured
  channel? Method: **Shapley-style attribution over a linear model** fitted on the peer
  panel (all peers, metrics season, n ≈ 9–10 rows — say so): `y` = per million; channels
  `x1` = U21 share of domestic minutes, `x2` = domestic league strength (M2 `m_L` of the
  country's top flight, or UEFA multiplier where the top flight is not in M2's set —
  state which), `x3` = median export age (recent, from `export_route`; where a country has
  no exports abroad, use its overall median); fit `y = a + Σ b_i x_i` (ridge with a small
  penalty because n is tiny), then for the pair (home, contrast) decompose
  `ŷ_contrast − ŷ_home = Σ b_i (x_i,contrast − x_i,home)` (a Blinder–Oaxaca-style
  linear split — cite Oaxaca (1973), Blinder (1973); verify DOIs) and report the residual
  `(y − ŷ)` difference separately. Shapley over three linear channels equals the linear
  split, so say "Shapley-equivalent for a linear model" rather than implementing the
  permutation. Bootstrap the panel (1 000) for intervals on each channel's share.
- Output per contrast: `{contrast, gap_total, channels: [{name, contribution, share, lo,
  hi}], residual, n}`; figure: one horizontal stacked bar per contrast (channels +
  residual), intervals as whiskers.
- Copy must say: a decomposition of a *correlation*, not a causal accounting; with n ≈ 9
  the shares are indicative; the residual is what the three channels do not carry.

## Report
- Slide 3 ("Do young players get minutes at home?") answer gains the panel slope: "…;
  across the {n_countries} countries and two seasons, 10 points more U21 share go with
  {beta} more top-{topn} players per million ({lo}–{hi})." Proof stays exhibit A; the
  panel figure goes into a `details.fold` under the proof ("Across countries").
- New **slide 8c** after the goalkeepers: "What is the gap made of?" (CS "Z čeho se rozdíl
  skládá?"), answer: "Of the {gap} players per million between {contrast} and {nation},
  U21 minutes go with {c1}, league strength with {c2}, export age with {c3}; {resid}
  is not carried by the three channels." Proof: the stacked bar (two contrasts). How-line:
  method + n + "a decomposition of a correlation, not a causal accounting" + cite.
- Chapter IV: `#youth-panel` and `#gap-decomposition` sections (design, figure, table,
  diagnostics/bootstrap line, cites); Validation & robustness list gains both.
- All EN + CS; numbers via placeholders. Makefile targets `panel`, `gap`; `all` updated;
  `render.load_data` tolerates missing JSONs.

## Tests
`tests/test_youth_panel.py`: panel assembly on a toy (two seasons, three countries); OLS
slope on known data; PyMC smoke fit (short). `tests/test_gap_decomposition.py`: linear
split sums to `ŷ_contrast − ŷ_home` exactly; bootstrap returns intervals containing the
point estimate; JSON shape.

## Verify
`uv run pytest -q -p no:warnings`; run both modules for cze and eng; render + build both;
screenshots of slide 3 fold and slide 8c (one tab, close it). Commit plain message, no AI
trailer; add src/config/templates/tests + rebuilt docs + snapshots; never data/processed,
outputs. Write incrementally; never spawn helper agents.
