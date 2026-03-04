"""
API module for procurement corruption analysis.
Includes request/response validation, pagination, rate limiting, and async jobs.
"""

from __future__ import annotations

from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import sys
import os
import io
import uuid
import time
import math
import threading
import json
import re
import shutil
import hmac
import hashlib
import traceback
from pathlib import Path
from collections import deque
from datetime import datetime, timezone, timedelta
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
from src.utils import Logger, ConfigManager
from reports.report_generator import ReportGenerator, ComplianceReporter

logger = Logger(__name__)
app = Flask(__name__)
CORS(app)
APP_CONFIG = ConfigManager().config or {}
SYSTEM_CONFIG = APP_CONFIG.get("system", {}) if isinstance(APP_CONFIG, dict) else {}
REPORTS_BASE_DIR = PROJECT_ROOT / "data" / "processed" / "reports"
REPORTS_BASE_DIR.mkdir(parents=True, exist_ok=True)
SECURITY_CONFIG = APP_CONFIG.get("security", {}) if isinstance(APP_CONFIG, dict) else {}
RETENTION_CONFIG = APP_CONFIG.get("retention", {}) if isinstance(APP_CONFIG, dict) else {}
PII_CONFIG = APP_CONFIG.get("pii_scrubbing", {}) if isinstance(APP_CONFIG, dict) else {}

REPORT_AUTH_REQUIRED = bool(SECURITY_CONFIG.get("report_auth_required", True))
REPORT_API_KEYS = SECURITY_CONFIG.get("report_api_keys", ["dev-report-api-key"])
if not isinstance(REPORT_API_KEYS, list):
    REPORT_API_KEYS = ["dev-report-api-key"]
REPORT_SIGNING_SECRET = str(SECURITY_CONFIG.get("download_signing_secret", "dev-download-signing-secret"))
SIGNED_URL_TTL_SEC = int(SECURITY_CONFIG.get("signed_url_ttl_seconds", 900))

RETENTION_ENABLED = bool(RETENTION_CONFIG.get("enabled", True))
REPORT_RETENTION_DAYS = int(RETENTION_CONFIG.get("report_retention_days", 30))
RETENTION_CLEANUP_INTERVAL_SEC = int(RETENTION_CONFIG.get("cleanup_interval_seconds", 600))

PII_SCRUB_ENABLED = bool(PII_CONFIG.get("enabled", True))
PII_REPLACEMENT = str(PII_CONFIG.get("replacement", "[REDACTED]"))
PII_PATTERNS = PII_CONFIG.get(
    "patterns",
    {
        "email": r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        "phone": r"((?=(?:\D*\d){10,})\+?\d[\d\-\s]{8,}\d)",
        "aadhaar_like": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
        "pan_like": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        "ssn_like": r"\b\d{3}-\d{2}-\d{4}\b",
        "bank_account_like": r"\b\d{9,18}\b",
    },
)
if not isinstance(PII_PATTERNS, dict):
    PII_PATTERNS = {}


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
RUN_METRICS: deque = deque(maxlen=5000)
METRICS_LOCK = threading.Lock()
RETENTION_LOCK = threading.Lock()
LAST_RETENTION_RUN_TS = 0.0
PII_REGEX: Dict[str, re.Pattern] = {
    name: re.compile(pattern, flags=re.IGNORECASE)
    for name, pattern in PII_PATTERNS.items()
    if isinstance(pattern, str) and pattern
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _parse_iso8601(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _extract_api_key() -> str:
    direct = request.headers.get("X-API-Key", "").strip()
    if direct:
        return direct
    auth = request.headers.get("Authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def _has_valid_api_key() -> bool:
    if not REPORT_AUTH_REQUIRED:
        return True
    key = _extract_api_key()
    if not key:
        return False
    return any(hmac.compare_digest(key, str(allowed)) for allowed in REPORT_API_KEYS)


def _make_download_signature(run_id: str, report_name: str, expires_at: int) -> str:
    payload = f"{run_id}:{report_name}:{expires_at}"
    return hmac.new(
        REPORT_SIGNING_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _build_signed_download_url(run_id: str, report_name: str, expires_in_sec: Optional[int] = None) -> str:
    ttl = expires_in_sec if expires_in_sec is not None else SIGNED_URL_TTL_SEC
    expires_at = int(time.time()) + max(1, int(ttl))
    sig = _make_download_signature(run_id, report_name, expires_at)
    return f"/api/v1/reports/{run_id}/download/{report_name}?exp={expires_at}&sig={sig}"


def _has_valid_signed_download(run_id: str, report_name: str) -> bool:
    exp = request.args.get("exp", "")
    sig = request.args.get("sig", "")
    if not exp or not sig:
        return False
    try:
        exp_int = int(exp)
    except ValueError:
        return False
    if exp_int < int(time.time()):
        return False
    expected = _make_download_signature(run_id, report_name, exp_int)
    return hmac.compare_digest(expected, sig)


def _enforce_report_list_auth():
    if not _has_valid_api_key():
        abort(401, description="Unauthorized. Provide valid API key for report endpoints.")


def _enforce_report_download_auth(run_id: str, report_name: str):
    if _has_valid_api_key():
        return
    if _has_valid_signed_download(run_id, report_name):
        return
    abort(401, description="Unauthorized. Provide API key or valid signed URL.")


def _run_retention_cleanup():
    if not RETENTION_ENABLED:
        return

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, REPORT_RETENTION_DAYS))
    removed_runs = 0

    for entry in REPORTS_BASE_DIR.iterdir():
        if not entry.is_dir():
            continue
        modified = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            shutil.rmtree(entry, ignore_errors=True)
            removed_runs += 1

    jobs_removed = 0
    jobs_cutoff = now - timedelta(days=max(1, REPORT_RETENTION_DAYS))
    with JOBS_LOCK:
        for job_id in list(JOBS.keys()):
            job = JOBS[job_id]
            created = _parse_iso8601(job.get("created_at", ""))
            if not created:
                continue
            if created < jobs_cutoff and job.get("status") in {"completed", "failed"}:
                del JOBS[job_id]
                jobs_removed += 1

    _log_event(
        "retention_cleanup_completed",
        removed_report_runs=removed_runs,
        removed_jobs=jobs_removed,
        retention_days=REPORT_RETENTION_DAYS,
    )


def _maybe_run_retention_cleanup():
    global LAST_RETENTION_RUN_TS
    if not RETENTION_ENABLED:
        return
    now_ts = time.time()
    with RETENTION_LOCK:
        if now_ts - LAST_RETENTION_RUN_TS < max(1, RETENTION_CLEANUP_INTERVAL_SEC):
            return
        LAST_RETENTION_RUN_TS = now_ts
    _run_retention_cleanup()


def _scrub_pii_from_records(rows: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not PII_SCRUB_ENABLED or not PII_REGEX:
        return rows, {
            "enabled": bool(PII_SCRUB_ENABLED),
            "rows_scanned": len(rows),
            "rows_modified": 0,
            "total_replacements": 0,
            "pattern_hits": {},
        }

    scrubbed_rows: List[Dict[str, Any]] = []
    rows_modified = 0
    total_replacements = 0
    pattern_hits = {name: 0 for name in PII_REGEX}

    for row in rows:
        row_modified = False
        updated = dict(row)
        for key, value in list(updated.items()):
            if not isinstance(value, str):
                continue
            original = value
            for name, pattern in PII_REGEX.items():
                value, hits = pattern.subn(PII_REPLACEMENT, value)
                if hits > 0:
                    row_modified = True
                    total_replacements += hits
                    pattern_hits[name] += hits
            if value != original:
                updated[key] = value
        if row_modified:
            rows_modified += 1
        scrubbed_rows.append(updated)

    return scrubbed_rows, {
        "enabled": True,
        "rows_scanned": len(rows),
        "rows_modified": rows_modified,
        "total_replacements": total_replacements,
        "pattern_hits": pattern_hits,
    }


def _log_event(event: str, level: str = "info", **kwargs):
    """Emit structured log event."""
    payload = {"timestamp": _now_iso(), "event": event, **kwargs}
    line = json.dumps(payload, default=str)
    if level == "error":
        logger.error(line)
    elif level == "warning":
        logger.warning(line)
    else:
        logger.info(line)


def _record_run_metric(run_id: str, status: str, execution_time: float = 0.0,
                       anomaly_rate: float = 0.0, step_timings: Optional[Dict[str, float]] = None,
                       error: Optional[str] = None, source: str = "sync"):
    with METRICS_LOCK:
        RUN_METRICS.append({
            "run_id": run_id,
            "status": status,
            "execution_time_sec": float(execution_time),
            "anomaly_rate": float(anomaly_rate),
            "step_timings": step_timings or {},
            "error": error,
            "source": source,
            "timestamp": _now_iso(),
        })


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
    _maybe_run_retention_cleanup()

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
    report_gen = ReportGenerator(
        system_version=SYSTEM_CONFIG.get("version"),
        model_version=SYSTEM_CONFIG.get("model_version"),
        config_version=SYSTEM_CONFIG.get("config_version"),
    )
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

    tender_scores_csv_path = output_dir / "all_tender_scores.csv"
    risk_results["tender_scores"].to_csv(tender_scores_csv_path, index=False)
    report_files["all_tender_scores_csv"] = tender_scores_csv_path.name

    return report_files


def _get_run_dir(run_id: str) -> Path:
    """Return a safe run directory path or raise 404."""
    run_dir = (REPORTS_BASE_DIR / run_id).resolve()
    if REPORTS_BASE_DIR.resolve() not in run_dir.parents or not run_dir.exists():
        abort(404, description="Report run not found")
    return run_dir


def _execute_analysis(data: List[Dict[str, Any]], options: AnalyzeOptionsModel,
                      run_id: Optional[str] = None, source: str = "sync") -> Dict[str, Any]:
    """Execute full analysis pipeline and return full unpaginated results."""
    run_id = run_id or uuid.uuid4().hex
    start_time = time.time()
    step_timings: Dict[str, float] = {}
    _log_event("analysis_started", run_id=run_id, source=source, input_rows=len(data))

    scrubbed_data, pii_report = _scrub_pii_from_records(data)
    if pii_report.get("total_replacements", 0) > 0:
        _log_event(
            "pii_scrubbing_applied",
            run_id=run_id,
            source=source,
            rows_modified=pii_report.get("rows_modified", 0),
            total_replacements=pii_report.get("total_replacements", 0),
            pattern_hits=pii_report.get("pattern_hits", {}),
        )

    def run_step(step_name: str, fn):
        step_start = time.time()
        out = fn()
        duration = round(time.time() - step_start, 6)
        step_timings[step_name] = duration
        _log_event("analysis_step_completed", run_id=run_id, source=source, step=step_name, duration_sec=duration)
        return out

    pipeline = DataIngestionPipeline(scrubbed_data)
    df = run_step("data_ingestion", lambda: pipeline.execute())
    validation_report = pipeline.get_validation_report()

    engineer = FeatureEngineer()
    df = run_step("feature_engineering", lambda: engineer.engineer_features(df))

    anomaly_engine = AnomalyDetectionEngine(contamination=options["contamination"])
    df = run_step(
        "anomaly_detection",
        lambda: anomaly_engine.detect_anomalies(
            df,
            auto_tune=options["tune_contamination"],
            label_column=options.get("label_column"),
            use_weak_labels=options["use_weak_labels"],
            contamination_candidates=options.get("contamination_candidates"),
        ),
    )
    anomaly_rate = float(df["is_anomaly"].mean()) if "is_anomaly" in df.columns and len(df) > 0 else 0.0

    network_analyzer = NetworkAnalyzer()
    network_results = run_step("network_analysis", lambda: network_analyzer.analyze(df))

    assessor = CorruptionRiskAssessor(APP_CONFIG.get("risk_scoring", {}))
    risk_results = run_step(
        "risk_scoring",
        lambda: assessor.assess_risk(
            df,
            network_results,
            calibration_config={
                "enabled": options["calibration_enabled"],
                "label_column": options.get("label_column"),
                "use_weak_labels": options["use_weak_labels"],
            },
        ),
    )

    execution_time = time.time() - start_time
    _log_event(
        "analysis_completed",
        run_id=run_id,
        source=source,
        execution_time_sec=round(execution_time, 6),
        anomaly_rate=round(anomaly_rate, 6),
        step_timings=step_timings,
    )

    return {
        "run_id": run_id,
        "tender_scores": risk_results["tender_scores"].to_dict(orient="records"),
        "contractor_scores": risk_results["contractor_scores"].to_dict(orient="records"),
        "department_scores": risk_results["department_scores"].to_dict(orient="records"),
        "network_stats": network_results["network_stats"],
        "calibration": risk_results.get("calibration", {}),
        "anomaly_tuning": anomaly_engine.tuning_report,
        "validation_report": validation_report,
        "pii_scrubbing": pii_report,
        "execution_time": execution_time,
        "anomaly_rate": anomaly_rate,
        "step_timings": step_timings,
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
        full_result = _execute_analysis(
            request_model["data"],
            request_model["options"],
            run_id=job_id,
            source="async",
        )
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
        _record_run_metric(
            run_id=job_id,
            status="success",
            execution_time=full_result["execution_time"],
            anomaly_rate=full_result.get("anomaly_rate", 0.0),
            step_timings=full_result.get("step_timings", {}),
            source="async",
        )
    except Exception as exc:  # pragma: no cover
        err_trace = traceback.format_exc()
        _log_event("async_job_failed", level="error", job_id=job_id, error=str(exc), traceback=err_trace)
        with JOBS_LOCK:
            if job_id not in JOBS:
                return
            JOBS[job_id]["status"] = "failed"
            JOBS[job_id]["updated_at"] = _now_iso()
            JOBS[job_id]["error"] = str(exc)
        _record_run_metric(run_id=job_id, status="failed", error=str(exc), source="async")


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
            "version": SYSTEM_CONFIG.get("version", "unknown"),
            "model_version": SYSTEM_CONFIG.get("model_version", "unknown"),
            "config_version": SYSTEM_CONFIG.get("config_version", "unknown"),
            "service": "procurement-corruption-detection",
            "features": ["schema-models", "pagination", "rate-limiting", "async-jobs"],
        }
    )


@app.route("/api/v1/ready", methods=["GET"])
def ready():
    """Readiness check endpoint for container orchestrators."""
    checks = {
        "config_loaded": isinstance(APP_CONFIG, dict) and bool(APP_CONFIG),
        "reports_dir_exists": REPORTS_BASE_DIR.exists(),
        "reports_dir_writable": REPORTS_BASE_DIR.exists() and os.access(REPORTS_BASE_DIR, os.W_OK),
    }
    ok = all(checks.values())
    return jsonify(
        {
            "status": "ready" if ok else "not_ready",
            "checks": checks,
            "service": "procurement-corruption-detection",
        }
    ), (200 if ok else 503)


@app.route("/api/v1/analyze", methods=["POST"])
def analyze():
    """
    Analyze procurement data synchronously.
    Supports paginated output via options.pagination.page / page_size.
    """
    try:
        payload = request.get_json(silent=True) or {}
        req_model = _validate_analyze_request(payload)
        run_id = uuid.uuid4().hex

        if len(req_model["data"]) > ASYNC_ROW_THRESHOLD:
            return _error_response(
                message=f"Dataset too large for sync analysis (> {ASYNC_ROW_THRESHOLD} rows). Use /api/v1/analyze/submit.",
                code=413,
                details={"rows": len(req_model["data"]), "async_submit_url": "/api/v1/analyze/submit"},
            )

        full_result = _execute_analysis(req_model["data"], req_model["options"], run_id=run_id, source="sync")
        page = req_model["options"]["pagination"]["page"]
        page_size = req_model["options"]["pagination"]["page_size"]
        results_payload = _build_paginated_results(full_result, page, page_size)

        response_payload = {
            "status": "success",
            "message": "Analysis completed",
            "run_id": run_id,
            "results": results_payload,
            "validation_report": full_result["validation_report"],
            "execution_time": full_result["execution_time"],
            "request_id": uuid.uuid4().hex,
            "metadata": {
                "system_version": SYSTEM_CONFIG.get("version", "unknown"),
                "model_version": SYSTEM_CONFIG.get("model_version", "unknown"),
                "config_version": SYSTEM_CONFIG.get("config_version", "unknown"),
            },
            "observability": {
                "step_timings": full_result.get("step_timings", {}),
                "anomaly_rate": full_result.get("anomaly_rate", 0.0),
            },
            "governance": {
                "pii_scrubbing": full_result.get("pii_scrubbing", {}),
            },
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

        _record_run_metric(
            run_id=run_id,
            status="success",
            execution_time=full_result["execution_time"],
            anomaly_rate=full_result.get("anomaly_rate", 0.0),
            step_timings=full_result.get("step_timings", {}),
            source="sync",
        )
        return jsonify(response_payload)
    except ValueError as exc:
        _log_event("analysis_validation_error", level="warning", message=str(exc))
        return _error_response(str(exc), code=400)
    except Exception as exc:  # pragma: no cover
        err_trace = traceback.format_exc()
        _log_event("analysis_failed", level="error", error=str(exc), traceback=err_trace)
        return _error_response("Internal server error", code=500, details={"exception": str(exc), "traceback": err_trace})


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
        "observability": {
            "step_timings": full_result.get("step_timings", {}),
            "anomaly_rate": full_result.get("anomaly_rate", 0.0),
        },
        "governance": {
            "pii_scrubbing": full_result.get("pii_scrubbing", {}),
        },
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
    _enforce_report_list_auth()
    run_dir = _get_run_dir(run_id)
    files = sorted([
        p.name for p in run_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".html", ".csv")
    ])
    signed_urls = [_build_signed_download_url(run_id, name) for name in files]
    signed_download_all = _build_signed_download_url(run_id, "all")
    return jsonify(
        {
            "status": "success",
            "run_id": run_id,
            "files": files,
            "download_urls": [f"/api/v1/reports/{run_id}/download/{name}" for name in files],
            "signed_download_urls": signed_urls,
            "download_all_url": f"/api/v1/reports/{run_id}/download/all",
            "signed_download_all_url": signed_download_all,
            "signed_url_ttl_seconds": SIGNED_URL_TTL_SEC,
        }
    )


@app.route("/api/v1/reports/<run_id>/download/<report_name>", methods=["GET"])
def download_report(run_id, report_name):
    """Download a specific generated report."""
    _enforce_report_download_auth(run_id, report_name)
    run_dir = _get_run_dir(run_id)
    file_path = (run_dir / report_name).resolve()

    if run_dir not in file_path.parents or not file_path.exists() or file_path.suffix.lower() not in (".html", ".csv"):
        abort(404, description="Report file not found")

    mime = "text/html" if file_path.suffix.lower() == ".html" else "text/csv"
    return send_file(file_path, as_attachment=True, download_name=file_path.name, mimetype=mime)


@app.route("/api/v1/reports/<run_id>/download/all", methods=["GET"])
def download_all_reports(run_id):
    """Download all generated reports for a run as ZIP."""
    _enforce_report_download_auth(run_id, "all")
    run_dir = _get_run_dir(run_id)
    report_files = sorted([
        p for p in run_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".html", ".csv")
    ])
    if not report_files:
        abort(404, description="No reports available for this run")

    zip_buffer = io.BytesIO()
    import zipfile

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in report_files:
            zf.write(file_path, arcname=file_path.name)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f"reports_{run_id}.zip",
        mimetype="application/zip",
    )


@app.route("/api/v1/metrics/summary", methods=["GET"])
def metrics_summary():
    """Get aggregate run metrics."""
    with METRICS_LOCK:
        runs = list(RUN_METRICS)
    total = len(runs)
    success_runs = [r for r in runs if r["status"] == "success"]
    failed_runs = [r for r in runs if r["status"] == "failed"]
    success_rate = (len(success_runs) / total) if total > 0 else 0.0
    avg_processing_time = (
        sum(r["execution_time_sec"] for r in success_runs) / len(success_runs)
        if success_runs else 0.0
    )
    recent = success_runs[-20:]
    previous = success_runs[-40:-20]
    recent_anomaly = (sum(r["anomaly_rate"] for r in recent) / len(recent)) if recent else 0.0
    previous_anomaly = (
        sum(r["anomaly_rate"] for r in previous) / len(previous)
    ) if previous else recent_anomaly
    anomaly_rate_drift = recent_anomaly - previous_anomaly

    return jsonify({
        "status": "success",
        "metrics": {
            "total_runs": total,
            "success_runs": len(success_runs),
            "failed_runs": len(failed_runs),
            "run_success_rate": round(success_rate, 6),
            "avg_processing_time_sec": round(avg_processing_time, 6),
            "recent_anomaly_rate": round(recent_anomaly, 6),
            "previous_anomaly_rate": round(previous_anomaly, 6),
            "anomaly_rate_drift": round(anomaly_rate_drift, 6),
        },
    })


@app.route("/api/v1/metrics/runs", methods=["GET"])
def metrics_runs():
    """Get run history for dashboard visualizations."""
    limit = request.args.get("limit", 200)
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return _error_response("limit must be integer", code=400)
    if limit < 1 or limit > 2000:
        return _error_response("limit must be between 1 and 2000", code=400)

    with METRICS_LOCK:
        runs = list(RUN_METRICS)[-limit:]
    return jsonify({"status": "success", "runs": runs})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
