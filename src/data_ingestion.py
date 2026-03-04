"""
Data Ingestion Module for Procurement Corruption Detection System.
Handles loading, validating, and ingesting tender data from various sources.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple, Union
from datetime import datetime
import os
from .utils import Logger, ProgressTracker, normalize_contractor_name

logger = Logger(__name__)


class DataValidator:
    """Validates tender data quality and completeness."""
    
    REQUIRED_FIELDS = [
        'tender_id', 'department', 'estimated_cost', 
        'participating_bidders', 'bid_amounts', 'winning_bidder',
        'tender_date', 'location'
    ]
    
    def __init__(self):
        """Initialize validator."""
        self.validation_report = {}
    
    def validate(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, any]]:
        """
        Validate tender dataset.
        
        Args:
            df: Tender DataFrame
        
        Returns:
            (is_valid, validation_report)
        """
        report = {
            'total_records': len(df),
            'missing_fields': [],
            'data_quality_issues': [],
            'warnings': []
        }
        
        # Check required fields
        missing_fields = [f for f in self.REQUIRED_FIELDS if f not in df.columns]
        if missing_fields:
            report['missing_fields'] = missing_fields
            logger.warning(f"Missing required fields: {missing_fields}")
        
        # Data type validation
        if 'tender_date' in df.columns:
            try:
                pd.to_datetime(df['tender_date'])
            except:
                report['data_quality_issues'].append("tender_date contains invalid dates")
        
        if 'estimated_cost' in df.columns:
            non_numeric = df[~pd.to_numeric(df['estimated_cost'], errors='coerce').notna()]
            if len(non_numeric) > 0:
                report['warnings'].append(
                    f"estimated_cost has {len(non_numeric)} non-numeric values"
                )
        
        # Completeness check
        missing_values = df.isnull().sum()
        for col in self.REQUIRED_FIELDS:
            if col in df.columns and missing_values[col] > 0:
                percentage = (missing_values[col] / len(df)) * 100
                if percentage > 5:
                    report['warnings'].append(
                        f"{col}: {percentage:.1f}% missing values"
                    )
        
        is_valid = len(report['missing_fields']) == 0
        self.validation_report = report
        
        return is_valid, report
    
    def print_report(self):
        """Print validation report."""
        print("\n=== DATA VALIDATION REPORT ===")
        print(f"Total Records: {self.validation_report['total_records']}")
        
        if self.validation_report['missing_fields']:
            print(f"Missing Fields: {self.validation_report['missing_fields']}")
        
        if self.validation_report['data_quality_issues']:
            print("Data Quality Issues:")
            for issue in self.validation_report['data_quality_issues']:
                print(f"  - {issue}")
        
        if self.validation_report['warnings']:
            print("Warnings:")
            for warning in self.validation_report['warnings']:
                print(f"  - {warning}")


class TenderDataLoader:
    """Loads tender data from various sources."""
    
    def __init__(self, source: Union[str, pd.DataFrame, List[Dict]]):
        """
        Initialize data loader.
        
        Args:
            source: File path (CSV/JSON) or DataFrame or list of dicts
        """
        self.source = source
        self.raw_data = None
        self.validator = DataValidator()
    
    def load(self) -> pd.DataFrame:
        """
        Load tender data.
        
        Returns:
            Loaded DataFrame
        """
        if isinstance(self.source, pd.DataFrame):
            self.raw_data = self.source.copy()
        elif isinstance(self.source, list):
            self.raw_data = pd.DataFrame(self.source)
        elif isinstance(self.source, str):
            self.raw_data = self._load_from_file(self.source)
        else:
            raise ValueError(f"Unsupported source type: {type(self.source)}")
        
        # Standardize column names
        self.raw_data.columns = [col.lower().replace(' ', '_') for col in self.raw_data.columns]
        
        logger.info(f"Loaded {len(self.raw_data)} tender records")
        return self.raw_data
    
    def _load_from_file(self, filepath: str) -> pd.DataFrame:
        """Load data from file."""
        if filepath.endswith('.csv'):
            return pd.read_csv(filepath)
        elif filepath.endswith('.json'):
            return pd.read_json(filepath)
        elif filepath.endswith('.xlsx'):
            return pd.read_excel(filepath)
        else:
            raise ValueError(f"Unsupported file format: {filepath}")
    
    def validate(self) -> bool:
        """
        Validate loaded data.
        
        Returns:
            True if valid, False otherwise
        """
        if self.raw_data is None:
            self.load()
        
        is_valid, report = self.validator.validate(self.raw_data)
        self.validator.print_report()
        
        return is_valid
    
    def get_data(self) -> pd.DataFrame:
        """Get loaded data."""
        if self.raw_data is None:
            self.load()
        return self.raw_data


class DataCleaner:
    """Cleans and standardizes tender data."""
    
    def __init__(self):
        """Initialize cleaner."""
        self.cleaning_log = []
    
    def clean(self, df: pd.DataFrame, config: Dict = None) -> pd.DataFrame:
        """
        Clean tender data.
        
        Args:
            df: Raw DataFrame
            config: Cleaning configuration
        
        Returns:
            Cleaned DataFrame
        """
        df = df.copy()
        
        # Remove duplicates
        initial_count = len(df)
        df = df.drop_duplicates(subset=['tender_id'], keep='first')
        self.cleaning_log.append(
            f"Removed {initial_count - len(df)} duplicate tender records"
        )
        
        # Convert data types
        if 'tender_date' in df.columns:
            df['tender_date'] = pd.to_datetime(df['tender_date'], errors='coerce')
        
        if 'estimated_cost' in df.columns:
            df['estimated_cost'] = pd.to_numeric(df['estimated_cost'], errors='coerce')
        
        # Handle missing values
        if 'location' in df.columns:
            df['location'] = df['location'].fillna('Unknown')
        
        if 'department' in df.columns:
            df['department'] = df['department'].fillna('Other')
        
        # Remove rows with critical missing values
        critical_cols = ['tender_id', 'estimated_cost', 'winning_bidder']
        initial_count = len(df)
        df = df.dropna(subset=critical_cols)
        self.cleaning_log.append(
            f"Removed {initial_count - len(df)} records with missing critical values"
        )
        
        # Normalize contractor names
        if 'winning_bidder' in df.columns:
            df['winning_bidder_normalized'] = df['winning_bidder'].apply(
                normalize_contractor_name
            )
        
        if 'participating_bidders' in df.columns:
            df['bidders_normalized'] = df['participating_bidders'].apply(
                lambda x: self._normalize_bidders(x)
            )
        
        logger.info(f"Cleaned data: {len(df)} records")
        return df
    
    def _normalize_bidders(self, bidders: Union[str, List]) -> List[str]:
        """Normalize list of bidders."""
        if pd.isna(bidders):
            return []
        
        if isinstance(bidders, str):
            # Assume comma-separated
            bidders = [b.strip() for b in bidders.split(',')]
        elif not isinstance(bidders, list):
            return []
        
        return [normalize_contractor_name(b) for b in bidders if pd.notna(b)]
    
    def get_log(self) -> List[str]:
        """Get cleaning log."""
        return self.cleaning_log


class DataIngestionPipeline:
    """Orchestrates the complete data ingestion process."""
    
    def __init__(self, source: Union[str, pd.DataFrame], config: Dict = None):
        """Initialize pipeline."""
        self.source = source
        self.config = config or {}
        self.loader = TenderDataLoader(source)
        self.cleaner = DataCleaner()
        self.data = None
    
    def execute(self) -> pd.DataFrame:
        """
        Execute the ingestion pipeline.
        
        Returns:
            Cleaned and validated DataFrame
        """
        logger.info("Starting data ingestion pipeline...")
        
        # Load data
        self.data = self.loader.load()
        
        # Validate
        is_valid = self.loader.validate()
        if not is_valid:
            logger.warning("Data validation failed, proceeding with caution")
        
        # Clean
        self.data = self.cleaner.clean(self.data, self.config)
        
        # Print cleaning log
        for log_entry in self.cleaner.get_log():
            logger.info(log_entry)
        
        logger.info("Data ingestion pipeline completed")
        return self.data
    
    def get_data(self) -> pd.DataFrame:
        """Get processed data."""
        if self.data is None:
            return self.execute()
        return self.data
