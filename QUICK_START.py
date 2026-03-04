#!/usr/bin/env python3
"""
Quick start guide and example usage.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and print status."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, cwd="/home/karl/project")
    return result.returncode == 0

def main():
    project_root = Path("/home/karl/project")
    os.chdir(project_root)
    
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "PROCUREMENT CORRUPTION DETECTION" + " "*15 + "║")
    print("║" + " "*16 + "AI-Powered Analysis Platform" + " "*14 + "║")
    print("╚" + "="*58 + "╝")
    
    print("\n📋 QUICK START GUIDE\n")
    
    # Step 1: Check Python and dependencies
    print("Step 1: Environment Setup")
    print("-" * 40)
    
    # Check if requirements are installed
    try:
        import pandas
        import numpy
        import sklearn
        print("✓ Core dependencies installed")
    except ImportError:
        print("⚠ Installing dependencies...")
        run_command("pip install -r requirements.txt", "Installing packages...")
    
    # Step 2: Generate sample data
    print("\nStep 2: Generate Sample Data")
    print("-" * 40)
    
    sample_data = project_root / "data" / "raw" / "sample_tenders.csv"
    
    if not sample_data.exists():
        print("Generating sample procurement data...")
        run_command(
            "python data/generate_sample_data.py",
            "Generating Sample Data"
        )
    else:
        print(f"✓ Sample data exists: {sample_data}")
    
    # Step 3: Run analysis
    print("\nStep 3: Run Analysis Pipeline")
    print("-" * 40)
    print("""
To run the complete analysis pipeline:

  python src/main.py --input data/raw/sample_tenders.csv --output data/processed
  
This will:
  1. Load and validate procurement data
  2. Engineer 15+ features
  3. Run anomaly detection (Isolation Forest, LOF)
  4. Analyze contractor networks
  5. Score corruption risk
  6. Generate reports
""")
    
    # Step 4: Launch dashboard
    print("\nStep 4: Interactive Dashboard")
    print("-" * 40)
    print("""
To launch the interactive dashboard:

  streamlit run dashboard/app.py
  
The dashboard provides:
  - Risk analysis visualization
  - Network graphs
  - Contractor rankings
  - Department insights
  - Export capabilities
""")
    
    # Step 5: System capabilities
    print("\nStep 5: System Capabilities")
    print("-" * 40)
    print("""
✓ Data Ingestion
  - Load tender records from CSV/JSON
  - Validate data quality
  - Handle missing values

✓ Feature Engineering
  - 15+ advanced features
  - Bid deviation analysis
  - Contractor win patterns
  - Temporal analysis
  - Geographic concentration

✓ Anomaly Detection
  - Isolation Forest (100 estimators)
  - Local Outlier Factor
  - Statistical detection (Z-scores, IQR)
  - Multi-algorithm ensemble

✓ Network Analysis
  - Co-participation graphs
  - Community detection
  - Centrality analysis
  - Bid rotation detection
  - Suspicious cluster identification

✓ Risk Scoring
  - Tender-level risk (0-1 scale)
  - Contractor evaluation
  - Department analysis
  - Multi-factor weighted scoring

✓ Reporting
  - Executive summaries
  - Detailed analysis
  - Network insights
  - CVC compliance reports
  - HTML/JSON export
""")
    
    # Step 6: Configuration
    print("\nStep 6: Configuration")
    print("-" * 40)
    print("""
Key configuration files:
  - config/config.yaml        : System settings
  - config/risk_weights.yaml : Risk scoring weights
  
Customize:
  - Contamination thresholds
  - Risk weights and factors
  - Community detection parameters
  - Report generation options
""")
    
    # Step 7: Project structure
    print("\nStep 7: Project Structure")
    print("-" * 40)
    print("""
src/
  ├── main.py                  : CLI orchestration
  ├── __init__.py             : Package init
  ├── data_ingestion.py       : Load & validate
  ├── preprocessing.py        : Clean data
  ├── feature_engineering.py  : Compute features
  ├── anomaly_detection.py    : ML detection
  ├── network_analysis.py     : Graph analysis
  ├── risk_scoring.py         : Risk assessment
  └── utils.py                : Utilities

dashboard/
  └── app.py                   : Streamlit dashboard

reports/
  └── report_generator.py     : Report creation

config/
  ├── config.yaml             : Configuration
  └── risk_weights.yaml       : Weights

data/
  ├── raw/                     : Raw datasets
  ├── processed/              : Results
  └── generate_sample_data.py : Sample generator
""")
    
    # Step 8: Next steps
    print("\nStep 8: Getting Started")
    print("-" * 40)
    print("""
Quick Start Commands:

1. Generate sample data:
   python data/generate_sample_data.py

2. Run analysis:
   python src/main.py --input data/raw/sample_tenders.csv

3. Launch dashboard:
   streamlit run dashboard/app.py

4. View reports:
   Open data/processed/*.html in browser

5. Advanced usage:
   python src/main.py --help
""")
    
    # Documentation links
    print("\nDocumentation")
    print("-" * 40)
    print("""
📖 See README.md for:
  - System architecture
  - Feature descriptions
  - API documentation
  - Governance alignment
""")
    
    print("\n" + "="*60)
    print("System Ready! Next: Run analysis or launch dashboard")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
