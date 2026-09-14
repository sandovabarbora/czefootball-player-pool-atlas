.PHONY: help install fetch pool photos features reduce benchmark analogs sensitivity pathways data-quality render all clean test lint check snapshot restore-snapshot pages

PYTHON ?= python
VENV   ?= .venv
ACT    := source $(VENV)/bin/activate &&

help:
	@echo "Targets:"
	@echo "  install          Create .venv, install deps with uv (or pip fallback)"
	@echo "  fetch            Run the data fetchers (leagues setup, FBref, Elo, squads)"
	@echo "  pool             Build the Czech-eligible player pool"
	@echo "  photos           Fetch Wikimedia portraits for the pool (needs pool.parquet)"
	@echo "  features         Build position-specific feature vectors + season trajectories"
	@echo "  reduce           Run PCA + UMAP + KMeans"
	@echo "  benchmark        Per-capita benchmark, cohort table and heatmap"
	@echo "  analogs          Showcase players and historical analogs"
	@echo "  sensitivity      League-multiplier sensitivity table"
	@echo "  pathways         Exhibits A-E (youth exposure, export routes, destinations)"
	@echo "  data-quality     Recompute the data-quality log checks"
	@echo "  render           Render the HTML report (en + cs)"
	@echo "  all              fetch -> pool -> photos -> features -> reduce -> benchmark -> analogs -> sensitivity -> pathways -> data-quality -> render"
	@echo "  pages            render, then build docs/ with site/build.sh"
	@echo "  test             Run pytest"
	@echo "  lint             Run ruff check"
	@echo "  check            lint + test"
	@echo "  snapshot         Copy processed parquet/json files into data/snapshot/"
	@echo "  restore-snapshot Copy data/snapshot/ into data/processed/ (never overwrites newer files)"
	@echo "  clean            Remove processed data and outputs (keeps raw)"

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

analogs:
	$(ACT) python -m src.historical_analogs

sensitivity:
	$(ACT) python -m src.sensitivity

pathways:
	$(ACT) python -m src.pathways

data-quality:
	$(ACT) python -m src.data_quality

render: data-quality
	$(ACT) python -m src.render

all: fetch pool photos features reduce benchmark analogs sensitivity pathways data-quality render

test:
	$(ACT) pytest

lint:
	$(ACT) ruff check src tests

check: lint test

snapshot:
	mkdir -p data/snapshot && cp data/processed/*.parquet data/processed/*.json data/snapshot/

# Copies every snapshot file that is missing from data/processed/ or older
# than the snapshot copy; a processed file newer than its snapshot is kept.
restore-snapshot:
	@mkdir -p data/processed
	@for f in data/snapshot/*; do \
		dest="data/processed/$$(basename "$$f")"; \
		if [ ! -e "$$dest" ] || [ "$$f" -nt "$$dest" ]; then \
			cp "$$f" "$$dest" && echo "restored $$dest"; \
		fi; \
	done

clean:
	rm -rf data/processed/* outputs/*.html outputs/*.pdf outputs/*.svg outputs/*.png
	@echo "Cleaned processed/ and outputs/ (raw/ preserved)"

pages: render
	./site/build.sh
