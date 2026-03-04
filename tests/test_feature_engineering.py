"""Unit tests for feature_engineering module."""

import unittest
import pandas as pd

from src.data_ingestion import DataIngestionPipeline
from src.feature_engineering import FeatureEngineer
from tests.helpers import make_valid_records


class TestFeatureEngineering(unittest.TestCase):
    def test_engineer_features_adds_expected_columns(self):
        df = pd.DataFrame(make_valid_records(6))
        ingested = DataIngestionPipeline(df).execute()

        fe = FeatureEngineer()
        engineered = fe.engineer_features(ingested)

        expected_cols = {
            "bid_deviation",
            "bid_deviation_zscore",
            "bid_above_estimate",
            "bid_variance",
            "bid_coefficient_variation",
            "complementary_bid_score",
            "dept_hhi",
            "temporal_anomaly_score",
            "bidder_set_repetition",
        }
        self.assertTrue(expected_cols.issubset(set(engineered.columns)))
        self.assertEqual(len(engineered), len(ingested))


if __name__ == "__main__":
    unittest.main()
