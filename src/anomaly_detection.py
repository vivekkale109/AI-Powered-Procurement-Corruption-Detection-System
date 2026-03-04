"""
Anomaly Detection Module.
Implements multiple anomaly detection algorithms for detecting suspicious tender patterns.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from scipy import stats
from .utils import Logger, compute_z_score, detect_outliers_iqr

logger = Logger(__name__)


class AnomalyDetectionEngine:
    """Orchestrates multiple anomaly detection algorithms."""
    
    def __init__(self, contamination: float = 0.05):
        """
        Initialize anomaly detection engine.
        
        Args:
            contamination: Expected proportion of anomalies (0-0.5)
        """
        self.contamination = contamination
        self.scaler = StandardScaler()
        self.isolation_forest = None
        self.lof = None
        self.feature_columns = []
        self.anomaly_scores = {}
    
    def detect_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect anomalies using multiple methods.
        
        Args:
            df: DataFrame with engineered features
        
        Returns:
            DataFrame with anomaly scores
        """
        df = df.copy()
        
        logger.info("Starting anomaly detection...")
        
        # Select features for anomaly detection
        self.feature_columns = self._select_features(df)
        
        if not self.feature_columns:
            logger.warning("No suitable features found for anomaly detection")
            df['anomaly_score'] = 0.0
            return df
        
        # Prepare data
        X = df[self.feature_columns].fillna(0).values
        
        # Detect anomalies using multiple methods
        logger.info("Running Isolation Forest...")
        iso_scores = self._isolation_forest_detection(X)
        
        logger.info("Running Local Outlier Factor...")
        lof_scores = self._lof_detection(X)
        
        logger.info("Running Statistical Detection...")
        stat_scores = self._statistical_detection(df)
        
        # Combine scores
        df['iso_forest_score'] = iso_scores
        df['lof_score'] = lof_scores
        df['statistical_score'] = stat_scores
        
        # Compute composite anomaly score
        df['anomaly_score'] = (
            df['iso_forest_score'] * 0.4 +
            df['lof_score'] * 0.35 +
            df['statistical_score'] * 0.25
        )
        
        # Flag anomalies
        df['is_anomaly'] = df['anomaly_score'] >= (1 - self.contamination)
        
        logger.info(f"Detected {df['is_anomaly'].sum()} anomalies")
        
        return df
    
    def _select_features(self, df: pd.DataFrame) -> List[str]:
        """Select suitable features for anomaly detection."""
        feature_candidates = [
            'bid_deviation_zscore',
            'bid_coefficient_variation',
            'complementary_bid_score',
            'dept_hhi',
            'temporal_anomaly_score',
            'bidder_set_repetition'
        ]
        
        available_features = [col for col in feature_candidates if col in df.columns]
        
        return available_features
    
    def _isolation_forest_detection(self, X: np.ndarray) -> np.ndarray:
        """
        Isolation Forest anomaly detection.
        
        Args:
            X: Feature matrix
        
        Returns:
            Anomaly scores (0-1)
        """
        iso_forest = IsolationForest(
            contamination=self.contamination,
            n_estimators=100,
            random_state=42,
            n_jobs=-1
        )

        iso_forest.fit(X)
        raw_scores = -iso_forest.decision_function(X)  # Higher = more anomalous

        # Normalize to 0-1 range
        score_min = np.percentile(raw_scores, 5)
        score_max = np.percentile(raw_scores, 95)
        if score_max > score_min:
            normalized_scores = (raw_scores - score_min) / (score_max - score_min)
        else:
            normalized_scores = np.zeros_like(raw_scores)

        return np.clip(normalized_scores, 0, 1)
    
    def _lof_detection(self, X: np.ndarray) -> np.ndarray:
        """
        Local Outlier Factor anomaly detection.
        
        Args:
            X: Feature matrix
        
        Returns:
            Anomaly scores (0-1)
        """
        lof = LocalOutlierFactor(
            n_neighbors=20,
            contamination=self.contamination,
            novelty=False
        )
        
        lof.fit(X)
        lof_scores = -lof.negative_outlier_factor_  # Higher = more anomalous
        
        # Normalize to 0-1 range
        lof_min = np.percentile(lof_scores, 5)
        lof_max = np.percentile(lof_scores, 95)
        
        if lof_max > lof_min:
            normalized_scores = (lof_scores - lof_min) / (lof_max - lof_min)
        else:
            normalized_scores = np.zeros_like(lof_scores)
        
        return np.clip(normalized_scores, 0, 1)
    
    def _statistical_detection(self, df: pd.DataFrame) -> np.ndarray:
        """
        Statistical anomaly detection using z-scores and IQR.
        
        Args:
            df: DataFrame with features
        
        Returns:
            Anomaly scores (0-1)
        """
        anomaly_indicators = []
        
        # Bid deviation anomaly
        if 'bid_deviation_zscore' in df.columns:
            zscore_anomaly = np.clip(
                np.abs(df['bid_deviation_zscore'].fillna(0)) / 3.0, 0, 1
            )
            anomaly_indicators.append(zscore_anomaly.values)
        
        # Bid variance anomaly
        if 'bid_coefficient_variation' in df.columns:
            cv_anomaly = np.clip(df['bid_coefficient_variation'].fillna(0), 0, 1)
            anomaly_indicators.append(cv_anomaly.values)
        
        # Complementary bid anomaly
        if 'complementary_bid_score' in df.columns:
            comp_anomaly = df['complementary_bid_score'].fillna(0).values
            anomaly_indicators.append(comp_anomaly)
        
        if not anomaly_indicators:
            return np.zeros(len(df))
        
        # Average indicators
        anomaly_scores = np.mean(anomaly_indicators, axis=0)
        
        return np.clip(anomaly_scores, 0, 1)


class BidGapAnalyzer:
    """Analyzes suspicious gaps in bid amounts (collusion sign)."""
    
    @staticmethod
    def analyze_bid_gaps(df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyze gaps between consecutive bid amounts (indicator of collusion).
        
        Args:
            df: DataFrame with bid data
        
        Returns:
            DataFrame with gap analysis scores
        """
        df = df.copy()
        gap_anomaly_scores = []
        
        for _, row in df.iterrows():
            if 'bid_amounts' not in df.columns or pd.isna(row['bid_amounts']):
                gap_anomaly_scores.append(0)
                continue
            
            bids = row['bid_amounts']
            if isinstance(bids, str):
                try:
                    bids = [float(b.strip()) for b in bids.split(',')]
                except:
                    gap_anomaly_scores.append(0)
                    continue
            
            if not isinstance(bids, list):
                gap_anomaly_scores.append(0)
                continue
            
            bids = sorted(np.array(bids))
            
            if len(bids) < 2:
                gap_anomaly_scores.append(0)
                continue
            
            # Calculate gaps between consecutive bids
            gaps = []
            for i in range(len(bids) - 1):
                if bids[i] != 0:
                    gap_ratio = (bids[i + 1] - bids[i]) / bids[i]
                    gaps.append(gap_ratio)
            
            if gaps:
                # Very consistent gaps suggest collusion
                gap_std = np.std(gaps)
                gap_cv = gap_std / np.mean(gaps) if np.mean(gaps) != 0 else 0
                
                # Low CV (consistent gaps) is suspicious
                anomaly_score = 1 - min(gap_cv, 1.0)
            else:
                anomaly_score = 0
            
            gap_anomaly_scores.append(anomaly_score)
        
        df['bid_gap_anomaly'] = gap_anomaly_scores
        
        return df


class PriceAnomalyDetector:
    """Detects price-related anomalies."""
    
    @staticmethod
    def detect_price_anomalies(df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect suspicious price anomalies.
        
        Args:
            df: DataFrame with bid data
        
        Returns:
            DataFrame with price anomaly scores
        """
        df = df.copy()
        
        price_anomaly_scores = {idx: [] for idx in df.index}
        
        # Group by department and location
        for group_key in ['department', 'location']:
            if group_key not in df.columns:
                continue
            
            for group_name, group_df in df.groupby(group_key):
                if 'winning_bid' not in group_df.columns:
                    continue
                
                # Compute z-scores within group
                bids = group_df['winning_bid'].values
                estimated_costs = group_df['estimated_cost'].values
                
                # Compute expected bid based on estimate
                bid_ratios = bids / estimated_costs
                bid_ratios = bid_ratios[~np.isnan(bid_ratios)]
                
                if len(bid_ratios) > 2:
                    z_scores = compute_z_score(bid_ratios)
                    
                    # High z-scores indicate unusual pricing
                    for idx, z in zip(group_df.index, z_scores):
                        price_anomaly_scores[idx].append(min(abs(z) / 3.0, 1.0))
        
        # Aggregate anomaly scores
        final_scores = []
        for idx in df.index:
            if price_anomaly_scores[idx]:
                score = np.mean(price_anomaly_scores[idx])
            else:
                score = 0
            final_scores.append(score)
        
        df['price_anomaly_score'] = final_scores
        
        return df


class WinnerAnomalyDetector:
    """Detects anomalies in winner selection patterns."""
    
    @staticmethod
    def detect_winner_anomalies(df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect suspicious winner selection patterns.
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            DataFrame with winner anomaly scores
        """
        df = df.copy()
        
        winner_anomaly_scores = []
        
        # Compute statistics per contractor
        contractor_stats = {}
        for _, row in df.iterrows():
            contractor = row['winning_bidder_normalized']
            
            if contractor not in contractor_stats:
                contractor_stats[contractor] = {
                    'total_participations': 0,
                    'total_wins': 0,
                    'departments': set(),
                    'locations': set()
                }
            
            if 'bidders_normalized' in df.columns:
                bidders = row['bidders_normalized']
                contractor_stats[contractor]['total_participations'] += len([b for b in bidders if pd.notna(b)])
            
            contractor_stats[contractor]['total_wins'] += 1
            contractor_stats[contractor]['departments'].add(row['department'])
            contractor_stats[contractor]['locations'].add(row['location'])
        
        # Compute anomaly scores
        for _, row in df.iterrows():
            contractor = row['winning_bidder_normalized']
            stats = contractor_stats[contractor]
            
            # Score based on:
            # 1. Geographic concentration
            locations = len(stats['locations'])
            location_concentration = 1 - (locations / max(1, stats['total_wins']))
            
            # 2. Department concentration
            departments = len(stats['departments'])
            dept_concentration = 1 - (departments / max(1, stats['total_wins']))
            
            # Combined anomaly score
            anomaly = np.mean([location_concentration, dept_concentration])
            winner_anomaly_scores.append(anomaly)
        
        df['winner_anomaly_score'] = winner_anomaly_scores
        
        return df
