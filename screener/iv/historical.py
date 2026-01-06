"""
Historical Volatility calculation.

Calculates HV from price data as a fallback when IV is unavailable.
"""

import numpy as np
import yfinance as yf

from screener.config import SYMBOL_MAP
from screener.utils.logging_setup import logger


# ================== CONFIGURABLE HV PARAMETERS ==================
# These can be overridden at runtime via set_hv_params()
_HV_PARAMS = {
    'period': '1y',    # Lookback period for HV calculation ('3mo', '6mo', '1y', '2y')
    'window': 30,      # Rolling window in days (10-60)
}


def set_hv_params(period='1y', window=30):
    """
    Set the HV calculation parameters.
    
    Args:
        period: Lookback period ('3mo', '6mo', '1y', '2y')
        window: Rolling window in days (10-60)
    """
    _HV_PARAMS['period'] = period
    _HV_PARAMS['window'] = window
    logger.debug("HV params set: period=%s, window=%d", period, window)


def get_hv_params():
    """Get current HV calculation parameters."""
    return _HV_PARAMS.copy()


def calculate_historical_volatility(symbol, period=None, window=None):
    """
    Calculate Historical Volatility (HV) from price data as a fallback.
    
    Note: This is NOT the same as Implied Volatility, but gives a rough estimate.
    
    Args:
        symbol: Stock or index symbol
        period: Lookback period for data (default: use _HV_PARAMS['period'])
        window: Rolling window in days (default: use _HV_PARAMS['window'])
    
    Returns:
        dict: {'iv': float, 'iv_percentile': int, 'iv_rank': int, 'source': 'hv_calculated'} or None
    """
    # Use configurable params if not specified
    if period is None:
        period = _HV_PARAMS['period']
    if window is None:
        window = _HV_PARAMS['window']
    
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        
        # Fetch historical data based on configured period
        hist = yf.Ticker(ticker).history(period=period, interval="1d")
        
        if len(hist) < 60:  # Need at least 60 days
            return None
        
        # Calculate daily returns
        hist['returns'] = np.log(hist['Close'] / hist['Close'].shift(1))
        
        # Calculate rolling HV (annualized) using configured window
        hist['hv'] = hist['returns'].rolling(window=window).std() * np.sqrt(252) * 100
        
        # Drop NaN values
        hv_values = hist['hv'].dropna().values
        
        if len(hv_values) < 30:
            return None
        
        current_hv = hv_values[-1]
        
        # Calculate HV percentile (similar to IV percentile)
        hv_percentile = int((np.sum(hv_values <= current_hv) / len(hv_values)) * 100)
        
        # Calculate HV rank
        hv_min = np.min(hv_values)
        hv_max = np.max(hv_values)
        if hv_max == hv_min:
            hv_rank = 50
        else:
            hv_rank = int(((current_hv - hv_min) / (hv_max - hv_min)) * 100)
        
        return {
            'iv': current_hv,  # Note: This is HV, not IV
            'iv_percentile': hv_percentile,
            'iv_rank': hv_rank,
            'source': 'hv_calculated'  # Clearly mark as calculated, not true IV
        }
    
    except Exception as e:
        logger.debug("HV calculation error for %s: %s", symbol, e)
        return None

