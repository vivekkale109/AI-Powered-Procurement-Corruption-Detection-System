PYTHON ?= python3.11
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

.PHONY: setup lint test benchmark-regression ci

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

lint:
	$(PY) -m ruff check api src reports dashboard tests benchmarks --select E9,F63,F7,F82

test:
	$(PY) -m unittest discover -s tests -p 'test_*.py'

benchmark-regression:
	$(PY) -m benchmarks.regression --dataset data/benchmarks/tender_regression_dataset.csv --baseline benchmarks/risk_score_baseline.json

ci: lint test benchmark-regression
