"""
Utility functions for the Procurement Corruption Detection System.
"""

import logging
import yaml
import os
from datetime import datetime
import json
import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple


class ConfigManager:
    """Manages system configuration."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize config manager."""
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.warning(f"Config file not found at {self.config_path}, using defaults")
            return {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot notation (e.g., 'data.input_path')."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value


class Logger:
    """Logging utility for the system."""
    
    def __init__(self, name: str = __name__, level: str = "INFO"):
        """Initialize logger."""
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(level)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        ch.setFormatter(formatter)
        
        self.logger.addHandler(ch)
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message."""
        self.logger.error(message)
    
    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)


def load_risk_weights(weights_path: str = "config/risk_weights.yaml") -> Dict[str, Any]:
    """
    Load risk scoring config.
    Primary source is config/config.yaml:risk_scoring, with legacy fallback.
    """
    cfg = ConfigManager().get("risk_scoring", {})
    if isinstance(cfg, dict) and cfg:
        return cfg
    try:
        with open(weights_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logging.warning(f"Risk weights file not found at {weights_path}")
        return {}


def load_system_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """Load full system configuration."""
    return ConfigManager(config_path=config_path).config


def normalize_contractor_name(name: str) -> str:
    """
    Normalize contractor name for comparison.
    
    Args:
        name: Contractor name string
    
    Returns:
        Normalized name
    """
    if pd.isna(name):
        return ""
    
    # Convert to lowercase
    name = str(name).lower().strip()
    
    # Remove common suffixes
    suffixes = [' pvt. ltd', ' pvt ltd', ' private limited', ' ltd', ' ltd.',
                ' limited', ' inc', ' inc.', ' corp', ' corp.', ' corporation',
                ' llc', ' llc.', ' co.', ' co']
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    return name


def fuzzy_match_contractors(names: List[str], threshold: float = 0.85) -> Dict[str, str]:
    """
    Find similar contractor names using fuzzy matching.
    
    Args:
        names: List of contractor names
        threshold: Similarity threshold (0-1)
    
    Returns:
        Dictionary mapping original names to canonical names
    """
    from rapidfuzz import fuzz
    
    mapping = {}
    canonical_names = set()
    
    for name in names:
        if pd.isna(name):
            continue
        
        normalized = normalize_contractor_name(name)
        
        # Find if similar to existing canonical
        found_match = False
        for canonical in canonical_names:
            similarity = fuzz.token_set_ratio(normalized, canonical) / 100
            if similarity >= threshold:
                mapping[name] = canonical
                found_match = True
                break
        
        if not found_match:
            mapping[name] = normalized
            canonical_names.add(normalized)
    
    return mapping


def compute_bid_deviation(bid_amount: float, estimated_cost: float) -> float:
    """
    Compute bid deviation from estimated cost.
    
    Args:
        bid_amount: Actual bid amount
        estimated_cost: Estimated tender cost
    
    Returns:
        Deviation percentage (-1 to infinity)
    """
    if estimated_cost == 0 or pd.isna(estimated_cost):
        return np.nan
    
    return (bid_amount - estimated_cost) / estimated_cost


def compute_z_score(values: np.ndarray, ignore_nan: bool = True) -> np.ndarray:
    """
    Compute Z-scores for array of values.
    
    Args:
        values: Array of values
        ignore_nan: Whether to ignore NaN values
    
    Returns:
        Z-scores array
    """
    if ignore_nan:
        valid_mask = ~np.isnan(values)
        mean = np.nanmean(values)
        std = np.nanstd(values)
    else:
        mean = np.mean(values)
        std = np.std(values)
    
    if std == 0:
        return np.zeros_like(values)
    
    return (values - mean) / std


def detect_outliers_iqr(values: np.ndarray, multiplier: float = 1.5) -> np.ndarray:
    """
    Detect outliers using Interquartile Range (IQR) method.
    
    Args:
        values: Array of values
        multiplier: IQR multiplier (typically 1.5)
    
    Returns:
        Boolean array where True indicates outlier
    """
    q1 = np.nanpercentile(values, 25)
    q3 = np.nanpercentile(values, 75)
    iqr = q3 - q1
    
    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr
    
    return (values < lower_bound) | (values > upper_bound)


def calculate_herfindahl_index(market_shares: List[float]) -> float:
    """
    Calculate Herfindahl-Hirschman Index (HHI) for market concentration.
    
    Args:
        market_shares: List of market share percentages (0-100 or 0-1)
    
    Returns:
        HHI value (0-10000 if percentages, 0-1 if fractions)
    """
    # Normalize to fractions if percentages
    if max(market_shares) > 1:
        market_shares = [s / 100 for s in market_shares]
    
    return sum(s**2 for s in market_shares)


def calculate_entropy(distribution: List[float]) -> float:
    """
    Calculate Shannon entropy of a distribution.
    Higher entropy = more uniform; Lower entropy = more concentrated
    
    Args:
        distribution: Probability distribution
    
    Returns:
        Entropy value
    """
    distribution = np.array(distribution)
    distribution = distribution[distribution > 0]  # Remove zero probabilities
    
    if len(distribution) == 0:
        return 0
    
    return -np.sum(distribution * np.log2(distribution))


def format_currency(value: float, currency: str = "INR") -> str:
    """Format currency value."""
    if currency == "INR":
        return f"₹{value:,.2f}"
    elif currency == "USD":
        return f"${value:,.2f}"
    else:
        return f"{value:,.2f} {currency}"


def format_percentage(value: float, decimal_places: int = 2) -> str:
    """Format percentage value."""
    return f"{value*100:.{decimal_places}f}%"


def save_results(data: Any, filepath: str, format: str = "json"):
    """
    Save analysis results to file.
    
    Args:
        data: Data to save
        filepath: Output file path
        format: Output format ('json', 'csv', 'pickle')
    """
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    
    if format == "json":
        with open(filepath, 'w') as f:
            if isinstance(data, pd.DataFrame):
                data.to_json(f, orient='records', indent=2)
            else:
                json.dump(data, f, indent=2, default=str)
    elif format == "csv" and isinstance(data, pd.DataFrame):
        data.to_csv(filepath, index=False)
    elif format == "pickle":
        import pickle
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)


def load_results(filepath: str, format: str = "json") -> Any:
    """Load analysis results from file."""
    if format == "json":
        with open(filepath, 'r') as f:
            return json.load(f)
    elif format == "csv":
        return pd.read_csv(filepath)
    elif format == "pickle":
        import pickle
        with open(filepath, 'rb') as f:
            return pickle.load(f)


def get_statistics_summary(data: pd.Series) -> Dict[str, float]:
    """Get summary statistics for a series."""
    return {
        "count": data.count(),
        "mean": data.mean(),
        "median": data.median(),
        "std": data.std(),
        "min": data.min(),
        "25%": data.quantile(0.25),
        "75%": data.quantile(0.75),
        "max": data.max()
    }


class ProgressTracker:
    """Track progress of long-running operations."""
    
    def __init__(self, total_items: int, name: str = "Processing"):
        """Initialize progress tracker."""
        self.total_items = total_items
        self.name = name
        self.current_item = 0
        self.start_time = datetime.now()
    
    def update(self, items: int = 1):
        """Update progress."""
        self.current_item += items
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        if self.current_item > 0:
            rate = elapsed / self.current_item
            remaining = (self.total_items - self.current_item) * rate
            
            percentage = (self.current_item / self.total_items) * 100
            print(f"\r{self.name}: {percentage:.1f}% ({self.current_item}/{self.total_items}) - "
                  f"ETA: {remaining:.0f}s", end='', flush=True)
    
    def finish(self):
        """Mark as complete."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        print(f"\n{self.name} completed in {elapsed:.2f} seconds")
