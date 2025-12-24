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
TELEGRAM_BOT_TOKEN = "8554491299:AAEYVxPF-THCg5f37JsDBHGUI3kTON2idPM"
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

# VERY RELAXED thresholds to ensure results
VOLUME_THRESHOLDS = {'TIER_1': 50, 'TIER_2': 20, 'TIER_3': 10}
OI_CHANGE_THRESHOLDS = {'TIER_1': 0, 'TIER_2': 0, 'TIER_3': 0}  # Accept any OI change

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
CSV_FILE = "options_scan_log.csv"

# GLOBAL: Store your session cookies here after logging in via browser
OPSTRA_COOKIES = {
    'JSESSIONID': '68C2B25E68942C37028E38FE43E12941',
    'DSESSIONID': '54BD4DA6614952A5841DF155A18F2C97',
    '_ga': 'GA1.1.703791765.1764073625',
    '_ga_6D0ZQ437SD': 'GS2.1.s1764145134$o4$g1$t1764145153$j41$l0$h0'
}
# Initialize CSV
headers = ["Timestamp", "Symbol", "Type", "Strategy", "Strike", "Premium", "PriceSource",
           "Spot", "Volume", "OI", "OI_Change", "IV_Percentile", "Market_Regime", "RSI", "Tier", "Moneyness"]
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        csv.writer(f).writerow(headers)

def log_to_csv(alert):
    with open(CSV_FILE, mode='a', newline='') as f:
        csv.writer(f).writerow([
            alert.get('timestamp', ''), alert.get('symbol', ''), alert.get('instrument_type', ''),
            alert.get('strategy', ''), alert.get('strike', ''), round(alert.get('premium', 0), 2),
            alert.get('price_source', 'ask'), round(alert.get('spot', 0), 2), alert.get('volume', 0),
            alert.get('open_interest', 0), alert.get('oi_change', 0), alert.get('iv_percentile', 0),
            alert.get('market_regime', ''), alert.get('rsi', 0), alert.get('tier', ''), alert.get('moneyness', '')
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
    pct_diff = (strike - spot) / spot * 100
    if opt_type == "CE":
        if pct_diff < -2: return "ITM"
        elif pct_diff > 2: return "OTM"
        else: return "ATM"
    else:
        if pct_diff > 2: return "ITM"
        elif pct_diff < -2: return "OTM"
        else: return "ATM"

def get_option_price(opt):
    """Get best available price with fallback logic"""
    # Try different possible field names
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
    # After hours fallback: assume 10% spread
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

def get_iv_data(symbol):
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
    """Stock scanning with LTP fallback and verbose logging"""
    alerts = []
    
    try:
        tier = get_stock_tier(symbol)
        vol_thresh = VOLUME_THRESHOLDS[tier]
        oi_thresh = OI_CHANGE_THRESHOLDS[tier]
        
        # Get spot price
        spot = get_underlying_price(symbol)
        if not spot:
            return []
        
        logger.info("Stock %s: Spot: %.2f", symbol, spot)
        
        if spot < MIN_STOCK_PRICE:
            logger.info("Stock %s: Spot below minimum price: %.2f", symbol, spot)
            return []
        
        # Get trend data
        trend_data = compute_trend_indicators(symbol)
        iv_data = get_iv_data(symbol)
        
        logger.info("Stock %s: Trend data: %s, IV data: %s", symbol, trend_data, iv_data)
        
        # Fetch option chain
        try:
            oc = nse_optionchain_scrapper(symbol)
        except Exception as e:
            logger.debug("Option chain error for %s: %s", symbol, e)
            return []
        
        if not oc or 'records' not in oc:
            logger.debug("Stock %s: No option chain data", symbol)
            return []
        
        records = oc['records'].get('data', [])
        if not records:
            logger.debug("Stock %s: Empty records", symbol)
            return []
        
        # Parse strikes
        calls, puts = {}, {}
        strikes = set()
        for rec in records:
            strike = rec.get('strikePrice')
            if strike:
                strikes.add(strike)
                if 'CE' in rec: calls[strike] = rec['CE']
                if 'PE' in rec: puts[strike] = rec['PE']
        
        strikes = sorted(strikes)
        if not strikes:
            return []
        
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else 50
        max_distance = step * STRIKE_RANGE_MULTIPLIER
        strikes_in_range = [s for s in strikes if abs(s - atm) <= max_distance]
        
        logger.info("Stock %s: ATM=%s, %d strikes in range, %d calls, %d puts",
                   symbol, atm, len(strikes_in_range), len(calls), len(puts))
        
        base_alert = {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'instrument_type': 'STOCK',
            'spot': spot,
            'iv_percentile': iv_data['iv_percentile'],
            'market_regime': market_regime,
            'vix': vix,
            'rsi': trend_data['rsi'],
            'tier': tier
        }
        
        directional_bias = trend_data['bias']
        rsi = trend_data['rsi']
        
        scan_calls = directional_bias in ["BULLISH", "NEUTRAL"] or rsi < RSI_OVERSOLD
        scan_puts = directional_bias in ["BEARISH", "NEUTRAL"] or rsi > RSI_OVERBOUGHT
        
        options_analyzed = 0
        options_passed = 0
        
        # SCAN CALLS
        if scan_calls:
            for strike in strikes_in_range:
                if strike not in calls:
                    continue
                
                opt = calls[strike]
                options_analyzed += 1
                
                price, price_source = get_option_price(opt)
                if price <= 0:
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                
                # Very relaxed filters
                # Accept if: has volume OR has OI OR OI is substantial
                if vol < vol_thresh and abs(oi_chg) < oi_thresh and oi < 1000:
                    continue
                
                spread_pct = get_option_spread(opt, price)
                if spread_pct > MAX_SPREAD_PCT_STOCK:
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO_STOCK:
                    continue
                
                options_passed += 1
                moneyness = get_moneyness(strike, spot, "CE")
                
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
                    'moneyness': moneyness
                })
                alerts.append(alert)
        
        # SCAN PUTS
        if scan_puts:
            for strike in strikes_in_range:
                if strike not in puts:
                    continue
                
                opt = puts[strike]
                options_analyzed += 1
                
                price, price_source = get_option_price(opt)
                if price <= 0:
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                
                if vol < vol_thresh and abs(oi_chg) < oi_thresh and oi < 1000:
                    continue
                
                spread_pct = get_option_spread(opt, price)
                if spread_pct > MAX_SPREAD_PCT_STOCK:
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO_STOCK:
                    continue
                
                options_passed += 1
                moneyness = get_moneyness(strike, spot, "PE")
                
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
                    'moneyness': moneyness
                })
                alerts.append(alert)
        
        if alerts:
            logger.info("Stock %s: %d/%d options passed filters, %d alerts",
                       symbol, options_passed, options_analyzed, len(alerts))
    
    except Exception as e:
        logger.debug("Stock %s scan error: %s", symbol, e)
    
    return alerts

def scan_index(symbol, iv_threshold, market_regime, vix):
    """Index scanning with same fixes"""
    alerts = []
    
    try:
        spot = get_underlying_price(symbol)
        if not spot:
            return []
        
        logger.info("Index %s: Spot: %.2f", symbol, spot)
        
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
        
        calls, puts = {}, {}
        strikes = set()
        for rec in records:
            strike = rec.get('strikePrice')
            if strike:
                strikes.add(strike)
                if 'CE' in rec: calls[strike] = rec['CE']
                if 'PE' in rec: puts[strike] = rec['PE']
        
        strikes = sorted(strikes)
        if not strikes:
            return []
        
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else (100 if symbol == "BANKNIFTY" else 50)
        max_distance = step * STRIKE_RANGE_MULTIPLIER
        strikes_in_range = [s for s in strikes if abs(s - atm) <= max_distance]
        
        logger.info("Index %s: ATM=%s, %d strikes in range", symbol, atm, len(strikes_in_range))
        
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
            'tier': 'INDEX'
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
                    
                    if vol >= VOLUME_THRESHOLD_INDEX or oi >= 10000:
                        spread_pct = get_option_spread(opt, price)
                        if spread_pct <= MAX_SPREAD_PCT and price / spot <= MAX_PREMIUM_RATIO:
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
                                'moneyness': get_moneyness(strike, spot, "CE")
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
                    
                    if vol >= VOLUME_THRESHOLD_INDEX or oi >= 10000:
                        spread_pct = get_option_spread(opt, price)
                        if spread_pct <= MAX_SPREAD_PCT and price / spot <= MAX_PREMIUM_RATIO:
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
                                'moneyness': get_moneyness(strike, spot, "PE")
                            })
                            alerts.append(alert)
        
        logger.info("Index %s: %d alerts generated", symbol, len(alerts))
    
    except Exception as e:
        logger.exception("Index %s scan error: %s", symbol, e)
    
    return alerts

# ================== MAIN JOB ==================

def job():
    logger.info("=" * 60)
    logger.info("Starting scan at %s", datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'))
    
    market_open = is_market_hours()
    logger.info("Market hours: %s", "YES" if market_open else "NO (using LTP fallback)")
    
    vix = get_india_vix()
    regime = determine_market_regime(vix)
    iv_threshold = 60
    
    logger.info("VIX=%.1f | Regime=%s", vix, regime)
    logger.info("=" * 60)
    
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
    
    logger.info("=" * 60)
    logger.info("SCAN COMPLETE: %d unique alerts", len(unique_alerts))
    logger.info("=" * 60)
    
    if unique_alerts:
        logger.info("\nTop 15 by Volume:")
        for i, alert in enumerate(unique_alerts[:15]):
            logger.info("  %2d. %s %s %s @ %s | ₹%.2f (%s) | Vol=%d OI=%d",
                       i+1, alert['symbol'], alert['strategy'], alert.get('moneyness', ''),
                       alert['strike'], alert['premium'], alert.get('price_source', ''),
                       alert['volume'], alert.get('open_interest', 0))
        
        for alert in unique_alerts:
            log_to_csv(alert)
    else:
        logger.info("\nNo alerts generated. Check:")
        logger.info("  1. Is market open? After 3:30 PM, only LTP-based data available")
        logger.info("  2. Run diagnostic_screener.py for detailed analysis")

if __name__ == "__main__":
    logger.info("Smart Options Screener v3.1 (Fixed)")
    logger.info("Stocks: %d | Indices: %d", len(STOCK_SYMBOLS), len(INDEX_SYMBOLS))
    
    job()
    
    schedule.every(60).seconds.do(job)
    logger.info("\nScheduler started. Press Ctrl+C to stop.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)
