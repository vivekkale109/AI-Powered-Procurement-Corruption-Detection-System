"""
Main orchestration script for the Procurement Corruption Detection System.
Provides CLI interface for running complete analysis pipeline.
"""

import sys
import os
import argparse
from pathlib import Path
import pandas as pd
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.data_ingestion import DataIngestionPipeline
from src.feature_engineering import FeatureEngineer, BidAnalyzer, ContractorAnalyzer
from src.anomaly_detection import AnomalyDetectionEngine, BidGapAnalyzer, PriceAnomalyDetector
from src.network_analysis import NetworkAnalyzer
from src.risk_scoring import CorruptionRiskAssessor
from src.utils import Logger, save_results, load_results, ConfigManager
from reports.report_generator import ReportGenerator, ComplianceReporter
from data.generate_sample_data import ProcurementDataGenerator

logger = Logger(__name__)


class ProcurementAnalysisPipeline:
    """Orchestrates complete analysis pipeline."""
    
    def __init__(self, config: dict = None):
        """Initialize pipeline."""
        self.config = config or ConfigManager().config or {}
        self.data = None
        self.results = {}
    
    def run(self, input_path: str, output_dir: str = "data/processed",
            generate_report: bool = True, verbose: bool = True):
        """
        Run complete analysis pipeline.
        
        Args:
            input_path: Path to input data file
            output_dir: Output directory for results
            generate_report: Whether to generate reports
            verbose: Verbose logging
        """
        logger.info("=" * 60)
        logger.info("PROCUREMENT CORRUPTION DETECTION SYSTEM")
        logger.info("Analysis Pipeline")
        logger.info("=" * 60)
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        try:
            # Step 1: Data Ingestion and Preprocessing
            logger.info("\n[1/5] Data Ingestion & Preprocessing")
            self._step_ingest(input_path)
            
            # Step 2: Feature Engineering
            logger.info("\n[2/5] Feature Engineering")
            self._step_feature_engineering()
            
            # Step 3: Anomaly Detection
            logger.info("\n[3/5] Anomaly Detection")
            self._step_anomaly_detection()
            
            # Step 4: Network Analysis
            logger.info("\n[4/5] Network Analysis")
            self._step_network_analysis()
            
            # Step 5: Risk Scoring
            logger.info("\n[5/5] Risk Assessment & Scoring")
            self._step_risk_scoring()
            
            # Save results
            self._save_results(output_dir)
            
            # Generate reports
            if generate_report:
                logger.info("\nGenerating Reports...")
                self._generate_reports(output_dir)
            
            logger.info("\n" + "=" * 60)
            logger.info("✓ Analysis completed successfully")
            logger.info(f"Results saved to: {output_dir}")
            logger.info("=" * 60)
            
            return self.results
        
        except Exception as e:
            logger.error(f"\n✗ Analysis failed: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def _step_ingest(self, input_path: str):
        """Step 1: Data ingestion."""
        pipeline = DataIngestionPipeline(input_path)
        self.data = pipeline.execute()
        
        logger.info(f"  • Loaded {len(self.data)} tender records")
        logger.info(f"  • Departments: {self.data['department'].nunique()}")
        logger.info(f"  • Locations: {self.data['location'].nunique()}")
    
    def _step_feature_engineering(self):
        """Step 2: Feature engineering."""
        engineer = FeatureEngineer()
        self.data = engineer.engineer_features(self.data)
        
        logger.info(f"  • Engineered 15+ features")
        logger.info(f"  • Features available: {self.data.shape[1]} columns")
    
    def _step_anomaly_detection(self):
        """Step 3: Anomaly detection."""
        anomaly_cfg = self.config.get('anomaly_detection', {})
        reliability_cfg = self.config.get('model_reliability', {})
        contamination = (
            anomaly_cfg.get('isolation_forest', {}).get('contamination', 0.05)
            if isinstance(anomaly_cfg, dict) else 0.05
        )
        label_column = reliability_cfg.get('label_column') if isinstance(reliability_cfg, dict) else None
        use_weak_labels = reliability_cfg.get('use_weak_labels', True) if isinstance(reliability_cfg, dict) else True
        tune_contamination = reliability_cfg.get('tune_contamination', False) if isinstance(reliability_cfg, dict) else False
        
        # Run multiple algorithms
        anomaly_engine = AnomalyDetectionEngine(contamination=contamination)
        self.data = anomaly_engine.detect_anomalies(
            self.data,
            auto_tune=tune_contamination,
            label_column=label_column,
            use_weak_labels=use_weak_labels,
            contamination_candidates=reliability_cfg.get('contamination_candidates') if isinstance(reliability_cfg, dict) else None
        )
        self.results['anomaly_tuning'] = anomaly_engine.tuning_report
        
        # Additional detectors
        self.data = BidGapAnalyzer.analyze_bid_gaps(self.data)
        self.data = PriceAnomalyDetector.detect_price_anomalies(self.data)
        
        num_anomalies = self.data['is_anomaly'].sum()
        logger.info(f"  • Detected {num_anomalies} anomalous tenders ({num_anomalies/len(self.data)*100:.1f}%)")
        logger.info(f"  • Anomaly detection algorithms: Isolation Forest, LOF, Statistical")
        if self.results.get('anomaly_tuning'):
            logger.info(f"  • Anomaly tuning: {self.results['anomaly_tuning']}")
    
    def _step_network_analysis(self):
        """Step 4: Network analysis."""
        analyzer = NetworkAnalyzer()
        network_results = analyzer.analyze(self.data)
        
        self.results['network'] = network_results
        
        stats = network_results['network_stats']
        logger.info(f"  • Network nodes (contractors): {stats['num_nodes']}")
        logger.info(f"  • Network edges (co-participation): {stats['num_edges']}")
        logger.info(f"  • Network density: {stats['density']:.3f}")
        
        suspicious_clusters = network_results['suspicious_clusters']
        logger.info(f"  • Suspicious clusters detected: {len(suspicious_clusters)}")
    
    def _step_risk_scoring(self):
        """Step 5: Risk scoring."""
        reliability_cfg = self.config.get('model_reliability', {})
        assessor = CorruptionRiskAssessor(self.config.get('risk_scoring', {}))
        risk_results = assessor.assess_risk(
            self.data,
            self.results.get('network'),
            calibration_config={
                'enabled': reliability_cfg.get('calibration_enabled', True) if isinstance(reliability_cfg, dict) else True,
                'label_column': reliability_cfg.get('label_column') if isinstance(reliability_cfg, dict) else None,
                'use_weak_labels': reliability_cfg.get('use_weak_labels', True) if isinstance(reliability_cfg, dict) else True
            }
        )
        
        self.results['risk'] = risk_results
        
        tender_scores = risk_results['tender_scores']
        contractor_scores = risk_results['contractor_scores']
        dept_scores = risk_results['department_scores']
        
        # Summary statistics
        critical_tenders = (tender_scores['risk_category'] == 'CRITICAL').sum()
        high_risk_tenders = (tender_scores['risk_category'] == 'HIGH').sum()
        
        logger.info(f"  • Tenders analyzed: {len(tender_scores)}")
        logger.info(f"    - CRITICAL risk: {critical_tenders} ({critical_tenders/len(tender_scores)*100:.1f}%)")
        logger.info(f"    - HIGH risk: {high_risk_tenders} ({high_risk_tenders/len(tender_scores)*100:.1f}%)")
        
        critical_contractors = (contractor_scores['risk_category'] == 'CRITICAL').sum()
        logger.info(f"  • Contractors evaluated: {len(contractor_scores)}")
        logger.info(f"    - CRITICAL risk: {critical_contractors}")
        
        logger.info(f"  • Departments analyzed: {len(dept_scores)}")
        if risk_results.get('calibration'):
            logger.info(f"  • Calibration: {risk_results['calibration']}")
    
    def _save_results(self, output_dir: str):
        """Save analysis results."""
        logger.info("\nSaving results...")
        
        # Save processed data
        data_path = f"{output_dir}/processed_data.csv"
        self.data.to_csv(data_path, index=False)
        logger.info(f"  • Data: {data_path}")
        
        # Save risk scores
        if 'risk' in self.results:
            risk_path = f"{output_dir}/risk_scores.json"
            risk_data = {
                'tender_scores': self.results['risk']['tender_scores'].to_dict(orient='records'),
                'contractor_scores': self.results['risk']['contractor_scores'].to_dict(orient='records'),
                'department_scores': self.results['risk']['department_scores'].to_dict(orient='records'),
                'calibration': self.results['risk'].get('calibration', {}),
                'anomaly_tuning': self.results.get('anomaly_tuning', {})
            }
            with open(risk_path, 'w') as f:
                json.dump(risk_data, f, indent=2, default=str)
            logger.info(f"  • Risk scores: {risk_path}")
        
        # Save network analysis
        if 'network' in self.results:
            network_path = f"{output_dir}/network_analysis.json"
            network_data = {
                'network_stats': self.results['network']['network_stats'],
                'num_suspicious_clusters': len(self.results['network']['suspicious_clusters']),
                'num_rotation_patterns': len(self.results['network']['rotation_patterns'])
            }
            with open(network_path, 'w') as f:
                json.dump(network_data, f, indent=2, default=str)
            logger.info(f"  • Network analysis: {network_path}")
    
    def _generate_reports(self, output_dir: str):
        """Generate analytical reports."""
        if 'risk' not in self.results:
            return
        
        report_gen = ReportGenerator(
            system_version=self.config.get('system', {}).get('version'),
            model_version=self.config.get('system', {}).get('model_version'),
            config_version=self.config.get('system', {}).get('config_version')
        )
        
        # Executive summary
        exec_summary = report_gen.generate_executive_summary(
            self.results['risk'], self.data
        )
        with open(f"{output_dir}/executive_summary.html", 'w') as f:
            f.write(exec_summary)
        logger.info(f"  • Executive Summary: {output_dir}/executive_summary.html")
        
        # Detailed analysis
        detailed = report_gen.generate_detailed_analysis(self.results['risk'])
        with open(f"{output_dir}/detailed_analysis.html", 'w') as f:
            f.write(detailed)
        logger.info(f"  • Detailed Analysis: {output_dir}/detailed_analysis.html")
        
        # Network report
        if 'network' in self.results:
            network_report = report_gen.generate_network_report(self.results['network'])
            with open(f"{output_dir}/network_analysis_report.html", 'w') as f:
                f.write(network_report)
            logger.info(f"  • Network Report: {output_dir}/network_analysis_report.html")
        
        # CVC Compliance report
        compliance_report = ComplianceReporter.generate_cvc_compliance_report(
            self.results['risk']
        )
        with open(f"{output_dir}/cvc_compliance_report.html", 'w') as f:
            f.write(compliance_report)
        logger.info(f"  • CVC Compliance: {output_dir}/cvc_compliance_report.html")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Procurement Corruption Detection System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run analysis on sample data
  python src/main.py --input data/raw/sample_tenders.csv
  
  # Generate sample data first
  python data/generate_sample_data.py
  
  # Run dashboard
  streamlit run dashboard/app.py
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['preprocess', 'analyze', 'full', 'generate-sample'],
        default='full',
        help='Operation mode (default: full)'
    )
    
    parser.add_argument(
        '--input',
        type=str,
        help='Input data file (CSV)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='data/processed',
        help='Output directory for results (default: data/processed)'
    )
    
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='Skip report generation'
    )
    
    parser.add_argument(
        '--sample-size',
        type=int,
        default=500,
        help='Sample size for generated data (default: 500)'
    )
    
    args = parser.parse_args()
    
    # Handle different modes
    if args.mode == 'generate-sample':
        logger.info("Generating sample procurement data...")
        generator = ProcurementDataGenerator()
        df = generator.generate_sample_data(args.sample_size)
        df = generator.add_anomalies(df, anomaly_rate=0.15)
        
        output_path = 'data/raw/sample_tenders.csv'
        Path('data/raw').mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        
        logger.info(f"✓ Sample data generated: {output_path}")
        return
    
    # Require input for other modes
    if not args.input:
        # Try to use sample data if it exists
        if Path('data/raw/sample_tenders.csv').exists():
            args.input = 'data/raw/sample_tenders.csv'
            logger.info(f"Using existing sample data: {args.input}")
        else:
            logger.error("Error: --input required (or generate sample data with --mode generate-sample)")
            parser.print_help()
            sys.exit(1)
    
    # Run pipeline
    pipeline = ProcurementAnalysisPipeline()
    
    try:
        pipeline.run(
            input_path=args.input,
            output_dir=args.output,
            generate_report=not args.no_report
        )
    except Exception as e:
        sys.exit(1)


if __name__ == "__main__":
    main()
