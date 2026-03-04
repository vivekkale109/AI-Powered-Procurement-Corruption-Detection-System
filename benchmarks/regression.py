"""Risk score benchmark and regression drift checks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

from src.data_ingestion import DataIngestionPipeline
from src.feature_engineering import FeatureEngineer
from src.anomaly_detection import AnomalyDetectionEngine
from src.network_analysis import NetworkAnalyzer
from src.risk_scoring import CorruptionRiskAssessor


DEFAULT_DATASET = Path("data/benchmarks/tender_regression_dataset.csv")
DEFAULT_BASELINE = Path("benchmarks/risk_score_baseline.json")


def run_pipeline(dataset_path: Path) -> Dict[str, Any]:
    """Run the full deterministic analysis flow for benchmarking."""
    pipeline = DataIngestionPipeline(str(dataset_path))
    df = pipeline.execute()
    validation_report = pipeline.get_validation_report()

    df = FeatureEngineer().engineer_features(df)
    df = AnomalyDetectionEngine(contamination=0.05).detect_anomalies(
        df,
        auto_tune=False,
        label_column=None,
        use_weak_labels=True,
    )
    network = NetworkAnalyzer().analyze(df)
    risk = CorruptionRiskAssessor().assess_risk(
        df,
        network,
        calibration_config={"enabled": True, "use_weak_labels": True, "label_column": None},
    )
    return {"data": df, "risk": risk, "network": network, "validation_report": validation_report}


def summarize_metrics(run_output: Dict[str, Any]) -> Dict[str, Any]:
    """Produce compact, stable metrics for regression checks."""
    tender_scores = run_output["risk"]["tender_scores"].copy()
    tender_scores = tender_scores.sort_values("final_risk_score", ascending=False).reset_index(drop=True)

    mean_score = float(tender_scores["final_risk_score"].mean())
    std_score = float(tender_scores["final_risk_score"].std(ddof=0))
    mean_probability = float(tender_scores["risk_probability"].mean())
    anomaly_rate = float(run_output["data"]["is_anomaly"].mean()) if "is_anomaly" in run_output["data"] else 0.0

    category_counts = (
        tender_scores["risk_category"].value_counts().reindex(["CRITICAL", "HIGH", "MEDIUM", "LOW"]).fillna(0).astype(int)
    )
    top_ids = tender_scores["tender_id"].head(5).tolist()

    return {
        "dataset_rows": int(len(tender_scores)),
        "mean_final_risk_score": round(mean_score, 6),
        "std_final_risk_score": round(std_score, 6),
        "mean_risk_probability": round(mean_probability, 6),
        "anomaly_rate": round(anomaly_rate, 6),
        "top_5_tender_ids": top_ids,
        "risk_category_counts": {k: int(v) for k, v in category_counts.to_dict().items()},
    }


def default_tolerances() -> Dict[str, float]:
    return {
        "mean_final_risk_score": 0.03,
        "std_final_risk_score": 0.03,
        "mean_risk_probability": 0.03,
        "anomaly_rate": 0.08,
    }


def compare_metrics(current: Dict[str, Any], baseline: Dict[str, Any], tolerances: Dict[str, float]) -> List[str]:
    """Return a list of drift failures."""
    failures: List[str] = []

    for metric, tol in tolerances.items():
        curr = float(current.get(metric, 0.0))
        base = float(baseline.get(metric, 0.0))
        if abs(curr - base) > float(tol):
            failures.append(
                f"{metric} drifted: current={curr:.6f}, baseline={base:.6f}, tolerance={tol:.6f}"
            )

    if current.get("top_5_tender_ids") != baseline.get("top_5_tender_ids"):
        failures.append(
            f"top_5_tender_ids changed: current={current.get('top_5_tender_ids')}, "
            f"baseline={baseline.get('top_5_tender_ids')}"
        )

    if current.get("risk_category_counts") != baseline.get("risk_category_counts"):
        failures.append(
            f"risk_category_counts changed: current={current.get('risk_category_counts')}, "
            f"baseline={baseline.get('risk_category_counts')}"
        )

    return failures


def load_baseline(path: Path) -> Tuple[Dict[str, Any], Dict[str, float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = payload.get("metrics", {})
    tolerances = payload.get("tolerances", default_tolerances())
    return metrics, tolerances


def write_baseline(path: Path, dataset_path: Path, metrics: Dict[str, Any], tolerances: Dict[str, float]) -> None:
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dataset_path": str(dataset_path),
        "metrics": metrics,
        "tolerances": tolerances,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run risk scoring benchmark regression checks.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Benchmark CSV dataset path.")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="Baseline JSON file path.")
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help="Write baseline from current run instead of validating drift.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    baseline_path = Path(args.baseline)
    run_output = run_pipeline(dataset_path)
    metrics = summarize_metrics(run_output)

    if args.write_baseline:
        write_baseline(baseline_path, dataset_path, metrics, default_tolerances())
        print(f"Baseline written to {baseline_path}")
        return 0

    if not baseline_path.exists():
        print(f"Baseline not found: {baseline_path}. Run with --write-baseline first.")
        return 2

    baseline_metrics, tolerances = load_baseline(baseline_path)
    failures = compare_metrics(metrics, baseline_metrics, tolerances)
    if failures:
        print("Score drift regression check failed:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Score drift regression check passed.")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

