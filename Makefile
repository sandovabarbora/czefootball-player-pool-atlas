.PHONY: help install fetch pool features reduce render all clean test lint check snapshot pages

PYTHON ?= python
VENV   ?= .venv
ACT    := source $(VENV)/bin/activate &&

help:
	@echo "Targets:"
	@echo "  install          Create .venv, install deps with uv (or pip fallback)"
	@echo "  fetch            Run all fetchers (leagues setup, FBref, Elo, squads, photos)"
	@echo "  pool             Build the Czech-eligible player pool"
	@echo "  features         Build position-specific feature vectors"
	@echo "  reduce           Run PCA + UMAP + KMeans"
	@echo "  render           Render HTML report"
	@echo "  all              fetch -> pool -> features -> reduce -> render"
	@echo "  test             Run pytest"
	@echo "  lint             Run ruff check"
	@echo "  check            lint + test"
	@echo "  snapshot         Copy processed parquet files into data/snapshot/"
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
	$(ACT) python -m src.fetch_photos

pool:
	$(ACT) python -m src.pool

features:
	$(ACT) python -m src.features
	$(ACT) python -m src.trajectory

reduce:
	$(ACT) python -m src.reduce
	$(ACT) python -m src.cluster

render:
	$(ACT) python -m src.render

all: fetch pool features reduce render

test:
	$(ACT) pytest

lint:
	$(ACT) ruff check src tests

check: lint test

snapshot:
	mkdir -p data/snapshot && cp data/processed/*.parquet data/processed/*.json data/snapshot/

clean:
	rm -rf data/processed/* outputs/*.html outputs/*.pdf outputs/*.svg outputs/*.png
	@echo "Cleaned processed/ and outputs/ (raw/ preserved)"

pages: render
	./site/build.sh
