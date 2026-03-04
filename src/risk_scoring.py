"""
Corruption Risk Scoring Module.
Computes multi-factor corruption risk scores for tenders, contractors, and departments.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

from .utils import Logger, load_risk_weights, calculate_herfindahl_index

logger = Logger(__name__)


class RiskScorer:
    """Base class for risk scoring."""
    
    def __init__(self, weights_config: Dict = None):
        """
        Initialize scorer.
        
        Args:
            weights_config: Dictionary with risk weights
        """
        self.weights_config = weights_config or load_risk_weights()
        self.risk_scores = {}
    
    def normalize_score(self, score: float, min_val: float = 0, max_val: float = 1) -> float:
        """Normalize score to 0-1 range."""
        if max_val == min_val:
            return 0
        return np.clip((score - min_val) / (max_val - min_val), 0, 1)
    
    def get_risk_category(self, score: float, thresholds: Dict = None) -> str:
        """
        Categorize risk level.
        
        Args:
            score: Risk score (0-1)
            thresholds: Category thresholds
        
        Returns:
            Risk category
        """
        if thresholds is None:
            thresholds = {
                'critical': 0.85,
                'high': 0.70,
                'medium': 0.40,
                'low': 0.00
            }
        
        if score >= thresholds.get('critical', 0.85):
            return 'CRITICAL'
        elif score >= thresholds.get('high', 0.70):
            return 'HIGH'
        elif score >= thresholds.get('medium', 0.40):
            return 'MEDIUM'
        else:
            return 'LOW'


class TenderRiskScorer(RiskScorer):
    """Scores risk for individual tenders."""
    
    def score_tender(self, tender: pd.Series, contractor_stats: Dict = None,
                    network_analysis: Dict = None) -> Dict:
        """
        Compute corruption risk score for a tender.
        
        Args:
            tender: Series with tender data
            contractor_stats: Dictionary with contractor statistics
            network_analysis: Network analysis results
        
        Returns:
            Dictionary with risk scores and components
        """
        scores = {}
        
        # 1. Price anomaly
        price_score = 0
        if 'bid_deviation_zscore' in tender.index and pd.notna(tender['bid_deviation_zscore']):
            price_score = min(abs(tender['bid_deviation_zscore']) / 3.0, 1.0)
        scores['price_anomaly'] = price_score
        
        # 2. Winner concentration (win rate)
        winner_score = 0
        if contractor_stats and tender['winning_bidder_normalized'] in contractor_stats:
            stats = contractor_stats[tender['winning_bidder_normalized']]
            win_rate = stats.get('win_rate', 0)
            # High win rate is suspicious
            winner_score = min(win_rate * 1.5, 1.0)
        scores['winner_concentration'] = winner_score
        
        # 3. Bid participation anomaly
        participation_score = 0
        if 'bidder_set_repetition' in tender.index and pd.notna(tender['bidder_set_repetition']):
            participation_score = tender['bidder_set_repetition']
        scores['participation_anomaly'] = participation_score
        
        # 4. Complementary bidding pattern
        comp_score = 0
        if 'complementary_bid_score' in tender.index and pd.notna(tender['complementary_bid_score']):
            comp_score = tender['complementary_bid_score']
        scores['complementary_bids'] = comp_score
        
        # 5. Temporal anomaly
        temporal_score = 0
        if 'temporal_anomaly_score' in tender.index and pd.notna(tender['temporal_anomaly_score']):
            temporal_score = tender['temporal_anomaly_score']
        scores['temporal_pattern'] = temporal_score
        
        # 6. Network-based suspicion
        network_score = 0
        if network_analysis and 'centrality' in network_analysis:
            contractor = tender['winning_bidder_normalized']
            if contractor in network_analysis['centrality']:
                centrality_data = network_analysis['centrality'][contractor]
                # High centrality + high betweenness = suspicious
                network_score = np.mean([
                    centrality_data.get('degree', 0),
                    centrality_data.get('betweenness', 0) * 0.7
                ])
        scores['network_suspicion'] = network_score
        
        # 7. Combined anomaly score
        anomaly_score = tender.get('anomaly_score', 0) if 'anomaly_score' in tender.index else 0
        scores['anomaly_detection'] = anomaly_score
        
        # Compute weighted final score
        weights = self.weights_config.get('tender_risk_factors', {})
        final_score = (
            scores['price_anomaly'] * weights.get('price_anomaly', {}).get('weight', 0.2) +
            scores['winner_concentration'] * weights.get('winner_concentration', {}).get('weight', 0.25) +
            scores['participation_anomaly'] * weights.get('participation_anomaly', {}).get('weight', 0.18) +
            scores['network_suspicion'] * weights.get('network_suspicion', {}).get('weight', 0.2) +
            scores['temporal_pattern'] * weights.get('temporal_pattern', {}).get('weight', 0.17)
        )
        
        scores['final_risk_score'] = final_score
        scores['risk_category'] = self.get_risk_category(final_score)
        
        return scores


class ContractorRiskScorer(RiskScorer):
    """Scores corruption risk for contractors."""
    
    def score_contractors(self, df: pd.DataFrame, network_analysis: Dict = None) -> pd.DataFrame:
        """
        Compute risk scores for all contractors.
        
        Args:
            df: DataFrame with tender data
            network_analysis: Network analysis results
        
        Returns:
            DataFrame with contractor risk scores
        """
        contractor_scores = {}
        
        # Get contractor statistics
        contractor_stats = self._compute_contractor_stats(df)
        
        # Score each contractor
        for contractor, stats in contractor_stats.items():
            scores = self._score_contractor(
                contractor, stats, df, network_analysis
            )
            contractor_scores[contractor] = scores
        
        # Convert to DataFrame
        contractor_df = pd.DataFrame.from_dict(
            contractor_scores, orient='index'
        )
        contractor_df = contractor_df.reset_index()
        contractor_df.columns = ['contractor'] + list(contractor_df.columns[1:])
        
        return contractor_df.sort_values('final_risk_score', ascending=False)
    
    def _compute_contractor_stats(self, df: pd.DataFrame) -> Dict:
        """Compute contractor statistics."""
        stats = defaultdict(lambda: {
            'total_participations': 0,
            'total_wins': 0,
            'win_rate': 0,
            'departments': set(),
            'locations': set(),
            'avg_bid_amount': 0,
            'total_bid_amount': 0,
            'tender_ids': []
        })
        
        for _, row in df.iterrows():
            winner = row['winning_bidder_normalized']
            
            # Winner statistics
            if pd.notna(winner):
                stats[winner]['total_wins'] += 1
                stats[winner]['tender_ids'].append(row['tender_id'])
                stats[winner]['departments'].add(row['department'])
                stats[winner]['locations'].add(row['location'])
                
                if 'winning_bid' in row.index and pd.notna(row['winning_bid']):
                    stats[winner]['total_bid_amount'] += row['winning_bid']
            
            # Bidder participation
            if 'bidders_normalized' in row.index:
                bidders = row['bidders_normalized']
                if isinstance(bidders, list):
                    for bidder in bidders:
                        if pd.notna(bidder) and bidder != '':
                            stats[bidder]['total_participations'] += 1
        
        # Compute derived metrics
        for contractor, s in stats.items():
            if s['total_participations'] > 0:
                s['win_rate'] = s['total_wins'] / s['total_participations']
            
            if s['total_wins'] > 0:
                s['avg_bid_amount'] = s['total_bid_amount'] / s['total_wins']
            
            s['departments'] = len(s['departments'])
            s['locations'] = len(s['locations'])
        
        return dict(stats)
    
    def _score_contractor(self, contractor: str, stats: Dict, df: pd.DataFrame,
                         network_analysis: Dict = None) -> Dict:
        """Score individual contractor."""
        scores = {}
        
        # 1. Win concentration (high win rate = suspicious)
        win_concentration_score = min(stats['win_rate'] * 1.5, 1.0)
        scores['win_concentration'] = win_concentration_score
        
        # 2. Geographic concentration (operates only in one region = suspicious)
        if stats['locations'] > 0:
            geographic_concentration = 1 - (stats['locations'] / max(1, stats['total_wins']))
        else:
            geographic_concentration = 0
        scores['geographic_concentration'] = min(geographic_concentration, 1.0)
        
        # 3. Department concentration
        if stats['departments'] > 0:
            dept_concentration = 1 - (stats['departments'] / max(1, stats['total_wins']))
        else:
            dept_concentration = 0
        scores['department_concentration'] = min(dept_concentration, 1.0)
        
        # 4. Network centrality
        network_centrality_score = 0
        if network_analysis and 'centrality' in network_analysis:
            if contractor in network_analysis['centrality']:
                centrality = network_analysis['centrality'][contractor]
                network_centrality_score = np.mean([
                    centrality.get('degree', 0),
                    centrality.get('betweenness', 0)
                ])
        scores['network_centrality'] = network_centrality_score
        
        # 5. Rotation pattern involvement
        rotation_score = 0
        if network_analysis and 'rotation_patterns' in network_analysis:
            if contractor in network_analysis['rotation_patterns']:
                rotation_data = network_analysis['rotation_patterns'][contractor]
                rotation_score = rotation_data.get('rotation_score', 0)
        scores['rotation_pattern'] = rotation_score
        
        # Compute weighted final score
        weights = self.weights_config.get('contractor_risk_factors', {})
        final_score = (
            scores['win_concentration'] * weights.get('win_concentration', {}).get('weight', 0.25) +
            scores['geographic_concentration'] * weights.get('geographic_concentration', {}).get('weight', 0.17) +
            scores['department_concentration'] * weights.get('department_concentration', {}).get('weight', 0.18) +
            scores['network_centrality'] * weights.get('network_centrality', {}).get('weight', 0.2) +
            scores['rotation_pattern'] * weights.get('rotation_pattern', {}).get('weight', 0.2)
        )
        
        scores['final_risk_score'] = final_score
        scores['risk_category'] = self.get_risk_category(final_score)
        scores['total_wins'] = stats['total_wins']
        scores['win_rate'] = stats['win_rate']
        scores['departments_count'] = stats['departments']
        scores['locations_count'] = stats['locations']
        
        return scores


class DepartmentRiskScorer(RiskScorer):
    """Scores corruption risk for departments."""
    
    def score_departments(self, df: pd.DataFrame, tender_risk_scores: pd.DataFrame = None) -> pd.DataFrame:
        """
        Compute risk scores for departments.
        
        Args:
            df: DataFrame with tender data
            tender_risk_scores: DataFrame with tender-level risk scores
        
        Returns:
            DataFrame with department risk scores
        """
        dept_scores = {}
        
        for dept in df['department'].unique():
            dept_data = df[df['department'] == dept]
            
            # Get tender risk scores for this department
            if tender_risk_scores is not None:
                dept_tender_scores = tender_risk_scores[
                    tender_risk_scores['tender_id'].isin(dept_data['tender_id'])
                ]
            else:
                dept_tender_scores = None
            
            scores = self._score_department(dept, dept_data, dept_tender_scores)
            dept_scores[dept] = scores
        
        dept_df = pd.DataFrame.from_dict(dept_scores, orient='index')
        dept_df = dept_df.reset_index()
        dept_df.columns = ['department'] + list(dept_df.columns[1:])
        
        return dept_df.sort_values('final_risk_score', ascending=False)
    
    def _score_department(self, dept: str, dept_data: pd.DataFrame,
                         tender_scores: pd.DataFrame = None) -> Dict:
        """Score individual department."""
        scores = {}
        
        # 1. Anomaly concentration
        if tender_scores is not None:
            anomaly_col = 'anomaly_score' if 'anomaly_score' in tender_scores.columns else 'anomaly_detection'
            anomaly_count = (tender_scores[anomaly_col] > 0.5).sum() if anomaly_col in tender_scores.columns else 0
            anomaly_concentration = anomaly_count / len(tender_scores) if len(tender_scores) > 0 else 0
        else:
            anomaly_concentration = 0
        scores['anomaly_concentration'] = anomaly_concentration
        
        # 2. Winner diversity (HHI)
        winners = dept_data['winning_bidder_normalized'].value_counts()
        if len(winners) > 0:
            total_tenders = len(dept_data)
            shares = winners.values / total_tenders
            hhi = calculate_herfindahl_index(shares.tolist())
            # Normalize HHI to 0-1 range
            winner_concentration = min(hhi / 0.3, 1.0)
        else:
            winner_concentration = 0
        scores['winner_concentration'] = winner_concentration
        
        # 3. Price analysis
        if 'winning_bid' in dept_data.columns and 'estimated_cost' in dept_data.columns:
            price_ratios = dept_data['winning_bid'] / dept_data['estimated_cost']
            price_ratios = price_ratios[~np.isinf(price_ratios) & ~np.isnan(price_ratios)]
            
            if len(price_ratios) > 0:
                # Deviation from expected (1.0)
                avg_ratio = price_ratios.mean()
                price_deviation = abs(avg_ratio - 1.0) / 1.0
                price_score = min(price_deviation, 1.0)
            else:
                price_score = 0
        else:
            price_score = 0
        scores['price_inflation'] = price_score
        
        # 4. Bidder diversity
        total_bidders = set()
        for bidders in dept_data.get('bidders_normalized', []):
            if isinstance(bidders, list):
                total_bidders.update(bidders)
        
        bidder_diversity = len(total_bidders) / (len(dept_data) * 3) if len(dept_data) > 0 else 0
        bidder_concentration = 1 - min(bidder_diversity, 1.0)
        scores['bidder_concentration'] = bidder_concentration
        
        # Compute weighted final score
        weights = self.weights_config.get('department_risk_factors', {})
        final_score = (
            scores['anomaly_concentration'] * weights.get('anomaly_concentration', {}).get('weight', 0.25) +
            scores['winner_concentration'] * weights.get('winner_diversity', {}).get('weight', 0.25) +
            scores['price_inflation'] * weights.get('price_inflation', {}).get('weight', 0.2) +
            scores['bidder_concentration'] * weights.get('network_density', {}).get('weight', 0.15) +
            0.05  # Complaint history placeholder
        )
        
        scores['final_risk_score'] = min(final_score, 1.0)
        scores['risk_category'] = self.get_risk_category(scores['final_risk_score'])
        scores['total_tenders'] = len(dept_data)
        scores['unique_winners'] = len(winners)
        
        return scores


class CorruptionRiskAssessor:
    """Orchestrates comprehensive corruption risk assessment."""
    
    def __init__(self, weights_config: Dict = None):
        """Initialize assessor."""
        self.weights_config = weights_config or load_risk_weights()
        self.tender_scorer = TenderRiskScorer(self.weights_config)
        self.contractor_scorer = ContractorRiskScorer(self.weights_config)
        self.dept_scorer = DepartmentRiskScorer(self.weights_config)
    
    def assess_risk(self, df: pd.DataFrame, network_analysis: Dict = None) -> Dict:
        """
        Perform comprehensive risk assessment.
        
        Args:
            df: DataFrame with tender data
            network_analysis: Network analysis results
        
        Returns:
            Dictionary with risk assessment results
        """
        logger.info("Starting risk assessment...")
        
        # Score tenders
        logger.info("Scoring tenders...")
        tender_scores = self._score_all_tenders(df, network_analysis)
        
        # Score contractors
        logger.info("Scoring contractors...")
        contractor_scores = self.contractor_scorer.score_contractors(df, network_analysis)
        
        # Score departments
        logger.info("Scoring departments...")
        dept_scores = self.dept_scorer.score_departments(df, tender_scores)
        
        logger.info("Risk assessment completed")
        
        return {
            'tender_scores': tender_scores,
            'contractor_scores': contractor_scores,
            'department_scores': dept_scores
        }
    
    def _score_all_tenders(self, df: pd.DataFrame, network_analysis: Dict) -> pd.DataFrame:
        """Score all tenders."""
        contractor_stats = self.contractor_scorer._compute_contractor_stats(df)
        
        tender_scores_list = []
        for _, row in df.iterrows():
            tender_score = self.tender_scorer.score_tender(
                row, contractor_stats, network_analysis
            )
            tender_score['tender_id'] = row['tender_id']
            tender_scores_list.append(tender_score)
        
        tender_scores_df = pd.DataFrame(tender_scores_list)
        if 'anomaly_score' not in tender_scores_df.columns and 'anomaly_detection' in tender_scores_df.columns:
            tender_scores_df['anomaly_score'] = tender_scores_df['anomaly_detection']
        return tender_scores_df
