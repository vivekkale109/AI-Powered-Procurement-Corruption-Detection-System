# Usage Guide

## 1) Start Services

## API

```bash
source .venv/bin/activate
python api/app.py
```

- Base URL: `http://localhost:5000`
- Health: `GET /api/v1/health`
- Ready: `GET /api/v1/ready`

## Dashboard

```bash
source .venv/bin/activate
streamlit run dashboard/app.py
```

- URL: `http://localhost:8501` 

## 2) Run Batch Pipeline

```bash
python src/main.py --input data/raw/sample_tenders.csv --output data/processed
```

Optional sample data generation:

```bash
python data/generate_sample_data.py
```

## 3) API Analysis Examples

## Synchronous analyze

```bash
curl -X POST http://localhost:5000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "data": [
      {
        "tender_id": "T1001",
        "department": "Transport",
        "estimated_cost": 100000,
        "participating_bidders": "Bidder A, Bidder B, Bidder C",
        "bid_amounts": "98000, 101500, 99500",
        "winning_bidder": "Bidder A",
        "winning_bid": 98000,
        "tender_date": "2024-03-01",
        "location": "North"
      }
    ],
    "options": {
      "generate_report": true,
      "pagination": {"page": 1, "page_size": 100}
    }
  }'
```

## Async mode for large datasets

```bash
# Submit
curl -X POST http://localhost:5000/api/v1/analyze/submit \
  -H "Content-Type: application/json" \
  -d @payload.json

# Poll status
curl http://localhost:5000/api/v1/analyze/jobs/<job_id>

# Fetch result
curl "http://localhost:5000/api/v1/analyze/jobs/<job_id>/result?page=1&page_size=100"
```

## 4) Report Download Flow (Secured)

Report routes require auth and/or signed URLs.

1. Call analyze with `generate_report=true`.
2. Read `reports.list_url` from response.
3. Request list with API key:

```bash
curl http://localhost:5000/api/v1/reports/<run_id> \
  -H "X-API-Key: dev-report-api-key"
```

4. Use returned `signed_download_urls` or `signed_download_all_url`, or download with API key.

## 5) Metrics and Observability

```bash
curl http://localhost:5000/api/v1/metrics/summary
curl "http://localhost:5000/api/v1/metrics/runs?limit=200"
```

Summary includes:

- run success rate
- average processing time
- anomaly rate drift

## 6) CLI and Development Commands

```bash
# tests
python -m unittest discover -s tests -p 'test_*.py'

# drift regression
python -m benchmarks.regression \
  --dataset data/benchmarks/tender_regression_dataset.csv \
  --baseline benchmarks/risk_score_baseline.json

# local CI workflow
make ci
```

## 7) Docker Usage

```bash
docker compose up --build
```

Services:

- API: `http://localhost:5000`
- Dashboard: `http://localhost:8501`
- Postgres: `localhost:5432`

## 8) Baseline Refresh (Intentional Only)

After approved model/config changes:

```bash
python -m benchmarks.regression \
  --dataset data/benchmarks/tender_regression_dataset.csv \
  --baseline benchmarks/risk_score_baseline.json \
  --write-baseline
```
