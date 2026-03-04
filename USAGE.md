"""
Usage Guide and Code Examples
"""

# USAGE GUIDE & CODE EXAMPLES

## Table of Contents
1. Quick Start
2. Python API Usage
3. Command Line Interface
4. Dashboard Usage
5. Advanced Examples
6. Integration Examples

---

## 1. QUICK START

### Minimal Example

```python
from src.data_ingestion import DataIngestionPipeline
from src.feature_engineering import FeatureEngineer
from src.anomaly_detection import AnomalyDetectionEngine
from src.network_analysis import NetworkAnalyzer
from src.risk_scoring import CorruptionRiskAssessor

# Load data
pipeline = DataIngestionPipeline('data.csv')
df = pipeline.execute()

# Engineer features
engineer = FeatureEngineer()
df = engineer.engineer_features(df)

# Detect anomalies
detector = AnomalyDetectionEngine()
df = detector.detect_anomalies(df)

# Analyze networks
analyzer = NetworkAnalyzer()
network = analyzer.analyze(df)

# Score risks
assessor = CorruptionRiskAssessor()
results = assessor.assess_risk(df, network)

# Access results
print(results['tender_scores'].head())
print(results['contractor_scores'].head())
```

---

## 2. PYTHON API USAGE

### Data Ingestion

```python
from src.data_ingestion import DataValidator, TenderDataLoader

# Load from CSV
loader = TenderDataLoader('tenders.csv')
df = loader.load()

# Validate data
is_valid, report = loader.validate()
if is_valid:
    print("Data validation passed")
else:
    print("Validation issues:", report['warnings'])

# Load from DataFrame
import pandas as pd
data_df = pd.read_csv('data.csv')
loader = TenderDataLoader(data_df)
df = loader.load()

# Load from list of dicts
tender_records = [
    {
        'tender_id': 'T001',
        'department': 'PWD',
        'estimated_cost': 1000000,
        'participating_bidders': 'Contractor A, Contractor B',
        'bid_amounts': '900000, 950000',
        'winning_bidder': 'Contractor A',
        'tender_date': '2024-01-15',
        'location': 'North'
    },
    # ... more records
]
loader = TenderDataLoader(tender_records)
df = loader.load()
```

### Feature Engineering

```python
from src.feature_engineering import FeatureEngineer, BidAnalyzer

# Engineer all features
engineer = FeatureEngineer()
df = engineer.engineer_features(df)

# Access specific analyzers
bid_analyzer = BidAnalyzer()
df = bid_analyzer.compute_bid_deviation_features(df)
df = bid_analyzer.compute_bid_variance_per_tender(df)

# Detect complementary bids (collusion sign)
df = bid_analyzer.detect_complementary_bids(df)

# Check engineered features
print("Available features:")
print(df.columns.tolist())
```

### Anomaly Detection

```python
from src.anomaly_detection import AnomalyDetectionEngine

# Create detector
detector = AnomalyDetectionEngine(contamination=0.05)

# Run detection
df = detector.detect_anomalies(df)

# Access anomaly scores
print("Anomaly scores by algorithm:")
print(df[['iso_forest_score', 'lof_score', 'statistical_score', 'anomaly_score']])

# Get anomalies
anomalies = df[df['is_anomaly']]
print(f"Found {len(anomalies)} anomalies")

# Get high-risk anomalies
high_risk_anomalies = df[df['anomaly_score'] > 0.8]
```

### Network Analysis

```python
from src.network_analysis import NetworkAnalyzer

# Analyze network
analyzer = NetworkAnalyzer(temporal_window_days=730)
results = analyzer.analyze(df)

# Network statistics
print("Network Statistics:")
print(results['network_stats'])

# Get suspicious clusters
clusters = results['suspicious_clusters']
for cluster_id, info in clusters.items():
    print(f"Cluster {cluster_id}:")
    print(f"  Members: {info['members']}")
    print(f"  Suspicion Score: {info['suspicion_score']:.3f}")

# Get rotation patterns
patterns = results['rotation_patterns']
for contractor, metrics in list(patterns.items())[:5]:
    print(f"{contractor}: Rotation Score = {metrics['rotation_score']:.3f}")

# Centrality measures
centrality = results['centrality']
for contractor, measures in list(centrality.items())[:5]:
    print(f"{contractor}:")
    print(f"  Degree: {measures['degree']:.3f}")
    print(f"  Betweenness: {measures['betweenness']:.3f}")
```

### Risk Scoring

```python
from src.risk_scoring import CorruptionRiskAssessor

# Create assessor
assessor = CorruptionRiskAssessor()

# Score risks
results = assessor.assess_risk(df, network_results)

# Access risk scores
tender_scores = results['tender_scores']
contractor_scores = results['contractor_scores']
department_scores = results['department_scores']

# High-risk tenders
high_risk = tender_scores[tender_scores['risk_category'] == 'HIGH']
critical = tender_scores[tender_scores['risk_category'] == 'CRITICAL']

# Top contractors by risk
top_contractors = contractor_scores.nlargest(10, 'final_risk_score')
print(top_contractors[['contractor', 'final_risk_score', 'risk_category', 'total_wins']])

# Department comparison
print(department_scores[['department', 'final_risk_score', 'risk_category']])
```

---

## 3. COMMAND LINE INTERFACE

### Generate Sample Data

```bash
python data/generate_sample_data.py

# Options
python data/generate_sample_data.py --num-tenders 1000
```

### Run Complete Analysis

```bash
# Basic usage
python src/main.py --input data.csv

# With options
python src/main.py \
  --input data.csv \
  --output results/ \
  --no-report

# Generate sample data and analyze
python src/main.py --mode generate-sample --sample-size 1000
```

### Help

```bash
python src/main.py --help
```

---

## 4. DASHBOARD USAGE

### Launch Dashboard

```bash
streamlit run dashboard/app.py
```

Access at: http://localhost:8501

### Dashboard Features

**Overview Tab:**
- System description
- Key capabilities
- Getting started guide

**Upload & Analyze Tab:**
- Drag-and-drop file upload
- Data preview
- Metadata display
- Run analysis button

**Risk Analysis Tab:**
- Risk distribution pie chart
- Risk score histogram
- Risk factor heatmap
- High-risk tenders list

**Network Analysis Tab:**
- Network statistics
- Suspicious clusters
- Bidding rotation patterns
- Contractor connections

**Contractor Insights Tab:**
- Contractor risk ranking
- Filtering options
- Risk score visualization
- Detailed metrics table

**Department Analysis Tab:**
- Department risk overview
- Comparative analysis
- Department metrics

**Export Report Tab:**
- Report generation options
- Output format selection
- Customization options

---

## 5. ADVANCED EXAMPLES

### Custom Risk Weights

```python
import yaml
from src.risk_scoring import CorruptionRiskAssessor

# Load custom weights
with open('custom_weights.yaml') as f:
    custom_config = yaml.safe_load(f)

# Create assessor with custom weights
assessor = CorruptionRiskAssessor(custom_config)
results = assessor.assess_risk(df, network)
```

### Batch Processing Large Files

```python
import pandas as pd
from src.main import ProcurementAnalysisPipeline

# Process in chunks
chunk_size = 5000
all_results = []

for chunk in pd.read_csv('large_data.csv', chunksize=chunk_size):
    pipeline = ProcurementAnalysisPipeline()
    results = pipeline.run(chunk, output_dir=f'results_{chunk_id}')
    all_results.append(results)

# Aggregate results
# Combine and summarize findings
```

### Real-Time Monitoring

```python
from src.data_ingestion import DataIngestionPipeline
from src.risk_scoring import CorruptionRiskAssessor
import time

# Continuous monitoring loop
while True:
    # Load latest data
    pipeline = DataIngestionPipeline('streaming_data.csv')
    df = pipeline.execute()
    
    # Score risks
    assessor = CorruptionRiskAssessor()
    results = assessor.assess_risk(df)
    
    # Alert on critical findings
    critical = results['tender_scores'][
        results['tender_scores']['risk_category'] == 'CRITICAL'
    ]
    
    if len(critical) > 0:
        print(f"ALERT: {len(critical)} critical tenders detected")
        alert_system(critical)
    
    # Wait before next check
    time.sleep(3600)  # 1 hour
```

### Integration with External Systems

```python
# Pull data from database
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine('postgresql://user:pass@localhost/procdb')
df = pd.read_sql('SELECT * FROM tenders', engine)

# Process
from src.main import ProcurementAnalysisPipeline
pipeline = ProcurementAnalysisPipeline()
# ... run analysis

# Save results to database
results_df = results['tender_scores']
results_df.to_sql('risk_scores', engine, if_exists='replace')
```

### Custom Anomaly Detection

```python
from src.anomaly_detection import AnomalyDetectionEngine
import numpy as np

# Create custom detector instance
detector = AnomalyDetectionEngine(contamination=0.1)

# Run standard detection
df = detector.detect_anomalies(df)

# Add custom detection rules
custom_anomalies = []

for _, row in df.iterrows():
    # Custom rule: No contractor should win > 30% of tenders
    if row['winner_concentration'] > 0.3:
        custom_anomalies.append(row['tender_id'])
    
    # Custom rule: Bid price < 50% of estimate
    if pd.notna(row['bid_deviation']) and row['bid_deviation'] < -0.5:
        custom_anomalies.append(row['tender_id'])

df['custom_anomaly'] = df['tender_id'].isin(custom_anomalies)
```

---

## 6. INTEGRATION EXAMPLES

### Integration with CVC Reporting System

```python
from reports.report_generator import ComplianceReporter
from src.main import ProcurementAnalysisPipeline

# Run analysis
pipeline = ProcurementAnalysisPipeline()
results = pipeline.run('cvc_data.csv')

# Generate CVC-aligned report
cvc_report = ComplianceReporter.generate_cvc_compliance_report(
    results['risk']
)

# Save to CVC standard format
with open('cvc_compliance_report.html', 'w') as f:
    f.write(cvc_report)
```

### REST API Usage

```python
import requests
import json

# Server running at http://localhost:5000

# Submit data for analysis
data = {
    "data": [
        {
            "tender_id": "T001",
            "department": "PWD",
            "estimated_cost": 1000000,
            # ... more fields
        }
    ],
    "options": {
        "contamination": 0.05,
        "generate_report": True
    }
}

response = requests.post(
    'http://localhost:5000/api/v1/analyze',
    json=data
)

if response.status_code == 200:
    results = response.json()['results']
    print(results)
```

### Docker Usage

```bash
# Build image
docker build -t procurement-detector .

# Run analysis
docker run \
  -v $(pwd)/data:/app/data \
  procurement-detector \
  python src/main.py --input data/tenders.csv

# Access dashboard
docker run \
  -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  procurement-detector

# Docker Compose
docker-compose up
# Dashboard: http://localhost:8501
# API: http://localhost:5000
```

---

## Performance Tips

### Optimize for Speed

```python
# Set appropriate anomaly detection threshold
detector = AnomalyDetectionEngine(contamination=0.1)

# Limit feature engineering
engineer = FeatureEngineer()
df = engineer.engineer_features(df)
# Skip unnecessary features in config

# Use faster algorithms for large datasets
# Isolation Forest scales better than LOF
```

### Memory Optimization

```python
# Process in chunks
chunk_size = 10000
for chunk in pd.read_csv('large_file.csv', chunksize=chunk_size):
    # Process chunk
    pass

# Drop unnecessary columns after feature engineering
df.drop(['participat_bidders'], axis=1, inplace=True)
```

---

## Troubleshooting

### Common Issues

**Import Error**
```python
# Ensure src is in path
import sys
sys.path.insert(0, '/path/to/project/src')
```

**Memory Error**
```bash
# Use chunking for large files
python src/main.py --input large_data.csv --chunk-size 5000
```

**Slow Execution**
```python
# Reduce contamination for faster anomaly detection
detector = AnomalyDetectionEngine(contamination=0.1)

# Skip heavy computations
skip_network_analysis = True
```

---

## Output Examples

### Tender Risk Scores Output

```
tender_id    final_risk_score  risk_category  price_anomaly  winner_concentration
T0001        0.725             HIGH           0.8            0.6
T0002        0.910             CRITICAL       0.95           0.9
T0003        0.325             LOW            0.2            0.3
```

### Contractor Risk Output

```
contractor               final_risk_score  risk_category  total_wins  win_rate  network_centrality
Tech Infrastructure LTD  0.780             HIGH           45          0.75      0.65
Global Projects Inc      0.650             MEDIUM         28          0.56      0.42
Prime Solutions Corp     0.450             MEDIUM         22          0.44      0.38
```

### Department Risk Output

```
department  final_risk_score  risk_category  total_tenders  unique_winners  winner_concentration
PWD         0.680             MEDIUM         67             12              0.45
Health      0.520             MEDIUM         54             18              0.32
Energy      0.890             CRITICAL       45             8               0.72
```

---

## Next Steps

1. **Generate sample data**: `python data/generate_sample_data.py`
2. **Run analysis**: `python src/main.py --input data/raw/sample_tenders.csv`
3. **View results**: Open HTML reports in `data/processed/`
4. **Launch dashboard**: `streamlit run dashboard/app.py`
5. **Customize**: Edit `config/` files for your requirements
