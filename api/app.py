"""
API module for procurement corruption analysis.
Includes request/response validation, pagination, rate limiting, and async jobs.
"""

from __future__ import annotations

from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import sys
import io
import uuid
import time
import math
import threading
from pathlib import Path
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.data_ingestion import DataIngestionPipeline
from src.feature_engineering import FeatureEngineer
from src.anomaly_detection import AnomalyDetectionEngine
from src.network_analysis import NetworkAnalyzer
from src.risk_scoring import CorruptionRiskAssessor
from src.utils import Logger
from reports.report_generator import ReportGenerator, ComplianceReporter

logger = Logger(__name__)
app = Flask(__name__)
CORS(app)
REPORTS_BASE_DIR = PROJECT_ROOT / "data" / "processed" / "reports"
REPORTS_BASE_DIR.mkdir(parents=True, exist_ok=True)


class AnalyzeOptionsModel(TypedDict, total=False):
    generate_report: bool
    contamination: float
    tune_contamination: bool
    label_column: Optional[str]
    use_weak_labels: bool
    calibration_enabled: bool
    contamination_candidates: List[float]
    pagination: Dict[str, int]


class AnalyzeRequestModel(TypedDict):
    data: List[Dict[str, Any]]
    options: AnalyzeOptionsModel


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000
ASYNC_ROW_THRESHOLD = 2000

RATE_LIMIT_STATE: Dict[str, deque] = {}
RATE_LIMIT_LOCK = threading.Lock()
GENERAL_LIMIT_PER_MIN = 180
ANALYZE_LIMIT_PER_MIN = 30
SUBMIT_LIMIT_PER_MIN = 20

JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _error_response(message: str, code: int = 400, details: Optional[Dict[str, Any]] = None):
    payload = {
        "status": "error",
        "message": message,
        "error": {
            "code": code,
            "details": details or {},
        },
    }
    return jsonify(payload), code


def _client_id() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _rate_limit_key() -> str:
    client = _client_id()
    return f"{client}:{request.path}"


def _check_rate_limit(limit_per_min: int) -> Optional[float]:
    key = _rate_limit_key()
    now = time.time()
    window_start = now - 60.0
    with RATE_LIMIT_LOCK:
        bucket = RATE_LIMIT_STATE.setdefault(key, deque())
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit_per_min:
            retry_after = 60.0 - (now - bucket[0])
            return max(retry_after, 1.0)
        bucket.append(now)
    return None


@app.before_request
def apply_rate_limiting():
    """Simple in-memory fixed-window rate limiting."""
    if not request.path.startswith("/api/v1/"):
        return None
    if request.path == "/api/v1/health":
        return None

    limit = GENERAL_LIMIT_PER_MIN
    if request.path == "/api/v1/analyze":
        limit = ANALYZE_LIMIT_PER_MIN
    elif request.path == "/api/v1/analyze/submit":
        limit = SUBMIT_LIMIT_PER_MIN

    retry_after = _check_rate_limit(limit)
    if retry_after is None:
        return None

    return _error_response(
        message="Rate limit exceeded",
        code=429,
        details={"retry_after_seconds": int(math.ceil(retry_after))},
    )


def _parse_pagination(options: AnalyzeOptionsModel) -> Dict[str, int]:
    pagination = options.get("pagination", {}) if isinstance(options.get("pagination"), dict) else {}
    page = pagination.get("page", DEFAULT_PAGE)
    page_size = pagination.get("page_size", DEFAULT_PAGE_SIZE)

    try:
        page = int(page)
        page_size = int(page_size)
    except (TypeError, ValueError):
        raise ValueError("pagination.page and pagination.page_size must be integers")

    if page < 1:
        raise ValueError("pagination.page must be >= 1")
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ValueError(f"pagination.page_size must be between 1 and {MAX_PAGE_SIZE}")

    return {"page": page, "page_size": page_size}


def _validate_analyze_request(payload: Dict[str, Any]) -> AnalyzeRequestModel:
    """Validate and normalize analyze payload."""
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    data = payload.get("data")
    if not isinstance(data, list) or len(data) == 0:
        raise ValueError("data must be a non-empty list of tender records")
    if not all(isinstance(row, dict) for row in data):
        raise ValueError("Each item in data must be an object")

    options = payload.get("options", {})
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ValueError("options must be an object")

    contamination = options.get("contamination", 0.05)
    try:
        contamination = float(contamination)
    except (TypeError, ValueError):
        raise ValueError("options.contamination must be numeric")
    if contamination <= 0 or contamination >= 0.5:
        raise ValueError("options.contamination must be between 0 and 0.5")

    candidates = options.get("contamination_candidates")
    if candidates is not None:
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("options.contamination_candidates must be a non-empty list")
        norm_candidates = []
        for c in candidates:
            try:
                c_val = float(c)
            except (TypeError, ValueError):
                raise ValueError("options.contamination_candidates must contain numeric values")
            if c_val <= 0 or c_val >= 0.5:
                raise ValueError("Each contamination candidate must be between 0 and 0.5")
            norm_candidates.append(c_val)
        candidates = norm_candidates

    pagination = _parse_pagination(options)

    normalized_options: AnalyzeOptionsModel = {
        "generate_report": bool(options.get("generate_report", False)),
        "contamination": contamination,
        "tune_contamination": bool(options.get("tune_contamination", False)),
        "label_column": options.get("label_column"),
        "use_weak_labels": bool(options.get("use_weak_labels", True)),
        "calibration_enabled": bool(options.get("calibration_enabled", True)),
        "pagination": pagination,
    }
    if candidates is not None:
        normalized_options["contamination_candidates"] = candidates

    return {"data": data, "options": normalized_options}


def _paginate_records(records: List[Dict[str, Any]], page: int, page_size: int):
    total_records = len(records)
    total_pages = max(1, math.ceil(total_records / page_size)) if total_records > 0 else 1
    start = (page - 1) * page_size
    end = start + page_size
    page_items = records[start:end]
    return page_items, {
        "page": page,
        "page_size": page_size,
        "total_records": total_records,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def _generate_reports(risk_results, network_results, processed_df, output_dir: Path):
    """Generate HTML reports and return metadata."""
    report_gen = ReportGenerator()
    output_dir.mkdir(parents=True, exist_ok=True)

    report_files = {}

    executive_path = output_dir / "executive_summary.html"
    executive_html = report_gen.generate_executive_summary(risk_results, processed_df)
    executive_path.write_text(executive_html, encoding="utf-8")
    report_files["executive_summary"] = executive_path.name

    detailed_path = output_dir / "detailed_analysis.html"
    detailed_html = report_gen.generate_detailed_analysis(risk_results)
    detailed_path.write_text(detailed_html, encoding="utf-8")
    report_files["detailed_analysis"] = detailed_path.name

    compliance_path = output_dir / "cvc_compliance_report.html"
    compliance_html = ComplianceReporter.generate_cvc_compliance_report(risk_results)
    compliance_path.write_text(compliance_html, encoding="utf-8")
    report_files["cvc_compliance_report"] = compliance_path.name

    if network_results:
        network_path = output_dir / "network_analysis_report.html"
        network_html = report_gen.generate_network_report(network_results)
        network_path.write_text(network_html, encoding="utf-8")
        report_files["network_analysis_report"] = network_path.name

    final_path = output_dir / "final_report_all_analysis.html"
    final_html = report_gen.generate_final_report(
        risk_results=risk_results,
        data=processed_df,
        network_analysis=network_results,
    )
    final_path.write_text(final_html, encoding="utf-8")
    report_files["final_report_all_analysis"] = final_path.name

    return report_files


def _get_run_dir(run_id: str) -> Path:
    """Return a safe run directory path or raise 404."""
    run_dir = (REPORTS_BASE_DIR / run_id).resolve()
    if REPORTS_BASE_DIR.resolve() not in run_dir.parents or not run_dir.exists():
        abort(404, description="Report run not found")
    return run_dir


def _execute_analysis(data: List[Dict[str, Any]], options: AnalyzeOptionsModel) -> Dict[str, Any]:
    """Execute full analysis pipeline and return full unpaginated results."""
    start_time = time.time()

    pipeline = DataIngestionPipeline(data)
    df = pipeline.execute()
    validation_report = pipeline.get_validation_report()

    engineer = FeatureEngineer()
    df = engineer.engineer_features(df)

    anomaly_engine = AnomalyDetectionEngine(contamination=options["contamination"])
    df = anomaly_engine.detect_anomalies(
        df,
        auto_tune=options["tune_contamination"],
        label_column=options.get("label_column"),
        use_weak_labels=options["use_weak_labels"],
        contamination_candidates=options.get("contamination_candidates"),
    )

    network_analyzer = NetworkAnalyzer()
    network_results = network_analyzer.analyze(df)

    assessor = CorruptionRiskAssessor()
    risk_results = assessor.assess_risk(
        df,
        network_results,
        calibration_config={
            "enabled": options["calibration_enabled"],
            "label_column": options.get("label_column"),
            "use_weak_labels": options["use_weak_labels"],
        },
    )

    execution_time = time.time() - start_time

    return {
        "tender_scores": risk_results["tender_scores"].to_dict(orient="records"),
        "contractor_scores": risk_results["contractor_scores"].to_dict(orient="records"),
        "department_scores": risk_results["department_scores"].to_dict(orient="records"),
        "network_stats": network_results["network_stats"],
        "calibration": risk_results.get("calibration", {}),
        "anomaly_tuning": anomaly_engine.tuning_report,
        "validation_report": validation_report,
        "execution_time": execution_time,
        "risk_results_df": risk_results,
        "processed_df": df,
        "network_results_raw": network_results,
    }


def _build_paginated_results(full_result: Dict[str, Any], page: int, page_size: int):
    tender_page, tender_meta = _paginate_records(full_result["tender_scores"], page, page_size)
    contractor_page, contractor_meta = _paginate_records(full_result["contractor_scores"], page, page_size)
    department_page, department_meta = _paginate_records(full_result["department_scores"], page, page_size)

    return {
        "tender_scores": tender_page,
        "contractor_scores": contractor_page,
        "department_scores": department_page,
        "network_stats": full_result["network_stats"],
        "calibration": full_result.get("calibration", {}),
        "anomaly_tuning": full_result.get("anomaly_tuning", {}),
        "pagination": {
            "tender_scores": tender_meta,
            "contractor_scores": contractor_meta,
            "department_scores": department_meta,
        },
    }


def _create_async_job(request_model: AnalyzeRequestModel) -> str:
    job_id = uuid.uuid4().hex
    job = {
        "job_id": job_id,
        "status": "queued",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "input_rows": len(request_model["data"]),
        "request_options": request_model["options"],
        "error": None,
        "result_full": None,
        "reports": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    return job_id


def _run_async_job(job_id: str, request_model: AnalyzeRequestModel):
    with JOBS_LOCK:
        if job_id not in JOBS:
            return
        JOBS[job_id]["status"] = "running"
        JOBS[job_id]["updated_at"] = _now_iso()

    try:
        full_result = _execute_analysis(request_model["data"], request_model["options"])
        reports = None
        if request_model["options"]["generate_report"]:
            run_id = uuid.uuid4().hex
            run_dir = REPORTS_BASE_DIR / run_id
            report_files = _generate_reports(
                risk_results=full_result["risk_results_df"],
                network_results=full_result["network_results_raw"],
                processed_df=full_result["processed_df"],
                output_dir=run_dir,
            )
            reports = {
                "run_id": run_id,
                "files": report_files,
                "list_url": f"/api/v1/reports/{run_id}",
                "download_base_url": f"/api/v1/reports/{run_id}/download",
            }

        with JOBS_LOCK:
            if job_id not in JOBS:
                return
            JOBS[job_id]["status"] = "completed"
            JOBS[job_id]["updated_at"] = _now_iso()
            JOBS[job_id]["result_full"] = full_result
            JOBS[job_id]["reports"] = reports
    except Exception as exc:  # pragma: no cover
        logger.error(f"Async job {job_id} failed: {str(exc)}")
        with JOBS_LOCK:
            if job_id not in JOBS:
                return
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["updated_at"] = _now_iso()
            JOBS[job_id]["error"] = str(exc)


def _get_job(job_id: str) -> Dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            abort(404, description="Job not found")
        return job


@app.route("/api/v1/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "version": "1.1.0",
            "service": "procurement-corruption-detection",
            "features": ["schema-models", "pagination", "rate-limiting", "async-jobs"],
        }
    )


@app.route("/api/v1/analyze", methods=["POST"])
def analyze():
    """
    Analyze procurement data synchronously.
    Supports paginated output via options.pagination.page / page_size.
    """
    try:
        payload = request.get_json(silent=True) or {}
        req_model = _validate_analyze_request(payload)

        if len(req_model["data"]) > ASYNC_ROW_THRESHOLD:
            return _error_response(
                message=f"Dataset too large for sync analysis (> {ASYNC_ROW_THRESHOLD} rows). Use /api/v1/analyze/submit.",
                code=413,
                details={"rows": len(req_model["data"]), "async_submit_url": "/api/v1/analyze/submit"},
            )

        full_result = _execute_analysis(req_model["data"], req_model["options"])
        page = req_model["options"]["pagination"]["page"]
        page_size = req_model["options"]["pagination"]["page_size"]
        results_payload = _build_paginated_results(full_result, page, page_size)

        response_payload = {
            "status": "success",
            "message": "Analysis completed",
            "results": results_payload,
            "validation_report": full_result["validation_report"],
            "execution_time": full_result["execution_time"],
            "request_id": uuid.uuid4().hex,
        }

        if req_model["options"]["generate_report"]:
            run_id = uuid.uuid4().hex
            run_dir = REPORTS_BASE_DIR / run_id
            report_files = _generate_reports(
                risk_results=full_result["risk_results_df"],
                network_results=full_result["network_results_raw"],
                processed_df=full_result["processed_df"],
                output_dir=run_dir,
            )
            response_payload["reports"] = {
                "run_id": run_id,
                "files": report_files,
                "list_url": f"/api/v1/reports/{run_id}",
                "download_base_url": f"/api/v1/reports/{run_id}/download",
            }

        return jsonify(response_payload)
    except ValueError as exc:
        return _error_response(str(exc), code=400)
    except Exception as exc:  # pragma: no cover
        logger.error(f"Analysis error: {str(exc)}")
        return _error_response("Internal server error", code=500, details={"exception": str(exc)})


@app.route("/api/v1/analyze/submit", methods=["POST"])
def analyze_submit():
    """Submit asynchronous analysis job."""
    try:
        payload = request.get_json(silent=True) or {}
        req_model = _validate_analyze_request(payload)
        job_id = _create_async_job(req_model)

        worker = threading.Thread(
            target=_run_async_job, args=(job_id, req_model), daemon=True
        )
        worker.start()

        return jsonify(
            {
                "status": "accepted",
                "message": "Analysis job submitted",
                "job": {
                    "job_id": job_id,
                    "status": "queued",
                    "status_url": f"/api/v1/analyze/jobs/{job_id}",
                    "result_url": f"/api/v1/analyze/jobs/{job_id}/result",
                },
            }
        ), 202
    except ValueError as exc:
        return _error_response(str(exc), code=400)
    except Exception as exc:  # pragma: no cover
        logger.error(f"Submit error: {str(exc)}")
        return _error_response("Internal server error", code=500, details={"exception": str(exc)})


@app.route("/api/v1/analyze/jobs/<job_id>", methods=["GET"])
def analyze_job_status(job_id):
    """Poll async job status."""
    job = _get_job(job_id)
    status_payload = {
        "status": "success",
        "job": {
            "job_id": job["job_id"],
            "state": job["status"],
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
            "input_rows": job["input_rows"],
            "error": job["error"],
        },
    }
    if job["status"] == "completed":
        status_payload["job"]["result_url"] = f"/api/v1/analyze/jobs/{job_id}/result"
    return jsonify(status_payload)


@app.route("/api/v1/analyze/jobs/<job_id>/result", methods=["GET"])
def analyze_job_result(job_id):
    """Fetch async job result with pagination."""
    job = _get_job(job_id)
    if job["status"] in ("queued", "running"):
        return jsonify(
            {
                "status": "accepted",
                "message": "Job still processing",
                "job": {"job_id": job_id, "state": job["status"]},
            }
        ), 202
    if job["status"] == "failed":
        return _error_response("Job failed", code=500, details={"job_id": job_id, "error": job["error"]})

    page = request.args.get("page", DEFAULT_PAGE)
    page_size = request.args.get("page_size", DEFAULT_PAGE_SIZE)
    try:
        page = int(page)
        page_size = int(page_size)
    except (TypeError, ValueError):
        return _error_response("page and page_size must be integers", code=400)
    if page < 1 or page_size < 1 or page_size > MAX_PAGE_SIZE:
        return _error_response(f"Invalid pagination params. page>=1 and 1<=page_size<={MAX_PAGE_SIZE}", code=400)

    full_result = job["result_full"]
    results_payload = _build_paginated_results(full_result, page, page_size)
    response_payload = {
        "status": "success",
        "message": "Job completed",
        "job": {"job_id": job_id, "state": job["status"]},
        "results": results_payload,
        "validation_report": full_result["validation_report"],
        "execution_time": full_result["execution_time"],
    }
    if job.get("reports"):
        response_payload["reports"] = job["reports"]
    return jsonify(response_payload)


@app.route("/api/v1/risk/<tender_id>", methods=["GET"])
def get_tender_risk(tender_id):
    """Get risk score for specific tender (requires database)."""
    return jsonify(
        {
            "status": "not_implemented",
            "message": "Database integration required",
        }
    ), 501


@app.route("/api/v1/contractors/<contractor>", methods=["GET"])
def get_contractor_risk(contractor):
    """Get risk score for specific contractor (requires database)."""
    return jsonify(
        {
            "status": "not_implemented",
            "message": "Database integration required",
        }
    ), 501


@app.route("/api/v1/reports/<run_id>", methods=["GET"])
def list_reports(run_id):
    """List generated reports for a specific analysis run."""
    run_dir = _get_run_dir(run_id)
    files = sorted([p.name for p in run_dir.glob("*.html") if p.is_file()])
    return jsonify(
        {
            "status": "success",
            "run_id": run_id,
            "files": files,
            "download_urls": [f"/api/v1/reports/{run_id}/download/{name}" for name in files],
            "download_all_url": f"/api/v1/reports/{run_id}/download/all",
        }
    )


@app.route("/api/v1/reports/<run_id>/download/<report_name>", methods=["GET"])
def download_report(run_id, report_name):
    """Download a specific generated report."""
    run_dir = _get_run_dir(run_id)
    file_path = (run_dir / report_name).resolve()

    if run_dir not in file_path.parents or not file_path.exists() or file_path.suffix.lower() != ".html":
        abort(404, description="Report file not found")

    return send_file(file_path, as_attachment=True, download_name=file_path.name, mimetype="text/html")


@app.route("/api/v1/reports/<run_id>/download/all", methods=["GET"])
def download_all_reports(run_id):
    """Download all generated reports for a run as ZIP."""
    run_dir = _get_run_dir(run_id)
    html_files = sorted([p for p in run_dir.glob("*.html") if p.is_file()])
    if not html_files:
        abort(404, description="No reports available for this run")

    zip_buffer = io.BytesIO()
    import zipfile

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in html_files:
            zf.write(file_path, arcname=file_path.name)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f"reports_{run_id}.zip",
        mimetype="application/zip",
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
