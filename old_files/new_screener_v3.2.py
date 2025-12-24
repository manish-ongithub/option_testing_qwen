import time
import pytz
from datetime import datetime, time as dtime
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import csv
import os
from nsepython import nse_optionchain_scrapper
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

# ================== LOT SIZES (Updated Nov 2024) ==================
# Source: NSE F&O lot sizes - update periodically from NSE website
LOT_SIZES = {
    # Indices
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    
    # Large Cap Stocks
    "RELIANCE": 250,
    "TCS": 175,
    "HDFCBANK": 550,
    "ICICIBANK": 700,
    "INFY": 400,
    "HINDUNILVR": 300,
    "ITC": 1600,
    "SBIN": 750,
    "BHARTIARTL": 475,
    "KOTAKBANK": 400,
    "LT": 150,
    "AXISBANK": 625,
    "BAJFINANCE": 125,
    "ASIANPAINT": 300,
    "MARUTI": 100,
    "TITAN": 375,
    "SUNPHARMA": 350,
    "TATAMOTORS": 1400,
    "NTPC": 2250,
    "POWERGRID": 2700,
    "M&M": 350,
    "ULTRACEMCO": 100,
    "HCLTECH": 350,
    "BAJAJFINSV": 500,
    "WIPRO": 1500,
    "NESTLEIND": 25,
    "TECHM": 600,
    "TATASTEEL": 1500,
    "JSWSTEEL": 675,
    "HINDALCO": 1075,
    "COALINDIA": 1900,
    "ONGC": 3850,
    "BPCL": 1800,
    "DRREDDY": 125,
    "BRITANNIA": 200,
    "CIPLA": 650,
    "DIVISLAB": 100,
    "EICHERMOT": 175,
    "HEROMOTOCO": 150,
    "APOLLOHOSP": 125,
    "ADANIPORTS": 1250,
    "ADANIENT": 250,
    "HDFCLIFE": 1100,
    "SBILIFE": 750,
    "BAJAJ-AUTO": 125,
    "INDUSINDBK": 500,
    "TATACONSUM": 700,
    "TATAPOWER": 2700,
    "DABUR": 1250,
    "PIDILITE": 250,
    "DMART": 125,
    "TRENT": 300,
    "SBICARD": 800,
    "HDFCAMC": 200,
    "BANKBARODA": 2925,
    "PNB": 4000,
    "CANBK": 6750,
    "FEDERALBNK": 5000,
    "CHOLAFIN": 625,
    "MUTHOOTFIN": 375,
    "PERSISTENT": 200,
    "COFORGE": 125,
    "MPHASIS": 275,
    "LTIM": 150,
    "AUROPHARMA": 425,
    "LUPIN": 425,
    "JINDALSTEL": 625,
    "BEL": 3900,
    "HAL": 150,
}

# Default lot size for stocks not in the list
DEFAULT_LOT_SIZE = 500

# ================== TIERED THRESHOLDS ==================
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

# Relaxed thresholds
VOLUME_THRESHOLDS = {'TIER_1': 50, 'TIER_2': 20, 'TIER_3': 10}
OI_CHANGE_THRESHOLDS = {'TIER_1': 0, 'TIER_2': 0, 'TIER_3': 0}

VOLUME_THRESHOLD_INDEX = 500
OI_CHANGE_THRESHOLD_INDEX = 0

STRIKE_RANGE_MULTIPLIER = 5
MAX_SPREAD_PCT = 0.15
MAX_SPREAD_PCT_STOCK = 0.20
MAX_PREMIUM_RATIO = 0.15
MAX_PREMIUM_RATIO_STOCK = 0.15
MIN_STOCK_PRICE = 100

RSI_OVERSOLD = 45
RSI_OVERBOUGHT = 55
IV_VERY_HIGH = 95
IV_LOW = 40

MARKET_START = dtime(9, 15)
MARKET_END = dtime(15, 30)
IST = pytz.timezone("Asia/Kolkata")
CSV_FILE = "new_screener_options_scan_log_v3_2.csv"

# GLOBAL: Store your session cookies here after logging in via browser
OPSTRA_COOKIES = {
    'JSESSIONID': '92A42996789EC8AEBB75918C1AADBBFB',
    'DSESSIONID': '403A5E4049386C43126BA5F85F9E87E4',
    '_ga': 'GA1.1.703791765.1764073625',
    '_ga_6D0ZQ437SD': 'GS2.1.s1764145134$o4$g1$t1764145153$j41$l0$h0'
}


# Initialize CSV with new columns
headers = [
    "Timestamp", "Symbol", "Type", "Strategy", "Strike", "Premium", "PriceSource",
    "Spot", "Volume", "OI", "OI_Change", "IV_Percentile", "Market_Regime", "RSI", 
    "Tier", "Moneyness", "Expiry", "DaysToExpiry", "LotSize", "TotalCost", 
    "Breakeven", "DistanceFromSpot"
]
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        csv.writer(f).writerow(headers)

def log_to_csv(alert):
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
            alert.get('iv_percentile', 0),
            alert.get('market_regime', ''),
            round(alert.get('rsi', 0), 1),
            alert.get('tier', ''),
            alert.get('moneyness', ''),
            alert.get('expiry', ''),
            alert.get('days_to_expiry', 0),
            alert.get('lot_size', 0),
            round(alert.get('total_cost', 0), 2),
            round(alert.get('breakeven', 0), 2),
            alert.get('distance_from_spot', '')
        ])

# ================== HELPER FUNCTIONS ==================

def get_lot_size(symbol):
    """Get lot size for a symbol"""
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
    """Calculate breakeven price for the option"""
    if opt_type == "CE":
        return strike + premium  # Call: breakeven = strike + premium
    else:
        return strike - premium  # Put: breakeven = strike - premium

def calculate_distance_from_spot(strike, spot, opt_type):
    """Calculate distance from spot as percentage with direction"""
    diff = strike - spot
    pct = abs(diff) / spot * 100
    
    if opt_type == "CE":
        if diff > 0:
            return f"+{pct:.1f}% OTM"
        elif diff < 0:
            return f"-{pct:.1f}% ITM"
        else:
            return "ATM"
    else:  # PE
        if diff < 0:
            return f"-{pct:.1f}% OTM"
        elif diff > 0:
            return f"+{pct:.1f}% ITM"
        else:
            return "ATM"

def parse_expiry_date(expiry_str):
    """Parse expiry date string to datetime object"""
    try:
        # NSE format is typically "28-Nov-2024" or "2024-11-28"
        for fmt in ["%d-%b-%Y", "%Y-%m-%d", "%d-%B-%Y", "%d/%m/%Y"]:
            try:
                return datetime.strptime(expiry_str, fmt)
            except ValueError:
                continue
        return None
    except:
        return None

def calculate_days_to_expiry(expiry_str):
    """Calculate days remaining to expiry"""
    expiry_date = parse_expiry_date(expiry_str)
    if expiry_date:
        today = datetime.now(IST).replace(tzinfo=None)
        expiry_date = expiry_date.replace(hour=15, minute=30)  # Expiry at 3:30 PM
        delta = expiry_date - today
        return max(0, delta.days)
    return -1  # Unknown

def get_option_price(opt):
    """Get best available price with fallback logic"""
    ask = opt.get('askprice') or opt.get('askPrice') or opt.get('ask') or 0
    bid = opt.get('bidprice') or opt.get('bidPrice') or opt.get('bid') or 0
    ltp = opt.get('lastPrice') or opt.get('ltp') or opt.get('last') or 0
    
    if ask and ask > 0:
        return float(ask), 'ask'
    elif ltp and ltp > 0:
        return float(ltp), 'ltp'
    elif bid and bid > 0:
        return float(bid), 'bid'
    return 0, 'none'

def get_option_spread(opt, price):
    """Calculate spread percentage"""
    ask = opt.get('askprice') or opt.get('askPrice') or 0
    bid = opt.get('bidprice') or opt.get('bidPrice') or 0
    
    if ask > 0 and bid > 0:
        return (ask - bid) / ask
    return 0.10  # Default 10% spread assumption

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
        data = yf.Ticker(ticker).history(period="1d", interval="5m" if symbol in ["NIFTY", "BANKNIFTY"] else "1d")
        if not data.empty:
            return data['Close'].iloc[-1]
    except Exception as e:
        logger.debug("Price error for %s: %s", symbol, e)
    return None

def compute_trend_indicators(symbol):
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        hist = yf.Ticker(ticker).history(period="1mo", interval="1d")
        if len(hist) < 14:
            return {'bias': 'NEUTRAL', 'rsi': 50, 'adx': 0}
        
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
        
        return {'bias': bias, 'rsi': current_rsi, 'adx': 0}
    except:
        return {'bias': 'NEUTRAL', 'rsi': 50, 'adx': 0}

def is_market_hours():
    now = datetime.now(IST).time()
    return MARKET_START <= now <= MARKET_END

# ================== SCANNING FUNCTIONS ==================

def scan_stock(symbol, market_regime, vix):
    """Stock scanning with enhanced alert data"""
    alerts = []
    
    try:
        tier = get_stock_tier(symbol)
        vol_thresh = VOLUME_THRESHOLDS[tier]
        oi_thresh = OI_CHANGE_THRESHOLDS[tier]
        lot_size = get_lot_size(symbol)
        
        spot = get_underlying_price(symbol)
        if not spot:
            return []
        
        logger.info("Stock %s: Spot: %.2f | Lot: %d", symbol, spot, lot_size)
        
        if spot < MIN_STOCK_PRICE:
            logger.info("Stock %s: Spot below minimum price: %.2f", symbol, spot)
            return []
        
        trend_data = compute_trend_indicators(symbol)
        iv_data = get_iv_data(symbol)
        
        logger.info("Stock %s: Trend: %s, RSI: %.1f", symbol, trend_data['bias'], trend_data['rsi'])
        
        try:
            oc = nse_optionchain_scrapper(symbol)
        except Exception as e:
            logger.debug("Option chain error for %s: %s", symbol, e)
            return []
        
        if not oc or 'records' not in oc:
            return []
        
        records = oc['records'].get('data', [])
        if not records:
            return []
        
        # Get expiry dates from option chain
        expiry_dates = oc['records'].get('expiryDates', [])
        nearest_expiry = expiry_dates[0] if expiry_dates else "Unknown"
        days_to_expiry = calculate_days_to_expiry(nearest_expiry)
        
        # Parse strikes
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
            'iv_percentile': iv_data['iv_percentile'],
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
        
        # SCAN CALLS
        if scan_calls:
            for strike in strikes_in_range:
                if strike not in calls:
                    continue
                
                opt = calls[strike]
                
                price, price_source = get_option_price(opt)
                if price <= 0:
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                expiry = opt.get('expiryDate', nearest_expiry)
                
                if vol < vol_thresh and abs(oi_chg) < oi_thresh and oi < 1000:
                    continue
                
                spread_pct = get_option_spread(opt, price)
                if spread_pct > MAX_SPREAD_PCT_STOCK:
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO_STOCK:
                    continue
                
                # Calculate enhanced fields
                moneyness = get_moneyness(strike, spot, "CE")
                breakeven = calculate_breakeven(strike, price, "CE")
                distance = calculate_distance_from_spot(strike, spot, "CE")
                total_cost = price * lot_size
                dte = calculate_days_to_expiry(expiry)
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Call',
                    'strike': strike,
                    'type': 'CE',
                    'premium': price,
                    'price_source': price_source,
                    'volume': vol,
                    'open_interest': oi,
                    'oi_change': oi_chg,
                    'moneyness': moneyness,
                    'expiry': expiry,
                    'days_to_expiry': dte,
                    'total_cost': total_cost,
                    'breakeven': breakeven,
                    'distance_from_spot': distance
                })
                alerts.append(alert)
        
        # SCAN PUTS
        if scan_puts:
            for strike in strikes_in_range:
                if strike not in puts:
                    continue
                
                opt = puts[strike]
                
                price, price_source = get_option_price(opt)
                if price <= 0:
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                expiry = opt.get('expiryDate', nearest_expiry)
                
                if vol < vol_thresh and abs(oi_chg) < oi_thresh and oi < 1000:
                    continue
                
                spread_pct = get_option_spread(opt, price)
                if spread_pct > MAX_SPREAD_PCT_STOCK:
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO_STOCK:
                    continue
                
                # Calculate enhanced fields
                moneyness = get_moneyness(strike, spot, "PE")
                breakeven = calculate_breakeven(strike, price, "PE")
                distance = calculate_distance_from_spot(strike, spot, "PE")
                total_cost = price * lot_size
                dte = calculate_days_to_expiry(expiry)
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Put',
                    'strike': strike,
                    'type': 'PE',
                    'premium': price,
                    'price_source': price_source,
                    'volume': vol,
                    'open_interest': oi,
                    'oi_change': oi_chg,
                    'moneyness': moneyness,
                    'expiry': expiry,
                    'days_to_expiry': dte,
                    'total_cost': total_cost,
                    'breakeven': breakeven,
                    'distance_from_spot': distance
                })
                alerts.append(alert)
        
        if alerts:
            logger.info("Stock %s: %d alerts generated", symbol, len(alerts))
    
    except Exception as e:
        logger.debug("Stock %s scan error: %s", symbol, e)
    
    return alerts

def scan_index(symbol, iv_threshold, market_regime, vix):
    """Index scanning with enhanced alert data"""
    alerts = []
    
    try:
        lot_size = get_lot_size(symbol)
        
        spot = get_underlying_price(symbol)
        if not spot:
            return []
        
        logger.info("Index %s: Spot: %.2f | Lot: %d", symbol, spot, lot_size)
        
        try:
            oc = nse_optionchain_scrapper(symbol)
        except Exception as e:
            logger.warning("Index %s option chain error: %s", symbol, e)
            return []
        
        if not oc or 'records' not in oc:
            return []
        
        records = oc['records'].get('data', [])
        if not records:
            return []
        
        # Get expiry dates
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
        
        logger.info("Index %s: ATM=%s, %d strikes in range, Expiry=%s", 
                   symbol, atm, len(strikes_in_range), nearest_expiry)
        
        iv_data = get_iv_data(symbol)
        
        base_alert = {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'instrument_type': 'INDEX',
            'spot': spot,
            'iv_percentile': iv_data['iv_percentile'],
            'market_regime': market_regime,
            'vix': vix,
            'rsi': 0,
            'tier': 'INDEX',
            'lot_size': lot_size
        }
        
        # Scan both calls and puts for indices
        for strike in strikes_in_range:
            # CALLS
            if strike in calls:
                opt = calls[strike]
                price, price_source = get_option_price(opt)
                
                if price > 0:
                    vol = opt.get('totalTradedVolume') or 0
                    oi = opt.get('openInterest') or 0
                    oi_chg = opt.get('changeinOpenInterest') or 0
                    expiry = opt.get('expiryDate', nearest_expiry)
                    
                    if vol >= VOLUME_THRESHOLD_INDEX or oi >= 10000:
                        spread_pct = get_option_spread(opt, price)
                        if spread_pct <= MAX_SPREAD_PCT and price / spot <= MAX_PREMIUM_RATIO:
                            moneyness = get_moneyness(strike, spot, "CE")
                            breakeven = calculate_breakeven(strike, price, "CE")
                            distance = calculate_distance_from_spot(strike, spot, "CE")
                            total_cost = price * lot_size
                            dte = calculate_days_to_expiry(expiry)
                            
                            alert = base_alert.copy()
                            alert.update({
                                'strategy': 'Long Call',
                                'strike': strike,
                                'type': 'CE',
                                'premium': price,
                                'price_source': price_source,
                                'volume': vol,
                                'open_interest': oi,
                                'oi_change': oi_chg,
                                'moneyness': moneyness,
                                'expiry': expiry,
                                'days_to_expiry': dte,
                                'total_cost': total_cost,
                                'breakeven': breakeven,
                                'distance_from_spot': distance
                            })
                            alerts.append(alert)
            
            # PUTS
            if strike in puts:
                opt = puts[strike]
                price, price_source = get_option_price(opt)
                
                if price > 0:
                    vol = opt.get('totalTradedVolume') or 0
                    oi = opt.get('openInterest') or 0
                    oi_chg = opt.get('changeinOpenInterest') or 0
                    expiry = opt.get('expiryDate', nearest_expiry)
                    
                    if vol >= VOLUME_THRESHOLD_INDEX or oi >= 10000:
                        spread_pct = get_option_spread(opt, price)
                        if spread_pct <= MAX_SPREAD_PCT and price / spot <= MAX_PREMIUM_RATIO:
                            moneyness = get_moneyness(strike, spot, "PE")
                            breakeven = calculate_breakeven(strike, price, "PE")
                            distance = calculate_distance_from_spot(strike, spot, "PE")
                            total_cost = price * lot_size
                            dte = calculate_days_to_expiry(expiry)
                            
                            alert = base_alert.copy()
                            alert.update({
                                'strategy': 'Long Put',
                                'strike': strike,
                                'type': 'PE',
                                'premium': price,
                                'price_source': price_source,
                                'volume': vol,
                                'open_interest': oi,
                                'oi_change': oi_chg,
                                'moneyness': moneyness,
                                'expiry': expiry,
                                'days_to_expiry': dte,
                                'total_cost': total_cost,
                                'breakeven': breakeven,
                                'distance_from_spot': distance
                            })
                            alerts.append(alert)
        
        logger.info("Index %s: %d alerts generated", symbol, len(alerts))
    
    except Exception as e:
        logger.exception("Index %s scan error: %s", symbol, e)
    
    return alerts

# ================== MAIN JOB ==================

def job():
    logger.info("=" * 80)
    logger.info("Starting scan at %s", datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'))
    
    market_open = is_market_hours()
    logger.info("Market hours: %s", "YES" if market_open else "NO (using LTP fallback)")
    
    vix = get_india_vix()
    regime = determine_market_regime(vix)
    iv_threshold = 60
    
    logger.info("VIX=%.1f | Regime=%s", vix, regime)
    logger.info("=" * 80)
    
    all_alerts = []
    
    # Scan indices
    logger.info("\n--- Scanning Indices ---")
    for sym in INDEX_SYMBOLS:
        alerts = scan_index(sym, iv_threshold, regime, vix)
        all_alerts.extend(alerts)
    
    # Scan stocks
    logger.info("\n--- Scanning Stocks (%d) ---", len(STOCK_SYMBOLS))
    for i, sym in enumerate(STOCK_SYMBOLS):
        if (i + 1) % 20 == 0:
            logger.info("Progress: %d/%d stocks...", i + 1, len(STOCK_SYMBOLS))
        alerts = scan_stock(sym, regime, vix)
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
    
    # Sort by volume (highest first)
    unique_alerts.sort(key=lambda x: x.get('volume', 0), reverse=True)
    
    logger.info("=" * 80)
    logger.info("SCAN COMPLETE: %d unique alerts", len(unique_alerts))
    logger.info("=" * 80)
    
    if unique_alerts:
        # Enhanced output format
        logger.info("\n" + "=" * 100)
        logger.info("TOP 15 ALERTS BY VOLUME")
        logger.info("=" * 100)
        logger.info("")
        logger.info("%-4s %-12s %-10s %-5s %-10s %-10s %-8s %-12s %-10s %-6s %-10s",
                   "#", "SYMBOL", "STRATEGY", "MON", "STRIKE", "PREMIUM", "VOLUME", 
                   "TOTAL COST", "BREAKEVEN", "DTE", "DISTANCE")
        logger.info("-" * 100)
        
        for i, alert in enumerate(unique_alerts[:15]):
            logger.info("%-4d %-12s %-10s %-5s %-10s ₹%-9.2f %-8d ₹%-11.0f %-10.2f %-6d %s",
                       i+1,
                       alert['symbol'],
                       alert['strategy'].replace('Long ', ''),
                       alert.get('moneyness', ''),
                       alert['strike'],
                       alert['premium'],
                       alert['volume'],
                       alert.get('total_cost', 0),
                       alert.get('breakeven', 0),
                       alert.get('days_to_expiry', -1),
                       alert.get('distance_from_spot', ''))
        
        logger.info("-" * 100)
        logger.info("")
        
        # Summary stats
        total_alerts = len(unique_alerts)
        calls = sum(1 for a in unique_alerts if 'Call' in a['strategy'])
        puts = sum(1 for a in unique_alerts if 'Put' in a['strategy'])
        atm = sum(1 for a in unique_alerts if a.get('moneyness') == 'ATM')
        otm = sum(1 for a in unique_alerts if a.get('moneyness') == 'OTM')
        itm = sum(1 for a in unique_alerts if a.get('moneyness') == 'ITM')
        
        logger.info("SUMMARY: %d Alerts | Calls: %d | Puts: %d | ATM: %d | OTM: %d | ITM: %d",
                   total_alerts, calls, puts, atm, otm, itm)
        logger.info("")
        
        # Log to CSV
        for alert in unique_alerts:
            log_to_csv(alert)
        
        logger.info("Results saved to: %s", CSV_FILE)
    else:
        logger.info("\nNo alerts generated.")

if __name__ == "__main__":
    logger.info("Smart Options Screener v3.2 (Enhanced)")
    logger.info("Features: Expiry, Lot Size, Total Cost, Breakeven, Distance from Spot")
    logger.info("Stocks: %d | Indices: %d", len(STOCK_SYMBOLS), len(INDEX_SYMBOLS))
    
    job()
    
    schedule.every(60).seconds.do(job)
    logger.info("\nScheduler started. Press Ctrl+C to stop.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)
