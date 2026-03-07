#  Installation


## Prerequisites

- Python 3.11.x (recommended: 3.11.9)
- `pip`
- Optional: Docker + Docker Compose


## Local Setup

1. Go to project root:

```bash
cd /home/karl/project
```

2. Create and activate virtual environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

For development tools:

```bash
pip install -r requirements-dev.txt
```

## Run the System


### API

```bash
python api/app.py
```

- API base: `http://localhost:5000`
- Health: `GET /api/v1/health`
- Ready: `GET /api/v1/ready`


### Dashboard

In a new terminal (with same venv):

```bash
streamlit run dashboard/app.py
```

- Dashboard: `http://localhost:8501`


### Batch Pipeline

```bash
python src/main.py --input data/raw/sample_tenders.csv --output data/processed
```

Generate sample data if needed:

```bash
python data/generate_sample_data.py
```

## Docker Deployment

Build and run all services:

```bash
docker compose up --build
```

Services:

- API: `http://localhost:5000`
- Dashboard: `http://localhost:8501`
- Postgres: `localhost:5432`

Health checks are configured for:

- API readiness endpoint
- Dashboard health endpoint
- Postgres `pg_isready`

## Security Configuration

Configure in `config/config.yaml`:

- `security.report_auth_required`
- `security.report_api_keys`
- `security.download_signing_secret`
- `security.signed_url_ttl_seconds`

Report endpoints require API key and/or valid signed download URL.

## Governance Configuration

In `config/config.yaml`:

- `retention.*` for report/job cleanup
- `pii_scrubbing.*` for inbound record redaction

## Validation and Tests

Run tests:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Run benchmark drift guardrail:

```bash
python -m benchmarks.regression \
  --dataset data/benchmarks/tender_regression_dataset.csv \
  --baseline benchmarks/risk_score_baseline.json
```

## Reproducible Local CI

Using Makefile:

```bash
make setup
make lint
make test
make benchmark-regression
make ci
```

## Troubleshooting

### Missing dependency errors

Reinstall dependencies in active venv:

```bash
pip install -r requirements.txt
```

### API starts but report downloads fail with 401

- ensure valid `X-API-Key` or `Authorization: Bearer <key>`
- or use signed URLs from `GET /api/v1/reports/<run_id>`

### Drift regression failure

If model/config change is intentional, refresh baseline:

```bash
python -m benchmarks.regression \
  --dataset data/benchmarks/tender_regression_dataset.csv \
  --baseline benchmarks/risk_score_baseline.json \
  --write-baseline
```
