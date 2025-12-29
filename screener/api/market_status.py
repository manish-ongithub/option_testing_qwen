"""
Market status and timing functions.

Checks if NSE market is open and fetches VIX data.
"""

import time
from datetime import datetime
import requests

from screener.api.nse_session import get_nse_session
from screener.config import MARKET_START, MARKET_END, IST, NSE_HEADERS
from screener.utils.logging_setup import logger

# Cache for market status validation
_market_status_cache = {'status': None, 'timestamp': 0}
_MARKET_STATUS_CACHE_DURATION = 300  # 5 minutes


def is_market_hours():
    """
    Check if NSE market is currently open using multiple methods:
    1. Check if it's a weekday (Mon-Fri)
    2. Check if within trading hours (9:15 AM - 3:30 PM IST)
    3. Validate against NSE API for holidays and special closures
    
    Returns:
        bool: True if market is open, False otherwise
    """
    now = datetime.now(IST)
    current_time = now.time()
    
    # Check 1: Is it a weekday? (Monday=0, Sunday=6)
    if now.weekday() >= 5:  # Saturday or Sunday
        logger.debug("Market closed: Weekend (day=%d)", now.weekday())
        return False
    
    # Check 2: Is it within trading hours?
    if not (MARKET_START <= current_time <= MARKET_END):
        logger.debug("Market closed: Outside trading hours (%s)", current_time.strftime('%H:%M'))
        return False
    
    # Check 3: Validate with NSE API (checks for holidays)
    return _validate_market_status_nse()


def _validate_market_status_nse():
    """
    Validate market status by checking NSE API response.
    Uses the market status API or checks if option chain data is fresh.
    
    Returns:
        bool: True if market appears to be open
    """
    global _market_status_cache
    
    current_time = time.time()
    
    # Return cached result if still valid
    if _market_status_cache['status'] is not None:
        if current_time - _market_status_cache['timestamp'] < _MARKET_STATUS_CACHE_DURATION:
            return _market_status_cache['status']
    
    try:
        session = get_nse_session()
        if not session:
            # If can't get session, assume market is open based on time
            return True
        
        # Try NSE market status API
        status_url = "https://www.nseindia.com/api/marketStatus"
        resp = session.get(status_url, headers=NSE_HEADERS, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Check market status from response
            # NSE returns market status for different segments
            market_state = data.get('marketState', [])
            
            for segment in market_state:
                # Check for Capital Market or F&O segment
                if segment.get('market') in ['Capital Market', 'currencyfutures', 'Normal Market']:
                    status = segment.get('marketStatus', '').lower()
                    
                    if 'open' in status or 'active' in status:
                        _market_status_cache = {'status': True, 'timestamp': current_time}
                        logger.debug("NSE API: Market is OPEN (%s)", status)
                        return True
                    elif 'close' in status or 'closed' in status:
                        _market_status_cache = {'status': False, 'timestamp': current_time}
                        logger.debug("NSE API: Market is CLOSED (%s)", status)
                        return False
            
            # If we got data but couldn't determine status, assume open during hours
            _market_status_cache = {'status': True, 'timestamp': current_time}
            return True
        
        else:
            # API failed, fall back to time-based check
            logger.debug("NSE market status API returned %d, using time-based check", resp.status_code)
            _market_status_cache = {'status': True, 'timestamp': current_time}
            return True
    
    except Exception as e:
        logger.debug("Error checking NSE market status: %s, using time-based check", e)
        # On error, assume market is open if within trading hours
        _market_status_cache = {'status': True, 'timestamp': current_time}
        return True


def get_market_status_details():
    """
    Get detailed market status information from NSE.
    
    Returns:
        dict: Market status details including segment-wise status
    """
    try:
        session = get_nse_session()
        if not session:
            return {'error': 'Could not establish NSE session'}
        
        status_url = "https://www.nseindia.com/api/marketStatus"
        resp = session.get(status_url, headers=NSE_HEADERS, timeout=10)
        
        if resp.status_code == 200:
            return resp.json()
        else:
            return {'error': f'API returned {resp.status_code}'}
    
    except Exception as e:
        return {'error': str(e)}


def get_india_vix():
    """
    Fetch the current India VIX value.
    
    Returns:
        float: Current VIX value, or 16.0 as default
    """
    try:
        url = "https://www.nseindia.com/api/allIndices"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=5)
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            for index in response.json().get('data', []):
                if index.get('index') == 'INDIA VIX':
                    return index.get('last', 16.0)
    except:
        pass
    
    return 16.0


def determine_market_regime(vix):
    """
    Determine the market volatility regime based on VIX.
    
    Args:
        vix: Current India VIX value
    
    Returns:
        str: 'LOW_VOL', 'NORMAL_VOL', or 'HIGH_VOL'
    """
    if vix < 14:
        return "LOW_VOL"
    elif vix <= 20:
        return "NORMAL_VOL"
    else:
        return "HIGH_VOL"

