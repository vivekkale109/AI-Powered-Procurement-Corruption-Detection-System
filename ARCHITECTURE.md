"""
Project Architecture and Design Documentation
"""

# ARCHITECTURE & DESIGN DOCUMENT

## System Overview

The Procurement Corruption Detection System is a modular, AI-powered analytical platform designed to detect potential corruption patterns in public procurement data.

```
┌─────────────────────────────────────────────────────────────┐
│          INTERACTIVE DASHBOARD (Streamlit)                  │
├─────────────────────────────────────────────────────────────┤
│  Risk Visualization │ Network Graphs │ Contractor Rankings  │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┴────────────────┐
        │                              │
┌───────▼─────────────┐    ┌──────────▼──────────────┐
│  API Layer (Flask)  │    │ Report Generation Module│
└─────────────────────┘    └──────────────────────────┘
        │
        │
┌───────▼────────────────────────────────────────────────┐
│         ANALYSIS ENGINE (Core Processing)              │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ Data Ingestion  │  │ Feature Engineering      │   │
│  │ - Load CSV/JSON │  │ - Bid analysis           │   │
│  │ - Validate data │  │ - Contractor patterns    │   │
│  │ - Normalize     │  │ - Temporal features      │   │
│  └─────────────────┘  │ - Network metrics        │   │
│                       └──────────────────────────┘   │
│                                                        │
│  ┌─────────────────┐  ┌──────────────────────────┐   │
│  │ Anomaly         │  │ Network Analysis         │   │
│  │ Detection       │  │ - Graph construction     │   │
│  │ - Isolation     │  │ - Community detection    │   │
│  │   Forest        │  │ - Centrality measures    │   │
│  │ - LOF           │  │ - Rotation patterns      │   │
│  │ - Statistical   │  │ - Suspicious clusters    │   │
│  └─────────────────┘  └──────────────────────────┘   │
│                                                        │
│  ┌──────────────────────────────────────────────┐    │
│  │ Risk Scoring                                 │    │
│  │ - Tender-level (weighted factors)            │    │
│  │ - Contractor evaluation                      │    │
│  │ - Department analysis                        │    │
│  │ - Multi-factor assessment                    │    │
│  └──────────────────────────────────────────────┘    │
│                                                        │
└────────────────────────────────────────────────────────┘
        │
        │
┌───────▼────────────────────────────────────────────────┐
│    DATA & PERSISTENCE LAYER                            │
├────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌───────────────────────────┐  │
│  │ File Storage     │  │ Database Backend          │  │
│  │ CSV, JSON        │  │ PostgreSQL (optional)     │  │
│  │ Results, Reports │  │ Caching & Persistence    │  │
│  └──────────────────┘  └───────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

## Module Architecture

### 1. Data Ingestion (`src/data_ingestion.py`)

**Responsibility:** Load and validate procurement data

**Classes:**
- `DataValidator`: Validates data completeness and types
- `TenderDataLoader`: Loads from CSV/JSON/DataFrame
- `DataCleaner`: Cleans and standardizes data
- `DataIngestionPipeline`: Orchestrates the pipeline

**Key Features:**
- Multi-source support (CSV, JSON, DataFrame, Database)
- Data quality reporting
- Missing value handling
- Duplicate detection and removal
- Contractor name normalization

**Data Flow:**
```
Raw Data → Validation → Cleaning → Standardization → Processed Data
```

### 2. Feature Engineering (`src/feature_engineering.py`)

**Responsibility:** Compute advanced features for analysis

**Classes:**
- `BidAnalyzer`: Analyzes bid amounts and patterns
- `ContractorAnalyzer`: Contractor statistics and concentration
- `TemporalAnalyzer`: Time-based patterns
- `ParticipationAnalyzer`: Bidder set patterns
- `FeatureEngineer`: Orchestrates feature computation

**Engineered Features:**
```
Bid Features:
  - bid_deviation: Price deviation from estimate
  - bid_deviation_zscore: Standardized deviation
  - bid_variance: Variance across bids
  - bid_coefficient_variation: CV across bids
  - complementary_bid_score: Collusion indicator

Contractor Features:
  - win_frequency: Win rate per contractor
  - market_concentration (HHI): Winner concentration
  - geographic_concentration: Location focus
  - department_concentration: Department focus

Temporal Features:
  - winning_intervals: Days between wins
  - temporal_anomaly_score: Unusual timing
  - temporal_regularity: Predictability

Participation Features:
  - bidder_set_repetition: Repeated participants
  - co_participation: How often bidders meet
```

**Computation Order:**
1. Bid-level features (foundation)
2. Contractor-level aggregates
3. Temporal patterns
4. Participation analysis

### 3. Anomaly Detection (`src/anomaly_detection.py`)

**Responsibility:** Identify unusual and suspicious patterns

**Algorithms Implemented:**

```
Multi-Algorithm Ensemble
├── Isolation Forest (40% weight)
│   └── Isolates unusual observations
│       in high-dimensional space
│
├── Local Outlier Factor (35% weight)
│   └── Identifies local density deviations
│       in feature space
│
└── Statistical Methods (25% weight)
    ├── Z-score based (|z| > 3σ)
    ├── IQR method (1.5 * IQR)
    └── Domain-specific checks
```

**Anomaly Types Detected:**
- Price anomalies (bids far from market)
- Bidding collusion (complementary bids)
- Unusual winner patterns
- Bid concentration
- Temporal irregularities

**Composite Score:**
- Range: 0.0 to 1.0
- Threshold for flagging: > 0.5 (customizable)
- Combines normalized scores from all algorithms

### 4. Network Analysis (`src/network_analysis.py`)

**Responsibility:** Analyze contractor relationships and collusion networks

**Graph Representation:**
```
Nodes: Contractors
Edges: Co-participation (weighted by frequency)

Graph Properties:
- Density: How connected is the network
- Clustering: Tendency to form cliques
- Centrality: Nodes in hub positions
```

**Analysis Components:**

1. **Network Builder**
   - Constructs contractor co-participation graph
   - Weights edges by participation frequency
   - Minimum threshold: 2+ co-participations

2. **Community Detection**
   - Greedy modularity optimization
   - Identifies tight clusters of contractors
   - Flags as suspicious if density > threshold

3. **Centrality Analysis**
   - Degree centrality: Node connectivity
   - Betweenness: Bridge nodes between clusters
   - Closeness: Average distance to others
   - Eigenvector: Influence in network

4. **Rotation Pattern Detection**
   - Analyzes winner sequences
   - Identifies predictable patterns
   - Computes sequence regularity
   - Flags as rotation if regularity > threshold

**Suspicious Cluster Detection:**
```
Suspicion Score = f(density, clustering, triangles)

High suspicion indicates:
- Tight coordination between contractors
- Possible bid rotation
- Network-based collusion patterns
```

### 5. Risk Scoring (`src/risk_scoring.py`)

**Responsibility:** Compute corruption risk scores

**Scoring Hierarchy:**

```
Level 1: TENDER RISK
├── Price Anomaly (20%)
├── Winner Concentration (25%)
├── Participation Anomaly (18%)
├── Network Suspicion (20%)
└── Temporal Pattern (17%)
    ↓ Final Score: 0-1 scale

Level 2: CONTRACTOR RISK
├── Win Concentration (25%)
├── Geographic Concentration (17%)
├── Department Concentration (18%)
├── Network Centrality (20%)
└── Rotation Pattern (20%)
    ↓ Final Score: 0-1 scale, Ranking

Level 3: DEPARTMENT RISK
├── Anomaly Concentration (25%)
├── Winner Diversity (25%)
├── Price Inflation (20%)
├── Bidder Concentration (15%)
└── Complaint History (15%)
    ↓ Final Score: 0-1 scale, Ranking
```

**Risk Categories:**
- CRITICAL: ≥ 0.85
- HIGH: ≥ 0.70
- MEDIUM: ≥ 0.40
- LOW: < 0.40

**Scoring Process:**

```python
risk_score = Σ(component_score × weight)

where:
  component_score = normalized(0-1)
  weight = configured in risk_weights.yaml
  Σ(weights) = 1.0
```

### 6. Dashboard (`dashboard/app.py`)

**Responsibility:** Interactive visualization and analysis

**Technology Stack:**
- Streamlit: Web framework
- Plotly: Interactive charts
- NetworkX: Network visualization
- Pandas: Data manipulation

**Pages:**
1. **Overview**: System introduction
2. **Upload & Analyze**: Data upload, pipeline execution
3. **Risk Analysis**: Tender-level risk visualization
4. **Network Analysis**: Network graphs, clusters, patterns
5. **Contractor Insights**: Risk rankings, detailed metrics
6. **Department Analysis**: Department-level overview
7. **Export Report**: Report generation

**Key Visualizations:**
- Risk distribution pie charts
- Risk score histograms
- Risk factor heatmaps
- Network graphs
- Contractor rankings (bar charts)
- Trend analysis
- Comparative analysis

### 7. Reporting (`reports/report_generator.py`)

**Responsibility:** Generate analytical reports

**Report Types:**
- Executive Summary (management overview)
- Detailed Analysis (comprehensive findings)
- Network Report (collusion analysis)
- CVC Compliance (governance alignment)

**Report Contents:**
- Key statistics and metrics
- Risk findings and rankings
- Network analysis insights
- Recommendations
- Compliance checklist

## Data Flow Pipeline

```
Input Data (CSV/JSON)
        ↓
    Ingestion Pipeline
    • Load data
    • Validate schema
    • Check quality
        ↓
    Cleaned Data
    • Remove duplicates
    • Handle missing values
    • Normalize names
        ↓
    Feature Engineering
    • Compute 15+ features
    • Aggregate statistics
    • Create indicators
        ↓
    Enriched Data
    • Bid features
    • Contractor metrics
    • Temporal patterns
        ↓
    Anomaly Detection
    • Run 3 algorithms
    • Compute ensemble score
    • Flag anomalies
        ↓
    Network Analysis
    • Build graphs
    • Detect communities
    • Compute centrality
        ↓
    Risk Scoring
    • Tender-level: weighted factors
    • Contractor-level: comprehensive assessment
    • Department-level: aggregate metrics
        ↓
    Risk Scores & Rankings
    • Tender scores (0-1)
    • Contractor rankings
    • Department rankings
        ↓
    Visualization & Reporting
    • Interactive dashboard
    • HTML reports
    • Risk rankings
    • Network insights
```

## Configuration Management

**Config Files:**
- `config/config.yaml`: System settings
- `config/risk_weights.yaml`: Risk factors and weights

**Key Configuration Parameters:**

```yaml
Anomaly Detection:
  - contamination: Expected anomaly rate (0.05)
  - n_estimators: Forest size (100)

Risk Scoring:
  - tender weights: 5 factors
  - contractor weights: 5 factors
  - department weights: 5 factors
  - thresholds: CRITICAL/HIGH/MEDIUM/LOW

Feature Engineering:
  - time_window_days: Analysis period (365)
  - similarity_threshold: Fuzzy match (0.85)
```

## Scalability & Performance

### Current Constraints
- Single-threaded processing
- In-memory DataFrame
- ~10,000 records in <5 minutes

### Scalability to 1M+ Records

1. **Database Backend**
   - Switch to PostgreSQL
   - Query optimization
   - Partitioned tables

2. **Distributed Processing**
   - Apache Spark
   - Dask for parallel computation
   - Batch processing

3. **Caching**
   - Redis for feature cache
   - Materialized views
   - Incremental updates

4. **API Optimization**
   - Async processing (Celery)
   - Rate limiting
   - Response pagination

## Security & Privacy

**Data Protection:**
- Input validation
- SQL injection prevention (ORM)
- XSS protection (Streamlit built-in)

**Access Control:**
- Role-based (future)
- API key authentication (future)
- Audit logging

**Compliance:**
- CVC framework alignment
- RTI requirements
- Data retention policies

## Testing Strategy

**Unit Tests:**
- Feature engineering correctness
- Risk score calculations
- Data validation

**Integration Tests:**
- Full pipeline execution
- Report generation
- Dashboard functionality

**Performance Tests:**
- Scalability benchmarks
- Memory profiling
- Execution time tracking

## Deployment Options

1. **Local Development**
   - Direct Python execution
   - Streamlit development server

2. **Docker**
   - Containerized application
   - Reproducible environment
   - Easy scaling

3. **Cloud Platforms**
   - AWS ECS/EKS
   - Google Cloud Run
   - Azure Container Instances

4. **On-Premise**
   - Government data centers
   - Private network deployment
   - Full data control

## Future Enhancements

- [ ] Real-time monitoring dashboard
- [ ] Predictive model for future collusion
- [ ] Integration with audit workflows
- [ ] Advanced visualization (3D networks)
- [ ] Machine learning pipeline updates
- [ ] Multi-language support
- [ ] Mobile app
- [ ] Blockchain-based audit trail
