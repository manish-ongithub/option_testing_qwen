"""
Historical Volatility calculation.

Calculates HV from price data as a fallback when IV is unavailable.
"""

import numpy as np
import yfinance as yf

from screener.config import SYMBOL_MAP
from screener.utils.logging_setup import logger


def calculate_historical_volatility(symbol, period=30):
    """
    Calculate Historical Volatility (HV) from price data as a fallback.
    
    Note: This is NOT the same as Implied Volatility, but gives a rough estimate.
    
    Args:
        symbol: Stock or index symbol
        period: Rolling window period (default: 30 days)
    
    Returns:
        dict: {'iv': float, 'iv_percentile': int, 'iv_rank': int, 'source': 'hv_calculated'} or None
    """
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        
        # Fetch 1 year of daily data
        hist = yf.Ticker(ticker).history(period="1y", interval="1d")
        
        if len(hist) < 60:  # Need at least 60 days
            return None
        
        # Calculate daily returns
        hist['returns'] = np.log(hist['Close'] / hist['Close'].shift(1))
        
        # Calculate rolling 30-day HV (annualized)
        hist['hv'] = hist['returns'].rolling(window=period).std() * np.sqrt(252) * 100
        
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

