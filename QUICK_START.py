#!/usr/bin/env python3
"""Quick start helper for the current project setup."""

from pathlib import Path
import os


def _exists(path: Path) -> str:
    return "OK" if path.exists() else "MISSING"


def main():
    project_root = Path(__file__).resolve().parent
    os.chdir(project_root)

    print("=" * 72)
    print("PROCUREMENT CORRUPTION DETECTION - QUICK START")
    print("=" * 72)
    print(f"Project root: {project_root}")
    print("")

    print("1) Environment")
    print("-" * 72)
    print("Recommended Python version: 3.11.9 (see .python-version)")
    print("Setup commands:")
    print("  python3.11 -m venv .venv")
    print("  source .venv/bin/activate")
    print("  pip install -r requirements.txt")
    print("")

    print("2) Core Run Commands")
    print("-" * 72)
    print("Start API:")
    print("  python api/app.py")
    print("  API base: http://localhost:5000")
    print("  Health:   http://localhost:5000/api/v1/health")
    print("  Ready:    http://localhost:5000/api/v1/ready")
    print("")
    print("Start dashboard (new terminal):")
    print("  streamlit run dashboard/app.py")
    print("  Dashboard: http://localhost:8501")
    print("")

    print("3) Pipeline + Reports")
    print("-" * 72)
    print("Run full batch pipeline:")
    print("  python src/main.py --input data/raw/sample_tenders.csv --output data/processed")
    print("")
    print("Generate sample data (if needed):")
    print("  python data/generate_sample_data.py")
    print("")
    print("Report endpoints are secured:")
    print("  - List reports requires API key (X-API-Key or Authorization: Bearer ...)")
    print("  - Download supports API key OR signed URL")
    print("  - Signed URL TTL configured in config/config.yaml")
    print("")

    print("4) Dev/Quality Commands")
    print("-" * 72)
    print("Using Makefile:")
    print("  make setup")
    print("  make test")
    print("  make benchmark-regression")
    print("  make ci")
    print("")
    print("Direct commands:")
    print("  python -m unittest discover -s tests -p 'test_*.py'")
    print("  python -m benchmarks.regression --dataset data/benchmarks/tender_regression_dataset.csv "
          "--baseline benchmarks/risk_score_baseline.json")
    print("")

    print("5) Container Run")
    print("-" * 72)
    print("Docker compose:")
    print("  docker compose up --build")
    print("")
    print("Container checks configured:")
    print("  - API: /api/v1/ready")
    print("  - Dashboard: /_stcore/health")
    print("  - Postgres: pg_isready")
    print("")

    print("6) Key Files Status")
    print("-" * 72)
    paths = [
        project_root / "api" / "app.py",
        project_root / "config" / "config.yaml",
        project_root / "docker-compose.yml",
        project_root / "Dockerfile",
        project_root / ".github" / "workflows" / "ci.yml",
        project_root / "benchmarks" / "regression.py",
        project_root / "benchmarks" / "risk_score_baseline.json",
        project_root / "data" / "benchmarks" / "tender_regression_dataset.csv",
        project_root / "Makefile",
        project_root / "requirements.txt",
        project_root / "requirements-dev.txt",
    ]
    for p in paths:
        print(f"  [{_exists(p):7}] {p.relative_to(project_root)}")

    print("")
    print("=" * 72)
    print("Done. Start with: source .venv/bin/activate && python api/app.py")
    print("=" * 72)


if __name__ == "__main__":
    main()
