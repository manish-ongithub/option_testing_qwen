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
TELEGRAM_BOT_TOKEN = "8554491299:AAEYVxPF-THCg5f37JsDBHGUI3kTON2idPM"
TELEGRAM_CHAT_ID = "@manish_private_bot"

# Instruments
INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY"]
STOCK_SYMBOLS = [
    # Large Cap Banks
    "HDFCBANK",
    "ICICIBANK", 
    "AXISBANK",
    "KOTAKBANK",
    "SBIN",
    
    # IT Giants
    "RELIANCE",
    "TCS",
    "INFY",
    "HCLTECH",
    "WIPRO",
    "TECHM",
    "LTI",  # LTIMindtree
    
    # Auto & Industrials
    "MARUTI",
    "M&M",  # Mahindra & Mahindra
    "LT",  # Larsen & Toubro
    "TATAMOTORS",
    
    # Pharma
    "SUNPHARMA",
    "DRREDDY",
    
    # Consumer
    "HINDUNILVR",
    "ITC",
    "BRITANNIA",
    "NESTLEIND",
    "TITAN",
    
    # Telecom & Energy
    "BHARTIARTL",
    "NTPC",
    "POWERGRID",
    "COALINDIA",
    
    # Finance
    "BAJFINANCE",
    "BAJAJFINSV",
    "HDFCLIFE",# Banks & NBFCs
    "INDUSINDBK",
    "BANDHANBNK",
    "IDFCFIRSTB",
    "FEDERALBNK",
    "CANBK",  # Canara Bank
    "PNB",  # Punjab National Bank
    "BANKBARODA",
    "BANKINDIA",
    "UNIONBANK",
    "CHOLAFIN",  # Cholamandalam
    "LICHSGFIN",
    "PNBHOUSING",
    "LTFH",  # L&T Finance Holdings
    "MUTHOOTFIN",
    "MANAPPURAM",
    
    # IT & Tech
    "PERSISTENT",
    "COFORGE",
    "MPHASIS",
    "OFSS",  # Oracle Financial Services
    "LTTS",  # L&T Technology Services
    
    # Auto & Auto Components
    "TATASTEEL",
    "HEROMOTOCO",
    "EICHERMOT",
    "BAJAJ-AUTO",
    "TVSMOTOR",
    "ASHOKLEY",
    "APOLLOTYRE",
    "MRF",
    "MOTHERSON",  # Samvardhana Motherson
    "SONACOMS",  # Sona BLW
    
    # Pharma & Healthcare
    "CIPLA",
    "AUROPHARMA",
    "LUPIN",
    "BIOCON",
    "TORNTPHARM",
    "ALKEM",
    "LAURUSLABS",
    "DIVISLAB",
    "ZYDUSLIFE",
    "APOLLOHOSP",
    "MAXHEALTH",
    "FORTIS",
    
    # Industrials & Infra
    "ADANIPORTS",
    "ADANIENT",
    "ADANIGREEN",
    "ADANIENSOL",  # Adani Energy Solutions
    "JSWSTEEL",
    "HINDALCO",
    "VEDL",  # Vedanta
    "TATASTEEL",
    "JINDALSTEL",
    "SAIL",  # Steel Authority of India
    "BHEL",
    "BEL",  # Bharat Electronics
    "HAL",  # Hindustan Aeronautics
    "BHARATFORG",
    "CUMMINSIND",
    
    # Consumer & Retail
    "DABUR",
    "GODREJCP",
    "MARICO",
    "COLPAL",  # Colgate-Palmolive
    "PIDILITE",
    "ASIANPAINT",
    "BERGEPAINT",
    "BATAINDIA",
    "TATACONSUM",
    "DMART",  # Avenue Supermarts
    "TRENT",
    "JUBLFOOD",
    "VARUN",  # Varun Beverages
    
    # Energy & Utilities
    "ONGC",
    "BPCL",
    "IOC",  # Indian Oil
    "GAIL",
    "HINDPETRO",
    "TATAPOWER",
    "POWERGRID",
    "ADANIPOWER",
    "NTPC",
    "NHPC",
    
    # Financials & Insurance
    "SBILIFE",
    "SBICARD",
    "HDFCAMC",
    "ICICIGI",  # ICICI Lombard
    "ICICIPRULI",  # ICICI Pru Life
    "MAXFIN",  # Max Financial Services
    "POLICYBZR",  # PB Fintech
]

SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "INDIAVIX": "^VIX"
}
for stock in STOCK_SYMBOLS:
    SYMBOL_MAP[stock] = f"{stock}.NS"

# ================== TIERED PARAMETERS ==================
STOCK_TIERS = {
    'TIER_1': [# Large Cap Banks
    "HDFCBANK",
    "ICICIBANK", 
    "AXISBANK",
    "KOTAKBANK",
    "SBIN",
    
    # IT Giants
    "RELIANCE",
    "TCS",
    "INFY",
    "HCLTECH",
    "WIPRO",
    "TECHM",
    "LTI",  # LTIMindtree
    
    # Auto & Industrials
    "MARUTI",
    "M&M",  # Mahindra & Mahindra
    "LT",  # Larsen & Toubro
    "TATAMOTORS",
    
    # Pharma
    "SUNPHARMA",
    "DRREDDY",
    
    # Consumer
    "HINDUNILVR",
    "ITC",
    "BRITANNIA",
    "NESTLEIND",
    "TITAN",
    
    # Telecom & Energy
    "BHARTIARTL",
    "NTPC",
    "POWERGRID",
    "COALINDIA",
    
    # Finance
    "BAJFINANCE",
    "BAJAJFINSV",
    "HDFCLIFE"],
    'TIER_2': [# Banks & NBFCs
    "INDUSINDBK",
    "BANDHANBNK",
    "IDFCFIRSTB",
    "FEDERALBNK",
    "CANBK",  # Canara Bank
    "PNB",  # Punjab National Bank
    "BANKBARODA",
    "BANKINDIA",
    "UNIONBANK",
    "CHOLAFIN",  # Cholamandalam
    "LICHSGFIN",
    "PNBHOUSING",
    "LTFH",  # L&T Finance Holdings
    "MUTHOOTFIN",
    "MANAPPURAM",
    
    # IT & Tech
    "PERSISTENT",
    "COFORGE",
    "MPHASIS",
    "OFSS",  # Oracle Financial Services
    "LTTS",  # L&T Technology Services
    
    # Auto & Auto Components
    "TATASTEEL",
    "HEROMOTOCO",
    "EICHERMOT",
    "BAJAJ-AUTO",
    "TVSMOTOR",
    "ASHOKLEY",
    "APOLLOTYRE",
    "MRF",
    "MOTHERSON",  # Samvardhana Motherson
    "SONACOMS",  # Sona BLW
    
    # Pharma & Healthcare
    "CIPLA",
    "AUROPHARMA",
    "LUPIN",
    "BIOCON",
    "TORNTPHARM",
    "ALKEM",
    "LAURUSLABS",
    "DIVISLAB",
    "ZYDUSLIFE",
    "APOLLOHOSP",
    "MAXHEALTH",
    "FORTIS",
    
    # Industrials & Infra
    "ADANIPORTS",
    "ADANIENT",
    "ADANIGREEN",
    "ADANIENSOL",  # Adani Energy Solutions
    "JSWSTEEL",
    "HINDALCO",
    "VEDL",  # Vedanta
    "TATASTEEL",
    "JINDALSTEL",
    "SAIL",  # Steel Authority of India
    "BHEL",
    "BEL",  # Bharat Electronics
    "HAL",  # Hindustan Aeronautics
    "BHARATFORG",
    "CUMMINSIND",
    
    # Consumer & Retail
    "DABUR",
    "GODREJCP",
    "MARICO",
    "COLPAL",  # Colgate-Palmolive
    "PIDILITE",
    "ASIANPAINT",
    "BERGEPAINT",
    "BATAINDIA",
    "TATACONSUM",
    "DMART",  # Avenue Supermarts
    "TRENT",
    "JUBLFOOD",
    "VARUN",  # Varun Beverages
    
    # Energy & Utilities
    "ONGC",
    "BPCL",
    "IOC",  # Indian Oil
    "GAIL",
    "HINDPETRO",
    "TATAPOWER",
    "POWERGRID",
    "ADANIPOWER",
    "NTPC",
    "NHPC",
    
    # Financials & Insurance
    "SBILIFE",
    "SBICARD",
    "HDFCAMC",
    "ICICIGI",  # ICICI Lombard
    "ICICIPRULI",  # ICICI Pru Life
    "MAXFIN",  # Max Financial Services
    "POLICYBZR"],
    'TIER_3': ['HINDUNILVR', 'ASIANPAINT', 'MARUTI', 'LT', 'SUNPHARMA', 
               'WIPRO', 'ULTRACEMCO', 'HCLTECH', 'TECHM']
}

VOLUME_THRESHOLDS = {
    'TIER_1': 800,
    'TIER_2': 400,
    'TIER_3': 200
}

OI_CHANGE_THRESHOLDS = {
    'TIER_1': 150,
    'TIER_2': 75,
    'TIER_3': 30
}

# thresholds = {
#         'TIER_1': {'volume': 800, 'oi_change': 150},
#         'TIER_2': {'volume': 400, 'oi_change': 75},
#         'TIER_3': {'volume': 200, 'oi_change': 30}
#     }

# Strategy Parameters
VOLUME_THRESHOLD_INDEX = 5000
VOLUME_THRESHOLD_STOCK = 1000  # Legacy, use VOLUME_THRESHOLDS instead
OI_CHANGE_THRESHOLD_INDEX = 1000
OI_CHANGE_THRESHOLD_STOCK = 200  # Legacy, use OI_CHANGE_THRESHOLDS instead

STRIKE_RANGE_MULTIPLIER = 2
MAX_SPREAD_PCT = 0.05
MAX_SPREAD_PCT_STOCK = 0.08
MAX_PREMIUM_RATIO = 0.05
MAX_PREMIUM_RATIO_STOCK = 0.08
STRADDLE_MAX_COST_PCT = 0.03
MIN_STOCK_PRICE = 500

# Trend Indicators
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65
ADX_TRENDING = 25

# IV-based thresholds
IV_VERY_HIGH = 80
IV_HIGH = 70
IV_LOW = 30

# Market Hours
MARKET_START = dtime(9, 15)
MARKET_END = dtime(15, 30)
IST = pytz.timezone("Asia/Kolkata")

CSV_FILE = "new_options_scan_log.csv"

# GLOBAL: Store your session cookies here after logging in via browser
OPSTRA_COOKIES = {
    'JSESSIONID': '68C2B25E68942C37028E38FE43E12941',
    'DSESSIONID': '54BD4DA6614952A5841DF155A18F2C97',
    '_ga': 'GA1.1.703791765.1764073625',
    '_ga_6D0ZQ437SD': 'GS2.1.s1764145134$o4$g1$t1764145153$j41$l0$h0'
}


def set_opstra_cookies(jsessionid, dsessionid):
    """
    Set Opstra session cookies. Get these from your browser after logging in:
    1. Login to opstra.definedge.com in Chrome
    2. Press F12 -> Application tab -> Cookies
    3. Copy JSESSIONID and DSESSIONID values
    4. Call this function: set_opstra_cookies('your_jsessionid', 'your_dsessionid')
    """
    global OPSTRA_COOKIES
    OPSTRA_COOKIES['JSESSIONID'] = jsessionid
    OPSTRA_COOKIES['DSESSIONID'] = dsessionid
    logger.info("Opstra cookies set successfully (JSESSIONID & DSESSIONID updated)")

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Initialize CSV
headers = [
    "Timestamp", "Symbol", "Type", "Strategy", "Strike", "Premium",
    "Spot", "Volume", "OI_Change", "IV", "IV_Percentile", "IV_Rank",
    "Market_Regime", "VIX", "RSI", "ADX", "Tier"
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
            alert.get('tier', 'N/A')
        ])

# ================== HELPER FUNCTIONS ==================

def get_stock_tier(symbol):
    """Return tier for a stock symbol"""
    for tier, stocks in STOCK_TIERS.items():
        if symbol in stocks:
            return tier
    return 'TIER_3'

def find_atm_strike(strikes, spot):
    """Find the strike closest to spot price"""
    return min(strikes, key=lambda x: abs(x - spot))

def get_india_vix():
    """Fetch India VIX (fallback to 16.0 on failure)."""
    try:
        logger.debug("Fetching India VIX from yfinance (^VIX)")
        data = yf.Ticker("^VIX").history(period="1d")
        if not data.empty:
            vix_val = data['Close'][-1]
            logger.debug("Fetched India VIX value: %.2f", vix_val)
            return vix_val
        logger.warning("India VIX history empty, using default 16.0")
        return 16.0
    except Exception as e:
        logger.exception("Error fetching India VIX, using default 16.0: %s", e)
        return 16.0

def determine_market_regime(vix_value):
    if vix_value < 14:
        return "LOW_VOL"
    elif vix_value <= 18:
        return "NORMAL_VOL"
    else:
        return "HIGH_VOL"

def get_iv_threshold(market_regime):
    thresholds = {"LOW_VOL": 50, "NORMAL_VOL": 40, "HIGH_VOL": 30}
    return thresholds.get(market_regime, 40)

def get_iv_data(symbol):
    """
    Fetch historical IV data from Opstra's ivcharts API and compute:
    - Current IV (last ImpVol)
    - IV Percentile (over last 252 days)
    - IV Rank (over last 252 days)
    """
    if not OPSTRA_COOKIES.get('JSESSIONID') or not OPSTRA_COOKIES.get('DSESSIONID'):
        logger.error("Opstra cookies not set. Call set_opstra_cookies() before get_iv_data for %s", symbol)
        logger.info(
            "Opstra IV instructions: login to https://opstra.definedge.com, "
            "copy JSESSIONID & DSESSIONID cookies, and call set_opstra_cookies()"
        )
        return None

    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,hi;q=0.7",
        "referer": "https://opstra.definedge.com/ivchart",
        "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
    }

    try:
        symbol_upper = symbol.upper()
        url = f"https://opstra.definedge.com/api/ivcharts/{symbol_upper}"
        logger.debug("Requesting Opstra IV data for %s via %s", symbol_upper, url)
        
        response = requests.get(url, headers=headers, cookies=OPSTRA_COOKIES, timeout=10)
        logger.debug("Opstra IV HTTP response for %s: %s", symbol_upper, response.status_code)
        
        if response.status_code == 401:
            logger.error("%s: Opstra session expired (401). Please login again and update cookies.", symbol)
            return None
        
        if response.status_code != 200:
            logger.error("%s: HTTP %s from Opstra IV API. Response snippet: %s",
                         symbol, response.status_code, response.text[:200])
            return None
        
        data = response.json()
        ivchart = data.get("ivchart", [])
        
        if not ivchart:
            logger.error("[IV ERROR] %s: No IV data returned from Opstra", symbol)
            return None

        # Extract ImpVol values (ignore nulls)
        iv_values = []
        for point in ivchart:
            iv = point.get("ImpVol")
            if iv is not None and iv > 0:
                iv_values.append(float(iv))

        if len(iv_values) < 30:
            logger.warning("[IV WARN] %s: Insufficient IV history (<30 days, got %d)", symbol, len(iv_values))
            return None

        # Use last 252 days (or all if less)
        window = iv_values[-252:]
        current_iv = window[-1]

        # Compute IV Percentile
        iv_percentile = int((np.sum(np.array(window) <= current_iv) / len(window)) * 100)

        # Compute IV Rank: (current - min) / (max - min)
        iv_min = min(window)
        iv_max = max(window)
        if iv_max == iv_min:
            iv_rank = 50
        else:
            iv_rank = int(((current_iv - iv_min) / (iv_max - iv_min)) * 100)
        
        logger.info(
            "IV data for %s: IV=%.2f, IV%%=%d, IVR=%d (window_len=%d)",
            symbol, current_iv, iv_percentile, iv_rank, len(window)
        )
        return {
            'iv': current_iv,
            'iv_percentile': iv_percentile,
            'iv_rank': iv_rank
        }

    except Exception as e:
        logger.exception("[IV EXCEPTION] %s while fetching IV data: %s", symbol, e)
        return None

def get_underlying_price(symbol):
    """
    Get near-real-time price for indices; daily close for stocks.
    Indices: uses 5-min data for freshness.
    Stocks: uses daily close (intraday often unavailable on yfinance).
    """
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        logger.debug("Fetching underlying price for %s using ticker %s", symbol, ticker)
        
        if symbol in ["NIFTY", "BANKNIFTY"]:
            data = yf.Ticker(ticker).history(period="1d", interval="5m")
            if not data.empty:
                price = data['Close'].iloc[-1]
                logger.debug("Underlying price for %s (index): %.2f", symbol, price)
                return price
            logger.warning("Empty intraday price data for index %s", symbol)
        else:
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                price = data['Close'].iloc[-1]
                logger.debug("Underlying price for %s (stock): %.2f", symbol, price)
                return price
            logger.warning("Empty daily price data for stock %s", symbol)
                
    except Exception as e:
        logger.exception("[PRICE ERROR] Error fetching underlying price for %s: %s", symbol, e)
    
    logger.error("Failed to fetch underlying price for %s, returning None", symbol)
    return None

def compute_trend_indicators(symbol):
    """
    Compute RSI, ADX, and directional bias for a stock
    Returns: {'bias': 'BULLISH/BEARISH/NEUTRAL', 'rsi': float, 'adx': float}
    """
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        hist = yf.Ticker(ticker).history(period="1mo", interval="1d")
        
        if len(hist) < 20:
            logger.warning("Insufficient data for trend indicators on %s (len=%d)", symbol, len(hist))
            return {'bias': 'NEUTRAL', 'rsi': 50, 'adx': 0}
        
        # RSI Calculation
        delta = hist['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = rsi.iloc[-1] if not rsi.empty else 50
        
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
        
        # Determine bias
        ema20 = hist['Close'].ewm(span=20).mean().iloc[-1]
        current_price = hist['Close'].iloc[-1]
        
        if current_price > ema20 * 1.02:
            bias = "BULLISH"
        elif current_price < ema20 * 0.98:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
        
        return {
            'bias': bias,
            'rsi': float(current_rsi),
            'adx': float(adx_approx)
        }
    
    except Exception as e:
        logger.exception("Error computing trend indicators for %s: %s", symbol, e)
        return {'bias': 'NEUTRAL', 'rsi': 50, 'adx': 0}

def is_market_hours():
    now = datetime.now(IST).time()
    in_hours = MARKET_START <= now <= MARKET_END
    logger.debug(
        "Market hours check: now=%s, start=%s, end=%s, in_hours=%s",
        now, MARKET_START, MARKET_END, in_hours
    )
    return in_hours

# ================== SCANNING FUNCTIONS ==================

def scan_index(symbol, iv_threshold, market_regime, vix):
    logger.info(
        "Starting index scan for %s | regime=%s, iv_threshold=%s, vix=%.2f",
        symbol, market_regime, iv_threshold, vix
    )
    alerts = []
    try:
        oc = nse_optionchain_scrapper(symbol)
        records = oc['records']['data']
        spot_nse = oc['records']['underlyingValue']
        spot = get_underlying_price(symbol) or spot_nse
        logger.debug("Index %s spot from NSE=%.2f, yfinance/underlying=%.2f", symbol, spot_nse, spot)

        iv_data = get_iv_data(symbol)
        calls = {}
        puts = {}
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
            logger.warning("No strikes found for index %s", symbol)
            return []
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else (100 if symbol == "BANKNIFTY" else 50)

        if market_regime == "HIGH_VOL":
            vol_thresh = 8000
            oi_thresh = 1500
            require_trend = True
        else:
            vol_thresh = VOLUME_THRESHOLD_INDEX
            oi_thresh = OI_CHANGE_THRESHOLD_INDEX
            require_trend = False

        directional_bias = "NEUTRAL"
        trend_confirmed = False
        try:
            hist = yf.Ticker(SYMBOL_MAP[symbol]).history(period="2d", interval="5m")
            if len(hist) >= 50:
                ema20 = hist['Close'].ewm(span=20).mean().iloc[-1]
                ema50 = hist['Close'].ewm(span=50).mean().iloc[-1]
                current = hist['Close'].iloc[-1]
                if current > ema20 and ema20 > ema50:
                    directional_bias = "BULLISH"
                    trend_confirmed = True
                elif current < ema20 and ema20 < ema50:
                    directional_bias = "BEARISH"
                    trend_confirmed = True
                logger.debug(
                    "Trend for %s: current=%.2f, EMA20=%.2f, EMA50=%.2f, bias=%s, confirmed=%s",
                    symbol, current, ema20, ema50, directional_bias, trend_confirmed
                )
        except Exception as e:
            logger.exception("Error computing EMA trend for %s: %s", symbol, e)

        if market_regime == "HIGH_VOL" and not trend_confirmed:
            directional_bias = "NEUTRAL"
            logger.info("High vol regime for %s but trend not confirmed, forcing NEUTRAL bias", symbol)

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

        for opt_type, opt_dict, bias in [("CE", calls, "BULLISH"), ("PE", puts, "BEARISH")]:
            allow = directional_bias == bias
            if market_regime != "HIGH_VOL":
                allow = allow or directional_bias == "NEUTRAL"

            if allow:
                for strike, opt in opt_dict.items():
                    if opt_type == "CE" and strike > atm + step:
                        continue
                    if opt_type == "PE" and strike < atm - step:
                        continue

                    bid = opt.get('bidprice', 0)
                    ask = opt.get('askprice', 0)
                    vol = opt.get('totalTradedVolume', 0)
                    oi_chg = opt.get('openInterest', 0) - opt.get('prevOpenInterest', 0)

                    if ask <= 0 or vol < vol_thresh or oi_chg < oi_thresh:
                        continue
                    if (ask - bid) / ask > MAX_SPREAD_PCT:
                        continue
                    if ask / spot > MAX_PREMIUM_RATIO:
                        continue

                    alert = base_alert.copy()
                    alert.update({
                        'strategy': f"Long {'Call' if opt_type == 'CE' else 'Put'}",
                        'strike': strike,
                        'type': opt_type,
                        'premium': ask,
                        'volume': vol,
                        'oi_change': oi_chg
                    })
                    alerts.append(alert)
        logger.debug("Directional single-leg alerts for %s: %d", symbol, len(alerts))

        if directional_bias in ["BULLISH", "NEUTRAL"] and market_regime != "HIGH_VOL":
            buy_strike = atm
            sell_candidates = [s for s in strikes if s > atm]
            if buy_strike in calls and sell_candidates:
                sell_strike = min(sell_candidates)
                long_leg = calls[buy_strike]
                short_leg = calls.get(sell_strike, {})
                net_debit = long_leg.get('askprice', 0) - short_leg.get('bidprice', 0)
                max_profit = (sell_strike - buy_strike) - net_debit
                if net_debit > 0 and max_profit > 0 and net_debit < max_profit * 0.5:
                    alert = base_alert.copy()
                    alert.update({
                        'strategy': "Bull Call Spread",
                        'strike': f"{buy_strike}/{sell_strike}",
                        'type': "CALL_SPREAD",
                        'premium': net_debit,
                        'volume': long_leg.get('totalTradedVolume', 0),
                        'oi_change': 0
                    })
                    alerts.append(alert)

        if directional_bias in ["BEARISH", "NEUTRAL"] and market_regime != "HIGH_VOL":
            buy_strike = atm
            sell_candidates = [s for s in strikes if s < atm]
            if buy_strike in puts and sell_candidates:
                sell_strike = max(sell_candidates)
                long_leg = puts[buy_strike]
                short_leg = puts.get(sell_strike, {})
                net_debit = long_leg.get('askprice', 0) - short_leg.get('bidprice', 0)
                max_profit = (buy_strike - sell_strike) - net_debit
                if net_debit > 0 and max_profit > 0 and net_debit < max_profit * 0.5:
                    alert = base_alert.copy()
                    alert.update({
                        'strategy': "Bear Put Spread",
                        'strike': f"{buy_strike}/{sell_strike}",
                        'type': "PUT_SPREAD",
                        'premium': net_debit,
                        'volume': long_leg.get('totalTradedVolume', 0),
                        'oi_change': 0
                    })
                    alerts.append(alert)

        if market_regime in ["LOW_VOL", "NORMAL_VOL"]:
            if iv_data and iv_data['iv_percentile'] <= iv_threshold:
                if atm in calls and atm in puts:
                    total = calls[atm].get('askprice', 0) + puts[atm].get('askprice', 0)
                    cost_pct = total / spot
                    max_cost = 0.03 if market_regime == "LOW_VOL" else 0.025
                    if total > 0 and cost_pct <= max_cost:
                        alert = base_alert.copy()
                        alert.update({
                            'strategy': "Long Straddle",
                            'strike': atm,
                            'type': "STRADDLE",
                            'premium': total,
                            'volume': calls[atm].get('totalTradedVolume', 0) + puts[atm].get('totalTradedVolume', 0),
                            'oi_change': 0
                        })
                        alerts.append(alert)

                call_strike = min([s for s in strikes if s > atm], default=None)
                put_strike = max([s for s in strikes if s < atm], default=None)
                if call_strike and put_strike:
                    total = calls.get(call_strike, {}).get('askprice', 0) + puts.get(put_strike, {}).get('askprice', 0)
                    cost_pct = total / spot
                    max_cost = 0.035 if market_regime == "LOW_VOL" else 0.03
                    if total > 0 and cost_pct <= max_cost:
                        alert = base_alert.copy()
                        alert.update({
                            'strategy': "Long Strangle",
                            'strike': f"{put_strike}/{call_strike}",
                            'type': "STRANGLE",
                            'premium': total,
                            'volume': calls.get(call_strike, {}).get('totalTradedVolume', 0) +
                                      puts.get(put_strike, {}).get('totalTradedVolume', 0),
                            'oi_change': 0
                        })
                        alerts.append(alert)

    except Exception as e:
        logger.exception("[INDEX SCAN ERROR] %s: %s", symbol, e)
    logger.info("Index scan completed for %s, total alerts: %d", symbol, len(alerts))
    return alerts

def scan_stock(symbol, market_regime, vix):
    """
    Enhanced stock scanning WITH IV data from Opstra and tiered thresholds
    """
    logger.info("Starting stock scan for %s | regime=%s, vix=%.2f", symbol, market_regime, vix)
    alerts = []
    
    try:
        # Get stock tier
        tier = get_stock_tier(symbol)
        vol_thresh = VOLUME_THRESHOLDS[tier]
        oi_thresh = OI_CHANGE_THRESHOLDS[tier]
        
        logger.info("Stock %s classified as %s | vol_thresh=%d | oi_thresh=%d",
                   symbol, tier, vol_thresh, oi_thresh)
        
        # Fetch option chain
        oc = nse_optionchain_scrapper(symbol) # handle no data case
        records = oc['records']['data']
        spot_nse = oc['records']['underlyingValue']
        spot = get_underlying_price(symbol) or spot_nse
        
        logger.info("Stock %s spot from NSE=%.2f, yfinance/underlying=%.2f", symbol, spot_nse, spot)
        
        # Skip low-priced stocks
        if spot < MIN_STOCK_PRICE:
            logger.info("[SKIP] %s: Spot ₹%.2f below minimum ₹%d", symbol, spot, MIN_STOCK_PRICE)
            return []
        
        # Fetch IV data for stocks
        logger.info("Fetching IV data for stock %s from Opstra...", symbol)
        iv_data = get_iv_data(symbol)
        
        if iv_data:
            logger.info("✓ IV Data for %s: IV=%.1f%%, IV Percentile=%d%%, IV Rank=%d%%",
                       symbol, iv_data['iv'], iv_data['iv_percentile'], iv_data['iv_rank'])
        else:
            logger.warning("⚠️  Could not fetch IV data for %s from Opstra, using defaults", symbol)
            iv_data = {'iv': 0, 'iv_percentile': 50, 'iv_rank': 50}
        
        # Compute trend indicators
        trend_data = compute_trend_indicators(symbol)
        directional_bias = trend_data['bias']
        rsi = trend_data['rsi']
        adx = trend_data['adx']
        
        logger.info("Stock %s trend: bias=%s | RSI=%.1f | ADX=%.1f | IV%%=%d",
                   symbol, directional_bias, rsi, adx, iv_data['iv_percentile'])
        
        # IV-BASED FILTERING LOGIC
        
        # Rule 1: VERY HIGH IV (>80th percentile) = AVOID BUYING OPTIONS
        if iv_data['iv_percentile'] > IV_VERY_HIGH:
            logger.info("📊 %s: IV Percentile=%d%% is VERY HIGH (>%d%%) - "
                       "Premium is EXPENSIVE, skipping long options to avoid IV crush",
                       symbol, iv_data['iv_percentile'], IV_VERY_HIGH)
            return []
        
        # Rule 2: HIGH IV (70-80th percentile) = CAUTIOUS, only strong trends
        if iv_data['iv_percentile'] > IV_HIGH:
            if adx < ADX_TRENDING:
                logger.info("📊 %s: IV Percentile=%d%% is HIGH but no strong trend (ADX=%.1f) - "
                           "skipping to avoid expensive premiums without conviction",
                           symbol, iv_data['iv_percentile'], adx)
                return []
            else:
                logger.info("📊 %s: IV Percentile=%d%% is HIGH but strong trend detected (ADX=%.1f) - "
                           "proceeding with TIGHT filters",
                           symbol, iv_data['iv_percentile'], adx)
                # Increase thresholds for high IV environment
                vol_thresh = int(vol_thresh * 1.5)
                oi_thresh = int(oi_thresh * 1.5)
        
        # Rule 3: LOW IV (<30th percentile) = IDEAL FOR BUYING OPTIONS
        if iv_data['iv_percentile'] < IV_LOW:
            logger.info("📊 %s: IV Percentile=%d%% is LOW (<%d%%) - "
                       "Premium is CHEAP, excellent time to buy options! Relaxing filters.",
                       symbol, iv_data['iv_percentile'], IV_LOW)
            # Relax thresholds for low IV (good buying opportunity)
            vol_thresh = int(vol_thresh * 0.7)
            oi_thresh = int(oi_thresh * 0.7)
        
        # Rule 4: NORMAL IV (30-70th percentile) = STANDARD SCANNING
        if IV_LOW <= iv_data['iv_percentile'] <= IV_HIGH:
            logger.info("📊 %s: IV Percentile=%d%% is NORMAL - using standard filters",
                       symbol, iv_data['iv_percentile'])
        
        # Parse strikes
        calls = {}
        puts = {}
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
            logger.info("[SKIP] %s: No strikes found", symbol)
            return []
        
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else 10
        max_distance = step * STRIKE_RANGE_MULTIPLIER
        
        logger.info("Stock %s: spot=%.0f atm=%s step=%s range=±%s", symbol, spot, atm, step, max_distance)
        
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
        
        # Determine which options to scan based on trend + RSI + IV
        scan_calls = (directional_bias in ["BULLISH", "NEUTRAL"] or rsi < RSI_OVERSOLD)
        scan_puts = (directional_bias in ["BEARISH", "NEUTRAL"] or rsi > RSI_OVERBOUGHT)
        
        # Additional IV-based strategy filter
        scan_straddle = False
        if iv_data['iv_percentile'] < 40 and directional_bias == "NEUTRAL":
            scan_straddle = True
            logger.info("📊 %s: Low IV + Neutral bias - will check for straddle opportunity", symbol)
        
        logger.info("Scanning strategy: Calls=%s | Puts=%s | Straddle=%s",
                   scan_calls, scan_puts, scan_straddle)
        
        # SCAN CALLS
        if scan_calls:
            for strike in [s for s in strikes if abs(s - atm) <= max_distance]:
                if strike not in calls:
                    continue
                
                opt = calls[strike]
                bid = opt.get('bidprice', 0)
                ask = opt.get('askprice', 0)
                vol = opt.get('totalTradedVolume', 0)
                oi_chg = opt.get('openInterest', 0) - opt.get('prevOpenInterest', 0)
                
                # Apply filters (using either/or for vol and OI)
                if ask <= 0:
                    continue
                if vol < vol_thresh and oi_chg < oi_thresh:
                    continue
                if ask > 0 and (ask - bid) / ask > MAX_SPREAD_PCT_STOCK:
                    continue
                if ask / spot > MAX_PREMIUM_RATIO_STOCK:
                    continue
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Call',
                    'strike': strike,
                    'type': 'CE',
                    'premium': ask,
                    'volume': vol,
                    'oi_change': oi_chg
                })
                alerts.append(alert)
                logger.info("✓ ALERT: %s Long Call @ %s | Premium=₹%.2f | IV%%=%d%%",
                           symbol, strike, ask, iv_data['iv_percentile'])
        
        # SCAN PUTS
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
                if vol < vol_thresh and oi_chg < oi_thresh:
                    continue
                if ask > 0 and (ask - bid) / ask > MAX_SPREAD_PCT_STOCK:
                    continue
                if ask / spot > MAX_PREMIUM_RATIO_STOCK:
                    continue
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Put',
                    'strike': strike,
                    'type': 'PE',
                    'premium': ask,
                    'volume': vol,
                    'oi_change': oi_chg
                })
                alerts.append(alert)
                logger.info("✓ ALERT: %s Long Put @ %s | Premium=₹%.2f | IV%%=%d%%",
                           symbol, strike, ask, iv_data['iv_percentile'])
        
        # SCAN STRADDLE (only in low IV environments)
        if scan_straddle and atm in calls and atm in puts:
            call_ask = calls[atm].get('askprice', 0)
            put_ask = puts[atm].get('askprice', 0)
            total_cost = call_ask + put_ask
            cost_pct = total_cost / spot
            
            # For stocks, allow slightly higher straddle cost than indices
            max_straddle_cost = 0.05
            
            if total_cost > 0 and cost_pct <= max_straddle_cost:
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Straddle',
                    'strike': atm,
                    'type': 'STRADDLE',
                    'premium': total_cost,
                    'volume': calls[atm].get('totalTradedVolume', 0) + puts[atm].get('totalTradedVolume', 0),
                    'oi_change': 0
                })
                alerts.append(alert)
                logger.info("✓ ALERT: %s Long Straddle @ %s | Cost=₹%.2f (%.2f%%) | IV%%=%d%%",
                           symbol, atm, total_cost, cost_pct*100, iv_data['iv_percentile'])
    
    except Exception as e:
        logger.exception("[STOCK SCAN ERROR] %s: %s", symbol, e)
    
    logger.info("Stock scan completed for %s, total alerts: %d", symbol, len(alerts))
    return alerts

# ================== TELEGRAM ALERT ==================

async def send_telegram_alert(alert):
    """Enhanced Telegram alert showing IV metrics"""
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
    
    # Create IV assessment
    if ivp < 30:
        iv_status = "🟢 LOW (CHEAP)"
    elif ivp < 50:
        iv_status = "🟡 BELOW AVG"
    elif ivp < 70:
        iv_status = "🟠 ABOVE AVG"
    else:
        iv_status = "🔴 HIGH (EXPENSIVE)"
    
    msg = f"🎯 *{strategy}*\n"
    msg += f"📊 {symbol}"
    if tier != 'INDEX':
        msg += f" ({tier})"
    msg += f"\nSpot: ₹{spot:.0f} | Strike: {strike}\n"
    msg += f"Premium: ₹{premium:.2f}\n"
    msg += f"\n📈 *Metrics:*\n"
    
    if iv > 0:
        msg += f"IV: {iv:.1f}% | IV%: {ivp}% {iv_status}\n"
    if rsi > 0:
        msg += f"RSI: {rsi:.1f} | "
    msg += f"Regime: {regime}\n"
    msg += f"\n🕒 {alert['timestamp']}"
    
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')
        logger.info("Telegram alert sent for %s %s @ %s", symbol, strategy, strike)
    except Exception as e:
        logger.exception("[TELEGRAM ERROR] Failed to send alert: %s", e)

# ================== MAIN JOB ==================

def job():
    """Main scanning job with IV-enabled stock scanning"""
    logger.info("=" * 80)
    logger.info("Starting smart scan cycle at %s", datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'))
    logger.info("=" * 80)
    
    vix = get_india_vix()
    regime = determine_market_regime(vix)
    iv_threshold = get_iv_threshold(regime)
    
    logger.info("Market Context:")
    logger.info("  VIX: %.1f | Regime: %s | IV%% Threshold: ≤%d", vix, regime, iv_threshold)
    logger.info("")
    
    all_alerts = []
    
    # Scan indices
    logger.info("Scanning Indices...")
    for sym in INDEX_SYMBOLS:
        alerts = scan_index(sym, iv_threshold, regime, vix)
        all_alerts.extend(alerts)
    
    # Scan stocks with IV data
    logger.info("")
    logger.info("Scanning Stocks with IV analysis...")
    for sym in STOCK_SYMBOLS:
        alerts = scan_stock(sym, regime, vix)
        all_alerts.extend(alerts)
        time.sleep(0.5)  # Small delay to avoid rate limiting
    
    # Remove duplicates
    seen = set()
    unique_alerts = []
    for a in all_alerts:
        key = (a['strategy'], a['symbol'], a['strike'], a['timestamp'][:16])
        if key not in seen:
            seen.add(key)
            unique_alerts.append(a)
    
    # Send alerts
    if unique_alerts:
        logger.info("=" * 80)
        logger.info("SCAN COMPLETE: %d unique alerts generated", len(unique_alerts))
        logger.info("=" * 80)
        
        for alert in unique_alerts:
            logger.info("ALERT: %s | %s | %s @ %s | ₹%.2f | IV%%=%d%% | Vol=%d | OI=%+d",
                       alert['instrument_type'], alert['strategy'], alert['symbol'],
                       alert['strike'], alert['premium'], alert['iv_percentile'],
                       alert['volume'], alert['oi_change'])
            log_to_csv(alert)
            asyncio.run(send_telegram_alert(alert))
    else:
        logger.info("=" * 80)
        logger.info("SCAN COMPLETE: No signals generated in current market conditions")
        logger.info("=" * 80)

# ================== MAIN EXECUTION ==================

if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("SMART Options Screener v2.0")
    logger.info("Features: Market Regime + Tiered Thresholds + IV Analysis + Trend Indicators")
    logger.info("=" * 80)
    logger.info("Instruments: %s", ", ".join(INDEX_SYMBOLS))
    logger.info("Stocks: %d symbols across 3 tiers", len(STOCK_SYMBOLS))
    logger.info("Logging to: %s", CSV_FILE)
    logger.info("=" * 80)
    logger.info("")
    
    # Run first scan immediately
    job()
    
    # Schedule recurring scans every 60 seconds
    schedule.every(60).seconds.do(job)
    
    logger.info("Scheduler started. Running scans every 60 seconds...")
    logger.info("Press Ctrl+C to stop")
    logger.info("")
    
    while True:
        schedule.run_pending()
        time.sleep(1)