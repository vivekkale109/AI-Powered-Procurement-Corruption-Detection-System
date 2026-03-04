"""Unit tests for risk_scoring module."""

import unittest
import pandas as pd

from src.data_ingestion import DataIngestionPipeline
from src.feature_engineering import FeatureEngineer
from src.anomaly_detection import AnomalyDetectionEngine
from src.network_analysis import NetworkAnalyzer
from src.risk_scoring import CorruptionRiskAssessor
from tests.helpers import make_valid_records


class TestRiskScoring(unittest.TestCase):
    def test_tender_scores_include_explainability_and_probability(self):
        df = pd.DataFrame(make_valid_records(10))
        df = DataIngestionPipeline(df).execute()
        df = FeatureEngineer().engineer_features(df)
        df = AnomalyDetectionEngine(contamination=0.1).detect_anomalies(
            df, auto_tune=True, label_column="is_corrupt", use_weak_labels=True
        )
        network_results = NetworkAnalyzer().analyze(df)

        assessor = CorruptionRiskAssessor()
        results = assessor.assess_risk(
            df,
            network_results,
            calibration_config={
                "enabled": True,
                "label_column": "is_corrupt",
                "use_weak_labels": True,
            },
        )

        tender_scores = results["tender_scores"]
        self.assertIn("risk_probability", tender_scores.columns)
        self.assertIn("factor_contributions", tender_scores.columns)
        self.assertIn("factor_breakdown_text", tender_scores.columns)
        self.assertIn("top_3_reasons", tender_scores.columns)
        self.assertIn("top_3_reasons_text", tender_scores.columns)
        self.assertTrue(((tender_scores["risk_probability"] >= 0) & (tender_scores["risk_probability"] <= 1)).all())

        first = tender_scores.iloc[0]
        self.assertIsInstance(first["factor_contributions"], list)
        self.assertLessEqual(len(first["top_3_reasons"]), 3)
        self.assertIn("calibration", results)


if __name__ == "__main__":
    unittest.main()
