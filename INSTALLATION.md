"""
Installation and Deployment Guide
"""

# INSTALLATION GUIDE

## Prerequisites

- Python 3.8+
- pip or conda
- Git
- ~2GB disk space

## Local Installation

### 1. Clone/Download Project

```bash
cd /path/to/project
```

### 2. Create Virtual Environment (Recommended)

```bash
# Using venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# OR using conda
conda create -n procurement python=3.9
conda activate procurement
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Generate Sample Data

```bash
python data/generate_sample_data.py
```

This creates `data/raw/sample_tenders.csv` with 500 tender records.

### 5. Run Analysis

```bash
python src/main.py --input data/raw/sample_tenders.csv
```

This will:
- Load and validate data
- Engineer features
- Detect anomalies
- Analyze networks
- Score risks
- Generate reports

Results saved to: `data/processed/`

### 6. Launch Dashboard

```bash
streamlit run dashboard/app.py
```

Access at: http://localhost:8501

## Docker Deployment

### Build Image

```bash
docker build -t procurement-corruption-detector .
```

### Run Container

```bash
docker run -p 8501:8501 -v $(pwd)/data:/app/data procurement-corruption-detector
```

### Docker Compose

```bash
docker-compose up
```

Services:
- Dashboard: http://localhost:8501
- API: http://localhost:5000
- Database: localhost:5432

## Cloud Deployment

### AWS Deployment

1. **Create ECR Repository**
```bash
aws ecr create-repository --repository-name procurement-detector
```

2. **Build and Push Image**
```bash
docker build -t procurement-detector .
docker tag procurement-detector:latest [AWS_ACCOUNT].dkr.ecr.[REGION].amazonaws.com/procurement-detector:latest
docker push [AWS_ACCOUNT].dkr.ecr.[REGION].amazonaws.com/procurement-detector:latest
```

3. **Deploy to ECS/EKS**
```bash
# Create CloudFormation stack or deploy to ECS
# See aws-deployment.yaml
```

### Google Cloud Deployment

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/[PROJECT]/procurement-detector

# Deploy to Cloud Run
gcloud run deploy procurement-detector \
  --image gcr.io/[PROJECT]/procurement-detector \
  --platform managed \
  --region us-central1
```

### Azure Deployment

```bash
# Push to Azure Container Registry
az acr build --registry [registryName] -t procurement-detector .

# Deploy to Container Instances
az container create \
  --resource-group myResourceGroup \
  --name procurement-detector \
  --image [registryName].azurecr.io/procurement-detector
```

## Performance Optimization

### For Large Datasets (>50,000 records)

1. **Enable Database Backend** (configure in config.yaml)
```yaml
database:
  enabled: true
  backend: postgresql
  hostname: localhost
  database: procurement_db
```

2. **Parallel Processing**
```bash
# Use -j flag for parallel operations
PYTHONPATH=. python -c "import os; os.environ['OPENBLAS_NUM_THREADS'] = '4'"
```

3. **Batch Processing**
```python
from src.main import ProcurementAnalysisPipeline

# Process in chunks
chunk_size = 5000
for chunk in pd.read_csv('data.csv', chunksize=chunk_size):
    pipeline.run(chunk)
```

## Configuration

### System Configuration

Edit `config/config.yaml`:
```yaml
data:
  input_path: "data/raw"
  output_path: "data/processed"

anomaly_detection:
  isolation_forest:
    contamination: 0.05
    n_estimators: 100

risk_scoring:
  thresholds:
    high_risk: 0.70
    medium_risk: 0.40
```

### Risk Weights

Edit `config/risk_weights.yaml`:
```yaml
tender_risk_factors:
  price_anomaly:
    weight: 0.20
  winner_concentration:
    weight: 0.25
  # ... more factors
```

## Troubleshooting

### ImportError: No module named 'sklearn'

```bash
pip install -r requirements.txt
```

### Memory Error with Large Files

```bash
# Use chunked processing
python src/main.py --input data/large_file.csv --chunk-size 5000
```

### Dashboard Not Rendering

```bash
# Clear Streamlit cache
streamlit cache clear

# Run with verbose logging
streamlit run dashboard/app.py --logger.level=debug
```

### Database Connection Error

```bash
# Check PostgreSQL is running
docker exec procurement-db psql -U postgres -d procurement -c "SELECT 1"

# Or use SQLite instead
# config.yaml: database.backend: sqlite
```

## Security

### Production Deployment Checklist

- [ ] Use HTTPS (configure nginx reverse proxy)
- [ ] Set strong database passwords
- [ ] Enable authentication/authorization
- [ ] Restrict data access by role
- [ ] Enable audit logging
- [ ] Encrypt sensitive data
- [ ] Regular backups
- [ ] Keep dependencies updated

### Example Nginx Configuration

```nginx
server {
    listen 443 ssl;
    server_name procurement-detector.example.com;
    
    ssl_certificate /etc/ssl/certs/certificate.crt;
    ssl_certificate_key /etc/ssl/private/key.key;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Monitoring & Maintenance

### Logs

```bash
# View application logs
tail -f logs/system.log

# Rotate logs
# See config.yaml: logging.max_file_size_mb
```

### Performance Monitoring

```bash
# Monitor system resources
watch -n 1 'docker stats procurement-detector'

# Check database performance
# psql > SELECT * FROM pg_stat_statements;
```

### Regular Maintenance

- Weekly: Check logs, verify backup
- Monthly: Update dependencies, review results
- Quarterly: Performance audit, capacity planning

## Support & Documentation

- README.md: System overview
- config/config.yaml: Configuration reference
- src/*.py: Inline code documentation
- Dashboard UI: Interactive help

## Testing

### Run Unit Tests

```bash
pytest tests/ -v
```

### Test Analysis Pipeline

```bash
python -m pytest tests/test_analysis_pipeline.py
```

### Integration Tests

```bash
python tests/test_integration.py
```

## Version Management

```bash
# See version
python -c "from src import __version__; print(__version__)"

# Update version in src/__init__.py
```
