"""
Preprocessing and Feature Engineering Module.
Computes advanced features for anomaly detection and risk assessment.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from .utils import (
    Logger, fuzzy_match_contractors, compute_bid_deviation,
    compute_z_score, detect_outliers_iqr, calculate_herfindahl_index,
    normalize_contractor_name
)

logger = Logger(__name__)


class BidAnalyzer:
    """Analyzes bid amounts and pricing patterns."""
    
    def __init__(self):
        """Initialize bid analyzer."""
        pass
    
    def compute_bid_deviation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute bid-related features.
        
        Args:
            df: DataFrame with bid data
        
        Returns:
            DataFrame with new features
        """
        df = df.copy()
        
        # Bid deviation from estimate
        df['bid_deviation'] = df.apply(
            lambda row: compute_bid_deviation(row['winning_bid'], row['estimated_cost']),
            axis=1
        )
        
        # Bid deviation z-score
        df['bid_deviation_zscore'] = compute_z_score(df['bid_deviation'].values)
        
        # Bid above/below estimate
        df['bid_above_estimate'] = (df['winning_bid'] > df['estimated_cost']).astype(int)
        
        # Win margin (difference between 1st and 2nd lowest bid)
        df['win_margin'] = df['estimated_cost'] * 0.1  # Placeholder
        
        return df
    
    def compute_bid_variance_per_tender(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute variance in bids across participants for each tender.
        
        Args:
            df: DataFrame with bid data
        
        Returns:
            DataFrame with variance features
        """
        df = df.copy()
        
        if 'bid_amounts' not in df.columns:
            logger.warning("bid_amounts column not found")
            return df
        
        bid_variances = []
        bid_coefficients = []
        
        for bids in df['bid_amounts']:
            if pd.isna(bids) or not isinstance(bids, (list, str)):
                bid_variances.append(np.nan)
                bid_coefficients.append(np.nan)
                continue
            
            # Parse bid amounts
            if isinstance(bids, str):
                try:
                    bids = [float(b.strip()) for b in bids.split(',')]
                except:
                    bid_variances.append(np.nan)
                    bid_coefficients.append(np.nan)
                    continue
            
            bids = np.array(bids)
            
            if len(bids) > 1:
                variance = np.var(bids)
                cv = np.std(bids) / np.mean(bids) if np.mean(bids) != 0 else 0
            else:
                variance = 0
                cv = 0
            
            bid_variances.append(variance)
            bid_coefficients.append(cv)
        
        df['bid_variance'] = bid_variances
        df['bid_coefficient_variation'] = bid_coefficients
        
        return df
    
    def detect_complementary_bids(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect complementary bidding patterns (collusion indicator).
        
        Args:
            df: DataFrame with bid data
        
        Returns:
            DataFrame with complementary bid scores
        """
        df = df.copy()
        
        complementary_scores = []
        
        for bids in df['bid_amounts']:
            if pd.isna(bids) or not isinstance(bids, (list, str)):
                complementary_scores.append(0)
                continue
            
            if isinstance(bids, str):
                try:
                    bids = [float(b.strip()) for b in bids.split(',')]
                except:
                    complementary_scores.append(0)
                    continue
            
            bids = sorted(np.array(bids))
            
            if len(bids) >= 2:
                # Check if bids form complementary pairs (high-low pattern)
                price_ranges = []
                for i in range(len(bids) - 1):
                    ratio = bids[i + 1] / bids[i] if bids[i] != 0 else 1
                    price_ranges.append(ratio)
                
                # High variance in ratios suggests complementary pattern
                if price_ranges:
                    cv = np.std(price_ranges) / np.mean(price_ranges) if np.mean(price_ranges) != 0 else 0
                    complementary_scores.append(min(cv, 1.0))
                else:
                    complementary_scores.append(0)
            else:
                complementary_scores.append(0)
        
        df['complementary_bid_score'] = complementary_scores
        
        return df


class ContractorAnalyzer:
    """Analyzes contractor behavior and patterns."""
    
    def __init__(self):
        """Initialize contractor analyzer."""
        pass
    
    def compute_win_frequency(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """
        Compute win frequency statistics for each contractor.
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            Dictionary with contractor statistics
        """
        contractor_stats = defaultdict(lambda: {
            'total_participations': 0,
            'total_wins': 0,
            'win_rate': 0.0,
            'tender_ids': [],
            'win_tender_ids': [],
            'avg_bid_amount': 0.0,
            'departments': set(),
            'locations': set(),
            'first_appearance': None,
            'last_appearance': None
        })
        
        for _, row in df.iterrows():
            tender_date = row['tender_date']
            winning_bidder = row['winning_bidder_normalized']
            department = row['department']
            location = row['location']
            tender_id = row['tender_id']
            
            # Process participating bidders
            if 'bidders_normalized' in df.columns:
                bidders = row['bidders_normalized']
            else:
                bidders = [winning_bidder]
            
            for bidder in bidders:
                if pd.isna(bidder) or bidder == '':
                    continue
                
                stats = contractor_stats[bidder]
                stats['total_participations'] += 1
                stats['tender_ids'].append(tender_id)
                stats['departments'].add(department)
                stats['locations'].add(location)
                
                if pd.notna(tender_date):
                    if stats['first_appearance'] is None:
                        stats['first_appearance'] = tender_date
                    stats['last_appearance'] = tender_date
                
                if bidder == winning_bidder:
                    stats['total_wins'] += 1
                    stats['win_tender_ids'].append(tender_id)
            
            # Update average bid
            if winning_bidder and 'winning_bid' in df.columns:
                stats = contractor_stats[winning_bidder]
                winning_bid = row['winning_bid']
                if pd.notna(winning_bid):
                    stats['avg_bid_amount'] = (
                        (stats['avg_bid_amount'] * (stats['total_wins'] - 1) + winning_bid) /
                        stats['total_wins']
                    )
        
        # Calculate win rates
        for contractor, stats in contractor_stats.items():
            if stats['total_participations'] > 0:
                stats['win_rate'] = stats['total_wins'] / stats['total_participations']
            stats['departments'] = list(stats['departments'])
            stats['locations'] = list(stats['locations'])
        
        return dict(contractor_stats)
    
    def compute_market_concentration(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute market concentration (HHI) at department and location level.
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            DataFrame with concentration metrics
        """
        df = df.copy()
        contractor_stats = self.compute_win_frequency(df)
        
        # Department-level HHI
        dept_winners = defaultdict(Counter)
        location_winners = defaultdict(Counter)
        
        for _, row in df.iterrows():
            dept = row['department']
            loc = row['location']
            winner = row['winning_bidder_normalized']
            
            dept_winners[dept][winner] += 1
            location_winners[loc][winner] += 1
        
        dept_hhi = {}
        for dept, winners in dept_winners.items():
            total = sum(winners.values())
            shares = [v / total for v in winners.values()]
            dept_hhi[dept] = calculate_herfindahl_index(shares)
        
        # Add HHI to dataframe
        df['dept_hhi'] = df['department'].map(dept_hhi)
        
        return df


class TemporalAnalyzer:
    """Analyzes temporal patterns in bidding."""
    
    def __init__(self):
        """Initialize temporal analyzer."""
        pass
    
    def compute_winning_intervals(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """
        Compute intervals between consecutive wins for each contractor.
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            Dictionary of contractor -> list of winning intervals (in days)
        """
        contractor_stats = defaultdict(list)
        
        for contractor, dates in self._get_contractor_win_dates(df).items():
            if len(dates) > 1:
                sorted_dates = sorted(dates)
                intervals = []
                for i in range(len(sorted_dates) - 1):
                    delta = (sorted_dates[i + 1] - sorted_dates[i]).days
                    intervals.append(delta)
                
                contractor_stats[contractor] = intervals
        
        return dict(contractor_stats)
    
    def _get_contractor_win_dates(self, df: pd.DataFrame) -> Dict[str, List]:
        """Get winning dates for each contractor."""
        contractor_dates = defaultdict(list)
        
        for _, row in df.iterrows():
            winner = row['winning_bidder_normalized']
            date = row['tender_date']
            if pd.notna(winner) and pd.notna(date):
                contractor_dates[winner].append(date)
        
        return contractor_dates
    
    def detect_temporal_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect temporal anomalies (e.g., unusual bidding patterns over time).
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            DataFrame with temporal anomaly scores
        """
        df = df.copy()
        
        # Group by contractor and compute winning interval statistics
        winning_intervals = self.compute_winning_intervals(df)
        
        temporal_anomaly_scores = []
        
        for _, row in df.iterrows():
            winner = row['winning_bidder_normalized']
            
            if winner in winning_intervals and len(winning_intervals[winner]) > 2:
                intervals = np.array(winning_intervals[winner])
                z_scores = compute_z_score(intervals)
                
                # Check if current win is at unusual interval
                max_z = np.max(np.abs(z_scores))
                anomaly_score = min(max_z / 3.0, 1.0)  # Normalize to 0-1
            else:
                anomaly_score = 0
            
            temporal_anomaly_scores.append(anomaly_score)
        
        df['temporal_anomaly_score'] = temporal_anomaly_scores
        
        return df


class ParticipationAnalyzer:
    """Analyzes bidder participation patterns."""
    
    def __init__(self):
        """Initialize participation analyzer."""
        pass
    
    def compute_co_participation(self, df: pd.DataFrame) -> Dict[Tuple, int]:
        """
        Compute co-participation frequency (bidders appearing together).
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            Dictionary of (bidder1, bidder2) -> count
        """
        co_participation = defaultdict(int)
        
        for _, row in df.iterrows():
            if 'bidders_normalized' in df.columns:
                bidders = row['bidders_normalized']
            else:
                bidders = [row['winning_bidder_normalized']]
            
            bidders = [b for b in bidders if pd.notna(b) and b != '']
            
            # Count all pairs
            for i in range(len(bidders)):
                for j in range(i + 1, len(bidders)):
                    pair = tuple(sorted([bidders[i], bidders[j]]))
                    co_participation[pair] += 1
        
        return dict(co_participation)
    
    def compute_participation_uniqueness(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute uniqueness of bidder sets (are bids repetitive?).
        
        Args:
            df: DataFrame with tender data
        
        Returns:
            DataFrame with uniqueness scores
        """
        df = df.copy()
        
        # Create signature of bidder set for each tender
        bidder_signatures = []
        signature_frequency = Counter()
        
        for _, row in df.iterrows():
            if 'bidders_normalized' in df.columns:
                bidders = row['bidders_normalized']
            else:
                bidders = [row['winning_bidder_normalized']]
            
            bidders = sorted([b for b in bidders if pd.notna(b) and b != ''])
            signature = tuple(bidders)
            bidder_signatures.append(signature)
            signature_frequency[signature] += 1
        
        # Map frequency to dataframe
        uniqueness_scores = []
        for sig in bidder_signatures:
            # Inverse of frequency (unique = low frequency)
            frequency = signature_frequency[sig]
            # Score: 1 if unique, 0 if highly repetitive
            score = 1.0 / (1.0 + frequency)
            uniqueness_scores.append(1 - score)  # Flip so high = repetitive
        
        df['bidder_set_repetition'] = uniqueness_scores
        
        return df


class FeatureEngineer:
    """Orchestrates feature engineering pipeline."""
    
    def __init__(self):
        """Initialize feature engineer."""
        self.bid_analyzer = BidAnalyzer()
        self.contractor_analyzer = ContractorAnalyzer()
        self.temporal_analyzer = TemporalAnalyzer()
        self.participation_analyzer = ParticipationAnalyzer()
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all features for anomaly detection.
        
        Args:
            df: Cleaned DataFrame with tender data
        
        Returns:
            DataFrame with engineered features
        """
        logger.info("Starting feature engineering...")
        
        # Bid features
        logger.info("Computing bid features...")
        df = self.bid_analyzer.compute_bid_deviation_features(df)
        df = self.bid_analyzer.compute_bid_variance_per_tender(df)
        df = self.bid_analyzer.detect_complementary_bids(df)
        
        # Contractor features
        logger.info("Computing contractor features...")
        df = self.contractor_analyzer.compute_market_concentration(df)
        
        # Temporal features
        logger.info("Computing temporal features...")
        df = self.temporal_analyzer.detect_temporal_anomalies(df)
        
        # Participation features
        logger.info("Computing participation features...")
        df = self.participation_analyzer.compute_participation_uniqueness(df)
        
        logger.info("Feature engineering completed")
        
        return df
