.PHONY: help install fetch fetch-big5 pool photos features reduce benchmark series analogs sensitivity strength pathways data-quality render all clean test lint check snapshot restore-snapshot share-tables pages

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
	@echo "  pathways         Exhibits A-E (youth exposure, export routes, destinations)"
	@echo "  data-quality     Recompute the data-quality log checks"
	@echo "  render           Render the HTML report (en + cs)"
	@echo "  all              fetch -> pool -> photos -> features -> reduce -> benchmark -> series -> analogs -> sensitivity -> strength -> pathways -> data-quality -> render"
	@echo "  pages            render, then build the site (docs/ for cze, docs/\$$(NATION) otherwise) with site/build.sh"
	@echo "  test             Run pytest"
	@echo "  lint             Run ruff check"
	@echo "  check            lint + test"
	@echo "  snapshot         Copy data/processed/\$$(NATION)/ parquet+json into data/snapshot/\$$(NATION)/"
	@echo "  restore-snapshot Copy data/snapshot/\$$(NATION)/ into data/processed/\$$(NATION)/ (never overwrites newer files)"
	@echo "  share-tables     Copy fbref_players.parquet + big5_history.parquet from data/processed/cze/ when absent for NATION (nation-independent raw tables; no refetch)"
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

pathways:
	$(ACT) python -m src.pathways

data-quality:
	$(ACT) python -m src.data_quality

render: data-quality
	$(ACT) python -m src.render

all: fetch pool photos features reduce benchmark series analogs sensitivity strength pathways data-quality render

test:
	$(ACT) pytest

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
	@for f in fbref_players.parquet big5_history.parquet; do \
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
