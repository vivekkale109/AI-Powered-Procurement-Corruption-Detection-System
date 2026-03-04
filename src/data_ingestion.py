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
        self.validated_data = pd.DataFrame()
    
    def _is_blank(self, value) -> bool:
        """Return True if a field value is blank-like."""
        if pd.isna(value):
            return True
        if isinstance(value, str) and value.strip() == '':
            return True
        return False
    
    def _parse_bidders(self, bidders: Union[str, List, float]) -> List[str]:
        """Parse participating bidders into normalized list."""
        if pd.isna(bidders):
            return []
        if isinstance(bidders, list):
            return [str(b).strip() for b in bidders if not self._is_blank(b)]
        if isinstance(bidders, str):
            return [b.strip() for b in bidders.split(',') if b.strip()]
        return []
    
    def _parse_bid_amounts(self, bid_amounts: Union[str, List, float]) -> Optional[List[float]]:
        """Parse bid amounts from list or comma-separated string."""
        if pd.isna(bid_amounts):
            return None
        if isinstance(bid_amounts, list):
            parsed = pd.to_numeric(pd.Series(bid_amounts), errors='coerce').tolist()
        elif isinstance(bid_amounts, str):
            parts = [p.strip() for p in bid_amounts.split(',') if p.strip()]
            if not parts:
                return None
            parsed = pd.to_numeric(pd.Series(parts), errors='coerce').tolist()
        else:
            return None
        
        if any(pd.isna(v) for v in parsed):
            return None
        return [float(v) for v in parsed]
    
    def _validate_row(self, row: pd.Series, row_idx: int) -> Tuple[bool, List[str], Dict[str, any]]:
        """Validate one row against required schema and range constraints."""
        reasons = []
        
        # Required fields must exist and not be blank
        for field in self.REQUIRED_FIELDS:
            if field not in row.index or self._is_blank(row.get(field)):
                reasons.append(f"{field} is missing or blank")
        
        if reasons:
            return False, reasons, {}
        
        cleaned = {}
        
        # tender_id
        tender_id = str(row['tender_id']).strip()
        if not tender_id:
            reasons.append("tender_id must be a non-empty string")
        cleaned['tender_id'] = tender_id
        
        # department
        department = str(row['department']).strip()
        if not department:
            reasons.append("department must be a non-empty string")
        cleaned['department'] = department
        
        # estimated_cost numeric and in range
        estimated_cost = pd.to_numeric([row['estimated_cost']], errors='coerce')[0]
        if pd.isna(estimated_cost):
            reasons.append("estimated_cost must be numeric")
        else:
            min_cost = 0
            max_cost = 1_000_000_000_000
            if estimated_cost <= min_cost:
                reasons.append("estimated_cost must be > 0")
            if estimated_cost > max_cost:
                reasons.append(f"estimated_cost exceeds max allowed ({max_cost})")
        cleaned['estimated_cost'] = float(estimated_cost) if not pd.isna(estimated_cost) else row['estimated_cost']
        
        # participating_bidders
        bidders = self._parse_bidders(row['participating_bidders'])
        if len(bidders) == 0:
            reasons.append("participating_bidders must contain at least one bidder")
        cleaned['participating_bidders'] = ', '.join(bidders)
        
        # bid_amounts numeric list and in range
        bid_amounts = self._parse_bid_amounts(row['bid_amounts'])
        if bid_amounts is None or len(bid_amounts) == 0:
            reasons.append("bid_amounts must be a non-empty numeric list")
        else:
            if any(v <= 0 for v in bid_amounts):
                reasons.append("bid_amounts values must be > 0")
            if len(bidders) > 0 and len(bid_amounts) != len(bidders):
                reasons.append("bid_amounts count must match participating_bidders count")
        cleaned['bid_amounts'] = ', '.join([str(v) for v in bid_amounts]) if bid_amounts else row['bid_amounts']
        
        # winning_bidder
        winning_bidder = str(row['winning_bidder']).strip()
        if not winning_bidder:
            reasons.append("winning_bidder must be a non-empty string")
        elif len(bidders) > 0 and winning_bidder not in bidders:
            reasons.append("winning_bidder is not present in participating_bidders")
        cleaned['winning_bidder'] = winning_bidder
        
        # tender_date
        parsed_date = pd.to_datetime(row['tender_date'], errors='coerce')
        if pd.isna(parsed_date):
            reasons.append("tender_date must be a valid date")
        else:
            min_date = pd.Timestamp('2000-01-01')
            max_date = pd.Timestamp(datetime.now().date())
            if parsed_date < min_date:
                reasons.append(f"tender_date must be on/after {min_date.date()}")
            if parsed_date > max_date:
                reasons.append("tender_date cannot be in the future")
        cleaned['tender_date'] = row['tender_date']
        
        # location
        location = str(row['location']).strip()
        if not location:
            reasons.append("location must be a non-empty string")
        cleaned['location'] = location
        
        return len(reasons) == 0, reasons, cleaned
    
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
            'warnings': [],
            'accepted_records': 0,
            'rejected_records': 0,
            'accepted_rate': 0.0,
            'rejected_rate': 0.0,
            'rejection_reasons_summary': {},
            'rejected_rows': []
        }
        
        # Check required fields
        missing_fields = [f for f in self.REQUIRED_FIELDS if f not in df.columns]
        if missing_fields:
            report['missing_fields'] = missing_fields
            logger.warning(f"Missing required fields: {missing_fields}")
            self.validation_report = report
            self.validated_data = pd.DataFrame(columns=df.columns)
            return False, report
        
        accepted_indices = []
        rejection_summary = {}
        rejected_rows = []

        for idx, row in df.iterrows():
            is_row_valid, reasons, _ = self._validate_row(row, idx)
            if is_row_valid:
                accepted_indices.append(idx)
            else:
                for reason in reasons:
                    rejection_summary[reason] = rejection_summary.get(reason, 0) + 1
                rejected_rows.append({
                    'row_index': int(idx) if isinstance(idx, (int, np.integer)) else str(idx),
                    'tender_id': str(row.get('tender_id', '')),
                    'reasons': reasons
                })

        report['accepted_records'] = len(accepted_indices)
        report['rejected_records'] = len(rejected_rows)
        if len(df) > 0:
            report['accepted_rate'] = round((len(accepted_indices) / len(df)) * 100, 2)
            report['rejected_rate'] = round((len(rejected_rows) / len(df)) * 100, 2)
        report['rejection_reasons_summary'] = rejection_summary
        report['rejected_rows'] = rejected_rows

        if report['rejected_records'] > 0:
            report['warnings'].append(
                f"{report['rejected_records']} row(s) rejected by strict schema validation"
            )

        # Keep only valid rows for downstream pipeline
        self.validated_data = df.loc[accepted_indices].copy()
        is_valid = len(report['missing_fields']) == 0 and report['accepted_records'] > 0
        self.validation_report = report
        
        return is_valid, report
    
    def print_report(self):
        """Print validation report."""
        print("\n=== DATA VALIDATION REPORT ===")
        print(f"Total Records: {self.validation_report['total_records']}")
        print(f"Accepted Records: {self.validation_report.get('accepted_records', 0)}")
        print(f"Rejected Records: {self.validation_report.get('rejected_records', 0)}")
        
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
        
        if self.validation_report.get('rejection_reasons_summary'):
            print("Rejection Reasons Summary:")
            for reason, count in self.validation_report['rejection_reasons_summary'].items():
                print(f"  - {reason}: {count}")


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
        self.validated_data = None
    
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
        self.validated_data = self.validator.validated_data
        self.validator.print_report()
        
        return is_valid
    
    def get_data(self) -> pd.DataFrame:
        """Get loaded data."""
        if self.raw_data is None:
            self.load()
        return self.raw_data
    
    def get_validated_data(self) -> pd.DataFrame:
        """Get strict-schema validated data."""
        if self.validated_data is None:
            if self.raw_data is None:
                self.load()
            self.validate()
        return self.validated_data
    
    def get_validation_report(self) -> Dict[str, any]:
        """Get validation report with row-level rejection reasons."""
        return self.validator.validation_report


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
        self.validation_report = {}
    
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
        self.validation_report = self.loader.get_validation_report()
        if not is_valid:
            raise ValueError(
                "Strict schema validation failed. "
                f"Missing fields: {self.validation_report.get('missing_fields', [])}, "
                f"accepted_records: {self.validation_report.get('accepted_records', 0)}"
            )
        
        # Move forward with only schema-valid rows
        self.data = self.loader.get_validated_data()
        
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
    
    def get_validation_report(self) -> Dict[str, any]:
        """Get strict schema validation report."""
        return self.validation_report
