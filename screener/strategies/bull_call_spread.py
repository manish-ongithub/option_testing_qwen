"""
Bull Call Spread strategy scanner.
"""

from datetime import datetime

from screener.config import (
    IST, IV_HIGH, SPREAD_WIDTH_INDEX, SPREAD_WIDTH_STOCKS,
    MIN_OI_PER_LEG_INDEX, MIN_OI_PER_LEG_STOCK, MIN_SPREAD_REWARD_RATIO
)
from screener.strategies.helpers import (
    find_spread_strikes,
    calculate_spread_metrics,
    is_spread_liquid
)
from screener.utils.helpers import calculate_days_to_expiry


def scan_bull_call_spread(symbol, calls, spot, strikes, atm_strike, expiry, iv_data, trend_data, lot_size, is_index=False):
    """
    Scan for Bull Call Spread opportunities.
    
    Bull Call Spread: Buy ATM/ITM call + Sell OTM call
    Trigger: Bullish bias + Low-Medium IV
    
    Args:
        symbol: Stock/Index symbol
        calls: Dict of call options {strike: option_data}
        spot: Current spot price
        strikes: Sorted list of available strikes
        atm_strike: ATM strike price
        expiry: Expiry date string
        iv_data: IV data dict from provider
        trend_data: Trend/RSI data dict
        lot_size: Lot size for the symbol
        is_index: True for index options
    
    Returns:
        list: List of spread alerts
    """
    alerts = []
    
    # Only scan if bullish conditions
    if trend_data['bias'] not in ['BULLISH', 'NEUTRAL']:
        return alerts
    
    # Skip if IV is too high (expensive premiums)
    if iv_data['iv_percentile'] > IV_HIGH:
        return alerts
    
    # Determine spread width based on instrument type
    width = SPREAD_WIDTH_INDEX if is_index else SPREAD_WIDTH_STOCKS
    min_oi = MIN_OI_PER_LEG_INDEX if is_index else MIN_OI_PER_LEG_STOCK
    
    # Find spread strikes
    buy_strike, sell_strike = find_spread_strikes(spot, strikes, atm_strike, 'bull', width)
    
    if not buy_strike or not sell_strike:
        return alerts
    
    # Check if both strikes have option data
    if buy_strike not in calls or sell_strike not in calls:
        return alerts
    
    buy_opt = calls[buy_strike]
    sell_opt = calls[sell_strike]
    
    # Get prices (use ask for buy, bid for sell - conservative)
    buy_price = buy_opt.get('askPrice') or buy_opt.get('lastPrice') or 0
    sell_price = sell_opt.get('bidPrice') or sell_opt.get('lastPrice') or 0
    
    if buy_price <= 0 or sell_price <= 0:
        return alerts
    
    # Check liquidity on both legs
    buy_oi = buy_opt.get('openInterest') or 0
    sell_oi = sell_opt.get('openInterest') or 0
    
    if not is_spread_liquid(buy_oi, sell_oi, min_oi):
        return alerts
    
    # Calculate spread metrics
    strike_diff = sell_strike - buy_strike
    metrics = calculate_spread_metrics(buy_price, sell_price, strike_diff, 'CE', buy_strike)
    
    # Filter: net debit should be positive and reward ratio should be acceptable
    if metrics['net_debit'] <= 0:
        return alerts
    
    if metrics['reward_ratio'] < MIN_SPREAD_REWARD_RATIO:
        return alerts
    
    # Create alert
    alert = {
        'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
        'symbol': symbol,
        'instrument_type': 'INDEX' if is_index else 'STOCK',
        'strategy': 'Bull Call Spread',
        'type': 'CE',
        'spot': spot,
        'strike': f"{buy_strike}/{sell_strike}",
        'premium': metrics['net_debit'],
        'price_source': 'spread',
        'leg1_strike': buy_strike,
        'leg1_premium': buy_price,
        'leg1_action': 'BUY',
        'leg2_strike': sell_strike,
        'leg2_premium': sell_price,
        'leg2_action': 'SELL',
        'volume': buy_opt.get('totalTradedVolume', 0) + sell_opt.get('totalTradedVolume', 0),
        'open_interest': min(buy_oi, sell_oi),
        'oi_change': 0,
        'iv': iv_data['iv'],
        'iv_percentile': iv_data['iv_percentile'],
        'iv_rank': iv_data['iv_rank'],
        'iv_source': iv_data['source'],
        'market_regime': '',
        'rsi': trend_data.get('rsi', 0),
        'tier': 'INDEX' if is_index else '',
        'moneyness': 'ATM',
        'expiry': expiry,
        'days_to_expiry': calculate_days_to_expiry(expiry),
        'lot_size': lot_size,
        'total_cost': metrics['net_debit'] * lot_size,
        'max_profit': metrics['max_profit'] * lot_size,
        'max_loss': metrics['max_loss'] * lot_size,
        'breakeven': metrics['breakeven'],
        'reward_ratio': metrics['reward_ratio'],
        'distance_from_spot': f"+{((sell_strike - spot) / spot * 100):.1f}%"
    }
    
    alerts.append(alert)
    return alerts

