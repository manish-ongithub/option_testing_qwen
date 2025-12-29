"""
NSE Option Chain API v3 integration.

Fetches and normalizes option chain data from NSE.
"""

import requests

from screener.api.nse_session import get_nse_session
from screener.config import NSE_HEADERS
from screener.utils.logging_setup import logger


def fetch_nse_option_chain(symbol, is_index=False):
    """
    Fetch option chain using NSE API v3.
    
    Args:
        symbol: Stock/Index symbol (e.g., 'NIFTY', 'RELIANCE')
        is_index: True for indices (NIFTY, BANKNIFTY), False for stocks
    
    Returns:
        dict with 'records' key containing option chain data, or None on failure
    """
    session = get_nse_session()
    if not session:
        return None
    
    try:
        # First get available expiry dates
        contract_url = f"https://www.nseindia.com/api/option-chain-contract-info?symbol={symbol}"
        resp = session.get(contract_url, headers=NSE_HEADERS, timeout=15)
        
        if resp.status_code != 200:
            logger.debug("Contract info failed for %s: HTTP %d", symbol, resp.status_code)
            return None
        
        contract_data = resp.json()
        expiry_dates = contract_data.get('expiryDates', [])
        
        if not expiry_dates:
            logger.debug("No expiry dates found for %s", symbol)
            return None
        
        # Use nearest expiry
        nearest_expiry = expiry_dates[0]
        
        # Fetch option chain for nearest expiry
        chain_type = "Indices" if is_index else "Equity"
        chain_url = f"https://www.nseindia.com/api/option-chain-v3?type={chain_type}&symbol={symbol}&expiry={nearest_expiry}"
        
        resp = session.get(chain_url, headers=NSE_HEADERS, timeout=15)
        
        if resp.status_code != 200:
            logger.debug("Option chain failed for %s: HTTP %d", symbol, resp.status_code)
            return None
        
        data = resp.json()
        
        if 'records' not in data:
            logger.debug("No records in option chain for %s", symbol)
            return None
        
        records = data['records']
        
        # Add expiryDates to records for compatibility
        records['expiryDates'] = expiry_dates
        
        # Normalize field names for compatibility with existing code
        # The new API uses buyPrice1/sellPrice1 instead of bidPrice/askPrice
        normalized_data = []
        for item in records.get('data', []):
            normalized_item = {
                'strikePrice': item.get('strikePrice'),
                'expiryDate': nearest_expiry
            }
            
            # Normalize CE data
            if 'CE' in item:
                ce = item['CE']
                normalized_item['CE'] = {
                    'strikePrice': ce.get('strikePrice'),
                    'expiryDate': nearest_expiry,
                    'openInterest': ce.get('openInterest', 0),
                    'changeinOpenInterest': ce.get('changeinOpenInterest', 0),
                    'totalTradedVolume': ce.get('totalTradedVolume', 0),
                    'impliedVolatility': ce.get('impliedVolatility', 0),
                    'lastPrice': ce.get('lastPrice', 0),
                    'bidPrice': ce.get('buyPrice1', 0),  # Normalize field name
                    'askPrice': ce.get('sellPrice1', 0),  # Normalize field name
                    'bidQty': ce.get('buyQuantity1', 0),
                    'askQty': ce.get('sellQuantity1', 0),
                    'underlyingValue': ce.get('underlyingValue', 0),
                }
            
            # Normalize PE data
            if 'PE' in item:
                pe = item['PE']
                normalized_item['PE'] = {
                    'strikePrice': pe.get('strikePrice'),
                    'expiryDate': nearest_expiry,
                    'openInterest': pe.get('openInterest', 0),
                    'changeinOpenInterest': pe.get('changeinOpenInterest', 0),
                    'totalTradedVolume': pe.get('totalTradedVolume', 0),
                    'impliedVolatility': pe.get('impliedVolatility', 0),
                    'lastPrice': pe.get('lastPrice', 0),
                    'bidPrice': pe.get('buyPrice1', 0),  # Normalize field name
                    'askPrice': pe.get('sellPrice1', 0),  # Normalize field name
                    'bidQty': pe.get('buyQuantity1', 0),
                    'askQty': pe.get('sellQuantity1', 0),
                    'underlyingValue': pe.get('underlyingValue', 0),
                }
            
            normalized_data.append(normalized_item)
        
        # Return in format compatible with existing code
        return {
            'records': {
                'data': normalized_data,
                'expiryDates': expiry_dates,
                'underlyingValue': records.get('underlyingValue', 0),
                'timestamp': records.get('timestamp', '')
            }
        }
    
    except requests.exceptions.Timeout:
        logger.debug("NSE API timeout for %s", symbol)
        return None
    except Exception as e:
        logger.debug("NSE API error for %s: %s", symbol, e)
        return None

