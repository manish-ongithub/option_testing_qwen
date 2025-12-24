import time
import pytz
from datetime import datetime, time as dtime
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import csv
import os
import json
import schedule
import logging
from logging.handlers import RotatingFileHandler

# Setup logging
LOG_FILE = "screener.log"
logger = logging.getLogger("smart_options_screener")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S")

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)

# ================== NSE API v3 SESSION ==================
# Global session for NSE API requests
_nse_session = None
_nse_session_time = 0
NSE_SESSION_TIMEOUT = 300  # Refresh session every 5 minutes

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/option-chain',
}

def get_nse_session():
    """Get or create NSE session with proper cookies"""
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

# ================== CONFIGURATION ==================
TTELEGRAM_BOT_TOKEN = "8554491299:AAEYVxPF-THCg5f37JsDBHGUI3kTON2idPM"
TELEGRAM_CHAT_ID = "@manish_private_bot"

INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY"]

STOCK_SYMBOLS = list(set([
    "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN",
    "RELIANCE", "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM",
    "MARUTI", "M&M", "LT", "TATAMOTORS",
    "SUNPHARMA", "DRREDDY",
    "HINDUNILVR", "ITC", "BRITANNIA", "NESTLEIND", "TITAN",
    "BHARTIARTL", "NTPC", "POWERGRID", "COALINDIA",
    "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE",
    "INDUSINDBK", "FEDERALBNK", "CANBK", "PNB",
    "BANKBARODA", "CHOLAFIN", "MUTHOOTFIN",
    "PERSISTENT", "COFORGE", "MPHASIS",
    "TATASTEEL", "HEROMOTOCO", "EICHERMOT", "BAJAJ-AUTO",
    "CIPLA", "AUROPHARMA", "LUPIN", "DIVISLAB", "APOLLOHOSP",
    "ADANIPORTS", "ADANIENT", "JSWSTEEL", "HINDALCO",
    "JINDALSTEL", "BEL", "HAL",
    "DABUR", "PIDILITE", "ASIANPAINT",
    "TATACONSUM", "DMART", "TRENT",
    "ONGC", "BPCL", "TATAPOWER",
    "SBILIFE", "SBICARD", "HDFCAMC",
]))

SYMBOL_MAP = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
for stock in STOCK_SYMBOLS:
    SYMBOL_MAP[stock] = f"{stock}.NS"

# ================== OPSTRA CONFIGURATION ==================
# To get cookies:
# 1. Login to https://opstra.definedge.com in Chrome
# 2. Press F12 → Application tab → Cookies → opstra.definedge.com
# 3. Copy JSESSIONID and DSESSIONID values below

# GLOBAL: Store your session cookies here after logging in via browser
OPSTRA_COOKIES = {
    'JSESSIONID': '84C31B852FBC308C805A4F4F7E545F5A',
    'DSESSIONID': '8C3E6E119C271BB466690E008F3A4AF9',
    '_ga': 'GA1.1.703791765.1764073625',
    '_ga_6D0ZQ437SD': 'GS2.1.s1764145134$o4$g1$t1764145153$j41$l0$h0'
}


OPSTRA_COOKIES['DSESSIONID'] = "718F8911E954CE00C69A6EF33AEC2388"
OPSTRA_COOKIES['JSESSIONID'] = "9DCB9574F3DEF1073EC92D2329E8CC4E"


# Set to True to require Opstra (will skip stocks without IV data)
# Set to False to use Historical Volatility fallback
REQUIRE_OPSTRA_IV = False

# Cache IV data to reduce API calls (symbol -> {data, timestamp})
IV_CACHE = {}
IV_CACHE_DURATION = 300  # 5 minutes

def set_opstra_cookies(jsessionid, dsessionid):
    """
    Set Opstra session cookies programmatically.
    
    Usage:
        set_opstra_cookies('ABC123...', 'XYZ789...')
    """
    global OPSTRA_COOKIES
    OPSTRA_COOKIES['JSESSIONID'] = jsessionid
    OPSTRA_COOKIES['DSESSIONID'] = dsessionid
    logger.info("✓ Opstra cookies updated successfully")

def is_opstra_configured():
    """Check if Opstra cookies are set"""
    return bool(OPSTRA_COOKIES.get('JSESSIONID') and OPSTRA_COOKIES.get('DSESSIONID'))

# ================== LOT SIZES ==================
LOT_SIZES = {
    "NIFTY": 25, "BANKNIFTY": 15, "FINNIFTY": 25, "MIDCPNIFTY": 50,
    "RELIANCE": 250, "TCS": 175, "HDFCBANK": 550, "ICICIBANK": 700,
    "INFY": 400, "HINDUNILVR": 300, "ITC": 1600, "SBIN": 750,
    "BHARTIARTL": 475, "KOTAKBANK": 400, "LT": 150, "AXISBANK": 625,
    "BAJFINANCE": 125, "ASIANPAINT": 300, "MARUTI": 100, "TITAN": 375,
    "SUNPHARMA": 350, "TATAMOTORS": 1400, "NTPC": 2250, "POWERGRID": 2700,
    "M&M": 350, "HCLTECH": 350, "BAJAJFINSV": 500, "WIPRO": 1500,
    "NESTLEIND": 25, "TECHM": 600, "TATASTEEL": 1500, "JSWSTEEL": 675,
    "HINDALCO": 1075, "COALINDIA": 1900, "ONGC": 3850, "BPCL": 1800,
    "DRREDDY": 125, "BRITANNIA": 200, "CIPLA": 650, "DIVISLAB": 100,
    "EICHERMOT": 175, "HEROMOTOCO": 150, "APOLLOHOSP": 125,
    "ADANIPORTS": 1250, "ADANIENT": 250, "HDFCLIFE": 1100, "SBILIFE": 750,
    "BAJAJ-AUTO": 125, "INDUSINDBK": 500, "TATACONSUM": 700,
    "TATAPOWER": 2700, "DABUR": 1250, "PIDILITE": 250, "DMART": 125,
    "TRENT": 300, "SBICARD": 800, "HDFCAMC": 200, "BANKBARODA": 2925,
    "PNB": 4000, "CANBK": 6750, "FEDERALBNK": 5000, "CHOLAFIN": 625,
    "MUTHOOTFIN": 375, "PERSISTENT": 200, "COFORGE": 125, "MPHASIS": 275,
    "LTIM": 150, "AUROPHARMA": 425, "LUPIN": 425, "JINDALSTEL": 625,
    "BEL": 3900, "HAL": 150,
}
DEFAULT_LOT_SIZE = 500

# ================== THRESHOLDS ==================
STOCK_TIERS = {
    'TIER_1': ["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN", "RELIANCE", "TCS", 
               "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "MARUTI", "M&M", "LT", "TATAMOTORS",
               "SUNPHARMA", "DRREDDY", "HINDUNILVR", "ITC", "BRITANNIA", "TITAN", "BHARTIARTL",
               "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "NTPC", "POWERGRID"],
    'TIER_2': ["INDUSINDBK", "FEDERALBNK", "CANBK", "PNB", "BANKBARODA", "CHOLAFIN",
               "PERSISTENT", "COFORGE", "MPHASIS", "TATASTEEL", "HEROMOTOCO", "EICHERMOT",
               "BAJAJ-AUTO", "CIPLA", "AUROPHARMA", "LUPIN", "DIVISLAB", "APOLLOHOSP",
               "ADANIPORTS", "ADANIENT", "JSWSTEEL", "HINDALCO", "JINDALSTEL", "BEL", "HAL"],
    'TIER_3': ["DABUR", "PIDILITE", "ASIANPAINT", "TATACONSUM", "DMART", "TRENT",
               "ONGC", "BPCL", "TATAPOWER", "SBILIFE", "SBICARD", "HDFCAMC", "MUTHOOTFIN",
               "NESTLEIND", "COALINDIA"]
}

# ================== REALISTIC VOLUME/OI THRESHOLDS ==================
# Live market thresholds (require significant volume activity)
VOLUME_THRESHOLDS = {'TIER_1': 1000, 'TIER_2': 500, 'TIER_3': 200}
OI_THRESHOLDS = {'TIER_1': 5000, 'TIER_2': 2000, 'TIER_3': 1000}  # Minimum OI for liquidity
VOLUME_THRESHOLD_INDEX = 10000   # High volume required for index options
OI_THRESHOLD_INDEX = 50000       # Minimum OI for index options

# After-hours thresholds (stricter - only show highly liquid options)
AFTER_HOURS_OI_THRESHOLD_STOCK = 8000    # High OI required after hours
AFTER_HOURS_OI_THRESHOLD_INDEX = 75000   # Very high OI for indices
AFTER_HOURS_SPREAD_PCT = 0.20            # Tighter spreads after hours

# Set to True to allow scanning during non-market hours with relaxed filters
ALLOW_AFTER_HOURS_SCAN = True

# ================== STRIKE & PREMIUM FILTERS ==================
STRIKE_RANGE_MULTIPLIER = 3      # Scan ATM ± 3 strikes only (was 5)
MAX_SPREAD_PCT = 0.10            # Max 10% spread for indices (was 15%)
MAX_SPREAD_PCT_STOCK = 0.15      # Max 15% spread for stocks (was 20%)
MAX_PREMIUM_RATIO = 0.08         # Premium < 8% of spot (was 15%)
MAX_PREMIUM_RATIO_STOCK = 0.10   # Premium < 10% of spot for stocks (was 15%)
MIN_STOCK_PRICE = 100
MIN_PREMIUM = 5                  # Minimum ₹5 premium (avoid penny options)
MIN_PREMIUM_INDEX = 10           # Minimum ₹10 premium for indices

# ================== RSI THRESHOLDS ==================
RSI_OVERSOLD = 40    # More extreme oversold (was 45)
RSI_OVERBOUGHT = 60  # More extreme overbought (was 55)

# IV-based filtering thresholds
IV_VERY_HIGH = 80    # Skip buying options above this percentile (was 85)
IV_HIGH = 65         # Caution zone (was 70)
IV_LOW = 30          # Cheap premiums - good for buying

# ================== SPREAD STRATEGY CONFIGURATION ==================
# Strike width for spreads (number of strikes away from ATM)
SPREAD_WIDTH_STOCKS = 1       # 1 strike away for stock spreads
SPREAD_WIDTH_INDEX = 2        # 2 strikes away for index spreads (wider spreads)

# IV thresholds for volatility strategies
IV_PERCENTILE_LOW = 35        # Long Straddle trigger (IV is cheap)
IV_PERCENTILE_VERY_LOW = 25   # Long Strangle trigger (IV is very cheap)

# Spread strategy filters
MIN_SPREAD_REWARD_RATIO = 0.5     # Minimum reward/risk ratio for spreads (50%)
MAX_SPREAD_COST_RATIO = 0.70      # Max cost should be 70% of max profit potential
MIN_OI_PER_LEG_STOCK = 500        # Minimum OI per leg for stock spreads
MIN_OI_PER_LEG_INDEX = 5000       # Minimum OI per leg for index spreads

# Straddle/Strangle filters
MAX_STRADDLE_COST_PCT = 0.04      # Max 4% of spot price for straddle cost
MAX_STRANGLE_COST_PCT = 0.025     # Max 2.5% of spot price for strangle cost
MIN_DAYS_TO_EXPIRY_VOLATILITY = 5 # Minimum DTE for volatility plays (avoid theta decay)

MARKET_START = dtime(9, 15)
MARKET_END = dtime(15, 30)
IST = pytz.timezone("Asia/Kolkata")
CSV_FILE = "/Users/manishkumarsingh/Documents/option_testing_qwen/new_screener_options_scan_log_v3_3.csv"
JSON_FILE = "/Users/manishkumarsingh/Documents/option_testing_qwen/new_screener_alerts_v3_3.json"

# Initialize CSV
headers = [
    "Timestamp", "Symbol", "Type", "Strategy", "Strike", "Premium", "PriceSource",
    "Spot", "Volume", "OI", "OI_Change", "IV", "IV_Percentile", "IV_Rank", "IV_Source",
    "Market_Regime", "RSI", "Tier", "Moneyness", "Expiry", "DaysToExpiry", 
    "LotSize", "TotalCost", "Breakeven", "DistanceFromSpot",
    # Multi-leg strategy fields
    "Leg1_Strike", "Leg1_Premium", "Leg1_Action", 
    "Leg2_Strike", "Leg2_Premium", "Leg2_Action",
    "MaxProfit", "MaxLoss", "RewardRatio"
]

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        csv.writer(f).writerow(headers)

    logger.info("CSV file created and headers written")

def log_to_csv(alert):
    """Log alert to CSV file, handling both single-leg and multi-leg strategies."""
    
    # Handle breakeven - can be number or string for multi-leg strategies
    breakeven = alert.get('breakeven', 0)
    if isinstance(breakeven, (int, float)):
        breakeven = round(breakeven, 2)
    
    with open(CSV_FILE, mode='a', newline='') as f:
        csv.writer(f).writerow([
            alert.get('timestamp', ''),
            alert.get('symbol', ''),
            alert.get('instrument_type', ''),
            alert.get('strategy', ''),
            alert.get('strike', ''),
            round(alert.get('premium', 0), 2),
            alert.get('price_source', 'ask'),
            round(alert.get('spot', 0), 2),
            alert.get('volume', 0),
            alert.get('open_interest', 0),
            alert.get('oi_change', 0),
            round(alert.get('iv', 0), 2),
            alert.get('iv_percentile', 0),
            alert.get('iv_rank', 0),
            alert.get('iv_source', 'unknown'),
            alert.get('market_regime', ''),
            round(alert.get('rsi', 0), 1),
            alert.get('tier', ''),
            alert.get('moneyness', ''),
            alert.get('expiry', ''),
            alert.get('days_to_expiry', 0),
            alert.get('lot_size', 0),
            round(alert.get('total_cost', 0), 2),
            breakeven,
            alert.get('distance_from_spot', ''),
            # Multi-leg strategy fields
            alert.get('leg1_strike', ''),
            round(alert.get('leg1_premium', 0), 2) if alert.get('leg1_premium') else '',
            alert.get('leg1_action', ''),
            alert.get('leg2_strike', ''),
            round(alert.get('leg2_premium', 0), 2) if alert.get('leg2_premium') else '',
            alert.get('leg2_action', ''),
            round(alert.get('max_profit', 0), 2) if alert.get('max_profit') else '',
            round(alert.get('max_loss', 0), 2) if alert.get('max_loss') else '',
            round(alert.get('reward_ratio', 0), 2) if alert.get('reward_ratio') else ''
        ])

def log_to_json(alert):
    """Log single alert to JSON file."""
    
    clean_alert = {
        'timestamp': alert.get('timestamp', ''),
        'symbol': alert.get('symbol', ''),
        'instrument_type': alert.get('instrument_type', ''),
        'strategy': alert.get('strategy', ''),
        'strike': alert.get('strike', ''),
        'premium': round(alert.get('premium', 0), 2),
        'price_source': alert.get('price_source', ''),
        'spot': round(alert.get('spot', 0), 2),
        'volume': alert.get('volume', 0),
        'open_interest': alert.get('open_interest', 0),
        'iv': round(alert.get('iv', 0), 2),
        'iv_percentile': alert.get('iv_percentile', 0),
        'expiry': alert.get('expiry', ''),
        'days_to_expiry': alert.get('days_to_expiry', 0),
        'lot_size': alert.get('lot_size', 0),
        'total_cost': round(alert.get('total_cost', 0), 2),
        'breakeven': alert.get('breakeven', ''),
        'distance_from_spot': alert.get('distance_from_spot', ''),
    }
    
    # Add multi-leg fields if present
    if alert.get('leg1_strike'):
        clean_alert['leg1'] = {
            'strike': alert.get('leg1_strike'),
            'premium': round(alert.get('leg1_premium', 0), 2),
            'action': alert.get('leg1_action', '')
        }
    if alert.get('leg2_strike'):
        clean_alert['leg2'] = {
            'strike': alert.get('leg2_strike'),
            'premium': round(alert.get('leg2_premium', 0), 2),
            'action': alert.get('leg2_action', '')
        }
    if alert.get('max_profit'):
        clean_alert['max_profit'] = round(alert.get('max_profit', 0), 2)
    if alert.get('max_loss'):
        clean_alert['max_loss'] = round(alert.get('max_loss', 0), 2)
    if alert.get('reward_ratio'):
        clean_alert['reward_ratio'] = round(alert.get('reward_ratio', 0), 2)
    
    return clean_alert

def log_alerts_batch_to_json(alerts, top_n=15):
    """
    Log top N alerts by volume to JSON file.
    
    Args:
        alerts: List of alert dictionaries
        top_n: Number of top alerts to save (default: 15)
    """
    
    if not alerts:
        return
    
    scan_timestamp = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S')
    
    # Sort alerts by volume (descending) and take top N
    sorted_alerts = sorted(alerts, key=lambda x: x.get('volume', 0), reverse=True)
    top_alerts = sorted_alerts[:top_n]
    
    # Convert to clean JSON format
    top_alerts_json = [log_to_json(alert) for alert in top_alerts]
    
    # Group all alerts by strategy for summary (before filtering)
    strategy_counts = {}
    for a in alerts:
        strat = a.get('strategy', 'Unknown')
        strategy_counts[strat] = strategy_counts.get(strat, 0) + 1
    
    # Create JSON structure with only top 15 alerts
    alerts_data = {
        'last_updated': scan_timestamp,
        'total_scanned': len(alerts),
        'top_alerts_count': len(top_alerts_json),
        'alerts_by_strategy': strategy_counts,
        'top_alerts': top_alerts_json
    }
    
    # Write to file (overwrites previous data with current scan's top alerts)
    with open(JSON_FILE, 'w') as f:
        json.dump(alerts_data, f, indent=2)
    
    logger.info("Top %d alerts saved to JSON: %s", len(top_alerts_json), JSON_FILE)

# ================== IV DATA FUNCTIONS ==================

def get_iv_from_opstra(symbol):
    """
    Fetch IV data from Opstra API.
    Returns: {'iv': float, 'iv_percentile': int, 'iv_rank': int, 'source': 'opstra'} or None
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
            logger.warning("⚠️ Opstra session expired (401). Please refresh cookies.")
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
        
        logger.debug("✓ Opstra IV for %s: IV=%.1f%%, IVP=%d%%, IVR=%d%%", 
                    symbol, current_iv, iv_percentile, iv_rank)
        return result
    
    except requests.exceptions.Timeout:
        logger.debug("Opstra timeout for %s", symbol)
        return None
    except Exception as e:
        logger.debug("Opstra error for %s: %s", symbol, e)
        return None

def calculate_historical_volatility(symbol, period=30):
    """
    Calculate Historical Volatility (HV) from price data as a fallback.
    This is NOT the same as Implied Volatility, but gives a rough estimate.
    
    Returns: {'iv': float, 'iv_percentile': int, 'iv_rank': int, 'source': 'hv_calculated'} or None
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

def get_iv_data(symbol):
    """
    Get IV data with fallback chain:
    1. Try Opstra API (if cookies configured)
    2. Fall back to Historical Volatility calculation
    3. Return defaults with warning
    
    Returns: {'iv': float, 'iv_percentile': int, 'iv_rank': int, 'source': str}
    """
    # Try Opstra first
    if is_opstra_configured():
        opstra_data = get_iv_from_opstra(symbol)
        if opstra_data:
            return opstra_data
    
    # Fallback to Historical Volatility
    hv_data = calculate_historical_volatility(symbol)
    if hv_data:
        return hv_data
    
    # Last resort: return defaults with warning
    logger.debug("⚠️ %s: Using default IV values (no data available)", symbol)
    return {
        'iv': 0,
        'iv_percentile': 50,  # Assume middle of the range
        'iv_rank': 50,
        'source': 'default'  # Clearly marked as unreliable
    }

# ================== HELPER FUNCTIONS ==================

def get_lot_size(symbol):
    return LOT_SIZES.get(symbol, DEFAULT_LOT_SIZE)

def get_stock_tier(symbol):
    for tier, stocks in STOCK_TIERS.items():
        if symbol in stocks:
            return tier
    return 'TIER_3'

def find_atm_strike(strikes, spot):
    return min(strikes, key=lambda x: abs(x - spot))

def get_moneyness(strike, spot, opt_type):
    pct_diff = (strike - spot) / spot * 100
    if opt_type == "CE":
        if pct_diff < -2: return "ITM"
        elif pct_diff > 2: return "OTM"
        else: return "ATM"
    else:
        if pct_diff > 2: return "ITM"
        elif pct_diff < -2: return "OTM"
        else: return "ATM"

def calculate_breakeven(strike, premium, opt_type):
    if opt_type == "CE":
        return strike + premium
    else:
        return strike - premium

def calculate_distance_from_spot(strike, spot, opt_type):
    diff = strike - spot
    pct = abs(diff) / spot * 100
    if opt_type == "CE":
        if diff > 0: return f"+{pct:.1f}% OTM"
        elif diff < 0: return f"-{pct:.1f}% ITM"
        else: return "ATM"
    else:
        if diff < 0: return f"-{pct:.1f}% OTM"
        elif diff > 0: return f"+{pct:.1f}% ITM"
        else: return "ATM"

def parse_expiry_date(expiry_str):
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
    """
    ask = opt.get('askprice') or opt.get('askPrice') or opt.get('ask') or 0
    bid = opt.get('bidprice') or opt.get('bidPrice') or opt.get('bid') or 0
    ltp = opt.get('lastPrice') or opt.get('ltp') or opt.get('last') or 0
    
    if not market_open:
        # After hours: prefer LTP as bid/ask may be stale or zero
        if ltp and ltp > 0: return float(ltp), 'ltp'
        elif ask and ask > 0: return float(ask), 'ask'
        elif bid and bid > 0: return float(bid), 'bid'
    else:
        # Market hours: prefer ask price for conservative entry
        if ask and ask > 0: return float(ask), 'ask'
        elif ltp and ltp > 0: return float(ltp), 'ltp'
        elif bid and bid > 0: return float(bid), 'bid'
    
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

def get_india_vix():
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
    if vix < 14: return "LOW_VOL"
    elif vix <= 20: return "NORMAL_VOL"
    else: return "HIGH_VOL"

def get_underlying_price(symbol):
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        data = yf.Ticker(ticker).history(period="1d", interval="5m" if symbol in INDEX_SYMBOLS else "1d")
        if not data.empty:
            return data['Close'].iloc[-1]
    except:
        pass
    return None

def compute_trend_indicators(symbol):
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        hist = yf.Ticker(ticker).history(period="1mo", interval="1d")
        if len(hist) < 14:
            return {'bias': 'NEUTRAL', 'rsi': 50}
        
        delta = hist['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
        
        ema20 = hist['Close'].ewm(span=20).mean().iloc[-1]
        current_price = hist['Close'].iloc[-1]
        
        if current_price > ema20 * 1.01: bias = "BULLISH"
        elif current_price < ema20 * 0.99: bias = "BEARISH"
        else: bias = "NEUTRAL"
        
        return {'bias': bias, 'rsi': current_rsi}
    except:
        return {'bias': 'NEUTRAL', 'rsi': 50}

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
    # This is cached to avoid excessive API calls
    return _validate_market_status_nse()

# Cache for market status validation
_market_status_cache = {'status': None, 'timestamp': 0}
_MARKET_STATUS_CACHE_DURATION = 300  # 5 minutes

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

# ================== SPREAD STRATEGY HELPERS ==================

def find_spread_strikes(spot, strikes, atm_strike, direction, width=1):
    """
    Find appropriate strikes for spread strategies.
    
    Args:
        spot: Current spot price
        strikes: List of available strikes (sorted)
        atm_strike: ATM strike price
        direction: 'bull' or 'bear'
        width: Number of strikes away for the short leg
    
    Returns:
        tuple: (buy_strike, sell_strike) or (None, None) if not found
    """
    try:
        atm_idx = strikes.index(atm_strike)
        
        if direction == 'bull':
            # Bull Call Spread: Buy lower strike, Sell higher strike
            buy_strike = atm_strike
            sell_idx = atm_idx + width
            if sell_idx < len(strikes):
                sell_strike = strikes[sell_idx]
                return (buy_strike, sell_strike)
        
        elif direction == 'bear':
            # Bear Put Spread: Buy higher strike, Sell lower strike
            buy_strike = atm_strike
            sell_idx = atm_idx - width
            if sell_idx >= 0:
                sell_strike = strikes[sell_idx]
                return (buy_strike, sell_strike)
    except (ValueError, IndexError):
        pass
    
    return (None, None)

def find_strangle_strikes(spot, strikes, atm_strike, width=1):
    """
    Find OTM call and put strikes for strangle.
    
    Args:
        spot: Current spot price
        strikes: List of available strikes (sorted)
        atm_strike: ATM strike price
        width: Number of strikes away from ATM
    
    Returns:
        tuple: (call_strike, put_strike) or (None, None) if not found
    """
    try:
        atm_idx = strikes.index(atm_strike)
        
        call_idx = atm_idx + width  # OTM call (higher strike)
        put_idx = atm_idx - width   # OTM put (lower strike)
        
        if call_idx < len(strikes) and put_idx >= 0:
            return (strikes[call_idx], strikes[put_idx])
    except (ValueError, IndexError):
        pass
    
    return (None, None)

def calculate_spread_metrics(buy_price, sell_price, strike_diff, opt_type, buy_strike):
    """
    Calculate spread strategy metrics.
    
    Args:
        buy_price: Premium paid for long leg
        sell_price: Premium received for short leg
        strike_diff: Absolute difference between strikes
        opt_type: 'CE' for call spread, 'PE' for put spread
        buy_strike: Strike of the long leg
    
    Returns:
        dict with net_debit, max_profit, max_loss, breakeven, reward_ratio
    """
    net_debit = buy_price - sell_price
    max_loss = net_debit
    max_profit = strike_diff - net_debit
    
    if max_loss > 0:
        reward_ratio = max_profit / max_loss
    else:
        reward_ratio = 0
    
    # Breakeven calculation
    if opt_type == 'CE':
        # Bull Call Spread: breakeven = buy_strike + net_debit
        breakeven = buy_strike + net_debit
    else:
        # Bear Put Spread: breakeven = buy_strike - net_debit
        breakeven = buy_strike - net_debit
    
    return {
        'net_debit': net_debit,
        'max_profit': max_profit,
        'max_loss': max_loss,
        'breakeven': breakeven,
        'reward_ratio': reward_ratio
    }

def calculate_straddle_metrics(call_price, put_price, strike, spot):
    """
    Calculate straddle/strangle metrics.
    
    Args:
        call_price: Premium for call
        put_price: Premium for put  
        strike: Strike price (same for straddle, different for strangle)
        spot: Current spot price
    
    Returns:
        dict with total_cost, upper_breakeven, lower_breakeven, move_required_pct
    """
    total_cost = call_price + put_price
    
    # For straddle (same strike)
    upper_breakeven = strike + total_cost
    lower_breakeven = strike - total_cost
    
    # Percentage move required to breakeven
    move_required = (total_cost / spot) * 100
    
    return {
        'total_cost': total_cost,
        'upper_breakeven': upper_breakeven,
        'lower_breakeven': lower_breakeven,
        'move_required_pct': move_required
    }

def calculate_strangle_metrics(call_price, put_price, call_strike, put_strike, spot):
    """
    Calculate strangle metrics (different strikes).
    
    Args:
        call_price: Premium for OTM call
        put_price: Premium for OTM put
        call_strike: Strike of the call (higher)
        put_strike: Strike of the put (lower)
        spot: Current spot price
    
    Returns:
        dict with total_cost, upper_breakeven, lower_breakeven, move_required_pct
    """
    total_cost = call_price + put_price
    
    upper_breakeven = call_strike + total_cost
    lower_breakeven = put_strike - total_cost
    
    # Percentage move required (use the closer breakeven)
    up_move = ((upper_breakeven - spot) / spot) * 100
    down_move = ((spot - lower_breakeven) / spot) * 100
    move_required = min(up_move, down_move)
    
    return {
        'total_cost': total_cost,
        'upper_breakeven': upper_breakeven,
        'lower_breakeven': lower_breakeven,
        'move_required_pct': move_required
    }

def is_spread_liquid(leg1_oi, leg2_oi, threshold):
    """Check if both legs of a spread have sufficient liquidity."""
    return leg1_oi >= threshold and leg2_oi >= threshold

# ================== SCANNING FUNCTIONS ==================

# ================== SPREAD STRATEGY SCANNERS ==================

def scan_bull_call_spread(symbol, calls, spot, strikes, atm_strike, expiry, iv_data, trend_data, lot_size, is_index=False):
    """
    Scan for Bull Call Spread opportunities.
    
    Bull Call Spread: Buy ATM/ITM call + Sell OTM call
    Trigger: Bullish bias + Low-Medium IV
    
    Returns: list of spread alerts
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


def scan_bear_put_spread(symbol, puts, spot, strikes, atm_strike, expiry, iv_data, trend_data, lot_size, is_index=False):
    """
    Scan for Bear Put Spread opportunities.
    
    Bear Put Spread: Buy ATM/ITM put + Sell OTM put
    Trigger: Bearish bias + Low-Medium IV
    
    Returns: list of spread alerts
    """
    alerts = []
    
    # Only scan if bearish conditions
    if trend_data['bias'] not in ['BEARISH', 'NEUTRAL']:
        return alerts
    
    # Skip if IV is too high (expensive premiums)
    if iv_data['iv_percentile'] > IV_HIGH:
        return alerts
    
    # Determine spread width based on instrument type
    width = SPREAD_WIDTH_INDEX if is_index else SPREAD_WIDTH_STOCKS
    min_oi = MIN_OI_PER_LEG_INDEX if is_index else MIN_OI_PER_LEG_STOCK
    
    # Find spread strikes
    buy_strike, sell_strike = find_spread_strikes(spot, strikes, atm_strike, 'bear', width)
    
    if not buy_strike or not sell_strike:
        return alerts
    
    # Check if both strikes have option data
    if buy_strike not in puts or sell_strike not in puts:
        return alerts
    
    buy_opt = puts[buy_strike]
    sell_opt = puts[sell_strike]
    
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
    strike_diff = buy_strike - sell_strike
    metrics = calculate_spread_metrics(buy_price, sell_price, strike_diff, 'PE', buy_strike)
    
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
        'strategy': 'Bear Put Spread',
        'type': 'PE',
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
        'distance_from_spot': f"-{((spot - sell_strike) / spot * 100):.1f}%"
    }
    
    alerts.append(alert)
    return alerts


def scan_long_straddle(symbol, calls, puts, spot, atm_strike, expiry, iv_data, lot_size, is_index=False):
    """
    Scan for Long Straddle opportunities.
    
    Long Straddle: Buy ATM Call + Buy ATM Put (same strike)
    Trigger: Low IV + Expecting big move
    
    Returns: list of straddle alerts
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


def scan_long_strangle(symbol, calls, puts, spot, strikes, atm_strike, expiry, iv_data, lot_size, is_index=False):
    """
    Scan for Long Strangle opportunities.
    
    Long Strangle: Buy OTM Call + Buy OTM Put (different strikes)
    Trigger: Very low IV + Expecting big move
    
    Returns: list of strangle alerts
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

# ================== MAIN SCANNING FUNCTIONS ==================

def scan_stock(symbol, market_regime, vix, market_open=True):
    alerts = []
    
    try:
        tier = get_stock_tier(symbol)
        lot_size = get_lot_size(symbol)
        
        # Set thresholds based on market status
        if market_open:
            vol_thresh = VOLUME_THRESHOLDS[tier]
            oi_thresh = OI_THRESHOLDS[tier]
            spread_limit = MAX_SPREAD_PCT_STOCK
            min_premium = MIN_PREMIUM
        else:
            # After-hours: require higher OI for liquidity
            vol_thresh = 0  # Don't require volume after hours
            oi_thresh = AFTER_HOURS_OI_THRESHOLD_STOCK
            spread_limit = AFTER_HOURS_SPREAD_PCT
            min_premium = MIN_PREMIUM
        
        spot = get_underlying_price(symbol)
        if not spot:
            return []
        
        if spot < MIN_STOCK_PRICE:
            logger.debug("Stock %s: Spot below minimum (%.2f)", symbol, spot)
            return []
        
        # Get IV data (Opstra or HV fallback)
        iv_data = get_iv_data(symbol)
        
        trend_data = compute_trend_indicators(symbol)
        
        # Log with IV source and mode
        mode_tag = "" if market_open else " [AFTER-HOURS]"
        logger.info("Stock %s: Spot=%.0f | IV=%.1f%% IVP=%d%% [%s] | RSI=%.0f %s%s",
                   symbol, spot, iv_data['iv'], iv_data['iv_percentile'], 
                   iv_data['source'].upper(), trend_data['rsi'], trend_data['bias'], mode_tag)
        
        # IV-based filtering (only if we have reliable IV data)
        if iv_data['source'] == 'opstra' and iv_data['iv_percentile'] > IV_VERY_HIGH:
            logger.info("  ⚠️ Skipping %s: IV Percentile %d%% > %d%% (expensive premiums)",
                       symbol, iv_data['iv_percentile'], IV_VERY_HIGH)
            return []
        
        # Fetch option chain using new NSE API v3
        oc = fetch_nse_option_chain(symbol, is_index=False)
        
        if not oc or 'records' not in oc:
            logger.debug("Option chain empty for %s", symbol)
            return []
        
        records = oc['records'].get('data', [])
        if not records:
            logger.debug("No option records for %s", symbol)
            return []
        
        expiry_dates = oc['records'].get('expiryDates', [])
        nearest_expiry = expiry_dates[0] if expiry_dates else "Unknown"
        
        calls, puts = {}, {}
        strikes = set()
        for rec in records:
            strike = rec.get('strikePrice')
            expiry = rec.get('expiryDate', nearest_expiry)
            if strike:
                strikes.add(strike)
                if 'CE' in rec:
                    calls[strike] = rec['CE']
                    calls[strike]['expiryDate'] = expiry
                if 'PE' in rec:
                    puts[strike] = rec['PE']
                    puts[strike]['expiryDate'] = expiry
        
        strikes = sorted(strikes)
        if not strikes:
            return []
        
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else 50
        max_distance = step * STRIKE_RANGE_MULTIPLIER
        strikes_in_range = [s for s in strikes if abs(s - atm) <= max_distance]
        
        base_alert = {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'instrument_type': 'STOCK',
            'spot': spot,
            'iv': iv_data['iv'],
            'iv_percentile': iv_data['iv_percentile'],
            'iv_rank': iv_data['iv_rank'],
            'iv_source': iv_data['source'],
            'market_regime': market_regime,
            'vix': vix,
            'rsi': trend_data['rsi'],
            'tier': tier,
            'lot_size': lot_size
        }
        
        directional_bias = trend_data['bias']
        rsi = trend_data['rsi']
        
        scan_calls = directional_bias in ["BULLISH", "NEUTRAL"] or rsi < RSI_OVERSOLD
        scan_puts = directional_bias in ["BEARISH", "NEUTRAL"] or rsi > RSI_OVERBOUGHT
        
        # Scan CALLS
        if scan_calls:
            for strike in strikes_in_range:
                if strike not in calls:
                    continue
                
                opt = calls[strike]
                price, price_source = get_option_price(opt, market_open)
                if price <= 0:
                    logger.debug("  [SKIP] %s %d CE: price=0 (no quote)", symbol, strike)
                    continue
                
                # Minimum premium filter (avoid penny options)
                if price < min_premium:
                    logger.debug("  [SKIP] %s %d CE: premium=%.2f < %.2f (too cheap)", 
                               symbol, strike, price, min_premium)
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                expiry = opt.get('expiryDate', nearest_expiry)
                
                # Volume/OI filter - require EITHER good volume OR good OI
                if market_open:
                    if vol < vol_thresh and oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d CE: vol=%d < %d AND oi=%d < %d", 
                                   symbol, strike, vol, vol_thresh, oi, oi_thresh)
                        continue
                else:
                    # After hours: require high OI for liquidity
                    if oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d CE: oi=%d < %d (after-hours)", 
                                   symbol, strike, oi, oi_thresh)
                        continue
                
                spread_pct = get_option_spread(opt, price, market_open)
                if spread_pct > spread_limit:
                    logger.debug("  [SKIP] %s %d CE: spread=%.2f > %.2f", 
                               symbol, strike, spread_pct, spread_limit)
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO_STOCK:
                    logger.debug("  [SKIP] %s %d CE: premium_ratio=%.2f > %.2f", 
                               symbol, strike, price/spot, MAX_PREMIUM_RATIO_STOCK)
                    continue
                
                moneyness = get_moneyness(strike, spot, "CE")
                breakeven = calculate_breakeven(strike, price, "CE")
                distance = calculate_distance_from_spot(strike, spot, "CE")
                total_cost = price * lot_size
                dte = calculate_days_to_expiry(expiry)
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Call', 'strike': strike, 'type': 'CE',
                    'premium': price, 'price_source': price_source,
                    'volume': vol, 'open_interest': oi, 'oi_change': oi_chg,
                    'moneyness': moneyness, 'expiry': expiry, 'days_to_expiry': dte,
                    'total_cost': total_cost, 'breakeven': breakeven, 'distance_from_spot': distance
                })
                alerts.append(alert)
        
        # Scan PUTS
        if scan_puts:
            for strike in strikes_in_range:
                if strike not in puts:
                    continue
                
                opt = puts[strike]
                price, price_source = get_option_price(opt, market_open)
                if price <= 0:
                    logger.debug("  [SKIP] %s %d PE: price=0 (no quote)", symbol, strike)
                    continue
                
                # Minimum premium filter (avoid penny options)
                if price < min_premium:
                    logger.debug("  [SKIP] %s %d PE: premium=%.2f < %.2f (too cheap)", 
                               symbol, strike, price, min_premium)
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                expiry = opt.get('expiryDate', nearest_expiry)
                
                # Volume/OI filter - require EITHER good volume OR good OI
                if market_open:
                    if vol < vol_thresh and oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d PE: vol=%d < %d AND oi=%d < %d", 
                                   symbol, strike, vol, vol_thresh, oi, oi_thresh)
                        continue
                else:
                    # After hours: require high OI for liquidity
                    if oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d PE: oi=%d < %d (after-hours)", 
                                   symbol, strike, oi, oi_thresh)
                        continue
                
                spread_pct = get_option_spread(opt, price, market_open)
                if spread_pct > spread_limit:
                    logger.debug("  [SKIP] %s %d PE: spread=%.2f > %.2f", 
                               symbol, strike, spread_pct, spread_limit)
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO_STOCK:
                    logger.debug("  [SKIP] %s %d PE: premium_ratio=%.2f > %.2f", 
                               symbol, strike, price/spot, MAX_PREMIUM_RATIO_STOCK)
                    continue
                
                moneyness = get_moneyness(strike, spot, "PE")
                breakeven = calculate_breakeven(strike, price, "PE")
                distance = calculate_distance_from_spot(strike, spot, "PE")
                total_cost = price * lot_size
                dte = calculate_days_to_expiry(expiry)
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Put', 'strike': strike, 'type': 'PE',
                    'premium': price, 'price_source': price_source,
                    'volume': vol, 'open_interest': oi, 'oi_change': oi_chg,
                    'moneyness': moneyness, 'expiry': expiry, 'days_to_expiry': dte,
                    'total_cost': total_cost, 'breakeven': breakeven, 'distance_from_spot': distance
                })
                alerts.append(alert)
        
        # ================== SPREAD STRATEGY SCANS ==================
        # Only scan spreads if we have enough data
        if calls and puts and strikes:
            # Bull Call Spread - for bullish stocks
            spread_alerts = scan_bull_call_spread(
                symbol, calls, spot, strikes, atm, nearest_expiry, 
                iv_data, trend_data, lot_size, is_index=False
            )
            alerts.extend(spread_alerts)
            
            # Bear Put Spread - for bearish stocks
            spread_alerts = scan_bear_put_spread(
                symbol, puts, spot, strikes, atm, nearest_expiry,
                iv_data, trend_data, lot_size, is_index=False
            )
            alerts.extend(spread_alerts)
            
            # Long Straddle - for low IV environment
            straddle_alerts = scan_long_straddle(
                symbol, calls, puts, spot, atm, nearest_expiry,
                iv_data, lot_size, is_index=False
            )
            alerts.extend(straddle_alerts)
            
            # Long Strangle - for very low IV environment
            strangle_alerts = scan_long_strangle(
                symbol, calls, puts, spot, strikes, atm, nearest_expiry,
                iv_data, lot_size, is_index=False
            )
            alerts.extend(strangle_alerts)
        
        if alerts:
            logger.info("  → %d alerts generated", len(alerts))
    
    except Exception as e:
        logger.debug("Stock %s scan error: %s", symbol, e)
    
    return alerts

def scan_index(symbol, iv_threshold, market_regime, vix, market_open=True):
    alerts = []
    
    try:
        lot_size = get_lot_size(symbol)
        
        # Set thresholds based on market status
        if market_open:
            vol_thresh = VOLUME_THRESHOLD_INDEX
            oi_thresh = OI_THRESHOLD_INDEX
            spread_limit = MAX_SPREAD_PCT
            min_premium = MIN_PREMIUM_INDEX
        else:
            vol_thresh = 0  # No volume requirement after hours
            oi_thresh = AFTER_HOURS_OI_THRESHOLD_INDEX
            spread_limit = AFTER_HOURS_SPREAD_PCT
            min_premium = MIN_PREMIUM_INDEX
        
        spot = get_underlying_price(symbol)
        if not spot:
            return []
        
        # Get IV data for index
        iv_data = get_iv_data(symbol)
        
        logger.info("Index %s: Spot=%.0f | IV=%.1f%% IVP=%d%% [%s] | Mode=%s",
                   symbol, spot, iv_data['iv'], iv_data['iv_percentile'], 
                   iv_data['source'].upper(), "LIVE" if market_open else "AFTER-HOURS")
        
        # Fetch option chain using new NSE API v3
        oc = fetch_nse_option_chain(symbol, is_index=True)
        
        if not oc or 'records' not in oc:
            logger.warning("Index %s: Option chain data unavailable", symbol)
            return []
        
        records = oc['records'].get('data', [])
        if not records:
            logger.warning("Index %s: No option records found", symbol)
            return []
        
        expiry_dates = oc['records'].get('expiryDates', [])
        nearest_expiry = expiry_dates[0] if expiry_dates else "Unknown"
        
        calls, puts = {}, {}
        strikes = set()
        for rec in records:
            strike = rec.get('strikePrice')
            expiry = rec.get('expiryDate', nearest_expiry)
            if strike:
                strikes.add(strike)
                if 'CE' in rec:
                    calls[strike] = rec['CE']
                    calls[strike]['expiryDate'] = expiry
                if 'PE' in rec:
                    puts[strike] = rec['PE']
                    puts[strike]['expiryDate'] = expiry
        
        strikes = sorted(strikes)
        if not strikes:
            return []
        
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else (100 if symbol == "BANKNIFTY" else 50)
        max_distance = step * STRIKE_RANGE_MULTIPLIER
        strikes_in_range = [s for s in strikes if abs(s - atm) <= max_distance]
        
        base_alert = {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol, 'instrument_type': 'INDEX', 'spot': spot,
            'iv': iv_data['iv'], 'iv_percentile': iv_data['iv_percentile'],
            'iv_rank': iv_data['iv_rank'], 'iv_source': iv_data['source'],
            'market_regime': market_regime, 'vix': vix, 'rsi': 0,
            'tier': 'INDEX', 'lot_size': lot_size
        }
        
        for strike in strikes_in_range:
            # CALLS
            if strike in calls:
                opt = calls[strike]
                price, price_source = get_option_price(opt, market_open)
                
                if price <= 0:
                    logger.debug("  [SKIP] %s %d CE: price=0 (no quote)", symbol, strike)
                    continue
                
                # Minimum premium filter (avoid penny options)
                if price < min_premium:
                    logger.debug("  [SKIP] %s %d CE: premium=%.2f < %.2f (too cheap)", 
                               symbol, strike, price, min_premium)
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                expiry = opt.get('expiryDate', nearest_expiry)
                
                # Volume/OI filter - require EITHER good volume OR good OI
                if market_open:
                    if not (vol >= vol_thresh or oi >= oi_thresh):
                        logger.debug("  [SKIP] %s %d CE: vol=%d < %d and oi=%d < %d", 
                                   symbol, strike, vol, vol_thresh, oi, oi_thresh)
                        continue
                else:
                    # After hours: require very high OI for liquidity
                    if oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d CE: oi=%d < %d (after-hours)", 
                                   symbol, strike, oi, oi_thresh)
                        continue
                
                spread_pct = get_option_spread(opt, price, market_open)
                if spread_pct > spread_limit:
                    logger.debug("  [SKIP] %s %d CE: spread=%.2f > %.2f", 
                               symbol, strike, spread_pct, spread_limit)
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO:
                    logger.debug("  [SKIP] %s %d CE: premium_ratio=%.2f > %.2f", 
                               symbol, strike, price/spot, MAX_PREMIUM_RATIO)
                    continue
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Call', 'strike': strike, 'type': 'CE',
                    'premium': price, 'price_source': price_source,
                    'volume': vol, 'open_interest': oi, 'oi_change': oi_chg,
                    'moneyness': get_moneyness(strike, spot, "CE"),
                    'expiry': expiry, 'days_to_expiry': calculate_days_to_expiry(expiry),
                    'total_cost': price * lot_size,
                    'breakeven': calculate_breakeven(strike, price, "CE"),
                    'distance_from_spot': calculate_distance_from_spot(strike, spot, "CE")
                })
                alerts.append(alert)
            
            # PUTS
            if strike in puts:
                opt = puts[strike]
                price, price_source = get_option_price(opt, market_open)
                
                if price <= 0:
                    logger.debug("  [SKIP] %s %d PE: price=0 (no quote)", symbol, strike)
                    continue
                
                # Minimum premium filter (avoid penny options)
                if price < min_premium:
                    logger.debug("  [SKIP] %s %d PE: premium=%.2f < %.2f (too cheap)", 
                               symbol, strike, price, min_premium)
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                expiry = opt.get('expiryDate', nearest_expiry)
                
                # Volume/OI filter - require EITHER good volume OR good OI
                if market_open:
                    if not (vol >= vol_thresh or oi >= oi_thresh):
                        logger.debug("  [SKIP] %s %d PE: vol=%d < %d and oi=%d < %d", 
                                   symbol, strike, vol, vol_thresh, oi, oi_thresh)
                        continue
                else:
                    # After hours: require very high OI for liquidity
                    if oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d PE: oi=%d < %d (after-hours)", 
                                   symbol, strike, oi, oi_thresh)
                        continue
                
                spread_pct = get_option_spread(opt, price, market_open)
                if spread_pct > spread_limit:
                    logger.debug("  [SKIP] %s %d PE: spread=%.2f > %.2f", 
                               symbol, strike, spread_pct, spread_limit)
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO:
                    logger.debug("  [SKIP] %s %d PE: premium_ratio=%.2f > %.2f", 
                               symbol, strike, price/spot, MAX_PREMIUM_RATIO)
                    continue
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Put', 'strike': strike, 'type': 'PE',
                    'premium': price, 'price_source': price_source,
                    'volume': vol, 'open_interest': oi, 'oi_change': oi_chg,
                    'moneyness': get_moneyness(strike, spot, "PE"),
                    'expiry': expiry, 'days_to_expiry': calculate_days_to_expiry(expiry),
                    'total_cost': price * lot_size,
                    'breakeven': calculate_breakeven(strike, price, "PE"),
                    'distance_from_spot': calculate_distance_from_spot(strike, spot, "PE")
                })
                alerts.append(alert)
        
        # ================== SPREAD STRATEGY SCANS FOR INDEX ==================
        # Create trend_data for index (neutral bias for spread strategies)
        index_trend = {'bias': 'NEUTRAL', 'rsi': 50}
        
        if calls and puts and strikes:
            # Bull Call Spread - for moderately bullish view
            spread_alerts = scan_bull_call_spread(
                symbol, calls, spot, strikes, atm, nearest_expiry,
                iv_data, index_trend, lot_size, is_index=True
            )
            alerts.extend(spread_alerts)
            
            # Bear Put Spread - for moderately bearish view
            spread_alerts = scan_bear_put_spread(
                symbol, puts, spot, strikes, atm, nearest_expiry,
                iv_data, index_trend, lot_size, is_index=True
            )
            alerts.extend(spread_alerts)
            
            # Long Straddle - for low IV environment (event play)
            straddle_alerts = scan_long_straddle(
                symbol, calls, puts, spot, atm, nearest_expiry,
                iv_data, lot_size, is_index=True
            )
            alerts.extend(straddle_alerts)
            
            # Long Strangle - for very low IV environment
            strangle_alerts = scan_long_strangle(
                symbol, calls, puts, spot, strikes, atm, nearest_expiry,
                iv_data, lot_size, is_index=True
            )
            alerts.extend(strangle_alerts)
        
        logger.info("  → %d alerts generated", len(alerts))
    
    except Exception as e:
        logger.exception("Index %s scan error: %s", symbol, e)
    
    return alerts

# ================== MAIN JOB ==================

def job():
    
    logger.info("=" * 100)
    logger.info("Starting scan at %s", datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'))
    
    market_open = is_market_hours()
    opstra_status = "✓ CONFIGURED" if is_opstra_configured() else "✗ NOT SET (using HV fallback)"
    
    # Check if we should skip scanning when market is closed
    if not market_open and not ALLOW_AFTER_HOURS_SCAN:
        logger.info("Market: CLOSED | Scanning disabled outside market hours")
        logger.info("Set ALLOW_AFTER_HOURS_SCAN=True to enable after-hours scanning")
        logger.info("=" * 100)
        return
    
    mode_str = "LIVE" if market_open else "AFTER-HOURS (relaxed filters)"
    logger.info("Market: %s | Mode: %s | Opstra: %s", 
               "OPEN" if market_open else "CLOSED", mode_str, opstra_status)
    
    if not market_open:
        logger.info("📋 After-Hours Mode: Using OI-only filters (OI >= %d for stocks, >= %d for indices)",
                   AFTER_HOURS_OI_THRESHOLD_STOCK, AFTER_HOURS_OI_THRESHOLD_INDEX)
    
    vix = get_india_vix()
    regime = determine_market_regime(vix)
    
    logger.info("VIX=%.1f | Regime=%s", vix, regime)
    logger.info("=" * 100)
    
    all_alerts = []
    
    # Scan indices
    logger.info("\n--- Scanning Indices ---")
    for sym in INDEX_SYMBOLS:
        alerts = scan_index(sym, 60, regime, vix, market_open)
        all_alerts.extend(alerts)
    
    # Scan stocks
    logger.info("\n--- Scanning Stocks (%d) ---", len(STOCK_SYMBOLS))
    for i, sym in enumerate(STOCK_SYMBOLS):
        if (i + 1) % 20 == 0:
            logger.info("Progress: %d/%d...", i + 1, len(STOCK_SYMBOLS))
        alerts = scan_stock(sym, regime, vix, market_open)
        all_alerts.extend(alerts)
        time.sleep(0.3)
    
    # Deduplicate
    seen = set()
    unique_alerts = []
    for a in all_alerts:
        key = (a['strategy'], a['symbol'], a['strike'])
        if key not in seen:
            seen.add(key)
            unique_alerts.append(a)
    
    unique_alerts.sort(key=lambda x: x.get('volume', 0), reverse=True)
    
    logger.info("=" * 100)
    logger.info("SCAN COMPLETE: %d unique alerts", len(unique_alerts))
    logger.info("=" * 100)
    
    if unique_alerts:
        logger.info("\n" + "=" * 120)
        logger.info("TOP 15 ALERTS BY VOLUME")
        logger.info("=" * 120)
        logger.info("")
        logger.info("%-3s %-10s %-6s %-4s %-10s %-10s %-7s %-11s %-10s %-4s %-12s %-8s",
                   "#", "SYMBOL", "TYPE", "MON", "STRIKE", "PREMIUM", "VOL", 
                   "COST", "BREAKEVEN", "DTE", "DISTANCE", "IV_SRC")
        logger.info("-" * 120)
        
        for i, alert in enumerate(unique_alerts[:15]):
            iv_src = alert.get('iv_source', '?')[:3].upper()
            # Handle breakeven - can be number or string for multi-leg strategies
            breakeven = alert.get('breakeven', 0)
            if isinstance(breakeven, (int, float)):
                breakeven_str = f"{breakeven:.0f}"
            else:
                breakeven_str = str(breakeven)[:10]  # Truncate if too long
            
            logger.info("%-3d %-10s %-6s %-4s %-10s ₹%-9.2f %-7d ₹%-10.0f %-10s %-4d %-12s %-8s",
                       i+1, alert['symbol'],
                       alert['strategy'].replace('Long ', ''),
                       alert.get('moneyness', '')[:3],
                       str(alert['strike'])[:10], alert['premium'], alert['volume'],
                       alert.get('total_cost', 0), breakeven_str,
                       alert.get('days_to_expiry', -1),
                       str(alert.get('distance_from_spot', ''))[:12],
                       iv_src)
        
        logger.info("-" * 120)
        
        # IV source summary
        opstra_count = sum(1 for a in unique_alerts if a.get('iv_source') == 'opstra')
        hv_count = sum(1 for a in unique_alerts if a.get('iv_source') == 'hv_calculated')
        default_count = sum(1 for a in unique_alerts if a.get('iv_source') == 'default')
        
        logger.info("\nIV Data Sources: Opstra=%d | HV Calculated=%d | Default=%d",
                   opstra_count, hv_count, default_count)
        
        if default_count > 0:
            logger.info("⚠️  WARNING: %d alerts have no reliable IV data", default_count)
        
        if not is_opstra_configured():
            logger.info("\n💡 TIP: Configure Opstra cookies for accurate IV data:")
            logger.info("   set_opstra_cookies('your_jsessionid', 'your_dsessionid')")
        
        # Save to CSV
        for alert in unique_alerts:
            log_to_csv(alert)
        
        # Save to JSON (batch for efficiency)
        log_alerts_batch_to_json(unique_alerts)
        
        logger.info("\nResults saved to:")
        logger.info("  CSV: %s", CSV_FILE)
        logger.info("  JSON: %s", JSON_FILE)
    else:
        logger.info("\nNo alerts generated.")

if __name__ == "__main__":
    logger.info("Smart Options Screener v3.3")
    logger.info("Features: Opstra IV + HV Fallback + Enhanced Alerts")
    logger.info("Stocks: %d | Indices: %d", len(STOCK_SYMBOLS), len(INDEX_SYMBOLS))
    
    if not is_opstra_configured():
        logger.info("")
        logger.info("⚠️  Opstra cookies not configured - using Historical Volatility fallback")
        logger.info("   For accurate IV data, set cookies after logging into Opstra:")
        logger.info("   set_opstra_cookies('JSESSIONID_value', 'DSESSIONID_value')")
        logger.info("")
    
    job()
    
    schedule.every(300).seconds.do(job)
    logger.info("\nScheduler started. Press Ctrl+C to stop.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)