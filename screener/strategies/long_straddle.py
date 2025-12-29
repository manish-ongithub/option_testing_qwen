"""
Long Straddle strategy scanner.
"""

from datetime import datetime

from screener.config import (
    IST, IV_PERCENTILE_LOW, MIN_DAYS_TO_EXPIRY_VOLATILITY,
    MIN_OI_PER_LEG_INDEX, MIN_OI_PER_LEG_STOCK, MAX_STRADDLE_COST_PCT
)
from screener.strategies.helpers import calculate_straddle_metrics, is_spread_liquid
from screener.utils.helpers import calculate_days_to_expiry


def scan_long_straddle(symbol, calls, puts, spot, atm_strike, expiry, iv_data, lot_size, is_index=False):
    """
    Scan for Long Straddle opportunities.
    
    Long Straddle: Buy ATM Call + Buy ATM Put (same strike)
    Trigger: Low IV + Expecting big move
    
    Args:
        symbol: Stock/Index symbol
        calls: Dict of call options {strike: option_data}
        puts: Dict of put options {strike: option_data}
        spot: Current spot price
        atm_strike: ATM strike price
        expiry: Expiry date string
        iv_data: IV data dict from provider
        lot_size: Lot size for the symbol
        is_index: True for index options
    
    Returns:
        list: List of straddle alerts
    """
    alerts = []
    
    # Only trigger when IV is low (cheap premiums)
    if iv_data['iv_percentile'] > IV_PERCENTILE_LOW:
        return alerts
    
    # Check days to expiry (need enough time for move to happen)
    dte = calculate_days_to_expiry(expiry)
    if dte < MIN_DAYS_TO_EXPIRY_VOLATILITY:
        return alerts
    
    # Check if ATM strike has both call and put
    if atm_strike not in calls or atm_strike not in puts:
        return alerts
    
    call_opt = calls[atm_strike]
    put_opt = puts[atm_strike]
    
    # Get prices
    call_price = call_opt.get('askPrice') or call_opt.get('lastPrice') or 0
    put_price = put_opt.get('askPrice') or put_opt.get('lastPrice') or 0
    
    if call_price <= 0 or put_price <= 0:
        return alerts
    
    # Check liquidity
    min_oi = MIN_OI_PER_LEG_INDEX if is_index else MIN_OI_PER_LEG_STOCK
    call_oi = call_opt.get('openInterest') or 0
    put_oi = put_opt.get('openInterest') or 0
    
    if not is_spread_liquid(call_oi, put_oi, min_oi):
        return alerts
    
    # Calculate straddle metrics
    metrics = calculate_straddle_metrics(call_price, put_price, atm_strike, spot)
    
    # Filter: total cost should not be too high relative to spot
    cost_pct = metrics['total_cost'] / spot
    if cost_pct > MAX_STRADDLE_COST_PCT:
        return alerts
    
    # Create alert
    alert = {
        'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
        'symbol': symbol,
        'instrument_type': 'INDEX' if is_index else 'STOCK',
        'strategy': 'Long Straddle',
        'type': 'CE+PE',
        'spot': spot,
        'strike': atm_strike,
        'premium': metrics['total_cost'],
        'price_source': 'straddle',
        'leg1_strike': atm_strike,
        'leg1_premium': call_price,
        'leg1_action': 'BUY CE',
        'leg2_strike': atm_strike,
        'leg2_premium': put_price,
        'leg2_action': 'BUY PE',
        'volume': call_opt.get('totalTradedVolume', 0) + put_opt.get('totalTradedVolume', 0),
        'open_interest': min(call_oi, put_oi),
        'oi_change': 0,
        'iv': iv_data['iv'],
        'iv_percentile': iv_data['iv_percentile'],
        'iv_rank': iv_data['iv_rank'],
        'iv_source': iv_data['source'],
        'market_regime': '',
        'rsi': 0,
        'tier': 'INDEX' if is_index else '',
        'moneyness': 'ATM',
        'expiry': expiry,
        'days_to_expiry': dte,
        'lot_size': lot_size,
        'total_cost': metrics['total_cost'] * lot_size,
        'max_profit': 0,  # Unlimited
        'max_loss': metrics['total_cost'] * lot_size,
        'breakeven': f"{metrics['lower_breakeven']:.0f}/{metrics['upper_breakeven']:.0f}",
        'reward_ratio': 0,  # Unlimited upside
        'distance_from_spot': f"±{metrics['move_required_pct']:.1f}% to breakeven"
    }
    
    alerts.append(alert)
    return alerts

