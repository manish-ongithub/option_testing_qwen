"""
CSV logging for options screener alerts.
Includes probability of profit calculations with STT adjustment.
"""

import csv
import os
import math

from screener.config import CSV_FILE, CSV_HEADERS
from screener.utils.logging_setup import logger


# =============================================================================
# Probability Calculator (Same as json_logger for consistency)
# =============================================================================

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


def calculate_probability_for_csv(alert):
    """
    Calculate Probability of Profit for CSV logging.
    Returns a dict with probability fields.
    """
    strategy = alert.get('strategy', '')
    spot = float(alert.get('spot', 0))
    iv = float(alert.get('iv', 0))
    days_to_expiry = int(alert.get('days_to_expiry', 0))
    premium = float(alert.get('premium', 0))
    
    # Default empty results
    result = {
        'pop_raw': '',
        'pop_stt_adjusted': '',
        'tax_risk': '',
        'prob_itm': '',
        'prob_max_profit': '',
        'breakeven_stt': '',
        'stt_cost': ''
    }
    
    if spot <= 0 or iv <= 0 or days_to_expiry <= 0:
        return result
    
    volatility = iv / 100 if iv > 1 else iv
    time_years = max(days_to_expiry / 365.0, 1/365)
    stt_cost = spot * STT_RATE
    
    try:
        if strategy == 'Long Call':
            strike = float(alert.get('strike', 0))
            breakeven_raw = strike + premium
            breakeven_stt = breakeven_raw + stt_cost
            
            d2_raw = _calculate_d2(spot, breakeven_raw, time_years, volatility, RISK_FREE_RATE)
            d2_stt = _calculate_d2(spot, breakeven_stt, time_years, volatility, RISK_FREE_RATE)
            d2_strike = _calculate_d2(spot, strike, time_years, volatility, RISK_FREE_RATE)
            
            result = {
                'pop_raw': round(_norm_cdf(d2_raw) * 100, 2),
                'pop_stt_adjusted': round(_norm_cdf(d2_stt) * 100, 2),
                'tax_risk': round((_norm_cdf(d2_raw) - _norm_cdf(d2_stt)) * 100, 2),
                'prob_itm': round(_norm_cdf(d2_strike) * 100, 2),
                'prob_max_profit': '',
                'breakeven_stt': round(breakeven_stt, 2),
                'stt_cost': round(stt_cost, 2)
            }
            
        elif strategy == 'Long Put':
            strike = float(alert.get('strike', 0))
            breakeven_raw = strike - premium
            breakeven_stt = breakeven_raw - stt_cost
            
            d2_raw = _calculate_d2(spot, breakeven_raw, time_years, volatility, RISK_FREE_RATE)
            d2_stt = _calculate_d2(spot, breakeven_stt, time_years, volatility, RISK_FREE_RATE)
            d2_strike = _calculate_d2(spot, strike, time_years, volatility, RISK_FREE_RATE)
            
            result = {
                'pop_raw': round(_norm_cdf(-d2_raw) * 100, 2),
                'pop_stt_adjusted': round(_norm_cdf(-d2_stt) * 100, 2),
                'tax_risk': round((_norm_cdf(-d2_raw) - _norm_cdf(-d2_stt)) * 100, 2),
                'prob_itm': round(_norm_cdf(-d2_strike) * 100, 2),
                'prob_max_profit': '',
                'breakeven_stt': round(breakeven_stt, 2),
                'stt_cost': round(stt_cost, 2)
            }
            
        elif strategy == 'Bull Call Spread':
            strike_str = str(alert.get('strike', ''))
            if '/' in strike_str:
                parts = strike_str.split('/')
                long_strike = float(parts[0])
                short_strike = float(parts[1])
            else:
                long_strike = float(alert.get('strike', 0))
                short_strike = long_strike + 100
            
            breakeven_raw = long_strike + premium
            breakeven_stt = breakeven_raw + stt_cost
            
            d2_raw = _calculate_d2(spot, breakeven_raw, time_years, volatility, RISK_FREE_RATE)
            d2_stt = _calculate_d2(spot, breakeven_stt, time_years, volatility, RISK_FREE_RATE)
            d2_short = _calculate_d2(spot, short_strike, time_years, volatility, RISK_FREE_RATE)
            
            result = {
                'pop_raw': round(_norm_cdf(d2_raw) * 100, 2),
                'pop_stt_adjusted': round(_norm_cdf(d2_stt) * 100, 2),
                'tax_risk': round((_norm_cdf(d2_raw) - _norm_cdf(d2_stt)) * 100, 2),
                'prob_itm': '',
                'prob_max_profit': round(_norm_cdf(d2_short) * 100, 2),
                'breakeven_stt': round(breakeven_stt, 2),
                'stt_cost': round(stt_cost, 2)
            }
            
        elif strategy == 'Bear Put Spread':
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
            
            result = {
                'pop_raw': round(_norm_cdf(-d2_raw) * 100, 2),
                'pop_stt_adjusted': round(_norm_cdf(-d2_stt) * 100, 2),
                'tax_risk': round((_norm_cdf(-d2_raw) - _norm_cdf(-d2_stt)) * 100, 2),
                'prob_itm': '',
                'prob_max_profit': round(_norm_cdf(-d2_short) * 100, 2),
                'breakeven_stt': round(breakeven_stt, 2),
                'stt_cost': round(stt_cost, 2)
            }
            
        elif strategy in ['Long Straddle', 'Long Strangle']:
            breakeven_str = str(alert.get('breakeven', ''))
            
            if '/' in breakeven_str:
                parts = breakeven_str.split('/')
                lower_be_raw = float(parts[0])
                upper_be_raw = float(parts[1])
            else:
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
            
            pop_raw = (_norm_cdf(-d2_lower_raw) + _norm_cdf(d2_upper_raw)) * 100
            pop_stt = (_norm_cdf(-d2_lower_stt) + _norm_cdf(d2_upper_stt)) * 100
            
            result = {
                'pop_raw': round(pop_raw, 2),
                'pop_stt_adjusted': round(pop_stt, 2),
                'tax_risk': round(pop_raw - pop_stt, 2),
                'prob_itm': '',
                'prob_max_profit': '',
                'breakeven_stt': f"{round(lower_be_stt, 2)}/{round(upper_be_stt, 2)}",
                'stt_cost': round(stt_cost, 2)
            }
            
    except Exception as e:
        logger.debug("Probability calculation error for CSV: %s", str(e))
    
    return result


# =============================================================================
# CSV Functions
# =============================================================================

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
    Includes probability of profit calculations.
    
    Args:
        alert: Alert dictionary with trade details
    """
    # Handle breakeven - can be number or string for multi-leg strategies
    breakeven = alert.get('breakeven', 0)
    if isinstance(breakeven, (int, float)):
        breakeven = round(breakeven, 2)
    
    # Calculate probability data
    prob_data = calculate_probability_for_csv(alert)
    
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
            # Probability of Profit fields
            prob_data['pop_raw'],
            prob_data['pop_stt_adjusted'],
            prob_data['tax_risk'],
            prob_data['prob_itm'],
            prob_data['prob_max_profit'],
            prob_data['breakeven_stt'],
            prob_data['stt_cost'],
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

