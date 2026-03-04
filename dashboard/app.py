"""
Interactive Dashboard using Streamlit.
Provides comprehensive visualization of corruption risk analysis results.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import networkx as nx
from datetime import datetime
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_ingestion import DataIngestionPipeline
from src.feature_engineering import FeatureEngineer
from src.anomaly_detection import AnomalyDetectionEngine
from src.network_analysis import NetworkAnalyzer
from src.risk_scoring import CorruptionRiskAssessor


def load_data(uploaded_file=None):
    """Load data from file or use sample data."""
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.success("✓ Data loaded successfully")
            return df
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None
    return None


def initialize_session_state():
    """Initialize session state variables."""
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'processed_data' not in st.session_state:
        st.session_state.processed_data = None


def main():
    """Main dashboard application."""
    # Page configuration
    st.set_page_config(
        page_title="Procurement Corruption Detection",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    initialize_session_state()
    
    # Sidebar
    st.sidebar.markdown("## 🔍 Procurement Corruption Detection System")
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio(
        "Navigation",
        ["Overview", "Upload & Analyze", "Risk Analysis", "Network Analysis", 
         "Contractor Insights", "Department Analysis", "Export Report"]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### System Status")
    
    # Main content
    if page == "Overview":
        show_overview()
    elif page == "Upload & Analyze":
        show_upload_analyze()
    elif page == "Risk Analysis":
        show_risk_analysis()
    elif page == "Network Analysis":
        show_network_analysis()
    elif page == "Contractor Insights":
        show_contractor_insights()
    elif page == "Department Analysis":
        show_department_analysis()
    elif page == "Export Report":
        show_export_report()


def show_overview():
    """Show overview page."""
    st.title("🏛️ Procurement Corruption Detection System")
    
    st.markdown("""
    ### AI-Powered Analytical System for Public Procurement Transparency
    
    This system detects potential corruption patterns in public procurement and tender bidding data through:
    
    **Core Capabilities:**
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("📊 **Anomaly Detection**\n\nMulti-algorithm detection using Isolation Forest, LOF, and statistical methods")
    
    with col2:
        st.info("🕸️ **Network Analysis**\n\nDetect contractor collusion networks and bid rotation patterns")
    
    with col3:
        st.info("⚠️ **Risk Scoring**\n\nMulti-factor corruption risk assessment at tender, contractor, and department levels")
    
    st.markdown("""
    ### Key Features
    
    - **Data Ingestion**: Process tender records with structured attributes
    - **Preprocessing**: Name normalization, data cleaning, quality validation
    - **Feature Engineering**: Compute 15+ advanced features from raw data
    - **Anomaly Detection**: Identify unusual patterns and suspicious outliers
    - **Network Analysis**: Build and analyze contractor relationship graphs
    - **Comprehensive Risk Scoring**: Weighted multi-factor risk assessment
    - **Interactive Visualizations**: Heatmaps, graphs, trends, and rankings
    - **Detailed Reporting**: Export analysis reports for governance review
    
    ### Governance Alignment
    
    The system aligns with governance oversight principles similar to:
    - Central Vigilance Commission (CVC) frameworks
    - Public Procurement Act requirements
    - Transparency and anti-corruption standards
    """)
    
    st.markdown("---")
    st.markdown("**Getting Started**: Upload procurement data using the 'Upload & Analyze' section")


def show_upload_analyze():
    """Show upload and analysis page."""
    st.title("📤 Upload & Analyze")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### Upload Tender Data")
        st.markdown("Supported format: CSV with columns like tender_id, department, estimated_cost, etc.")
        
        uploaded_file = st.file_uploader(
            "Choose a CSV file with tender data",
            type=['csv'],
            key='data_upload'
        )
    
    with col2:
        st.markdown("### Data Format")
        st.markdown("""
        **Required Columns:**
        - tender_id
        - department
        - estimated_cost
        - participating_bidders
        - bid_amounts
        - winning_bidder
        - tender_date
        - location
        """)
    
    if uploaded_file is not None:
        try:
            # Streamlit uploader returns an UploadedFile object.
            # Convert it to DataFrame before passing to the ingestion pipeline.
            raw_df = pd.read_csv(uploaded_file)
            pipeline = DataIngestionPipeline(raw_df)
            df = pipeline.execute()
            
            st.session_state.processed_data = df
            
            st.success("✓ Data loaded and preprocessed")
            
            # Display data summary
            st.subheader("Data Summary")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Tenders", len(df))
            with col2:
                st.metric("Departments", df['department'].nunique())
            with col3:
                st.metric("Locations", df['location'].nunique() if 'location' in df.columns else 0)
            with col4:
                st.metric("Date Range", f"{df['tender_date'].min().date()}" if 'tender_date' in df.columns else "N/A")
            
            # Show data preview
            with st.expander("View Data Preview"):
                st.dataframe(df.head(10), use_container_width=True)
            
            # Run analysis button
            if st.button("▶️ Run Complete Analysis", key='run_analysis', use_container_width=True):
                with st.spinner("Analyzing data... This may take a minute"):
                    try:
                        # Feature engineering
                        feature_engineer = FeatureEngineer()
                        df = feature_engineer.engineer_features(df)
                        
                        # Anomaly detection
                        anomaly_engine = AnomalyDetectionEngine(contamination=0.05)
                        df = anomaly_engine.detect_anomalies(df)
                        
                        # Network analysis
                        network_analyzer = NetworkAnalyzer()
                        network_results = network_analyzer.analyze(df)
                        
                        # Risk scoring
                        risk_assessor = CorruptionRiskAssessor()
                        risk_results = risk_assessor.assess_risk(df, network_results)
                        
                        st.session_state.analysis_results = {
                            'data': df,
                            'network': network_results,
                            'risk': risk_results
                        }
                        st.session_state.analysis_complete = True
                        
                        st.success("✓ Analysis complete! Navigate to other sections to view results.")
                        
                    except Exception as e:
                        st.error(f"Analysis failed: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
        
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")


def show_risk_analysis():
    """Show tender-level risk analysis."""
    st.title("⚠️ Tender Risk Analysis")
    
    if not st.session_state.analysis_complete:
        st.warning("⚠️ Please upload data and run analysis first")
        return
    
    results = st.session_state.analysis_results
    tender_scores = results['risk']['tender_scores']
    
    # Risk distribution
    col1, col2 = st.columns(2)
    
    with col1:
        # Risk category pie chart
        risk_counts = tender_scores['risk_category'].value_counts()
        
        fig = go.Figure(data=[
            go.Pie(
                labels=risk_counts.index,
                values=risk_counts.values,
                marker=dict(colors=['#d62728', '#ff7f0e', '#2ca02c', '#1f77b4'])
            )
        ])
        fig.update_layout(title="Risk Distribution by Category", height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Risk score distribution
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=tender_scores['final_risk_score'],
            nbinsx=30,
            marker=dict(color='rgba(255, 127, 14, 0.7)')
        ))
        fig.update_layout(
            title="Risk Score Distribution",
            xaxis_title="Risk Score",
            yaxis_title="Count",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # High-risk tenders
    st.subheader("🔴 High-Risk Tenders")
    
    high_risk = tender_scores[tender_scores['risk_category'].isin(['CRITICAL', 'HIGH'])].copy()
    high_risk = high_risk.sort_values('final_risk_score', ascending=False)
    
    if len(high_risk) > 0:
        display_cols = ['tender_id', 'price_anomaly', 'winner_concentration', 
                       'participation_anomaly', 'network_suspicion', 'final_risk_score', 'risk_category']
        available_cols = [col for col in display_cols if col in high_risk.columns]
        
        st.dataframe(
            high_risk[available_cols].head(20),
            use_container_width=True
        )
    else:
        st.info("No high-risk tenders detected")
    
    # Risk factor heatmap
    st.subheader("Risk Factor Heatmap")
    
    risk_factors = ['price_anomaly', 'winner_concentration', 'participation_anomaly', 
                    'complementary_bids', 'temporal_pattern', 'network_suspicion']
    
    if all(col in tender_scores.columns for col in risk_factors):
        heatmap_data = tender_scores[risk_factors].head(30)
        
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=risk_factors,
            y=[f"Tender {i}" for i in range(len(heatmap_data))],
            colorscale='RdYlGn_r'
        ))
        fig.update_layout(height=500, title="Risk Factors Heatmap (Top 30 Tenders)")
        st.plotly_chart(fig, use_container_width=True)


def show_network_analysis():
    """Show network analysis visualization."""
    st.title("🕸️ Network Analysis")
    
    if not st.session_state.analysis_complete:
        st.warning("⚠️ Please upload data and run analysis first")
        return
    
    results = st.session_state.analysis_results
    network_results = results['network']
    
    st.subheader("Network Statistics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    stats = network_results['network_stats']
    with col1:
        st.metric("Nodes", stats['num_nodes'])
    with col2:
        st.metric("Edges", stats['num_edges'])
    with col3:
        st.metric("Density", f"{stats['density']:.3f}")
    with col4:
        st.metric("Avg Clustering", f"{stats['avg_clustering']:.3f}")
    with col5:
        st.metric("Triangles", stats['num_triangles'])
    
    st.subheader("Suspicious Clusters")
    
    suspicious = network_results['suspicious_clusters']
    
    if suspicious:
        cluster_data = []
        for cluster_id, cluster_info in suspicious.items():
            cluster_data.append({
                'Cluster ID': cluster_id,
                'Members': len(cluster_info['members']),
                'Suspicion Score': f"{cluster_info['suspicion_score']:.3f}",
                'Contractors': ', '.join(cluster_info['members'][:3]) + ('...' if len(cluster_info['members']) > 3 else '')
            })
        
        st.dataframe(pd.DataFrame(cluster_data), use_container_width=True)
    else:
        st.info("No suspicious clusters detected")
    
    # Rotation patterns
    st.subheader("Bid Rotation Patterns")
    
    rotation_patterns = network_results['rotation_patterns']
    
    if rotation_patterns:
        rotation_data = []
        for contractor, metrics in list(rotation_patterns.items())[:20]:
            if metrics.get('rotation_score', 0) > 0.3:
                rotation_data.append({
                    'Contractor': contractor,
                    'Rotation Score': f"{metrics['rotation_score']:.3f}",
                    'Total Wins': len(metrics['wins']),
                    'Interval Variance': f"{metrics['interval_variance']:.0f}"
                })
        
        if rotation_data:
            st.dataframe(pd.DataFrame(rotation_data), use_container_width=True)
        else:
            st.info("No significant rotation patterns detected")
    else:
        st.info("No rotation analysis available")


def show_contractor_insights():
    """Show contractor-level analysis."""
    st.title("🏢 Contractor Risk Insights")
    
    if not st.session_state.analysis_complete:
        st.warning("⚠️ Please upload data and run analysis first")
        return
    
    results = st.session_state.analysis_results
    contractor_scores = results['risk']['contractor_scores']
    
    # Contractor ranking
    st.subheader("Contractor Risk Ranking")
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        min_wins = st.slider("Minimum Wins", 0, int(contractor_scores['total_wins'].max()), 5)
    
    with col2:
        risk_filter = st.selectbox(
            "Filter by Risk Level",
            ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"]
        )
    
    with col3:
        top_n = st.slider("Show Top N", 5, 50, 20)
    
    # Apply filters
    filtered = contractor_scores[contractor_scores['total_wins'] >= min_wins]
    
    if risk_filter != "ALL":
        filtered = filtered[filtered['risk_category'] == risk_filter]
    
    filtered = filtered.head(top_n)
    
    # Risk score chart
    fig = px.bar(
        filtered.sort_values('final_risk_score', ascending=True),
        x='final_risk_score',
        y='contractor',
        color='risk_category',
        color_discrete_map={
            'CRITICAL': '#d62728',
            'HIGH': '#ff7f0e',
            'MEDIUM': '#2ca02c',
            'LOW': '#1f77b4'
        },
        title="Contractor Risk Scores"
    )
    fig.update_layout(height=500, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)
    
    # Detailed metrics
    st.subheader("Detailed Metrics")
    
    display_cols = ['contractor', 'final_risk_score', 'risk_category', 'total_wins', 
                   'win_rate', 'geographic_concentration', 'network_centrality']
    available_cols = [col for col in display_cols if col in filtered.columns]
    
    st.dataframe(filtered[available_cols], use_container_width=True)


def show_department_analysis():
    """Show department-level analysis."""
    st.title("🏦 Department Analysis")
    
    if not st.session_state.analysis_complete:
        st.warning("⚠️ Please upload data and run analysis first")
        return
    
    results = st.session_state.analysis_results
    dept_scores = results['risk']['department_scores']
    
    st.subheader("Department Risk Overview")
    
    # Department risk chart
    fig = px.bar(
        dept_scores.sort_values('final_risk_score', ascending=False),
        x='department',
        y='final_risk_score',
        color='risk_category',
        color_discrete_map={
            'CRITICAL': '#d62728',
            'HIGH': '#ff7f0e',
            'MEDIUM': '#2ca02c',
            'LOW': '#1f77b4'
        },
        title="Department Risk Scores"
    )
    fig.update_layout(height=400, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    # Department metrics table
    st.subheader("Department Metrics")
    
    if 'total_tenders' in dept_scores.columns:
        cols = ['department', 'final_risk_score', 'risk_category', 'total_tenders', 
               'unique_winners', 'anomaly_concentration', 'winner_concentration', 'price_inflation']
        available_cols = [col for col in cols if col in dept_scores.columns]
        
        st.dataframe(dept_scores[available_cols], use_container_width=True)


def show_export_report():
    """Show export and reporting options."""
    st.title("📄 Export & Reporting")
    
    if not st.session_state.analysis_complete:
        st.warning("⚠️ Please upload data and run analysis first")
        return
    
    st.subheader("Generate Report")
    
    report_type = st.selectbox(
        "Select Report Type",
        ["Executive Summary", "Detailed Analysis", "Risk Rankings", "Network Analysis", "All Reports"]
    )
    
    include_charts = st.checkbox("Include visualizations", value=True)
    include_data = st.checkbox("Include detailed data tables", value=True)
    
    if st.button("Generate Report", use_container_width=True):
        st.info("📊 Report generation feature coming soon")
        st.markdown("""
        The system will generate:
        - **Executive Summary**: Key findings and recommendations
        - **Risk Analysis**: Detailed tender and contractor risk assessments
        - **Network Insights**: Collusion patterns and suspicious clusters
        - **Department Review**: Procurement integrity by department
        - **Governance Compliance**: Alignment with CVC framework
        """)


if __name__ == "__main__":
    main()
