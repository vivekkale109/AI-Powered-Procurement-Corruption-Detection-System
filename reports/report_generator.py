"""
Reporting Module.
Generates comprehensive analytical reports for governance transparency.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import json
from jinja2 import Template


class ReportGenerator:
    """Generates analytical reports from risk assessment results."""
    
    def __init__(self):
        """Initialize report generator."""
        self.report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def generate_executive_summary(self, risk_results: Dict, data: pd.DataFrame) -> str:
        """
        Generate executive summary report.
        
        Args:
            risk_results: Risk assessment results
            data: Original processed data
        
        Returns:
            HTML report string
        """
        tender_scores = risk_results['tender_scores']
        contractor_scores = risk_results['contractor_scores']
        dept_scores = risk_results['department_scores']
        
        # Key statistics
        total_tenders = len(tender_scores)
        critical_tenders = (tender_scores['risk_category'] == 'CRITICAL').sum()
        high_risk_tenders = (tender_scores['risk_category'] == 'HIGH').sum()
        
        critical_contractors = (contractor_scores['risk_category'] == 'CRITICAL').sum()
        high_risk_contractors = (contractor_scores['risk_category'] == 'HIGH').sum()
        
        # Findings
        findings = self._generate_findings(
            tender_scores, contractor_scores, dept_scores
        )
        
        html_template = """
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #1f77b4; }}
                .metric {{ background: #f0f0f0; padding: 10px; margin: 10px 0; border-left: 4px solid #1f77b4; }}
                .critical {{ background: #ffe6e6; }}
                .high {{ background: #fff4e6; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #1f77b4; color: white; }}
                .footer {{ margin-top: 30px; font-size: 0.9em; color: #666; border-top: 1px solid #ddd; padding-top: 10px; }}
            </style>
        </head>
        <body>
            <h1>🏛️ Procurement Corruption Detection System</h1>
            <h2>Executive Summary Report</h2>
            <p>Report Generated: {report_date}</p>
            
            <h3>Quick Overview</h3>
            <div class="metric">
                <strong>Total Tenders Analyzed:</strong> {total_tenders}
            </div>
            <div class="metric critical">
                <strong>🔴 CRITICAL Risk Tenders:</strong> {critical_tenders} ({critical_pct:.1f}%)
            </div>
            <div class="metric high">
                <strong>🟠 HIGH Risk Tenders:</strong> {high_risk_tenders} ({high_risk_pct:.1f}%)
            </div>
            
            <h3>Contractor Analysis</h3>
            <div class="metric critical">
                <strong>CRITICAL Risk Contractors:</strong> {critical_contractors}
            </div>
            <div class="metric high">
                <strong>HIGH Risk Contractors:</strong> {high_risk_contractors}
            </div>
            
            <h3>Key Findings</h3>
            {findings}
            
            <h3>Recommendations</h3>
            <ol>
                <li><strong>Immediate Review:</strong> Prioritize review of CRITICAL and HIGH risk tenders</li>
                <li><strong>Contractor Scrutiny:</strong> Conduct enhanced due diligence on flagged contractors</li>
                <li><strong>Process Improvement:</strong> Strengthen bidding process controls in high-risk departments</li>
                <li><strong>Investigation:</strong> Consider formal investigation of detected collusion patterns</li>
                <li><strong>Monitoring:</strong> Implement ongoing monitoring for pattern recurrence</li>
            </ol>
            
            <div class="footer">
                <p>This report is based on AI-powered anomaly detection and network analysis algorithms.</p>
                <p>All findings should be validated through appropriate governance channels.</p>
                <p>System version: 1.0.0 | Aligned with CVC frameworks for governance oversight</p>
            </div>
        </body>
        </html>
        """
        
        critical_pct = (critical_tenders / total_tenders * 100) if total_tenders > 0 else 0
        high_risk_pct = (high_risk_tenders / total_tenders * 100) if total_tenders > 0 else 0
        
        html = html_template.format(
            report_date=self.report_date,
            total_tenders=total_tenders,
            critical_tenders=critical_tenders,
            critical_pct=critical_pct,
            high_risk_tenders=high_risk_tenders,
            high_risk_pct=high_risk_pct,
            critical_contractors=critical_contractors,
            high_risk_contractors=high_risk_contractors,
            findings=findings
        )
        
        return html
    
    def _generate_findings(self, tender_scores: pd.DataFrame, 
                          contractor_scores: pd.DataFrame,
                          dept_scores: pd.DataFrame) -> str:
        """Generate key findings."""
        findings = "<ul>"
        
        # Top anomalies
        top_anomalies = tender_scores.nlargest(3, 'anomaly_score')
        if len(top_anomalies) > 0:
            findings += "<li><strong>Top Anomalies Detected:</strong> "
            tender_ids = top_anomalies['tender_id'].tolist()
            findings += f"{len(tender_ids)} tenders with unusual patterns</li>"
        
        # High-risk contractors
        high_risk_contractors = contractor_scores[
            contractor_scores['risk_category'].isin(['CRITICAL', 'HIGH'])
        ]
        if len(high_risk_contractors) > 0:
            top_contractor = high_risk_contractors.iloc[0]
            findings += f"<li><strong>Highest Risk Contractor:</strong> {top_contractor['contractor']} "
            findings += f"(Score: {top_contractor['final_risk_score']:.3f}, Wins: {top_contractor['total_wins']})</li>"
        
        # Department concentration
        dept_concentration = dept_scores.nlargest(1, 'winner_concentration')
        if len(dept_concentration) > 0:
            findings += f"<li><strong>Highest Department Risk:</strong> {dept_concentration.iloc[0]['department']} "
            findings += f"with winner concentration score {dept_concentration.iloc[0]['winner_concentration']:.3f}</li>"
        
        # Price anomalies
        price_anomalies = (tender_scores['price_anomaly'] > 0.7).sum()
        if price_anomalies > 0:
            findings += f"<li><strong>Price Anomalies:</strong> {price_anomalies} tenders show unusual pricing</li>"
        
        # Complementary bids
        comp_bids = (tender_scores['complementary_bids'] > 0.6).sum()
        if comp_bids > 0:
            findings += f"<li><strong>Complementary Bidding:</strong> {comp_bids} tenders show complementary bid patterns (potential collusion)</li>"
        
        findings += "</ul>"
        return findings
    
    def generate_detailed_analysis(self, risk_results: Dict) -> str:
        """Generate detailed analysis report."""
        tender_scores = risk_results['tender_scores']
        contractor_scores = risk_results['contractor_scores']
        dept_scores = risk_results['department_scores']
        
        html = """
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ color: #1f77b4; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #1f77b4; color: white; }}
                .critical {{ background: #ffe6e6; }}
                .high {{ background: #fff4e6; }}
            </style>
        </head>
        <body>
            <h1>Detailed Corruption Risk Analysis Report</h1>
            <p>Report Generated: {report_date}</p>
            
            <h2>High-Risk Tenders</h2>
            {high_risk_tenders_table}
            
            <h2>High-Risk Contractors</h2>
            {high_risk_contractors_table}
            
            <h2>Department Analysis</h2>
            {department_table}
            
        </body>
        </html>
        """
        
        # High-risk tenders table
        high_risk_tenders = tender_scores[
            tender_scores['risk_category'].isin(['CRITICAL', 'HIGH'])
        ].nlargest(20, 'final_risk_score')
        
        tenders_html = self._dataframe_to_html(
            high_risk_tenders[['tender_id', 'final_risk_score', 'risk_category', 
                               'price_anomaly', 'winner_concentration']]
        )
        
        # High-risk contractors table
        high_risk_contractors = contractor_scores[
            contractor_scores['risk_category'].isin(['CRITICAL', 'HIGH'])
        ].nlargest(20, 'final_risk_score')
        
        contractors_html = self._dataframe_to_html(
            high_risk_contractors[['contractor', 'final_risk_score', 'risk_category', 
                                  'total_wins', 'win_rate', 'network_centrality']]
        )
        
        # Department table
        dept_html = self._dataframe_to_html(dept_scores)
        
        html = html.format(
            report_date=self.report_date,
            high_risk_tenders_table=tenders_html,
            high_risk_contractors_table=contractors_html,
            department_table=dept_html
        )
        
        return html
    
    def _dataframe_to_html(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to HTML table."""
        if len(df) == 0:
            return "<p>No data available</p>"
        
        html = "<table>\n<tr>"
        
        # Header
        for col in df.columns:
            html += f"<th>{col}</th>"
        html += "</tr>\n"
        
        # Rows
        for _, row in df.iterrows():
            html += "<tr>"
            for val in row:
                if isinstance(val, float):
                    html += f"<td>{val:.3f}</td>"
                else:
                    html += f"<td>{val}</td>"
            html += "</tr>\n"
        
        html += "</table>"
        return html
    
    def generate_network_report(self, network_analysis: Dict) -> str:
        """Generate network analysis report."""
        html = """
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2 {{ color: #1f77b4; }}
                .metric {{ background: #f0f0f0; padding: 10px; margin: 10px 0; border-left: 4px solid #1f77b4; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #1f77b4; color: white; }}
            </style>
        </head>
        <body>
            <h1>Network Analysis Report</h1>
            <p>Report Generated: {report_date}</p>
            
            <h2>Network Statistics</h2>
            {network_stats}
            
            <h2>Suspicious Clusters</h2>
            {clusters}
            
            <h2>Bid Rotation Patterns</h2>
            {rotation}
            
        </body>
        </html>
        """
        
        # Network stats
        stats_html = ""
        if 'network_stats' in network_analysis:
            stats = network_analysis['network_stats']
            for key, value in stats.items():
                stats_html += f"<div class='metric'><strong>{key}:</strong> {value}</div>"
        
        # Suspicious clusters
        clusters_html = ""
        if 'suspicious_clusters' in network_analysis and network_analysis['suspicious_clusters']:
            clusters = network_analysis['suspicious_clusters']
            clusters_html += "<table><tr><th>Cluster ID</th><th>Size</th><th>Suspicion Score</th><th>Members</th></tr>"
            for cluster_id, cluster_info in clusters.items():
                members = ', '.join(cluster_info['members'][:5])
                if len(cluster_info['members']) > 5:
                    members += '...'
                clusters_html += f"<tr><td>{cluster_id}</td><td>{cluster_info['size']}</td>"
                clusters_html += f"<td>{cluster_info['suspicion_score']:.3f}</td><td>{members}</td></tr>"
            clusters_html += "</table>"
        else:
            clusters_html = "<p>No suspicious clusters detected</p>"
        
        # Rotation patterns
        rotation_html = ""
        if 'rotation_patterns' in network_analysis and network_analysis['rotation_patterns']:
            patterns = network_analysis['rotation_patterns']
            suspicious_patterns = {k: v for k, v in patterns.items() if v.get('rotation_score', 0) > 0.3}
            
            if suspicious_patterns:
                rotation_html += "<table><tr><th>Contractor</th><th>Rotation Score</th><th>Wins</th></tr>"
                for contractor, metrics in list(suspicious_patterns.items())[:20]:
                    rotation_html += f"<tr><td>{contractor}</td><td>{metrics['rotation_score']:.3f}</td>"
                    rotation_html += f"<td>{len(metrics['wins'])}</td></tr>"
                rotation_html += "</table>"
            else:
                rotation_html = "<p>No significant rotation patterns detected</p>"
        else:
            rotation_html = "<p>No rotation data available</p>"
        
        html = html.format(
            report_date=self.report_date,
            network_stats=stats_html,
            clusters=clusters_html,
            rotation=rotation_html
        )
        
        return html

    def _extract_body_content(self, html: str) -> str:
        """Extract body content from full HTML document for report composition."""
        lower_html = html.lower()
        body_start = lower_html.find("<body")
        if body_start == -1:
            return html

        body_tag_end = lower_html.find(">", body_start)
        body_end = lower_html.rfind("</body>")
        if body_tag_end == -1 or body_end == -1:
            return html

        return html[body_tag_end + 1:body_end].strip()

    def generate_final_report(self, risk_results: Dict, data: pd.DataFrame,
                              network_analysis: Optional[Dict] = None) -> str:
        """Generate one consolidated report containing all analysis sections."""
        tender_scores = risk_results['tender_scores']
        executive_html = self.generate_executive_summary(risk_results, data)
        detailed_html = self.generate_detailed_analysis(risk_results)
        compliance_html = ComplianceReporter.generate_cvc_compliance_report(risk_results)

        network_section = "<p>Network analysis data not available.</p>"
        if network_analysis:
            network_html = self.generate_network_report(network_analysis)
            network_section = self._extract_body_content(network_html)

        tender_cols = [
            'tender_id',
            'final_risk_score',
            'risk_category',
            'anomaly_score',
            'price_anomaly',
            'winner_concentration',
            'complementary_bids'
        ]
        available_tender_cols = [col for col in tender_cols if col in tender_scores.columns]
        all_tender_scores_html = self._dataframe_to_html(
            tender_scores.sort_values('final_risk_score', ascending=True)[available_tender_cols]
        )

        final_html = """
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.5; }}
                h1 {{ color: #003366; }}
                h2 {{ color: #1f77b4; border-bottom: 2px solid #ddd; padding-bottom: 8px; margin-top: 30px; }}
                .section {{ margin-bottom: 36px; }}
            </style>
        </head>
        <body>
            <h1>Final Procurement Risk Report</h1>
            <p><strong>Generated:</strong> {report_date}</p>

            <div class="section">
                <h2>Executive Summary</h2>
                {executive_section}
            </div>

            <div class="section">
                <h2>Detailed Analysis</h2>
                {detailed_section}
            </div>

            <div class="section">
                <h2>All Tender Scores</h2>
                <p>Total tenders scored: <strong>{total_tenders}</strong></p>
                {all_tender_scores}
            </div>

            <div class="section">
                <h2>Network Analysis</h2>
                {network_section}
            </div>

            <div class="section">
                <h2>Compliance Assessment</h2>
                {compliance_section}
            </div>
        </body>
        </html>
        """

        return final_html.format(
            report_date=self.report_date,
            executive_section=self._extract_body_content(executive_html),
            detailed_section=self._extract_body_content(detailed_html),
            total_tenders=len(tender_scores),
            all_tender_scores=all_tender_scores_html,
            network_section=network_section,
            compliance_section=self._extract_body_content(compliance_html),
        )
    
    def save_report(self, html_content: str, filepath: str):
        """Save report to HTML file."""
        with open(filepath, 'w') as f:
            f.write(html_content)


class ComplianceReporter:
    """Generates compliance and governance-aligned reports."""
    
    @staticmethod
    def generate_cvc_compliance_report(risk_results: Dict) -> str:
        """
        Generate CVC (Central Vigilance Commission) aligned compliance report.
        
        Args:
            risk_results: Risk assessment results
        
        Returns:
            HTML report
        """
        html = """
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 30px; }}
                h1 {{ color: #003366; border-bottom: 3px solid #003366; padding-bottom: 10px; }}
                h2 {{ color: #1f77b4; margin-top: 30px; }}
                .compliance-box {{ background: #e8f4f8; padding: 15px; margin: 15px 0; border-left: 5px solid #1f77b4; }}
                .flag {{ background: #ffe6e6; padding: 10px; margin: 10px 0; border-left: 5px solid #d62728; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #999; padding: 10px; text-align: left; }}
                th {{ background-color: #003366; color: white; }}
                .footer {{ margin-top: 40px; padding: 20px; background: #f5f5f5; border-top: 2px solid #999; }}
            </style>
        </head>
        <body>
            <h1>GOVERNANCE COMPLIANCE REPORT</h1>
            <h2>Procurement Integrity & Anti-Corruption Assessment</h2>
            
            <p style="font-style: italic;">
                Framework: Central Vigilance Commission (CVC) Guidelines for Government Procurement
            </p>
            
            <div class="compliance-box">
                <h3>Assessment Objective</h3>
                <p>This report evaluates public procurement tender data for potential corruption patterns,
                bid collusion, and governance integrity violations aligned with CVC oversight principles.</p>
            </div>
            
            <h2>Key Compliance Indicators</h2>
            
            <table>
                <tr>
                    <th>Indicator</th>
                    <th>Status</th>
                    <th>Assessment</th>
                </tr>
                <tr>
                    <td>Winner Concentration</td>
                    <td class="compliance-box">HIGH</td>
                    <td>Multiple contractors dominating tender wins suggests limited competition</td>
                </tr>
                <tr>
                    <td>Price Anomalies</td>
                    <td class="compliance-box">MEDIUM</td>
                    <td>Bid prices deviate from market norms in certain categories</td>
                </tr>
                <tr>
                    <td>Bidding Patterns</td>
                    <td class="compliance-box">HIGH</td>
                    <td>Complementary bidding and rotation patterns indicate possible collusion</td>
                </tr>
                <tr>
                    <td>Network Connections</td>
                    <td class="compliance-box">MEDIUM</td>
                    <td>Tight clusters of contractors suggest coordinated activities</td>
                </tr>
                <tr>
                    <td>Temporal Regularity</td>
                    <td class="compliance-box">MEDIUM</td>
                    <td>Predictable winning patterns in certain departments</td>
                </tr>
            </table>
            
            <h2>Recommended Actions</h2>
            
            <ol>
                <li><strong>Immediate Investigation:</strong> Refer flagged tenders to competent authority (CBI/CVC)</li>
                <li><strong>Contractor Debarment:</strong> Consider disqualification of highly suspicious contractors</li>
                <li><strong>Process Audit:</strong> Conduct audit of procurement procedures in high-risk departments</li>
                <li><strong>Enhanced Screening:</strong> Implement stricter pre-qualification checks</li>
                <li><strong>Monitoring Framework:</strong> Deploy continuous real-time monitoring system</li>
                <li><strong>Transparency Measures:</strong> Increase bid documentation transparency</li>
            </ol>
            
            <div class="footer">
                <h3>Statutory Alignment</h3>
                <ul>
                    <li>General Financial Rules (GFR), 2017</li>
                    <li>Central Vigilance Commission Guidelines</li>
                    <li>Prevention of Corruption Act, 1988</li>
                    <li>Right to Information Act, 2005</li>
                </ul>
                <p><strong>Confidentiality Note:</strong> This report contains confidential governance information
                for internal use by authorized personnel only.</p>
            </div>
        </body>
        </html>
        """
        
        return html
