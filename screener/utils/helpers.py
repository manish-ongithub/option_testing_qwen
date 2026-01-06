"""
Utility helper functions for the options screener.
"""

from datetime import datetime
import pandas as pd
import numpy as np
import yfinance as yf

from screener.config import (
    LOT_SIZES, DEFAULT_LOT_SIZE, STOCK_TIERS,
    SYMBOL_MAP, IST
)
from screener.utils.logging_setup import logger


# ================== CONFIGURABLE TREND PARAMETERS ==================
# These can be overridden at runtime via set_trend_params()
_TREND_PARAMS = {
    'period': '1mo',   # Lookback period for RSI/EMA (1w, 1mo, 3mo, 6mo, 1y)
    'interval': '1d',  # Data interval (1d, 1h, 5m)
}


def set_trend_params(period='1mo', interval='1d'):
    """
    Set the trend calculation parameters (used by compute_trend_indicators).
    
    Args:
        period: Lookback period ('1w', '1mo', '3mo', '6mo', '1y')
        interval: Data interval ('1d', '1h', '5m')
    """
    _TREND_PARAMS['period'] = period
    _TREND_PARAMS['interval'] = interval
    logger.debug("Trend params set: period=%s, interval=%s", period, interval)


def get_trend_params():
    """Get current trend calculation parameters."""
    return _TREND_PARAMS.copy()


def get_lot_size(symbol):
    """Get the lot size for a symbol."""
    return LOT_SIZES.get(symbol, DEFAULT_LOT_SIZE)


def get_stock_tier(symbol):
    """Get the tier classification for a stock."""
    for tier, stocks in STOCK_TIERS.items():
        if symbol in stocks:
            return tier
    return 'TIER_3'


def find_atm_strike(strikes, spot):
    """Find the at-the-money strike closest to spot price."""
    return min(strikes, key=lambda x: abs(x - spot))


def get_moneyness(strike, spot, opt_type):
    """
    Determine if an option is ITM, ATM, or OTM.
    
    Args:
        strike: Strike price
        spot: Current spot price
        opt_type: 'CE' for call, 'PE' for put
    
    Returns:
        str: 'ITM', 'ATM', or 'OTM'
    """
    pct_diff = (strike - spot) / spot * 100
    if opt_type == "CE":
        if pct_diff < -2:
            return "ITM"
        elif pct_diff > 2:
            return "OTM"
        else:
            return "ATM"
    else:
        if pct_diff > 2:
            return "ITM"
        elif pct_diff < -2:
            return "OTM"
        else:
            return "ATM"


def calculate_breakeven(strike, premium, opt_type):
    """Calculate the breakeven price for an option."""
    if opt_type == "CE":
        return strike + premium
    else:
        return strike - premium


def calculate_distance_from_spot(strike, spot, opt_type):
    """
    Calculate the percentage distance of strike from spot.
    
    Returns:
        str: Human-readable distance (e.g., '+2.5% OTM')
    """
    diff = strike - spot
    pct = abs(diff) / spot * 100
    if opt_type == "CE":
        if diff > 0:
            return f"+{pct:.1f}% OTM"
        elif diff < 0:
            return f"-{pct:.1f}% ITM"
        else:
            return "ATM"
    else:
        if diff < 0:
            return f"-{pct:.1f}% OTM"
        elif diff > 0:
            return f"+{pct:.1f}% ITM"
        else:
            return "ATM"


def parse_expiry_date(expiry_str):
    """
    Parse expiry date string into datetime object.
    
    Supports formats: '31-Dec-2024', '2024-12-31', '31-December-2024', '31/12/2024'
    """
    try:
        for fmt in ["%d-%b-%Y", "%Y-%m-%d", "%d-%B-%Y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(expiry_str, fmt)
            except ValueError:
                continue
        return None
    except:
        return None


def calculate_days_to_expiry(expiry_str):
    """Calculate the number of days until expiry."""
    expiry_date = parse_expiry_date(expiry_str)
    if expiry_date:
        today = datetime.now(IST).replace(tzinfo=None)
        expiry_date = expiry_date.replace(hour=15, minute=30)
        delta = expiry_date - today
        return max(0, delta.days)
    return -1


def get_option_price(opt, market_open=True):
    """
    Get option price with priority based on market status.
    
    During market hours: prefer ask price (conservative entry)
    After hours: prefer LTP (last traded price is more reliable)
    
    Args:
        opt: Option data dictionary
        market_open: Whether market is currently open
    
    Returns:
        tuple: (price, source) where source is 'ask', 'bid', 'ltp', or 'none'
    """
    ask = opt.get('askprice') or opt.get('askPrice') or opt.get('ask') or 0
    bid = opt.get('bidprice') or opt.get('bidPrice') or opt.get('bid') or 0
    ltp = opt.get('lastPrice') or opt.get('ltp') or opt.get('last') or 0
    
    if not market_open:
        # After hours: prefer LTP as bid/ask may be stale or zero
        if ltp and ltp > 0:
            return float(ltp), 'ltp'
        elif ask and ask > 0:
            return float(ask), 'ask'
        elif bid and bid > 0:
            return float(bid), 'bid'
    else:
        # Market hours: prefer ask price for conservative entry
        if ask and ask > 0:
            return float(ask), 'ask'
        elif ltp and ltp > 0:
            return float(ltp), 'ltp'
        elif bid and bid > 0:
            return float(bid), 'bid'
    
    return 0, 'none'


def get_option_spread(opt, price, market_open=True):
    """
    Calculate bid-ask spread percentage.
    
    After hours: if bid/ask unavailable, return a reasonable default.
    """
    ask = opt.get('askprice') or opt.get('askPrice') or 0
    bid = opt.get('bidprice') or opt.get('bidPrice') or 0
    
    if ask > 0 and bid > 0:
        return (ask - bid) / ask
    
    # After hours: be lenient if bid/ask is missing
    if not market_open:
        return 0.05  # Assume reasonable spread when data unavailable
    
    return 0.10


def get_underlying_price(symbol):
    """
    Get the current price of the underlying asset.
    
    Args:
        symbol: Stock or index symbol
    
    Returns:
        float or None: Current price
    """
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        from screener.config import INDEX_SYMBOLS
        
        # Use 5m interval for indices, 1d for stocks
        interval = "5m" if symbol in INDEX_SYMBOLS else "1d"
        data = yf.Ticker(ticker).history(period="1d", interval=interval)
        
        if not data.empty:
            return data['Close'].iloc[-1]
    except Exception as e:
        logger.debug("Error fetching price for %s: %s", symbol, e)
    
    return None


def compute_trend_indicators(symbol, period=None, interval=None):
    """
    Compute RSI and trend bias for a symbol.
    
    Args:
        symbol: Stock or index symbol
        period: Lookback period (default: use _TREND_PARAMS)
        interval: Data interval (default: use _TREND_PARAMS)
    
    Returns:
        dict: {'bias': 'BULLISH'|'BEARISH'|'NEUTRAL', 'rsi': float}
    """
    # Use configurable params if not specified
    if period is None:
        period = _TREND_PARAMS['period']
    if interval is None:
        interval = _TREND_PARAMS['interval']
    
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        hist = yf.Ticker(ticker).history(period=period, interval=interval)
        
        if len(hist) < 14:
            return {'bias': 'NEUTRAL', 'rsi': 50}
        
        # Calculate RSI
        delta = hist['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
        
        # Calculate EMA-based bias
        ema20 = hist['Close'].ewm(span=20).mean().iloc[-1]
        current_price = hist['Close'].iloc[-1]
        
        if current_price > ema20 * 1.01:
            bias = "BULLISH"
        elif current_price < ema20 * 0.99:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
        
        return {'bias': bias, 'rsi': current_rsi}
    except Exception as e:
        logger.debug("Error computing trend for %s: %s", symbol, e)
        return {'bias': 'NEUTRAL', 'rsi': 50}

