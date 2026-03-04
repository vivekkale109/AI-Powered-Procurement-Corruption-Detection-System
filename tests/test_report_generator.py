"""Unit tests for report_generator module."""

import unittest
import pandas as pd

from src.data_ingestion import DataIngestionPipeline
from src.feature_engineering import FeatureEngineer
from src.anomaly_detection import AnomalyDetectionEngine
from src.network_analysis import NetworkAnalyzer
from src.risk_scoring import CorruptionRiskAssessor
from reports.report_generator import ReportGenerator
from tests.helpers import make_valid_records


class TestReportGenerator(unittest.TestCase):
    def _build_results(self):
        df = pd.DataFrame(make_valid_records(8))
        df = DataIngestionPipeline(df).execute()
        df = FeatureEngineer().engineer_features(df)
        df = AnomalyDetectionEngine(contamination=0.1).detect_anomalies(df)
        network_results = NetworkAnalyzer().analyze(df)
        risk_results = CorruptionRiskAssessor().assess_risk(
            df,
            network_results,
            calibration_config={"enabled": True, "use_weak_labels": True},
        )
        return df, risk_results, network_results

    def test_generate_final_report_contains_tender_reasoning(self):
        df, risk_results, network_results = self._build_results()
        report_gen = ReportGenerator()
        html = report_gen.generate_final_report(risk_results, df, network_results)

        self.assertIn("Final Procurement Risk Report", html)
        self.assertIn("All Tender Scores", html)
        self.assertIn("top_3_reasons_text", html)
        self.assertIn("factor_breakdown_text", html)

    def test_generate_detailed_analysis_contains_high_risk_section(self):
        df, risk_results, _ = self._build_results()
        report_gen = ReportGenerator()
        html = report_gen.generate_detailed_analysis(risk_results)
        self.assertIn("Detailed Corruption Risk Analysis Report", html)
        self.assertIn("High-Risk Tenders", html)


if __name__ == "__main__":
    unittest.main()
