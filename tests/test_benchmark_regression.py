"""Regression checks to prevent risk score drift on benchmark data."""

import unittest
from pathlib import Path

from benchmarks.regression import (
    compare_metrics,
    load_baseline,
    run_pipeline,
    summarize_metrics,
)


class TestBenchmarkRegression(unittest.TestCase):
    def test_risk_score_drift_guardrail(self):
        dataset = Path("data/benchmarks/tender_regression_dataset.csv")
        baseline = Path("benchmarks/risk_score_baseline.json")

        baseline_metrics, tolerances = load_baseline(baseline)
        current = summarize_metrics(run_pipeline(dataset))
        failures = compare_metrics(current, baseline_metrics, tolerances)

        self.assertEqual(
            failures,
            [],
            msg="Benchmark score drift detected:\n- " + "\n- ".join(failures),
        )


if __name__ == "__main__":
    unittest.main()

