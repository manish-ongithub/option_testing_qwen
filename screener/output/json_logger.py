"""
JSON logging for options screener alerts.
Includes enhanced probability of profit (PoP) calculations with STT adjustment.
"""

import json
import math
from datetime import datetime
from typing import Dict, Any, Optional

from screener.config import JSON_FILE, IST
from screener.utils.logging_setup import logger


# =============================================================================
# Probability Calculator (Embedded for efficiency)
# =============================================================================

# Indian market constants
RISK_FREE_RATE = 0.066  # 6.6% - India 10Y bond rate
STT_RATE = 0.00125      # 0.125% STT on exercise


def _norm_cdf(x: float) -> float:
    """Cumulative normal distribution using Abramowitz/Stegun approximation."""
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    
    sign = 1 if x >= 0 else -1
    x = abs(x)
    
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x / 2)
    
    return 0.5 * (1.0 + sign * y)


def _calculate_d2(spot: float, target_price: float, time_years: float, 
                  volatility: float, drift: float) -> float:
    """Calculate Black-Scholes d2 for probability calculations."""
    if time_years <= 0:
        time_years = 1/365
    if volatility <= 0:
        volatility = 0.01
    
    sqrt_t = math.sqrt(time_years)
    d1 = (math.log(spot / target_price) + (drift + 0.5 * volatility ** 2) * time_years) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    
    return d2


def calculate_probability_of_profit(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Probability of Profit (PoP) for an options alert.
    
    Supports: Long Call, Long Put, Bull Call Spread, Bear Put Spread, 
              Long Straddle, Long Strangle
    
    Returns:
        Dict with pop_raw, pop_stt_adjusted, tax_risk, breakeven info
    """
    strategy = alert.get('strategy', '')
    spot = float(alert.get('spot', 0))
    iv = float(alert.get('iv', 0))
    days_to_expiry = int(alert.get('days_to_expiry', 0))
    premium = float(alert.get('premium', 0))
    
    if spot <= 0 or iv <= 0 or days_to_expiry <= 0:
        return None
    
    # Convert IV to decimal and calculate time
    volatility = iv / 100 if iv > 1 else iv
    time_years = max(days_to_expiry / 365.0, 1/365)
    stt_cost = spot * STT_RATE
    
    result = {
        'method': 'Black-Scholes d2',
        'drift_used': RISK_FREE_RATE,
        'stt_cost': round(stt_cost, 2)
    }
    
    try:
        if strategy == 'Long Call':
            strike = float(alert.get('strike', 0))
            breakeven_raw = strike + premium
            breakeven_stt = breakeven_raw + stt_cost
            
            d2_raw = _calculate_d2(spot, breakeven_raw, time_years, volatility, RISK_FREE_RATE)
            d2_stt = _calculate_d2(spot, breakeven_stt, time_years, volatility, RISK_FREE_RATE)
            
            pop_raw = _norm_cdf(d2_raw) * 100
            pop_stt = _norm_cdf(d2_stt) * 100
            
            # Probability ITM
            d2_strike = _calculate_d2(spot, strike, time_years, volatility, RISK_FREE_RATE)
            prob_itm = _norm_cdf(d2_strike) * 100
            
            result.update({
                'pop_raw': round(pop_raw, 2),
                'pop_stt_adjusted': round(pop_stt, 2),
                'tax_risk': round(pop_raw - pop_stt, 2),
                'breakeven_raw': round(breakeven_raw, 2),
                'breakeven_stt_adjusted': round(breakeven_stt, 2),
                'probability_itm': round(prob_itm, 2),
            })
            
        elif strategy == 'Long Put':
            strike = float(alert.get('strike', 0))
            breakeven_raw = strike - premium
            breakeven_stt = breakeven_raw - stt_cost
            
            d2_raw = _calculate_d2(spot, breakeven_raw, time_years, volatility, RISK_FREE_RATE)
            d2_stt = _calculate_d2(spot, breakeven_stt, time_years, volatility, RISK_FREE_RATE)
            
            pop_raw = _norm_cdf(-d2_raw) * 100
            pop_stt = _norm_cdf(-d2_stt) * 100
            
            # Probability ITM
            d2_strike = _calculate_d2(spot, strike, time_years, volatility, RISK_FREE_RATE)
            prob_itm = _norm_cdf(-d2_strike) * 100
            
            result.update({
                'pop_raw': round(pop_raw, 2),
                'pop_stt_adjusted': round(pop_stt, 2),
                'tax_risk': round(pop_raw - pop_stt, 2),
                'breakeven_raw': round(breakeven_raw, 2),
                'breakeven_stt_adjusted': round(breakeven_stt, 2),
                'probability_itm': round(prob_itm, 2),
            })
            
        elif strategy == 'Bull Call Spread':
            # Parse multi-leg strikes
            strike_str = str(alert.get('strike', ''))
            if '/' in strike_str:
                parts = strike_str.split('/')
                long_strike = float(parts[0])
                short_strike = float(parts[1])
            else:
                long_strike = float(alert.get('strike', 0))
                short_strike = long_strike + 100  # Default spread width
            
            breakeven_raw = long_strike + premium
            breakeven_stt = breakeven_raw + stt_cost
            
            d2_raw = _calculate_d2(spot, breakeven_raw, time_years, volatility, RISK_FREE_RATE)
            d2_stt = _calculate_d2(spot, breakeven_stt, time_years, volatility, RISK_FREE_RATE)
            d2_short = _calculate_d2(spot, short_strike, time_years, volatility, RISK_FREE_RATE)
            
            pop_raw = _norm_cdf(d2_raw) * 100
            pop_stt = _norm_cdf(d2_stt) * 100
            prob_max_profit = _norm_cdf(d2_short) * 100
            
            result.update({
                'pop_raw': round(pop_raw, 2),
                'pop_stt_adjusted': round(pop_stt, 2),
                'tax_risk': round(pop_raw - pop_stt, 2),
                'breakeven_raw': round(breakeven_raw, 2),
                'probability_max_profit': round(prob_max_profit, 2),
            })
            
        elif strategy == 'Bear Put Spread':
            # Parse multi-leg strikes
            strike_str = str(alert.get('strike', ''))
            if '/' in strike_str:
                parts = strike_str.split('/')
                long_strike = float(parts[0])
                short_strike = float(parts[1])
            else:
                long_strike = float(alert.get('strike', 0))
                short_strike = long_strike - 100
            
            breakeven_raw = long_strike - premium
            breakeven_stt = breakeven_raw - stt_cost
            
            d2_raw = _calculate_d2(spot, breakeven_raw, time_years, volatility, RISK_FREE_RATE)
            d2_stt = _calculate_d2(spot, breakeven_stt, time_years, volatility, RISK_FREE_RATE)
            d2_short = _calculate_d2(spot, short_strike, time_years, volatility, RISK_FREE_RATE)
            
            pop_raw = _norm_cdf(-d2_raw) * 100
            pop_stt = _norm_cdf(-d2_stt) * 100
            prob_max_profit = _norm_cdf(-d2_short) * 100
            
            result.update({
                'pop_raw': round(pop_raw, 2),
                'pop_stt_adjusted': round(pop_stt, 2),
                'tax_risk': round(pop_raw - pop_stt, 2),
                'breakeven_raw': round(breakeven_raw, 2),
                'probability_max_profit': round(prob_max_profit, 2),
            })
            
        elif strategy in ['Long Straddle', 'Long Strangle']:
            # Parse breakeven from alert (format: "lower/upper")
            breakeven_str = str(alert.get('breakeven', ''))
            
            if '/' in breakeven_str:
                parts = breakeven_str.split('/')
                lower_be_raw = float(parts[0])
                upper_be_raw = float(parts[1])
            else:
                # Calculate from strike and premium
                strike_str = str(alert.get('strike', ''))
                if '/' in strike_str:
                    parts = strike_str.split('/')
                    put_strike = float(parts[0])
                    call_strike = float(parts[1])
                else:
                    put_strike = call_strike = float(alert.get('strike', 0))
                
                lower_be_raw = put_strike - premium
                upper_be_raw = call_strike + premium
            
            lower_be_stt = lower_be_raw - stt_cost
            upper_be_stt = upper_be_raw + stt_cost
            
            d2_upper_raw = _calculate_d2(spot, upper_be_raw, time_years, volatility, RISK_FREE_RATE)
            d2_lower_raw = _calculate_d2(spot, lower_be_raw, time_years, volatility, RISK_FREE_RATE)
            d2_upper_stt = _calculate_d2(spot, upper_be_stt, time_years, volatility, RISK_FREE_RATE)
            d2_lower_stt = _calculate_d2(spot, lower_be_stt, time_years, volatility, RISK_FREE_RATE)
            
            # P(Profit) = P(S < Lower BE) + P(S > Upper BE)
            pop_raw = (_norm_cdf(-d2_lower_raw) + _norm_cdf(d2_upper_raw)) * 100
            pop_stt = (_norm_cdf(-d2_lower_stt) + _norm_cdf(d2_upper_stt)) * 100
            
            result.update({
                'pop_raw': round(pop_raw, 2),
                'pop_stt_adjusted': round(pop_stt, 2),
                'tax_risk': round(pop_raw - pop_stt, 2),
                'breakeven_lower': round(lower_be_raw, 2),
                'breakeven_upper': round(upper_be_raw, 2),
                'prob_above_upper': round(_norm_cdf(d2_upper_raw) * 100, 2),
                'prob_below_lower': round(_norm_cdf(-d2_lower_raw) * 100, 2),
            })
        else:
            # Unknown strategy
            return None
            
    except Exception as e:
        logger.debug("Probability calculation error for %s: %s", strategy, str(e))
        return None
    
    return result


# =============================================================================
# JSON Logging Functions
# =============================================================================

def log_to_json(alert):
    """
    Convert a single alert to clean JSON format with probability data.
    
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
    
    # Calculate and add probability of profit
    probability_data = calculate_probability_of_profit(clean_alert)
    if probability_data:
        clean_alert['probability'] = probability_data
    
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

