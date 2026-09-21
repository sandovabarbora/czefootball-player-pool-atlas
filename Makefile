.PHONY: help install fetch fetch-big5 fetch-history pool photos features reduce benchmark series analogs sensitivity strength compare pathways eda data-quality render all clean test test-all-nations lint check snapshot restore-snapshot share-tables pages keepers goalkeepers facts

# NATION selects the home nation for every target below (default: cze) --
# it is read straight from the environment by src/config.py, so
# `NATION=eng make features` (or `export NATION=eng` first) is enough to
# point every target at config/nations/eng.yaml and the eng/ data dirs; no
# target here hardcodes a nation. `NATION ?=` only fixes the value this
# Makefile itself falls back to and reports in `snapshot`/`restore-snapshot`/
# `share-tables`'s paths below.
NATION ?= cze
export NATION

PYTHON ?= python
VENV   ?= .venv
ACT    := source $(VENV)/bin/activate &&

help:
	@echo "Targets (NATION=<code> selects the home nation, default cze):"
	@echo "  install          Create .venv, install deps with uv (or pip fallback)"
	@echo "  fetch            Run the data fetchers (leagues setup, FBref, Elo, squads)"
	@echo "  fetch-big5       Fetch the 26-season Big-5 player-standard history"
	@echo "  pool             Build the home-nation-eligible player pool"
	@echo "  photos           Fetch Wikimedia portraits for the pool (needs pool.parquet)"
	@echo "  features         Build position-specific feature vectors + season trajectories"
	@echo "  reduce           Run PCA + UMAP + KMeans"
	@echo "  benchmark        Per-capita benchmark, cohort table and heatmap"
	@echo "  series           26-season Big-5 series (home nation vs peers) exhibit"
	@echo "  analogs          Showcase players and historical analogs"
	@echo "  sensitivity      League-multiplier sensitivity table"
	@echo "  strength         Hierarchical Bayesian league-strength model from league movers"
	@echo "  compare          Three-model rolling-origin comparison (M1 core: monitor performance over time)"
	@echo "  pathways         Exhibits A-E (youth exposure, export routes, destinations)"
	@echo "  keepers          Fetch keeper-stat tables (fbref_keepers.parquet)"
	@echo "  goalkeepers      Goalkeepers chapter: per-million, export age, club tier, production, cards"
	@echo "  panel            Cross-country youth-minutes panel (M3): Bayesian slope + OLS comparison"
	@echo "  gap              Gap decomposition (M5): Blinder-Oaxaca-style linear split of the per-capita gap"
	@echo "  facts            Pipeline facts for the why-funnel: club breadth of youth minutes, league age structure, age at first move abroad"
	@echo "  eda              One raw row to a feature vector: cleaning ledger link, rejected candidates, two EDA figures"
	@echo "  data-quality     Recompute the data-quality log checks"
	@echo "  render           Render the HTML report (en + cs)"
	@echo "  all              fetch -> pool -> photos -> features -> reduce -> benchmark -> series -> analogs -> sensitivity -> strength -> compare -> pathways -> keepers -> goalkeepers -> panel -> gap -> eda -> data-quality -> render"
	@echo "  pages            render, then build the site (docs/ for cze, docs/\$$(NATION) otherwise) with site/build.sh"
	@echo "  test             Run pytest"
	@echo "  test-all-nations Run pytest under NATION=cze and NATION=eng (CI-style nation-agnostic guard)"
	@echo "  lint             Run ruff check"
	@echo "  check            lint + test"
	@echo "  snapshot         Copy data/processed/\$$(NATION)/ parquet+json into data/snapshot/\$$(NATION)/"
	@echo "  restore-snapshot Copy data/snapshot/\$$(NATION)/ into data/processed/\$$(NATION)/ (never overwrites newer files)"
	@echo "  share-tables     Copy fbref_players.parquet + big5_history.parquet + fbref_keepers.parquet from data/processed/cze/ when absent for NATION (nation-independent raw tables; no refetch)"
	@echo "  clean            Remove processed data and outputs for \$$(NATION) (keeps raw)"

install:
	@if command -v uv >/dev/null 2>&1; then \
		uv venv $(VENV) && uv pip install -e ".[dev]"; \
	else \
		$(PYTHON) -m venv $(VENV) && $(ACT) pip install -e ".[dev]"; \
	fi

fetch:
	$(ACT) python -m src.leagues_setup
	$(ACT) python -m src.fetch_fbref
	$(ACT) python -m src.fetch_elo
	$(ACT) python -m src.fetch_squads

roles:
	$(ACT) python -m src.fetch_roles

fetch-big5:
	$(ACT) python -m src.fetch_big5_history

pool:
	$(ACT) python -m src.pool

photos:
	$(ACT) python -m src.fetch_photos

features:
	$(ACT) python -m src.features
	$(ACT) python -m src.trajectory

reduce:
	$(ACT) python -m src.reduce
	$(ACT) python -m src.cluster

benchmark:
	$(ACT) python -m src.international_benchmark
	$(ACT) python -m src.squad_lens

series:
	$(ACT) python -m src.big5_series

analogs:
	$(ACT) python -m src.historical_analogs

sensitivity:
	$(ACT) python -m src.sensitivity

strength:
	$(ACT) python -m src.league_strength

compare:
	$(ACT) python -m src.model_comparison

pathways:
	$(ACT) python -m src.pathways

keepers:
	$(ACT) python -m src.fetch_keepers

goalkeepers:
	$(ACT) python -m src.goalkeepers

# Cross-country youth-minutes panel (M3): needs fbref_players.parquet only
# (recomputes per_capita/youth_exposure itself, season by season).
panel:
	$(ACT) python -m src.youth_panel

# Gap decomposition (M5): needs per_capita.parquet (benchmark), pathways.json
# (pathways) and league_strength.json (strength) already built.
gap:
	$(ACT) python -m src.gap_decomposition

# Pipeline facts for the why-funnel (Task 26B): needs fbref_players.parquet
# only.
facts:
	$(ACT) python -m src.pipeline_facts

pool-table:
	$(ACT) python -m src.pool_table

changes:
	$(ACT) python -m src.season_changes

charts:
	$(ACT) python -m src.charts_export
	$(ACT) python -m src.tracking_showcase
	$(ACT) python -m src.careers_export

# the history seasons of the non-headline leagues, for the player atlas's
# career view (slow: one FBref request per league-season, rate-limited)
fetch-history:
	$(ACT) python -m src.fetch_history

eda:
	$(ACT) python -m src.feature_eda

data-quality:
	$(ACT) python -m src.data_quality

render: data-quality
	$(ACT) python -m src.render

all: fetch roles pool photos features reduce benchmark series analogs sensitivity strength compare pathways keepers goalkeepers panel gap facts pool-table changes charts eda data-quality render

test:
	$(ACT) pytest

# CI-style guard: the test suite must be nation-agnostic, not just correct
# under the default NATION=cze. Runs it twice, once per configured nation.
test-all-nations:
	$(ACT) pytest -q -p no:warnings
	NATION=eng $(ACT) pytest -q -p no:warnings

lint:
	$(ACT) ruff check src tests

check: lint test

snapshot:
	mkdir -p data/snapshot/$(NATION) && cp data/processed/$(NATION)/*.parquet data/processed/$(NATION)/*.json data/snapshot/$(NATION)/

# Copies every snapshot file that is missing from data/processed/$(NATION)/ or
# older than the snapshot copy; a processed file newer than its snapshot is kept.
restore-snapshot:
	@mkdir -p data/processed/$(NATION)
	@for f in data/snapshot/$(NATION)/*; do \
		dest="data/processed/$(NATION)/$$(basename "$$f")"; \
		if [ ! -e "$$dest" ] || [ "$$f" -nt "$$dest" ]; then \
			cp "$$f" "$$dest" && echo "restored $$dest"; \
		fi; \
	done

# The two raw FBref tables are nation-independent (every fetched player,
# every nation); a run for a nation other than cze can reuse cze's copy
# instead of refetching, when its own hasn't been fetched yet.
share-tables:
	@mkdir -p data/processed/$(NATION)
	@for f in fbref_players.parquet big5_history.parquet fbref_keepers.parquet; do \
		src="data/processed/cze/$$f"; dest="data/processed/$(NATION)/$$f"; \
		if [ -e "$$dest" ]; then echo "$$dest already present, skipped"; \
		elif [ -e "$$src" ]; then cp "$$src" "$$dest" && echo "copied $$dest from $$src"; \
		else echo "$$src not found; fetch it first" >&2; exit 1; \
		fi; \
	done

clean:
	rm -rf data/processed/$(NATION)/* outputs/$(NATION)/*.html outputs/$(NATION)/*.pdf outputs/$(NATION)/*.svg outputs/$(NATION)/*.png
	@echo "Cleaned processed/$(NATION) and outputs/$(NATION) (raw/ preserved)"

pages: render
	@if [ "$(NATION)" = "cze" ]; then ./site/build.sh; else ./site/build.sh docs/$(NATION); fi
