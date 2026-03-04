# Procurement Corruption Detection System

AI-assisted analysis platform for detecting procurement risk patterns across tenders, contractors, and departments.

## Features

- Strict schema validation with row-level rejection reasons.
- Feature engineering for bid, contractor, temporal, and participation signals.
- Multi-model anomaly detection (Isolation Forest, LOF, statistical checks).
- Contractor network analysis (communities, centrality, suspicious clusters).
- Explainable risk scoring and calibrated risk probability.
- Final report with all tender scores ranked best-to-worst.
- Downloadable report artifacts (HTML + CSV + ZIP).
- Dashboard for interactive analysis and observability metrics.

## Security and Governance

Implemented in API:

- report endpoint authentication via API key
- signed download URLs (HMAC + expiry)
- retention cleanup for old report runs/jobs
- configurable PII scrubbing before analysis
- run IDs, step timings, and structured logs

## API Endpoints

- `GET /api/v1/health`
- `GET /api/v1/ready`
- `POST /api/v1/analyze`
- `POST /api/v1/analyze/submit`
- `GET /api/v1/analyze/jobs/<job_id>`
- `GET /api/v1/analyze/jobs/<job_id>/result`
- `GET /api/v1/reports/<run_id>`
- `GET /api/v1/reports/<run_id>/download/<report_name>`
- `GET /api/v1/reports/<run_id>/download/all`
- `GET /api/v1/metrics/summary`
- `GET /api/v1/metrics/runs`

## Quick Start

```bash
cd /home/karl/project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run API
python api/app.py

# Run dashboard (new terminal)
streamlit run dashboard/app.py
```

## Batch Pipeline

```bash
# Generate sample data (optional)
python data/generate_sample_data.py

# Run end-to-end analysis
python src/main.py --input data/raw/sample_tenders.csv --output data/processed
```

## Tests and Quality

```bash
# Unit + integration tests
python -m unittest discover -s tests -p 'test_*.py'

# Score drift regression guardrail
python -m benchmarks.regression \
  --dataset data/benchmarks/tender_regression_dataset.csv \
  --baseline benchmarks/risk_score_baseline.json
```

## Deployment Maturity

- Docker image: `Dockerfile`
- Multi-service deploy: `docker-compose.yml`
- Container health checks:
  - API `GET /api/v1/ready`
  - Dashboard `/_stcore/health`
  - Postgres `pg_isready`
- CI pipeline: `.github/workflows/ci.yml`
  - lint
  - tests
  - benchmark drift regression
  - docker build

Run with Docker:

```bash
docker compose up --build
```

## Reproducible Environments

- Python pin: `.python-version`
- Runtime deps: `requirements.txt`
- Dev deps: `requirements-dev.txt`
- Repeatable local CI commands: `Makefile`

```bash
make setup
make ci
```

## Benchmark Regression Guardrail

- Dataset: `data/benchmarks/tender_regression_dataset.csv`
- Baseline: `benchmarks/risk_score_baseline.json`
- Checker: `benchmarks/regression.py`

To intentionally refresh baseline after approved scoring changes:

```bash
python -m benchmarks.regression \
  --dataset data/benchmarks/tender_regression_dataset.csv \
  --baseline benchmarks/risk_score_baseline.json \
  --write-baseline
```
