"""
Sample Procurement Data Generator.
Creates realistic procurement data for testing and demonstration.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from typing import List, Dict


class ProcurementDataGenerator:
    """Generates realistic procurement tender data."""
    
    def __init__(self, seed: int = 42):
        """Initialize generator."""
        random.seed(seed)
        np.random.seed(seed)
    
    def generate_sample_data(self, num_tenders: int = 500) -> pd.DataFrame:
        """
        Generate sample procurement data.
        
        Args:
            num_tenders: Number of tenders to generate
        
        Returns:
            DataFrame with tender data
        """
        # Define data categories
        departments = ['PWD', 'Health', 'Education', 'Energy', 'Transport', 'Water Supply', 'Housing']
        locations = ['North', 'South', 'East', 'West', 'Central', 'Northeast', 'Northwest']
        
        # Generate contractors (with some clustering for realistic patterns)
        contractors = self._generate_contractors(num_tenders)
        
        # Generate tenders
        tenders = []
        base_date = datetime.now() - timedelta(days=730)
        
        for i in range(num_tenders):
            tender_date = base_date + timedelta(days=random.randint(0, 730))
            
            dept = random.choice(departments)
            location = random.choice(locations)
            
            # Generate estimated cost
            estimated_cost = np.random.lognormal(mean=np.log(500000), sigma=1.5)
            estimated_cost = int(estimated_cost)
            
            # Select bidders
            num_bidders = random.randint(2, 8)
            bidders = random.sample(contractors, min(num_bidders, len(contractors)))
            
            # Generate bids with some collusion patterns
            bids = self._generate_bids(estimated_cost, len(bidders), i)
            
            # Select winner
            winner = bidders[np.argmin(bids)]
            winning_bid = min(bids)
            
            tender = {
                'tender_id': f'T{i+1:05d}',
                'department': dept,
                'estimated_cost': estimated_cost,
                'participating_bidders': ','.join(bidders),
                'bid_amounts': ','.join(str(int(b)) for b in bids),
                'winning_bidder': winner,
                'winning_bid': winning_bid,
                'tender_date': tender_date,
                'location': location
            }
            
            tenders.append(tender)
        
        df = pd.DataFrame(tenders)
        
        return df
    
    def _generate_contractors(self, num_tenders: int) -> List[str]:
        """Generate realistic contractor names."""
        prefixes = ['Tech', 'Global', 'Prime', 'Best', 'Elite', 'United', 'Crown', 'Royal']
        middles = ['Infrastructure', 'Projects', 'Engineering', 'Constructions', 'Solutions', 'Services']
        suffixes = ['LTD', 'PVT LTD', 'Inc', 'Corp', 'Ltd']
        
        contractors = set()
        for _ in range(min(int(num_tenders / 10), 100)):
            name = f"{random.choice(prefixes)} {random.choice(middles)} {random.choice(suffixes)}"
            contractors.add(name)
        
        return list(contractors)
    
    def _generate_bids(self, estimated_cost: float, num_bidders: int, tender_idx: int) -> List[float]:
        """
        Generate bid amounts with realistic patterns.
        Some tenders have collusion patterns.
        """
        bids = []
        
        # 80% normal bidding, 20% suspicious patterns
        if np.random.random() < 0.2:
            # Suspicious pattern: complementary bids
            # One very high, others clustered around estimate
            for i in range(num_bidders):
                if i == 0:
                    # Outlier bid
                    bid = estimated_cost * np.random.uniform(0.9, 1.1)
                else:
                    # Clustered bids
                    bid = estimated_cost * np.random.uniform(0.98, 1.02)
                bids.append(bid)
        elif np.random.random() < 0.1:
            # Suspicious: rotation pattern (check sequence)
            # Generate bids very close to each other
            base = estimated_cost * np.random.uniform(0.95, 1.05)
            for i in range(num_bidders):
                bid = base * np.random.uniform(0.99, 1.01)
                bids.append(bid)
        else:
            # Normal competitive bidding
            for i in range(num_bidders):
                bid = estimated_cost * np.random.lognormal(0, 0.2)
                bids.append(bid)
        
        return bids
    
    def add_anomalies(self, df: pd.DataFrame, anomaly_rate: float = 0.1) -> pd.DataFrame:
        """
        Add artificial anomalies to test detection.
        
        Args:
            df: DataFrame
            anomaly_rate: Percentage of records to mark as anomalies
        
        Returns:
            DataFrame with anomalies
        """
        df = df.copy()
        
        num_anomalies = int(len(df) * anomaly_rate)
        anomaly_indices = np.random.choice(len(df), num_anomalies, replace=False)
        
        for idx in anomaly_indices:
            # Introduce different types of anomalies
            anomaly_type = np.random.choice(['price', 'winner', 'bidding'])
            
            if anomaly_type == 'price':
                # Unusual price
                df.loc[idx, 'winning_bid'] = df.loc[idx, 'estimated_cost'] * np.random.uniform(0.5, 1.5)
            elif anomaly_type == 'winner':
                # Repeat winner
                high_freq_winner = df.loc[df.index < idx, 'winning_bidder'].mode()
                if len(high_freq_winner) > 0:
                    df.loc[idx, 'winning_bidder'] = high_freq_winner[0]
            elif anomaly_type == 'bidding':
                # Suspicious bidding pattern
                df.loc[idx, 'bid_amounts'] = ','.join(
                    str(int(df.loc[idx, 'estimated_cost'])) for _ in range(5)
                )
        
        return df


def main():
    """Generate sample data."""
    print("Generating sample procurement data...")
    
    generator = ProcurementDataGenerator()
    df = generator.generate_sample_data(num_tenders=500)
    
    # Add some anomalies
    df = generator.add_anomalies(df, anomaly_rate=0.15)
    
    # Save to CSV
    output_path = 'data/raw/sample_tenders.csv'
    df.to_csv(output_path, index=False)
    
    print(f"\n✓ Sample data generated: {output_path}")
    print(f"\nDataset Summary:")
    print(f"  Total Tenders: {len(df)}")
    print(f"  Departments: {df['department'].nunique()}")
    print(f"  Contractors: {len(set([b for bidders in df['participating_bidders'] for b in bidders.split(',')]))} unique")
    print(f"  Date Range: {df['tender_date'].min().date()} to {df['tender_date'].max().date()}")
    print(f"  Estimated Cost Range: ₹{df['estimated_cost'].min():,.0f} - ₹{df['estimated_cost'].max():,.0f}")
    
    print("\nColumn Information:")
    print(df.dtypes)
    
    print("\nFirst 5 Records:")
    print(df.head())


if __name__ == "__main__":
    main()
