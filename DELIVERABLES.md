# Deliverables

## Current Deliverables (Implemented)


## 1) Core Analytics Modules

- `src/data_ingestion.py`
  - strict schema validation
  - row-level rejection reasons
  - validation report generation
- `src/feature_engineering.py`
  - engineered bid/contractor/temporal/participation features
- `src/anomaly_detection.py`
  - multi-model anomaly detection
  - contamination tuning support
- `src/network_analysis.py`
  - co-participation graph analytics
  - suspicious cluster and centrality outputs
- `src/risk_scoring.py`
  - tender/contractor/department risk scoring
  - explainability (`factor_contributions`, `top_3_reasons`)
  - calibration to risk probability
- `src/main.py`
  - batch orchestration and artifact persistence


## 2) API Deliverables

- `api/app.py`
  - request/response validation and pagination
  - rate limiting
  - async job mode (submit/status/result)
  - health and readiness endpoints
  - observability endpoints and run metrics
  - report listing/download endpoints
  - report endpoint auth and signed URLs
  - retention cleanup and PII scrubbing


## 3) Reporting Deliverables

- `reports/report_generator.py`
  - executive, detailed, network, compliance, and final report HTML
  - final report includes every tender score ranked best-to-worst
  - trend sections: department over time and contractor drift
  - downloadable `all_tender_scores.csv`


## 4) Dashboard Deliverables

- `dashboard/app.py`
  - end-to-end analysis UI
  - risk and network views
  - report download integration
  - system metrics view


## 5) Security and Governance Deliverables

- API key auth for report listing/download access
- HMAC signed download URLs with expiry
- retention policy and cleanup execution
- PII scrubbing with configurable regex patterns
- config/model version metadata included in API/report outputs


## 6) Test Deliverables

Test suite under `tests/` includes:

- unit tests:
  - `test_data_ingestion.py`
  - `test_feature_engineering.py`
  - `test_risk_scoring.py`
  - `test_report_generator.py`
- integration test:
  - `test_api_integration.py`
- benchmark drift regression test:
  - `test_benchmark_regression.py`


## 7) Deployment Maturity Deliverables

- `Dockerfile`
  - runtime image + health check
- `docker-compose.yml`
  - api/dashboard/db services with health probes
- `.github/workflows/ci.yml`
  - lint, tests, benchmark regression, docker build
- `.python-version`
  - pinned interpreter target
- `requirements.txt` + `requirements-dev.txt`
  - pinned dependency sets
- `Makefile`
  - reproducible local CI commands

## 8) Benchmark and Drift Guardrail Deliverables

- dataset: `data/benchmarks/tender_regression_dataset.csv`
- baseline: `benchmarks/risk_score_baseline.json`
- runner: `benchmarks/regression.py`

## 9) Documentation Deliverables

- `README.md` (overview + deployment maturity)
- `INSTALLATION.md` (setup and deployment)
- `USAGE.md` (CLI/API/dashboard examples)
- `ARCHITECTURE.md` (component architecture)
- `PROJECT_SUMMARY.md` (status + structure)
- `QUICK_START.py` (quick operational guide)
