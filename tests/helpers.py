"""Shared test helpers."""

from datetime import datetime, timedelta
from typing import List, Dict


def make_valid_records(count: int = 6) -> List[Dict]:
    """Create valid tender records for tests."""
    records = []
    base_date = datetime(2024, 1, 1)
    for i in range(count):
        bidders = [f"Bidder {j}" for j in range(1, 4)]
        winning_idx = i % 3
        winning_bid = 95000 + (i * 1000) + (winning_idx * 500)
        bid_amounts = [
            winning_bid + 1200,
            winning_bid + 2000,
            winning_bid
        ]

        records.append(
            {
                "tender_id": f"T{i+1:04d}",
                "department": "Transport" if i % 2 == 0 else "Water",
                "estimated_cost": 100000 + i * 5000,
                "participating_bidders": ", ".join(bidders),
                "bid_amounts": ", ".join(str(x) for x in bid_amounts),
                "winning_bidder": bidders[winning_idx],
                "winning_bid": float(winning_bid),
                "tender_date": (base_date + timedelta(days=i * 10)).strftime("%Y-%m-%d"),
                "location": "North" if i % 2 == 0 else "South",
                "is_corrupt": 1 if i in (1, 4) else 0,
            }
        )
    return records
