"""
CSV logging for options screener alerts.
"""

import csv
import os

from screener.config import CSV_FILE, CSV_HEADERS
from screener.utils.logging_setup import logger


def initialize_csv():
    """
    Initialize CSV file with headers if it doesn't exist.
    """
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode='w', newline='') as f:
            csv.writer(f).writerow(CSV_HEADERS)
        logger.info("CSV file created and headers written")


def log_to_csv(alert):
    """
    Log alert to CSV file, handling both single-leg and multi-leg strategies.
    
    Args:
        alert: Alert dictionary with trade details
    """
    # Handle breakeven - can be number or string for multi-leg strategies
    breakeven = alert.get('breakeven', 0)
    if isinstance(breakeven, (int, float)):
        breakeven = round(breakeven, 2)
    
    with open(CSV_FILE, mode='a', newline='') as f:
        csv.writer(f).writerow([
            alert.get('timestamp', ''),
            alert.get('symbol', ''),
            alert.get('instrument_type', ''),
            alert.get('strategy', ''),
            alert.get('strike', ''),
            round(alert.get('premium', 0), 2),
            alert.get('price_source', 'ask'),
            round(alert.get('spot', 0), 2),
            alert.get('volume', 0),
            alert.get('open_interest', 0),
            alert.get('oi_change', 0),
            round(alert.get('iv', 0), 2),
            alert.get('iv_percentile', 0),
            alert.get('iv_rank', 0),
            alert.get('iv_source', 'unknown'),
            alert.get('market_regime', ''),
            round(alert.get('rsi', 0), 1),
            alert.get('tier', ''),
            alert.get('moneyness', ''),
            alert.get('expiry', ''),
            alert.get('days_to_expiry', 0),
            alert.get('lot_size', 0),
            round(alert.get('total_cost', 0), 2),
            breakeven,
            alert.get('distance_from_spot', ''),
            # Multi-leg strategy fields
            alert.get('leg1_strike', ''),
            round(alert.get('leg1_premium', 0), 2) if alert.get('leg1_premium') else '',
            alert.get('leg1_action', ''),
            alert.get('leg2_strike', ''),
            round(alert.get('leg2_premium', 0), 2) if alert.get('leg2_premium') else '',
            alert.get('leg2_action', ''),
            round(alert.get('max_profit', 0), 2) if alert.get('max_profit') else '',
            round(alert.get('max_loss', 0), 2) if alert.get('max_loss') else '',
            round(alert.get('reward_ratio', 0), 2) if alert.get('reward_ratio') else ''
        ])


# Initialize CSV on module import
initialize_csv()

