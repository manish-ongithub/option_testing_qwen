"""
NSE API session management.

Handles session creation, cookie management, and automatic refresh.
"""

import time
import requests

from screener.config import NSE_SESSION_TIMEOUT, NSE_HEADERS
from screener.utils.logging_setup import logger

# Global session for NSE API requests
_nse_session = None
_nse_session_time = 0


def get_nse_session():
    """
    Get or create NSE session with proper cookies.
    
    The session is cached and refreshed every NSE_SESSION_TIMEOUT seconds.
    
    Returns:
        requests.Session or None: Active session, or None on failure
    """
    global _nse_session, _nse_session_time
    
    current_time = time.time()
    
    if _nse_session is None or (current_time - _nse_session_time) > NSE_SESSION_TIMEOUT:
        _nse_session = requests.Session()
        try:
            # Visit homepage to get session cookies (use simpler headers for initial request)
            homepage_headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            _nse_session.get('https://www.nseindia.com/', headers=homepage_headers, timeout=15)
            _nse_session_time = current_time
            logger.debug("NSE session initialized/refreshed")
        except Exception as e:
            logger.warning("Failed to initialize NSE session: %s", e)
            return None
    
    return _nse_session


def reset_nse_session():
    """Force reset the NSE session on next request."""
    global _nse_session, _nse_session_time
    _nse_session = None
    _nse_session_time = 0

