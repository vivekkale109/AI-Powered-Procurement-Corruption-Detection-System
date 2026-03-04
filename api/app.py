"""
API Module for REST endpoints (Future implementation).
Framework: Flask with CORS support.
"""

from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
import sys
import io
import uuid
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

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
REPORTS_BASE_DIR = PROJECT_ROOT / 'data' / 'processed' / 'reports'
REPORTS_BASE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_reports(risk_results, network_results, processed_df, output_dir: Path):
    """Generate HTML reports and return metadata."""
    report_gen = ReportGenerator()
    output_dir.mkdir(parents=True, exist_ok=True)

    report_files = {}

    executive_path = output_dir / 'executive_summary.html'
    executive_html = report_gen.generate_executive_summary(risk_results, processed_df)
    executive_path.write_text(executive_html, encoding='utf-8')
    report_files['executive_summary'] = executive_path.name

    detailed_path = output_dir / 'detailed_analysis.html'
    detailed_html = report_gen.generate_detailed_analysis(risk_results)
    detailed_path.write_text(detailed_html, encoding='utf-8')
    report_files['detailed_analysis'] = detailed_path.name

    compliance_path = output_dir / 'cvc_compliance_report.html'
    compliance_html = ComplianceReporter.generate_cvc_compliance_report(risk_results)
    compliance_path.write_text(compliance_html, encoding='utf-8')
    report_files['cvc_compliance_report'] = compliance_path.name

    if network_results:
        network_path = output_dir / 'network_analysis_report.html'
        network_html = report_gen.generate_network_report(network_results)
        network_path.write_text(network_html, encoding='utf-8')
        report_files['network_analysis_report'] = network_path.name

    final_path = output_dir / 'final_report_all_analysis.html'
    final_html = report_gen.generate_final_report(
        risk_results=risk_results,
        data=processed_df,
        network_analysis=network_results
    )
    final_path.write_text(final_html, encoding='utf-8')
    report_files['final_report_all_analysis'] = final_path.name

    return report_files


def _get_run_dir(run_id: str) -> Path:
    """Return a safe run directory path or raise 404."""
    run_dir = (REPORTS_BASE_DIR / run_id).resolve()
    if REPORTS_BASE_DIR.resolve() not in run_dir.parents or not run_dir.exists():
        abort(404, description='Report run not found')
    return run_dir


@app.route('/api/v1/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'service': 'procurement-corruption-detection'
    })


@app.route('/api/v1/analyze', methods=['POST'])
def analyze():
    """
    Analyze procurement data.
    
    POST body:
      {
        "data": [list of tender records],
        "options": {
          "generate_report": true,
          "contamination": 0.05
        }
      }
    
    Returns:
      {
        "status": "success/error",
        "results": { ... },
        "execution_time": seconds
      }
    """
    try:
        import time
        start_time = time.time()
        pipeline = None
        
        data = request.json.get('data', [])
        options = request.json.get('options', {})
        
        if not data:
            return jsonify({
                'status': 'error',
                'message': 'No data provided'
            }), 400
        
        # Run analysis pipeline
        pipeline = DataIngestionPipeline(data)
        df = pipeline.execute()
        validation_report = pipeline.get_validation_report()
        
        # Feature engineering
        engineer = FeatureEngineer()
        df = engineer.engineer_features(df)
        
        # Anomaly detection
        anomaly_engine = AnomalyDetectionEngine(
            contamination=options.get('contamination', 0.05)
        )
        df = anomaly_engine.detect_anomalies(df)
        
        # Network analysis
        network_analyzer = NetworkAnalyzer()
        network_results = network_analyzer.analyze(df)
        
        # Risk scoring
        assessor = CorruptionRiskAssessor()
        risk_results = assessor.assess_risk(df, network_results)
        
        execution_time = time.time() - start_time
        
        response_payload = {
            'status': 'success',
            'results': {
                'tender_scores': risk_results['tender_scores'].to_dict(orient='records'),
                'contractor_scores': risk_results['contractor_scores'].to_dict(orient='records'),
                'department_scores': risk_results['department_scores'].to_dict(orient='records'),
                'network_stats': network_results['network_stats']
            },
            'validation_report': validation_report,
            'execution_time': execution_time
        }

        if options.get('generate_report', False):
            run_id = uuid.uuid4().hex
            run_dir = REPORTS_BASE_DIR / run_id
            report_files = _generate_reports(
                risk_results=risk_results,
                network_results=network_results,
                processed_df=df,
                output_dir=run_dir
            )
            response_payload['reports'] = {
                'run_id': run_id,
                'files': report_files,
                'list_url': f'/api/v1/reports/{run_id}',
                'download_base_url': f'/api/v1/reports/{run_id}/download'
            }

        return jsonify(response_payload)
    except ValueError as e:
        validation_report = {}
        try:
            if pipeline is not None:
                validation_report = pipeline.get_validation_report()
        except Exception:
            validation_report = {}
        return jsonify({
            'status': 'error',
            'message': str(e),
            'validation_report': validation_report
        }), 400
    
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/api/v1/risk/<tender_id>', methods=['GET'])
def get_tender_risk(tender_id):
    """Get risk score for specific tender (requires database)."""
    return jsonify({
        'status': 'not_implemented',
        'message': 'Database integration required'
    }), 501


@app.route('/api/v1/contractors/<contractor>', methods=['GET'])
def get_contractor_risk(contractor):
    """Get risk score for specific contractor (requires database)."""
    return jsonify({
        'status': 'not_implemented',
        'message': 'Database integration required'
    }), 501


@app.route('/api/v1/reports/<run_id>', methods=['GET'])
def list_reports(run_id):
    """List generated reports for a specific analysis run."""
    run_dir = _get_run_dir(run_id)
    files = sorted([p.name for p in run_dir.glob('*.html') if p.is_file()])
    return jsonify({
        'status': 'success',
        'run_id': run_id,
        'files': files,
        'download_urls': [f'/api/v1/reports/{run_id}/download/{name}' for name in files],
        'download_all_url': f'/api/v1/reports/{run_id}/download/all'
    })


@app.route('/api/v1/reports/<run_id>/download/<report_name>', methods=['GET'])
def download_report(run_id, report_name):
    """Download a specific generated report."""
    run_dir = _get_run_dir(run_id)
    file_path = (run_dir / report_name).resolve()

    if run_dir not in file_path.parents or not file_path.exists() or file_path.suffix.lower() != '.html':
        abort(404, description='Report file not found')

    return send_file(file_path, as_attachment=True, download_name=file_path.name, mimetype='text/html')


@app.route('/api/v1/reports/<run_id>/download/all', methods=['GET'])
def download_all_reports(run_id):
    """Download all generated reports for a run as ZIP."""
    run_dir = _get_run_dir(run_id)
    html_files = sorted([p for p in run_dir.glob('*.html') if p.is_file()])
    if not html_files:
        abort(404, description='No reports available for this run')

    zip_buffer = io.BytesIO()
    import zipfile

    with zipfile.ZipFile(zip_buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in html_files:
            zf.write(file_path, arcname=file_path.name)

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        as_attachment=True,
        download_name=f'reports_{run_id}.zip',
        mimetype='application/zip'
    )


if __name__ == '__main__':
    app.run(debug=True, port=5000)
