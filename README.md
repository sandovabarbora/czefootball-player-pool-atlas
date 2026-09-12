# Czech Football — Player Pool Atlas

A position-normalized 2D map of Czech-eligible professional football players from
the nine headline UEFA-ranked leagues (England, Italy, Spain, Germany, France,
Netherlands, Portugal, Belgium, Turkey), the Czech First League, and a handful of
stepping-stone / second-tier competitions, benchmarked against peer nations
(Slovakia, Austria, Hungary, Poland, Croatia, Denmark, Switzerland, Norway).

**This is a methodology showcase, not a selection recommendation.** The deliverable
is a replicable mapping method intended as a planning tool over the multi-year
international cycle. It is not a squad suggestion, and it does not commentate on
match results, tactics, or individual coaching choices.

---

## What the project produces

Two map projections, side by side:

1. **Style map** — position-normalized per-90 z-scores, no league quality
   multipliers. Players are grouped by performance fingerprint independent of
   league strength.
2. **Quality-adjusted map** — same features, with league quality multipliers
   applied to production rates, making players from different leagues directly
   comparable on a single quality axis. The multipliers are subjective;
   sensitivity analysis (±20% perturbation) is included.

Plus:

- **Trajectory arrows** — season-over-season delta, shown only for players with
  sufficient minutes in both seasons.
- **Cluster archetypes** — KMeans with K selected by silhouette score, post-hoc
  labelled by inspection.
- **International benchmark** — a per-capita comparison of headline-league player
  pool depth against peer countries.
- **Limitations section** — explicit, mandatory, in the report.

## Architecture

```
FBref competitions → unified player records → per-90 features
   → standardize within position group → PCA + UMAP + KMeans
   → Jinja2 → HTML report
```

See `src/` for the module layout and `config/` for the leagues, countries, seasons,
and feature definitions that drive the pipeline.

## Data sources

Player and match statistics are sourced from FBref via the `soccerdata` package.
League identifiers (`comp_id` + `slug`) are registered in `config/leagues.yaml`
and verified against the live FBref page before each fetch.

## Methodology — key choices

- **Position-specific features.** Forwards, midfielders, and defenders share one
  feature vector definition (see `config/feature_definitions.yaml`); goalkeepers
  are excluded from the main projection.
- **League quality multipliers are subjective.** A sensitivity pass shows how the
  map changes when multipliers shift by ±20%. The multipliers themselves live in
  `config/league_quality.yaml` with source citations.
- **K (cluster count) is data-driven.** Selected by silhouette score, per position
  group. Archetype labels are post-hoc, applied after inspection
  (`config/cluster_labels.yaml`).
- **Minutes floor.** Players below `min_minutes` (see
  `config/feature_definitions.yaml`) are excluded from the main projection to
  avoid small-sample noise.

## Running the pipeline

```bash
make install            # uv venv + deps
make all                # fetch -> pool -> features -> reduce -> render
```

Output at `outputs/index.html`.

## What this project is not

- It is not a selection recommendation.
- It is not a critique of coaching, tactics, or specific match results.
- It does not use any private scouting, video, or tracking data.

## License

MIT. See [LICENSE](LICENSE).

## Contact

Barbora Šandová · barbora@datasimply.eu · [linkedin.com/in/barborasandova](https://linkedin.com/in/barborasandova)
