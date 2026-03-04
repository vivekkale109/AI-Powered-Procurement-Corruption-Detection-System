# Project Summary

## What This Project Does

This system analyzes procurement tender data to identify corruption risk indicators using:

- schema-validated data ingestion
- feature engineering
- anomaly detection
- contractor network analysis
- risk scoring and calibration
- explainable results and downloadable reports

## Current Status

Production-oriented prototype with:

- working batch pipeline
- working Flask API
- working Streamlit dashboard
- security/governance controls on report flows
- test coverage across modules and integration
- CI workflow and benchmark drift checks

## Key Implemented Capabilities

1. Data quality and schema contracts
- strict required-column/type/range validation
- row-level rejection reasons and validation summaries

2. Reliability and calibration
- contamination tuning support
- final risk probability calibration

3. Explainability
- per-tender factor contribution breakdown
- top 3 reasons in API/report outputs

4. Reports
- executive, detailed, network, compliance, and final report
- final report includes all tender scores and rank ordering
- downloadable CSV (`all_tender_scores.csv`)

5. API hardening
- request/response validation
- pagination
- rate limiting
- async job mode for large analysis workloads

6. Security and governance
- API key auth for report endpoints
- signed download URLs (HMAC + expiry)
- retention cleanup for old report runs/jobs
- configurable PII scrubbing

7. Observability
- structured run logs
- run IDs and step timings
- metrics endpoints for success rate/time/anomaly drift

8. Deployment maturity
- container health checks
- CI pipeline (lint/test/benchmark/build)
- benchmark dataset + regression baseline for drift prevention

## Main Runtime Interfaces

- API: `api/app.py`
- Dashboard: `dashboard/app.py`
- Batch CLI: `src/main.py`

## Important API Endpoints

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

## Repository Highlights

- `src/` core analytics
- `api/` API service
- `dashboard/` interactive UI
- `reports/` report rendering
- `tests/` unit + integration + drift tests
- `benchmarks/` regression harness
- `.github/workflows/ci.yml` CI pipeline

## Run Commands

```bash
# API
python api/app.py

# Dashboard
streamlit run dashboard/app.py

# Batch pipeline
python src/main.py --input data/raw/sample_tenders.csv --output data/processed

# Tests
python -m unittest discover -s tests -p 'test_*.py'

# Drift regression
python -m benchmarks.regression --dataset data/benchmarks/tender_regression_dataset.csv --baseline benchmarks/risk_score_baseline.json
```
