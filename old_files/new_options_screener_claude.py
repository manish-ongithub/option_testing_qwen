import time
import pytz
from datetime import datetime, time as dtime
import asyncio
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import csv
import os
from nsepython import nse_optionchain_scrapper
from telegram import Bot
import schedule
import logging
from logging.handlers import RotatingFileHandler

# Setup logging
LOG_FILE = "screener.log"
logger = logging.getLogger("smart_options_screener")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s", "%Y-%m-%d %H:%M:%S")

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

# Rotating file handler
fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)
logger.addHandler(fh)

# ================== CONFIGURATION ==================
# ================== CONFIGURATION ==================
TELEGRAM_BOT_TOKEN = "8554491299:AAEYVxPF-THCg5f37JsDBHGUI3kTON2idPM"
TELEGRAM_CHAT_ID = "@manish_private_bot"

# Instruments - Removed duplicates
INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY"]

# IMPROVEMENT #1: Removed duplicate symbols (TATASTEEL, POWERGRID, NTPC were duplicated)
STOCK_SYMBOLS = list(set([
    # Large Cap Banks
    "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN",
    # IT Giants
    "RELIANCE", "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM",  # Changed LTI to LTIM
    # Auto & Industrials
    "MARUTI", "M&M", "LT", "TATAMOTORS",
    # Pharma
    "SUNPHARMA", "DRREDDY",
    # Consumer
    "HINDUNILVR", "ITC", "BRITANNIA", "NESTLEIND", "TITAN",
    # Telecom & Energy
    "BHARTIARTL", "NTPC", "POWERGRID", "COALINDIA",
    # Finance
    "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE",
    # Banks & NBFCs
    "INDUSINDBK", "BANDHANBNK", "IDFCFIRSTB", "FEDERALBNK", "CANBK", "PNB",
    "BANKBARODA", "BANKINDIA", "CHOLAFIN", "LICHSGFIN", "MUTHOOTFIN", "MANAPPURAM",
    # IT & Tech
    "PERSISTENT", "COFORGE", "MPHASIS", "OFSS", "LTTS",
    # Auto & Auto Components
    "TATASTEEL", "HEROMOTOCO", "EICHERMOT", "BAJAJ-AUTO", "TVSMOTOR",
    "ASHOKLEY", "APOLLOTYRE", "MRF", "MOTHERSON",
    # Pharma & Healthcare
    "CIPLA", "AUROPHARMA", "LUPIN", "BIOCON", "TORNTPHARM", "ALKEM",
    "LAURUSLABS", "DIVISLAB", "ZYDUSLIFE", "APOLLOHOSP", "FORTIS",
    # Industrials & Infra
    "ADANIPORTS", "ADANIENT", "JSWSTEEL", "HINDALCO", "VEDL",
    "JINDALSTEL", "SAIL", "BHEL", "BEL", "HAL", "BHARATFORG", "CUMMINSIND",
    # Consumer & Retail
    "DABUR", "GODREJCP", "MARICO", "COLPAL", "PIDILITE", "ASIANPAINT",
    "BERGEPAINT", "BATAINDIA", "TATACONSUM", "DMART", "TRENT", "JUBLFOOD",
    # Energy & Utilities
    "ONGC", "BPCL", "IOC", "GAIL", "HINDPETRO", "TATAPOWER", "NHPC",
    # Financials & Insurance
    "SBILIFE", "SBICARD", "HDFCAMC", "ICICIGI", "ICICIPRULI",
]))

SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}
for stock in STOCK_SYMBOLS:
    SYMBOL_MAP[stock] = f"{stock}.NS"

# ================== TIERED PARAMETERS ==================
STOCK_TIERS = {
    'TIER_1': [
        "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "SBIN",
        "RELIANCE", "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM",
        "MARUTI", "M&M", "LT", "TATAMOTORS",
        "SUNPHARMA", "DRREDDY",
        "HINDUNILVR", "ITC", "BRITANNIA", "NESTLEIND", "TITAN",
        "BHARTIARTL", "NTPC", "POWERGRID", "COALINDIA",
        "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE"
    ],
    'TIER_2': [
        "INDUSINDBK", "BANDHANBNK", "IDFCFIRSTB", "FEDERALBNK", "CANBK", "PNB",
        "BANKBARODA", "BANKINDIA", "CHOLAFIN", "LICHSGFIN", "MUTHOOTFIN", "MANAPPURAM",
        "PERSISTENT", "COFORGE", "MPHASIS", "OFSS", "LTTS",
        "TATASTEEL", "HEROMOTOCO", "EICHERMOT", "BAJAJ-AUTO", "TVSMOTOR",
        "ASHOKLEY", "APOLLOTYRE", "MRF", "MOTHERSON",
        "CIPLA", "AUROPHARMA", "LUPIN", "BIOCON", "TORNTPHARM", "ALKEM",
        "LAURUSLABS", "DIVISLAB", "ZYDUSLIFE", "APOLLOHOSP", "FORTIS",
        "ADANIPORTS", "ADANIENT", "JSWSTEEL", "HINDALCO", "VEDL",
        "JINDALSTEL", "SAIL", "BHEL", "BEL", "HAL", "BHARATFORG", "CUMMINSIND",
    ],
    'TIER_3': [
        "DABUR", "GODREJCP", "MARICO", "COLPAL", "PIDILITE", "ASIANPAINT",
        "BERGEPAINT", "BATAINDIA", "TATACONSUM", "DMART", "TRENT", "JUBLFOOD",
        "ONGC", "BPCL", "IOC", "GAIL", "HINDPETRO", "TATAPOWER", "NHPC",
        "SBILIFE", "SBICARD", "HDFCAMC", "ICICIGI", "ICICIPRULI",
    ]
}

# IMPROVEMENT #2: Significantly relaxed thresholds
VOLUME_THRESHOLDS = {
    'TIER_1': 200,   # Was 800 - too restrictive
    'TIER_2': 100,   # Was 400
    'TIER_3': 50     # Was 200
}

OI_CHANGE_THRESHOLDS = {
    'TIER_1': 50,    # Was 150 - too restrictive
    'TIER_2': 25,    # Was 75
    'TIER_3': 10     # Was 30
}

# IMPROVEMENT #3: Relaxed index thresholds
VOLUME_THRESHOLD_INDEX = 1000     # Was 5000
OI_CHANGE_THRESHOLD_INDEX = 200   # Was 1000

# IMPROVEMENT #4: Expanded strike range
STRIKE_RANGE_MULTIPLIER = 4       # Was 2 - now scans 4 strikes each side

# IMPROVEMENT #5: Slightly relaxed spread and premium filters
MAX_SPREAD_PCT = 0.08             # Was 0.05
MAX_SPREAD_PCT_STOCK = 0.12       # Was 0.08
MAX_PREMIUM_RATIO = 0.08          # Was 0.05
MAX_PREMIUM_RATIO_STOCK = 0.10    # Was 0.08
STRADDLE_MAX_COST_PCT = 0.04      # Was 0.03
MIN_STOCK_PRICE = 300             # Was 500 - allow more stocks

# Trend Indicators - Slightly relaxed
RSI_OVERSOLD = 40                 # Was 35
RSI_OVERBOUGHT = 60               # Was 65
ADX_TRENDING = 20                 # Was 25

# IMPROVEMENT #6: Relaxed IV thresholds
IV_VERY_HIGH = 90                 # Was 80 - only skip extreme IV
IV_HIGH = 75                      # Was 70
IV_LOW = 35                       # Was 30

# Market Hours
MARKET_START = dtime(9, 15)
MARKET_END = dtime(15, 30)
IST = pytz.timezone("Asia/Kolkata")

CSV_FILE = "new_options_claude_scan_log.csv"

# IMPROVEMENT #7: Option to work without Opstra (fallback to defaults)
REQUIRE_IV_DATA = False  # Set True to require IV data, False to proceed with defaults

# Opstra cookies - update these after logging in
# GLOBAL: Store your session cookies here after logging in via browser
OPSTRA_COOKIES = {
    'JSESSIONID': '68C2B25E68942C37028E38FE43E12941',
    'DSESSIONID': '54BD4DA6614952A5841DF155A18F2C97',
    '_ga': 'GA1.1.703791765.1764073625',
    '_ga_6D0ZQ437SD': 'GS2.1.s1764145134$o4$g1$t1764145153$j41$l0$h0'
}

def set_opstra_cookies(jsessionid, dsessionid):
    global OPSTRA_COOKIES
    OPSTRA_COOKIES['JSESSIONID'] = jsessionid
    OPSTRA_COOKIES['DSESSIONID'] = dsessionid
    logger.info("Opstra cookies set successfully")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Initialize CSV
headers = [
    "Timestamp", "Symbol", "Type", "Strategy", "Strike", "Premium",
    "Spot", "Volume", "OI_Change", "IV", "IV_Percentile", "IV_Rank",
    "Market_Regime", "VIX", "RSI", "ADX", "Tier", "Moneyness"
]
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        csv.writer(f).writerow(headers)

def log_to_csv(alert):
    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            alert.get('timestamp', ''),
            alert.get('symbol', ''),
            alert.get('instrument_type', 'INDEX'),
            alert.get('strategy', ''),
            alert.get('strike', ''),
            round(alert.get('premium', 0), 2),
            round(alert.get('spot', 0), 2),
            alert.get('volume', 0),
            alert.get('oi_change', 0),
            alert.get('iv', 0),
            alert.get('iv_percentile', 0),
            alert.get('iv_rank', 0),
            alert.get('market_regime', ''),
            alert.get('vix', 0),
            alert.get('rsi', 0),
            alert.get('adx', 0),
            alert.get('tier', 'N/A'),
            alert.get('moneyness', 'N/A')
        ])

# ================== HELPER FUNCTIONS ==================

def get_stock_tier(symbol):
    for tier, stocks in STOCK_TIERS.items():
        if symbol in stocks:
            return tier
    return 'TIER_3'

def find_atm_strike(strikes, spot):
    return min(strikes, key=lambda x: abs(x - spot))

def get_moneyness(strike, spot, opt_type):
    """Calculate moneyness label"""
    pct_diff = (strike - spot) / spot * 100
    if opt_type == "CE":
        if pct_diff < -2:
            return "ITM"
        elif pct_diff > 2:
            return "OTM"
        else:
            return "ATM"
    else:  # PE
        if pct_diff > 2:
            return "ITM"
        elif pct_diff < -2:
            return "OTM"
        else:
            return "ATM"

# IMPROVEMENT #8: Fixed India VIX fetching
def get_india_vix():
    """Fetch India VIX from NSE directly"""
    try:
        # Try NSE API first
        url = "https://www.nseindia.com/api/allIndices"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        session = requests.Session()
        # First hit main page to get cookies
        session.get("https://www.nseindia.com", headers=headers, timeout=5)
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            for index in data.get('data', []):
                if index.get('index') == 'INDIA VIX':
                    vix_val = index.get('last', 16.0)
                    logger.info("Fetched India VIX from NSE: %.2f", vix_val)
                    return vix_val
    except Exception as e:
        logger.warning("Error fetching India VIX from NSE: %s", e)
    
    # Fallback to yfinance with correct ticker
    try:
        # Try ^INDIAVIX first
        data = yf.Ticker("^INDIAVIX").history(period="5d")
        if not data.empty:
            vix_val = data['Close'].iloc[-1]
            logger.info("Fetched India VIX from yfinance: %.2f", vix_val)
            return vix_val
    except Exception as e:
        logger.warning("yfinance India VIX failed: %s", e)
    
    logger.warning("Using default VIX: 16.0")
    return 16.0

def determine_market_regime(vix_value):
    if vix_value < 14:
        return "LOW_VOL"
    elif vix_value <= 20:  # Widened normal range
        return "NORMAL_VOL"
    else:
        return "HIGH_VOL"

def get_iv_threshold(market_regime):
    # Higher thresholds = more permissive
    thresholds = {"LOW_VOL": 60, "NORMAL_VOL": 50, "HIGH_VOL": 40}
    return thresholds.get(market_regime, 50)

def get_iv_data(symbol):
    """Fetch IV data from Opstra with graceful fallback"""
    if not OPSTRA_COOKIES.get('JSESSIONID') or not OPSTRA_COOKIES.get('DSESSIONID'):
        if REQUIRE_IV_DATA:
            logger.error("Opstra cookies not set for %s", symbol)
            return None
        else:
            logger.debug("Opstra cookies not set, using defaults for %s", symbol)
            return {'iv': 25, 'iv_percentile': 50, 'iv_rank': 50}  # Default values

    headers = {
        "accept": "application/json, text/plain, */*",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        url = f"https://opstra.definedge.com/api/ivcharts/{symbol.upper()}"
        response = requests.get(url, headers=headers, cookies=OPSTRA_COOKIES, timeout=10)
        
        if response.status_code != 200:
            logger.warning("Opstra returned %s for %s, using defaults", response.status_code, symbol)
            return {'iv': 25, 'iv_percentile': 50, 'iv_rank': 50}
        
        data = response.json()
        ivchart = data.get("ivchart", [])
        
        if not ivchart:
            return {'iv': 25, 'iv_percentile': 50, 'iv_rank': 50}

        iv_values = [float(p["ImpVol"]) for p in ivchart if p.get("ImpVol") and p["ImpVol"] > 0]

        if len(iv_values) < 20:
            return {'iv': 25, 'iv_percentile': 50, 'iv_rank': 50}

        window = iv_values[-252:]
        current_iv = window[-1]
        iv_percentile = int((np.sum(np.array(window) <= current_iv) / len(window)) * 100)
        iv_min, iv_max = min(window), max(window)
        iv_rank = int(((current_iv - iv_min) / (iv_max - iv_min)) * 100) if iv_max != iv_min else 50
        
        return {'iv': current_iv, 'iv_percentile': iv_percentile, 'iv_rank': iv_rank}

    except Exception as e:
        logger.warning("IV fetch error for %s: %s, using defaults", symbol, e)
        return {'iv': 25, 'iv_percentile': 50, 'iv_rank': 50}

def get_underlying_price(symbol):
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        if symbol in ["NIFTY", "BANKNIFTY"]:
            data = yf.Ticker(ticker).history(period="1d", interval="5m")
        else:
            data = yf.Ticker(ticker).history(period="1d")
        
        if not data.empty:
            return data['Close'].iloc[-1]
    except Exception as e:
        logger.warning("Price fetch error for %s: %s", symbol, e)
    return None

def compute_trend_indicators(symbol):
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        hist = yf.Ticker(ticker).history(period="1mo", interval="1d")
        
        if len(hist) < 14:
            return {'bias': 'NEUTRAL', 'rsi': 50, 'adx': 0}
        
        # RSI
        delta = hist['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
        
        # Simple ADX approximation
        high_low = hist['High'] - hist['Low']
        high_close = abs(hist['High'] - hist['Close'].shift())
        low_close = abs(hist['Low'] - hist['Close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        plus_dm = (hist['High'] - hist['High'].shift()).where(
            (hist['High'] - hist['High'].shift()) > (hist['Low'].shift() - hist['Low']), 0
        ).rolling(window=14).mean()
        minus_dm = (hist['Low'].shift() - hist['Low']).where(
            (hist['Low'].shift() - hist['Low']) > (hist['High'] - hist['High'].shift()), 0
        ).rolling(window=14).mean()
        
        adx_approx = abs(plus_dm.iloc[-1] - minus_dm.iloc[-1]) / atr * 100 if atr > 0 else 0
        
        # Bias determination
        ema20 = hist['Close'].ewm(span=20).mean().iloc[-1]
        current_price = hist['Close'].iloc[-1]
        
        if current_price > ema20 * 1.01:  # Relaxed from 1.02
            bias = "BULLISH"
        elif current_price < ema20 * 0.99:  # Relaxed from 0.98
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
        
        return {'bias': bias, 'rsi': current_rsi, 'adx': float(adx_approx)}
    
    except Exception as e:
        logger.warning("Trend calc error for %s: %s", symbol, e)
        return {'bias': 'NEUTRAL', 'rsi': 50, 'adx': 0}

def is_market_hours():
    now = datetime.now(IST).time()
    return MARKET_START <= now <= MARKET_END

# ================== SCANNING FUNCTIONS ==================

def scan_index(symbol, iv_threshold, market_regime, vix):
    logger.info("Scanning index: %s | regime=%s", symbol, market_regime)
    alerts = []
    
    try:
        oc = nse_optionchain_scrapper(symbol)
        if not oc or 'records' not in oc:
            logger.warning("No option chain data for %s", symbol)
            return []
            
        records = oc['records']['data']
        spot_nse = oc['records']['underlyingValue']
        spot = get_underlying_price(symbol) or spot_nse

        iv_data = get_iv_data(symbol)
        
        calls, puts = {}, {}
        strikes = set()
        for rec in records:
            strike = rec['strikePrice']
            strikes.add(strike)
            if 'CE' in rec:
                calls[strike] = rec['CE']
            if 'PE' in rec:
                puts[strike] = rec['PE']
        
        strikes = sorted(strikes)
        if not strikes:
            return []
            
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else (100 if symbol == "BANKNIFTY" else 50)
        max_distance = step * STRIKE_RANGE_MULTIPLIER  # Now 4 strikes each side

        # IMPROVEMENT #9: Use OR logic for volume/OI (either one passing is enough)
        vol_thresh = VOLUME_THRESHOLD_INDEX
        oi_thresh = OI_CHANGE_THRESHOLD_INDEX

        # Trend detection
        directional_bias = "NEUTRAL"
        try:
            hist = yf.Ticker(SYMBOL_MAP[symbol]).history(period="2d", interval="5m")
            if len(hist) >= 50:
                ema20 = hist['Close'].ewm(span=20).mean().iloc[-1]
                ema50 = hist['Close'].ewm(span=50).mean().iloc[-1]
                current = hist['Close'].iloc[-1]
                if current > ema20 and ema20 > ema50:
                    directional_bias = "BULLISH"
                elif current < ema20 and ema20 < ema50:
                    directional_bias = "BEARISH"
        except Exception as e:
            logger.warning("Trend error for %s: %s", symbol, e)

        base_alert = {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'instrument_type': 'INDEX',
            'spot': spot,
            'iv': iv_data['iv'] if iv_data else 0,
            'iv_percentile': iv_data['iv_percentile'] if iv_data else 0,
            'iv_rank': iv_data['iv_rank'] if iv_data else 0,
            'market_regime': market_regime,
            'vix': vix,
            'rsi': 0,
            'adx': 0,
            'tier': 'INDEX'
        }

        # IMPROVEMENT #10: Scan both calls and puts always (not just directional)
        # Scan CALLS
        for strike in [s for s in strikes if abs(s - atm) <= max_distance]:
            if strike not in calls:
                continue
            
            opt = calls[strike]
            bid = opt.get('bidprice', 0)
            ask = opt.get('askprice', 0)
            vol = opt.get('totalTradedVolume', 0)
            oi_chg = opt.get('openInterest', 0) - opt.get('prevOpenInterest', 0)
            
            # Relaxed filters with OR logic
            if ask <= 0:
                continue
            if vol < vol_thresh and abs(oi_chg) < oi_thresh:  # Changed to abs() and OR
                continue
            if ask > 0 and (ask - bid) / ask > MAX_SPREAD_PCT:
                continue
            if ask / spot > MAX_PREMIUM_RATIO:
                continue
            
            moneyness = get_moneyness(strike, spot, "CE")
            alert = base_alert.copy()
            alert.update({
                'strategy': 'Long Call',
                'strike': strike,
                'type': 'CE',
                'premium': ask,
                'volume': vol,
                'oi_change': oi_chg,
                'moneyness': moneyness,
                'directional_bias': directional_bias
            })
            alerts.append(alert)

        # Scan PUTS
        for strike in [s for s in strikes if abs(s - atm) <= max_distance]:
            if strike not in puts:
                continue
            
            opt = puts[strike]
            bid = opt.get('bidprice', 0)
            ask = opt.get('askprice', 0)
            vol = opt.get('totalTradedVolume', 0)
            oi_chg = opt.get('openInterest', 0) - opt.get('prevOpenInterest', 0)
            
            if ask <= 0:
                continue
            if vol < vol_thresh and abs(oi_chg) < oi_thresh:
                continue
            if ask > 0 and (ask - bid) / ask > MAX_SPREAD_PCT:
                continue
            if ask / spot > MAX_PREMIUM_RATIO:
                continue
            
            moneyness = get_moneyness(strike, spot, "PE")
            alert = base_alert.copy()
            alert.update({
                'strategy': 'Long Put',
                'strike': strike,
                'type': 'PE',
                'premium': ask,
                'volume': vol,
                'oi_change': oi_chg,
                'moneyness': moneyness,
                'directional_bias': directional_bias
            })
            alerts.append(alert)

        # Straddle check
        if iv_data and iv_data['iv_percentile'] <= iv_threshold:
            if atm in calls and atm in puts:
                total = calls[atm].get('askprice', 0) + puts[atm].get('askprice', 0)
                cost_pct = total / spot
                if total > 0 and cost_pct <= STRADDLE_MAX_COST_PCT:
                    alert = base_alert.copy()
                    alert.update({
                        'strategy': "Long Straddle",
                        'strike': atm,
                        'type': "STRADDLE",
                        'premium': total,
                        'volume': calls[atm].get('totalTradedVolume', 0) + puts[atm].get('totalTradedVolume', 0),
                        'oi_change': 0,
                        'moneyness': 'ATM'
                    })
                    alerts.append(alert)

    except Exception as e:
        logger.exception("Index scan error for %s: %s", symbol, e)
    
    logger.info("Index %s: %d alerts", symbol, len(alerts))
    return alerts

def scan_stock(symbol, market_regime, vix):
    """Enhanced stock scanning with relaxed filters"""
    logger.debug("Scanning stock: %s", symbol)
    alerts = []
    
    try:
        tier = get_stock_tier(symbol)
        vol_thresh = VOLUME_THRESHOLDS[tier]
        oi_thresh = OI_CHANGE_THRESHOLDS[tier]
        
        # Fetch option chain
        try:
            oc = nse_optionchain_scrapper(symbol)
            if not oc or 'records' not in oc:
                logger.debug("No option chain for %s", symbol)
                return []
        except Exception as e:
            logger.debug("Option chain fetch failed for %s: %s", symbol, e)
            return []
            
        records = oc['records']['data']
        spot_nse = oc['records']['underlyingValue']
        spot = get_underlying_price(symbol) or spot_nse
        logger.info("Stock %s: Spot: %s", symbol, spot)
        if spot < MIN_STOCK_PRICE:
            logger.info("Stock %s: Spot below minimum price: %s", symbol, spot)
            return []
        
        iv_data = get_iv_data(symbol)
        
        # IMPROVEMENT #11: Don't skip stocks on high IV, just log warning
        if iv_data['iv_percentile'] > IV_VERY_HIGH:
            logger.info("⚠️ %s: Very high IV (%d%%) - premiums expensive", symbol, iv_data['iv_percentile'])
            # Continue scanning but note the high IV
        
        trend_data = compute_trend_indicators(symbol)
        directional_bias = trend_data['bias']
        rsi = trend_data['rsi']
        adx = trend_data['adx']
        logger.info("Stock %s: Trend data: %s, IV data: %s", symbol, trend_data,iv_data)
        # Parse strikes
        calls, puts = {}, {}
        strikes = set()
        for rec in records:
            strike = rec['strikePrice']
            strikes.add(strike)
            if 'CE' in rec:
                calls[strike] = rec['CE']
            if 'PE' in rec:
                puts[strike] = rec['PE']
        
        strikes = sorted(strikes)
        if not strikes:
            return []
        
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else 10
        max_distance = step * STRIKE_RANGE_MULTIPLIER
        
        base_alert = {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'instrument_type': 'STOCK',
            'spot': spot,
            'iv': iv_data['iv'],
            'iv_percentile': iv_data['iv_percentile'],
            'iv_rank': iv_data['iv_rank'],
            'market_regime': market_regime,
            'vix': vix,
            'rsi': rsi,
            'adx': adx,
            'tier': tier
        }
        
        # IMPROVEMENT #12: Scan calls and puts based on multiple conditions
        # Bullish bias or RSI oversold -> scan calls
        # Bearish bias or RSI overbought -> scan puts
        # Neutral -> scan both
        scan_calls = directional_bias in ["BULLISH", "NEUTRAL"] or rsi < RSI_OVERSOLD
        scan_puts = directional_bias in ["BEARISH", "NEUTRAL"] or rsi > RSI_OVERBOUGHT
        
        # Scan CALLS
        if scan_calls:
            for strike in [s for s in strikes if abs(s - atm) <= max_distance]:
                if strike not in calls:
                    continue
                
                opt = calls[strike]
                bid = opt.get('bidprice', 0)
                ask = opt.get('askprice', 0)
                vol = opt.get('totalTradedVolume', 0)
                oi_chg = opt.get('openInterest', 0) - opt.get('prevOpenInterest', 0)
                
                if ask <= 0:
                    continue
                # OR logic - either volume or OI change passes
                if vol < vol_thresh and abs(oi_chg) < oi_thresh:
                    continue
                if ask > 0 and (ask - bid) / ask > MAX_SPREAD_PCT_STOCK:
                    continue
                if ask / spot > MAX_PREMIUM_RATIO_STOCK:
                    continue
                
                moneyness = get_moneyness(strike, spot, "CE")
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Call',
                    'strike': strike,
                    'type': 'CE',
                    'premium': ask,
                    'volume': vol,
                    'oi_change': oi_chg,
                    'moneyness': moneyness
                })
                alerts.append(alert)
        
        # Scan PUTS
        if scan_puts:
            for strike in [s for s in strikes if abs(s - atm) <= max_distance]:
                if strike not in puts:
                    continue
                
                opt = puts[strike]
                bid = opt.get('bidprice', 0)
                ask = opt.get('askprice', 0)
                vol = opt.get('totalTradedVolume', 0)
                oi_chg = opt.get('openInterest', 0) - opt.get('prevOpenInterest', 0)
                
                if ask <= 0:
                    continue
                if vol < vol_thresh and abs(oi_chg) < oi_thresh:
                    continue
                if ask > 0 and (ask - bid) / ask > MAX_SPREAD_PCT_STOCK:
                    continue
                if ask / spot > MAX_PREMIUM_RATIO_STOCK:
                    continue
                
                moneyness = get_moneyness(strike, spot, "PE")
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Put',
                    'strike': strike,
                    'type': 'PE',
                    'premium': ask,
                    'volume': vol,
                    'oi_change': oi_chg,
                    'moneyness': moneyness
                })
                alerts.append(alert)
        
        # Straddle check for low IV
        if iv_data['iv_percentile'] < 40 and directional_bias == "NEUTRAL":
            if atm in calls and atm in puts:
                call_ask = calls[atm].get('askprice', 0)
                put_ask = puts[atm].get('askprice', 0)
                total_cost = call_ask + put_ask
                cost_pct = total_cost / spot
                
                if total_cost > 0 and cost_pct <= 0.06:  # Relaxed from 0.05
                    alert = base_alert.copy()
                    alert.update({
                        'strategy': 'Long Straddle',
                        'strike': atm,
                        'type': 'STRADDLE',
                        'premium': total_cost,
                        'volume': calls[atm].get('totalTradedVolume', 0) + puts[atm].get('totalTradedVolume', 0),
                        'oi_change': 0,
                        'moneyness': 'ATM'
                    })
                    alerts.append(alert)
    
    except Exception as e:
        logger.debug("Stock scan error for %s: %s", symbol, e)
    
    return alerts

# ================== TELEGRAM ALERT ==================

async def send_telegram_alert(alert):
    """Send formatted alert to Telegram"""
    strategy = alert['strategy']
    symbol = alert['symbol']
    strike = alert['strike']
    premium = alert['premium']
    spot = alert['spot']
    iv = alert.get('iv', 0)
    ivp = alert.get('iv_percentile', 0)
    regime = alert['market_regime']
    rsi = alert.get('rsi', 0)
    tier = alert.get('tier', 'N/A')
    moneyness = alert.get('moneyness', 'N/A')
    
    if ivp < 30:
        iv_status = "🟢 CHEAP"
    elif ivp < 50:
        iv_status = "🟡 BELOW AVG"
    elif ivp < 70:
        iv_status = "🟠 ABOVE AVG"
    else:
        iv_status = "🔴 EXPENSIVE"
    
    msg = f"🎯 *{strategy}* ({moneyness})\n"
    msg += f"📊 {symbol}"
    if tier != 'INDEX':
        msg += f" ({tier})"
    msg += f"\nSpot: ₹{spot:.0f} | Strike: {strike}\n"
    msg += f"Premium: ₹{premium:.2f}\n"
    msg += f"\n📈 IV: {iv:.1f}% ({ivp}%) {iv_status}\n"
    if rsi > 0:
        msg += f"RSI: {rsi:.1f} | "
    msg += f"Regime: {regime}\n"
    msg += f"\n🕒 {alert['timestamp']}"
    
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')
        logger.info("Telegram sent: %s %s @ %s", symbol, strategy, strike)
    except Exception as e:
        logger.error("Telegram error: %s", e)

# ================== MAIN JOB ==================

def job():
    """Main scanning job"""
    logger.info("=" * 60)
    logger.info("Starting scan at %s", datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 60)
    
    vix = get_india_vix()
    regime = determine_market_regime(vix)
    iv_threshold = get_iv_threshold(regime)
    
    logger.info("Market: VIX=%.1f | Regime=%s | IV Threshold=%d%%", vix, regime, iv_threshold)
    
    all_alerts = []
    
    # Scan indices
    logger.info("\n--- Scanning Indices ---")
    for sym in INDEX_SYMBOLS:
        alerts = scan_index(sym, iv_threshold, regime, vix)
        all_alerts.extend(alerts)
    
    # Scan stocks
    logger.info("\n--- Scanning Stocks (%d symbols) ---", len(STOCK_SYMBOLS))
    for i, sym in enumerate(STOCK_SYMBOLS):
        if (i + 1) % 20 == 0:
            logger.info("Progress: %d/%d stocks scanned...", i + 1, len(STOCK_SYMBOLS))
        alerts = scan_stock(sym, regime, vix)
        all_alerts.extend(alerts)
        time.sleep(0.3)  # Rate limiting
    
    # Remove duplicates
    seen = set()
    unique_alerts = []
    for a in all_alerts:
        key = (a['strategy'], a['symbol'], a['strike'])
        if key not in seen:
            seen.add(key)
            unique_alerts.append(a)
    
    # Sort by IV percentile (lowest first - best opportunities)
    unique_alerts.sort(key=lambda x: x.get('iv_percentile', 50))
    
    logger.info("=" * 60)
    logger.info("SCAN COMPLETE: %d unique alerts", len(unique_alerts))
    logger.info("=" * 60)
    
    if unique_alerts:
        # Show top 10 by IV percentile
        logger.info("\nTop opportunities (sorted by IV - lowest first):")
        for i, alert in enumerate(unique_alerts[:10]):
            logger.info("  %d. %s %s @ %s | IV%%=%d%% | Premium=₹%.2f | %s",
                       i+1, alert['symbol'], alert['strategy'], alert['strike'],
                       alert['iv_percentile'], alert['premium'], alert.get('moneyness', ''))
        
        for alert in unique_alerts:
            log_to_csv(alert)
            # Uncomment to send Telegram alerts:
            # asyncio.run(send_telegram_alert(alert))
    else:
        logger.info("No signals found. Consider relaxing filters if this persists.")

# ================== MAIN EXECUTION ==================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("SMART Options Screener v3.0 (Improved)")
    logger.info("=" * 60)
    logger.info("Indices: %s", ", ".join(INDEX_SYMBOLS))
    logger.info("Stocks: %d symbols", len(STOCK_SYMBOLS))
    logger.info("Logging to: %s", CSV_FILE)
    logger.info("=" * 60)
    
    # Run first scan immediately
    job()
    
    # Schedule recurring scans every 60 seconds
    schedule.every(60).seconds.do(job)
    
    logger.info("\nScheduler started. Press Ctrl+C to stop.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)