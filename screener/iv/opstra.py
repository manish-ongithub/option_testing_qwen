"""
Opstra IV data provider.

Fetches Implied Volatility data from Opstra API.
"""

import time
import requests
import numpy as np

from screener.config import OPSTRA_COOKIES, IV_CACHE, IV_CACHE_DURATION
from screener.utils.logging_setup import logger



def set_opstra_cookies(jsessionid, dsessionid):
    """
    Set Opstra session cookies programmatically.
    
    Usage:
        set_opstra_cookies('ABC123...', 'XYZ789...')
    """
    OPSTRA_COOKIES['JSESSIONID'] = jsessionid
    OPSTRA_COOKIES['DSESSIONID'] = dsessionid
    logger.info("Opstra cookies updated successfully")


def is_opstra_configured():
    """Check if Opstra cookies are set."""
    return bool(OPSTRA_COOKIES.get('JSESSIONID') and OPSTRA_COOKIES.get('DSESSIONID'))


def validate_opstra_session():
    """
    Validate if current Opstra cookies are still working.
    
    Makes a test API call to check session validity.
    
    Returns:
        bool: True if session is valid, False otherwise
    """
    if not is_opstra_configured():
        return False
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "referer": "https://opstra.definedge.com/ivchart",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Test with NIFTY - always available
        url = "https://opstra.definedge.com/api/ivcharts/NIFTY"
        response = requests.get(url, headers=headers, cookies=OPSTRA_COOKIES, timeout=10)
        
        if response.status_code == 401:
            logger.debug("Opstra session expired (401)")
            return False
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ivchart"):
                logger.debug("Opstra session validated successfully")
                return True
        
        return False
        
    except Exception as e:
        logger.debug("Opstra validation error: %s", e)
        return False


def get_iv_from_opstra(symbol):
    """
    Fetch IV data from Opstra API.
    
    Args:
        symbol: Stock or index symbol
    
    Returns:
        dict: {'iv': float, 'iv_percentile': int, 'iv_rank': int, 'source': 'opstra'} or None
    """
    if not is_opstra_configured():
        return None
    
    # Check cache first
    cache_key = symbol.upper()
    if cache_key in IV_CACHE:
        cached = IV_CACHE[cache_key]
        if time.time() - cached['timestamp'] < IV_CACHE_DURATION:
            return cached['data']
    
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        "referer": "https://opstra.definedge.com/ivchart",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        url = f"https://opstra.definedge.com/api/ivcharts/{symbol.upper()}"
        response = requests.get(url, headers=headers, cookies=OPSTRA_COOKIES, timeout=10)
        
        if response.status_code == 401:
            logger.warning("Opstra session expired (401). Please refresh cookies.")
            return None
        
        if response.status_code != 200:
            logger.debug("Opstra returned %s for %s", response.status_code, symbol)
            return None
        
        data = response.json()
        ivchart = data.get("ivchart", [])
        
        if not ivchart:
            return None
        
        # Extract IV values (ignore nulls)
        iv_values = []
        for point in ivchart:
            iv = point.get("ImpVol")
            if iv is not None and iv > 0:
                iv_values.append(float(iv))
        
        if len(iv_values) < 30:
            logger.debug("%s: Insufficient IV history from Opstra (%d days)", symbol, len(iv_values))
            return None
        
        # Use last 252 trading days (1 year)
        window = iv_values[-252:]
        current_iv = window[-1]
        
        # IV Percentile: % of days where IV was lower than current
        iv_percentile = int((np.sum(np.array(window) <= current_iv) / len(window)) * 100)
        
        # IV Rank: (current - min) / (max - min) * 100
        iv_min = min(window)
        iv_max = max(window)
        if iv_max == iv_min:
            iv_rank = 50
        else:
            iv_rank = int(((current_iv - iv_min) / (iv_max - iv_min)) * 100)
        
        result = {
            'iv': current_iv,
            'iv_percentile': iv_percentile,
            'iv_rank': iv_rank,
            'source': 'opstra'
        }
        
        # Cache the result
        IV_CACHE[cache_key] = {'data': result, 'timestamp': time.time()}
        
        logger.debug("Opstra IV for %s: IV=%.1f%%, IVP=%d%%, IVR=%d%%", 
                    symbol, current_iv, iv_percentile, iv_rank)
        return result
    
    except requests.exceptions.Timeout:
        logger.debug("Opstra timeout for %s", symbol)
        return None
    except Exception as e:
        logger.debug("Opstra error for %s: %s", symbol, e)
        return None

