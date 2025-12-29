"""
JSON logging for options screener alerts.
"""

import json
from datetime import datetime

from screener.config import JSON_FILE, IST
from screener.utils.logging_setup import logger


def log_to_json(alert):
    """
    Convert a single alert to clean JSON format.
    
    Args:
        alert: Alert dictionary
    
    Returns:
        dict: Cleaned alert suitable for JSON serialization
    """
    clean_alert = {
        'timestamp': alert.get('timestamp', ''),
        'symbol': alert.get('symbol', ''),
        'instrument_type': alert.get('instrument_type', ''),
        'strategy': alert.get('strategy', ''),
        'strike': alert.get('strike', ''),
        'premium': round(alert.get('premium', 0), 2),
        'price_source': alert.get('price_source', ''),
        'spot': round(alert.get('spot', 0), 2),
        'volume': alert.get('volume', 0),
        'open_interest': alert.get('open_interest', 0),
        'iv': round(alert.get('iv', 0), 2),
        'iv_percentile': alert.get('iv_percentile', 0),
        'expiry': alert.get('expiry', ''),
        'days_to_expiry': alert.get('days_to_expiry', 0),
        'lot_size': alert.get('lot_size', 0),
        'total_cost': round(alert.get('total_cost', 0), 2),
        'breakeven': alert.get('breakeven', ''),
        'distance_from_spot': alert.get('distance_from_spot', ''),
    }
    
    # Add multi-leg fields if present
    if alert.get('leg1_strike'):
        clean_alert['leg1'] = {
            'strike': alert.get('leg1_strike'),
            'premium': round(alert.get('leg1_premium', 0), 2),
            'action': alert.get('leg1_action', '')
        }
    if alert.get('leg2_strike'):
        clean_alert['leg2'] = {
            'strike': alert.get('leg2_strike'),
            'premium': round(alert.get('leg2_premium', 0), 2),
            'action': alert.get('leg2_action', '')
        }
    if alert.get('max_profit'):
        clean_alert['max_profit'] = round(alert.get('max_profit', 0), 2)
    if alert.get('max_loss'):
        clean_alert['max_loss'] = round(alert.get('max_loss', 0), 2)
    if alert.get('reward_ratio'):
        clean_alert['reward_ratio'] = round(alert.get('reward_ratio', 0), 2)
    
    return clean_alert


def log_alerts_batch_to_json(alerts, top_n=15):
    """
    Log top N alerts by volume to JSON file.
    
    Args:
        alerts: List of alert dictionaries
        top_n: Number of top alerts to save (default: 15)
    """
    if not alerts:
        return
    
    scan_timestamp = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
    
    # Sort alerts by volume (descending) and take top N
    sorted_alerts = sorted(alerts, key=lambda x: x.get('volume', 0), reverse=True)
    top_alerts = sorted_alerts[:top_n]
    
    # Convert to clean JSON format
    top_alerts_json = [log_to_json(alert) for alert in top_alerts]
    
    # Group all alerts by strategy for summary (before filtering)
    strategy_counts = {}
    for a in alerts:
        strat = a.get('strategy', 'Unknown')
        strategy_counts[strat] = strategy_counts.get(strat, 0) + 1
    
    # Create JSON structure with only top alerts
    alerts_data = {
        'last_updated': scan_timestamp,
        'total_scanned': len(alerts),
        'top_alerts_count': len(top_alerts_json),
        'alerts_by_strategy': strategy_counts,
        'top_alerts': top_alerts_json
    }
    
    # Write to file (overwrites previous data with current scan's top alerts)
    with open(JSON_FILE, 'w') as f:
        json.dump(alerts_data, f, indent=2)
    
    logger.info("Top %d alerts saved to JSON: %s", len(top_alerts_json), JSON_FILE)

