# Architecture

## System Overview


The project is a modular procurement-risk analysis system with three runtime surfaces:

1. Batch pipeline (`src/main.py`)
2. REST API (`api/app.py`)
3. Dashboard (`dashboard/app.py`)

Core analysis flow:

`Data Ingestion -> Feature Engineering -> Anomaly Detection -> Network Analysis -> Risk Scoring -> Reports`

## Runtime Components


### 1) Core Analysis Engine (`src/`)

- `data_ingestion.py`
  - Strict schema checks, row-level rejection reasons, validation report.
- `feature_engineering.py`
  - Bid, contractor, temporal, and participation features.
- `anomaly_detection.py`
  - Ensemble of Isolation Forest, LOF, and statistical checks.
  - Contamination auto-tuning support.
- `network_analysis.py`
  - Contractor co-participation graph, centrality, communities, suspicious clusters.
- `risk_scoring.py`
  - Tender/contractor/department scoring.
  - Explainability fields: factor contributions and top 3 reasons.
  - Score calibration to `risk_probability`.
- `main.py`
  - Batch orchestration and artifact generation.

### 2) API Layer (`api/app.py`)

Flask API provides:

- Analysis endpoints
  - `POST /api/v1/analyze` (sync + pagination)
  - `POST /api/v1/analyze/submit` (async job submit)
  - `GET /api/v1/analyze/jobs/<job_id>`
  - `GET /api/v1/analyze/jobs/<job_id>/result`
- Report endpoints
  - `GET /api/v1/reports/<run_id>`
  - `GET /api/v1/reports/<run_id>/download/<report_name>`
  - `GET /api/v1/reports/<run_id>/download/all`
- Ops endpoints
  - `GET /api/v1/health`
  - `GET /api/v1/ready`
  - `GET /api/v1/metrics/summary`
  - `GET /api/v1/metrics/runs`

### 3) Security and Governance Controls

Implemented in API:

- Report endpoint authentication with API key.
- Signed download URLs (HMAC + expiry) for report files.
- Data retention cleanup for old report runs/jobs.
- PII scrubbing on inbound records before analysis.
- Structured run logging with run IDs and step timings.

### 4) Reporting (`reports/report_generator.py`)

Generated outputs include:

- Executive summary
- Detailed analysis
- Network analysis report
- CVC compliance report
- Final combined report
- CSV with all tender scores

Trend sections in final report:

- Department risk over time
- Contractor behavior drift

### 5) Dashboard (`dashboard/app.py`)

Streamlit interface for:

- Data upload and analysis execution
- Risk and network visualizations
- Metrics/observability views
- Report listing and download

### 6) Deployment and CI

- Containerized with `Dockerfile` and `docker-compose.yml`.
- Health checks configured for API/dashboard/db.
- CI workflow at `.github/workflows/ci.yml`:
  - lint
  - tests
  - benchmark drift regression
  - docker build

### 7) Benchmark Regression Guardrail

- Dataset: `data/benchmarks/tender_regression_dataset.csv`
- Baseline: `benchmarks/risk_score_baseline.json`
- Checker: `benchmarks/regression.py`
- Enforced in unit test and CI to prevent unintended score drift.

## Configuration-Driven Behavior

Primary runtime configuration comes from `config/config.yaml`:

- model/config version metadata
- anomaly and scoring controls
- security settings (API keys, signed URL TTL)
- retention policy
- PII scrub patterns

## Data Artifacts

Common output paths:

- Processed data: `data/processed/processed_data.csv`
- Risk scores: `data/processed/risk_scores.json`
- Network summary: `data/processed/network_analysis.json`
- Generated reports: `data/processed/reports/<run_id>/`
