"""Unit tests for data_ingestion module."""

import unittest
import pandas as pd

from src.data_ingestion import DataValidator, DataIngestionPipeline
from tests.helpers import make_valid_records


class TestDataIngestion(unittest.TestCase):
    def test_strict_validation_rejects_bad_rows_with_reasons(self):
        records = make_valid_records(3)
        records[1]["estimated_cost"] = -10
        records[2]["winning_bidder"] = "Unknown Bidder"
        df = pd.DataFrame(records)

        validator = DataValidator()
        is_valid, report = validator.validate(df)

        self.assertTrue(is_valid)
        self.assertEqual(report["accepted_records"], 1)
        self.assertEqual(report["rejected_records"], 2)
        self.assertIn("estimated_cost must be > 0", report["rejection_reasons_summary"])
        self.assertIn("winning_bidder is not present in participating_bidders", report["rejection_reasons_summary"])
        self.assertEqual(len(validator.validated_data), 1)

    def test_pipeline_execute_keeps_only_valid_rows(self):
        records = make_valid_records(4)
        records[0]["bid_amounts"] = "1000, 2000"  # count mismatch with bidders
        records[3]["tender_date"] = "2040-01-01"  # future date

        pipeline = DataIngestionPipeline(pd.DataFrame(records))
        cleaned = pipeline.execute()
        report = pipeline.get_validation_report()

        self.assertEqual(len(cleaned), 2)
        self.assertEqual(report["accepted_records"], 2)
        self.assertEqual(report["rejected_records"], 2)


if __name__ == "__main__":
    unittest.main()
