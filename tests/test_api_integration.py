"""Integration test for analyze and report download endpoints."""

import importlib
import tempfile
import unittest
from pathlib import Path

from tests.helpers import make_valid_records


class TestApiIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.api_module = importlib.import_module("api.app")
        self.api_module.REPORTS_BASE_DIR = Path(self.tmp_dir.name) / "reports"
        self.api_module.REPORTS_BASE_DIR.mkdir(parents=True, exist_ok=True)
        self.client = self.api_module.app.test_client()
        self.api_module.app.testing = True

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_analyze_and_download_reports(self):
        payload = {
            "data": make_valid_records(10),
            "options": {
                "generate_report": True,
                "tune_contamination": False,
                "calibration_enabled": True,
                "label_column": "is_corrupt",
                "use_weak_labels": True,
            },
        }
        analyze_resp = self.client.post("/api/v1/analyze", json=payload)
        self.assertEqual(analyze_resp.status_code, 200)
        analyze_json = analyze_resp.get_json()

        self.assertEqual(analyze_json["status"], "success")
        self.assertIn("validation_report", analyze_json)
        self.assertIn("reports", analyze_json)
        self.assertIn("run_id", analyze_json["reports"])
        self.assertIn("files", analyze_json["reports"])

        list_url = analyze_json["reports"]["list_url"]
        list_resp = self.client.get(list_url)
        self.assertEqual(list_resp.status_code, 200)
        list_json = list_resp.get_json()
        self.assertIn("final_report_all_analysis.html", list_json["files"])
        self.assertIn("all_tender_scores.csv", list_json["files"])
        self.assertGreaterEqual(len(list_json["files"]), 1)

        html_file = next(name for name in list_json["files"] if name.endswith(".html"))
        one_download = self.client.get(f"/api/v1/reports/{list_json['run_id']}/download/{html_file}")
        self.assertEqual(one_download.status_code, 200)
        self.assertGreater(len(one_download.data), 0)
        self.assertIn("text/html", one_download.content_type)
        one_download.close()

        csv_download = self.client.get(f"/api/v1/reports/{list_json['run_id']}/download/all_tender_scores.csv")
        self.assertEqual(csv_download.status_code, 200)
        self.assertGreater(len(csv_download.data), 0)
        self.assertIn("text/csv", csv_download.content_type)
        csv_download.close()

        all_download = self.client.get(f"/api/v1/reports/{list_json['run_id']}/download/all")
        self.assertEqual(all_download.status_code, 200)
        self.assertGreater(len(all_download.data), 0)
        self.assertIn("zip", all_download.content_type)
        all_download.close()


if __name__ == "__main__":
    unittest.main()
