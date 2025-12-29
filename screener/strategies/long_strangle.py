"""
Long Strangle strategy scanner.
"""

from datetime import datetime

from screener.config import (
    IST, IV_PERCENTILE_VERY_LOW, MIN_DAYS_TO_EXPIRY_VOLATILITY,
    SPREAD_WIDTH_INDEX, SPREAD_WIDTH_STOCKS,
    MIN_OI_PER_LEG_INDEX, MIN_OI_PER_LEG_STOCK, MAX_STRANGLE_COST_PCT
)
from screener.strategies.helpers import (
    find_strangle_strikes,
    calculate_strangle_metrics,
    is_spread_liquid
)
from screener.utils.helpers import calculate_days_to_expiry


def scan_long_strangle(symbol, calls, puts, spot, strikes, atm_strike, expiry, iv_data, lot_size, is_index=False):
    """
    Scan for Long Strangle opportunities.
    
    Long Strangle: Buy OTM Call + Buy OTM Put (different strikes)
    Trigger: Very low IV + Expecting big move
    
    Args:
        symbol: Stock/Index symbol
        calls: Dict of call options {strike: option_data}
        puts: Dict of put options {strike: option_data}
        spot: Current spot price
        strikes: Sorted list of available strikes
        atm_strike: ATM strike price
        expiry: Expiry date string
        iv_data: IV data dict from provider
        lot_size: Lot size for the symbol
        is_index: True for index options
    
    Returns:
        list: List of strangle alerts
    """
    alerts = []
    
    # Only trigger when IV is very low
    if iv_data['iv_percentile'] > IV_PERCENTILE_VERY_LOW:
        return alerts
    
    # Check days to expiry
    dte = calculate_days_to_expiry(expiry)
    if dte < MIN_DAYS_TO_EXPIRY_VOLATILITY:
        return alerts
    
    # Determine width
    width = SPREAD_WIDTH_INDEX if is_index else SPREAD_WIDTH_STOCKS
    
    # Find OTM strikes
    call_strike, put_strike = find_strangle_strikes(spot, strikes, atm_strike, width)
    
    if not call_strike or not put_strike:
        return alerts
    
    # Check if both strikes have option data
    if call_strike not in calls or put_strike not in puts:
        return alerts
    
    call_opt = calls[call_strike]
    put_opt = puts[put_strike]
    
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
    
    # Calculate strangle metrics
    metrics = calculate_strangle_metrics(call_price, put_price, call_strike, put_strike, spot)
    
    # Filter: total cost should not be too high
    cost_pct = metrics['total_cost'] / spot
    if cost_pct > MAX_STRANGLE_COST_PCT:
        return alerts
    
    # Create alert
    alert = {
        'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
        'symbol': symbol,
        'instrument_type': 'INDEX' if is_index else 'STOCK',
        'strategy': 'Long Strangle',
        'type': 'CE+PE',
        'spot': spot,
        'strike': f"{put_strike}/{call_strike}",
        'premium': metrics['total_cost'],
        'price_source': 'strangle',
        'leg1_strike': call_strike,
        'leg1_premium': call_price,
        'leg1_action': 'BUY CE',
        'leg2_strike': put_strike,
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
        'moneyness': 'OTM',
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

