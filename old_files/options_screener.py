# ...existing code...
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
CSV_FILE = "options_scan_log.csv"
# New logging imports
import logging
from logging.handlers import RotatingFileHandler

# Strategy Parameters
VOLUME_THRESHOLD_INDEX = 5000
VOLUME_THRESHOLD_STOCK = 1000
OI_CHANGE_THRESHOLD_INDEX = 1000
OI_CHANGE_THRESHOLD_STOCK = 200
MAX_SPREAD_PCT = 0.05
MAX_PREMIUM_RATIO = 0.05
STRADDLE_MAX_COST_PCT = 0.03

# Market Hours
MARKET_START = dtime(9, 15)
MARKET_END = dtime(15, 30)
IST = pytz.timezone("Asia/Kolkata")

CSV_FILE = "options_scan_log.csv"
# ...existing code...
# Instruments
INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY"]
STOCK_SYMBOLS = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "KOTAKBANK",
    "HINDUNILVR", "SBIN", "BAJFINANCE", "BHARTIARTL", "ITC", "AXISBANK",
    "ASIANPAINT", "MARUTI", "LT", "SUNPHARMA", "WIPRO", "ULTRACEMCO",
    "HCLTECH", "TECHM"
]

SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "INDIAVIX": "^VIX"
}
for stock in STOCK_SYMBOLS:
    SYMBOL_MAP[stock] = f"{stock}.NS"

# ================== CONFIGURATION ==================
TELEGRAM_BOT_TOKEN = "8554491299:AAEYVxPF-THCg5f37JsDBHGUI3kTON2idPM"  # ← REPLACE THIS
TELEGRAM_CHAT_ID = "@manish_private_bot"              # ← REPLACE THIS
# ...existing code...

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

# ...existing code...
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Initialize CSV
headers = [
    "Timestamp", "Symbol", "Type", "Strategy", "Strike", "Premium",
    "Spot", "Volume", "OI_Change", "IV", "IV_Percentile", "IV_Rank",
    "Market_Regime", "VIX"
]
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        csv.writer(f).writerow(headers)

def log_to_csv(alert):
    try:
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
                alert.get('vix', 0)
            ])
        logger.debug("Logged alert to CSV: %s | %s | %s", alert.get('symbol'), alert.get('strategy'), alert.get('strike'))
    except Exception:
        logger.exception("Failed to write alert to CSV")

def get_india_vix():
    try:
        data = yf.Ticker("^VIX").history(period="1d")
        v = data['Close'][-1] if not data.empty else 16.0
        logger.debug("Fetched India VIX: %s", v)
        return v
    except Exception:
        logger.exception("Error fetching India VIX, returning fallback 16.0")
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

import pdb

import numpy as np

def get_iv_data(symbol):
    """
    Fetch historical IV data from Opstra's ivcharts API and compute:
    - Current IV (last ImpVol)
    - IV Percentile (over last 252 days)
    - IV Rank (over last 252 days)
    """
    symbol_upper = symbol.upper()
    url = f"https://opstra.definedge.com/api/ivcharts/{symbol_upper}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://opstra.definedge.com/",
        "Origin": "https://opstra.definedge.com"
    }

    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            print(f"[IV ERROR] {symbol}: HTTP {response.status_code}")
            return None

        data = response.json()
        ivchart = data.get("ivchart", [])
        
        if not ivchart:
            print(f"[IV ERROR] {symbol}: No IV data returned")
            return None

        # Extract ImpVol values (ignore nulls)
        iv_values = []
        for point in ivchart:
            iv = point.get("ImpVol")
            if iv is not None and iv > 0:
                iv_values.append(float(iv))

        if len(iv_values) < 30:
            print(f"[IV WARN] {symbol}: Insufficient IV history (<30 days)")
            return None

        # Use last 252 days (or all if less)
        window = iv_values[-252:]
        current_iv = window[-1]

        # Compute IV Percentile
        iv_percentile = int(np.percentile(window, np.sum(np.array(window) <= current_iv) / len(window) * 100))
        # Alternative (more accurate):
        iv_percentile = int((np.sum(np.array(window) <= current_iv) / len(window)) * 100)

        # Compute IV Rank: (current - min) / (max - min)
        iv_min = min(window)
        iv_max = max(window)
        if iv_max == iv_min:
            iv_rank = 50
        else:
            iv_rank = int(((current_iv - iv_min) / (iv_max - iv_min)) * 100)
            
        logger.debug("IV data for %s: IV=%.2f IV%%=%d IVR=%d", symbol, current_iv, iv_percentile, iv_rank)
        return {
            'iv': current_iv,
            'iv_percentile': iv_percentile,
            'iv_rank': iv_rank
        }

    except Exception as e:
        print(f"[IV EXCEPTION] {symbol}: {e}")
        return None


def get_iv_data_V1(symbol):
    pdb.set_trace()
    url_map = {
        "NIFTY": "https://opstra.definedge.com/api/ivcharts/NIFTY",
        "BANKNIFTY": "https://opstra.definedge.com/api/ivcharts/BANKNIFTY"
    }
    if symbol in STOCK_SYMBOLS:
        return None
    url = url_map.get(symbol.upper())
    if not url:
        logger.debug("No IV URL for symbol: %s", symbol)
        return None
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            iv = {
                'iv': float(data.get('iv', 0)),
                'iv_percentile': int(data.get('ivp', 0)),
                'iv_rank': int(data.get('ivr', 0))
            }
            logger.debug("IV data for %s: %s", symbol, iv)
            return iv
        else:
            logger.warning("IV request for %s returned status %s", symbol, response.status_code)
    except Exception:
        logger.exception("Exception while fetching IV data for %s", symbol)
    return None

# ...existing code...
def get_underlying_price(symbol):
    """
    Get near-real-time price for indices; daily close for stocks.
    Indices: uses 5-min data for freshness.
    Stocks: uses daily close (intraday often unavailable on yfinance).
    """
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        
        if symbol in ["NIFTY", "BANKNIFTY"]:
            # Use 5-minute data for indices (more responsive)
            data = yf.Ticker(ticker).history(period="1d", interval="5m")
            if not data.empty:
                price = data['Close'].iloc[-1]
                logger.debug("Index price for %s from 5m: %s", symbol, price)
                return price
        else:
            # For stocks: use daily close (intraday often not available)
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                price = data['Close'].iloc[-1]
                logger.debug("Stock price for %s from daily: %s", symbol, price)
                return price
                
    except Exception:
        logger.exception("Error getting underlying price for %s", symbol)
    
    logger.debug("Underlying price unavailable for %s", symbol)
    return None

# ...existing code...
def is_market_hours():
    now = datetime.now(IST).time()
    return MARKET_START <= now <= MARKET_END

# ...existing code...
def scan_index(symbol, iv_threshold, market_regime, vix):
    alerts = []
    try:
        logger.info("Scanning index: %s | Regime: %s", symbol, market_regime)
        oc = nse_optionchain_scrapper(symbol)
        records = oc['records']['data']
        spot_nse = oc['records']['underlyingValue']
        spot = get_underlying_price(symbol) or spot_nse

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

        # ...existing logic...
        logger.debug("Index %s: spot=%s atm=%s step=%s", symbol, spot, atm, step)
        # (rest of function unchanged aside from exception logging)
        # ...existing code...

    except Exception:
        logger.exception("Error scanning index %s", symbol)
    return alerts

def scan_stock(symbol, market_regime, vix):
    alerts = []
    try:
        logger.info("Scanning stock: %s | Regime: %s", symbol, market_regime)
        oc = nse_optionchain_scrapper(symbol)
        records = oc['records']['data']
        spot_nse = oc['records']['underlyingValue']
        spot = get_underlying_price(symbol) or spot_nse
        if spot < 100:
            logger.debug("Skipping %s due to low spot price: %s", symbol, spot)
            return []

        # ...existing logic...
        logger.debug("Stock %s: spot=%s", symbol, spot)
        # (rest of function unchanged aside from exception logging)
        # ...existing code...

    except Exception:
        logger.exception("Error scanning stock %s", symbol)
    return alerts

async def send_telegram_alert(alert):
    strategy = alert['strategy']
    symbol = alert['symbol']
    strike = alert['strike']
    premium = alert['premium']
    spot = alert['spot']
    ivp = alert.get('iv_percentile', 0)
    regime = alert['market_regime']
    
    msg = (
        f"🎯 *{strategy}*\n"
        f"📌 {symbol} @ ₹{spot:.0f}\n"
        f"Strike: {strike}\n"
        f"Cost: ₹{premium:.2f}\n"
        f"Regime: {regime}"
    )
    if ivp > 0:
        msg += f"\nIV%: {ivp}%"
    msg += f"\n🕒 {alert['timestamp']}"
    try:
        logger.debug("Sending Telegram alert: %s | %s | %s", symbol, strategy, strike)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')
        logger.info("Telegram alert sent: %s | %s | %s", symbol, strategy, strike)
    except Exception:
        logger.exception("Failed to send Telegram message for %s %s", symbol, strike)

def job():
    # if not is_market_hours():
    #     logger.info("Outside market hours.")
    #     return

    logger.info("Starting smart scan...")

    vix = get_india_vix()
    regime = determine_market_regime(vix)
    iv_threshold = get_iv_threshold(regime)
    logger.info("Market Regime: %s | India VIX: %.1f | IV%% Threshold: ≤%s", regime, vix, iv_threshold)

    all_alerts = []
    for sym in INDEX_SYMBOLS:
        alerts = scan_index(sym, iv_threshold, regime, vix)
        all_alerts.extend(alerts)
    for sym in STOCK_SYMBOLS:
        alerts = scan_stock(sym, regime, vix)
        all_alerts.extend(alerts)

    seen = set()
    unique_alerts = []
    for a in all_alerts:
        key = (a['strategy'], a['symbol'], a['strike'], a['timestamp'][:16])
        if key not in seen:
            seen.add(key)
            unique_alerts.append(a)

    if unique_alerts:
        for alert in unique_alerts:
            logger.info("Signal: %s | %s | %s", alert['instrument_type'], alert['strategy'], alert['symbol'])
            log_to_csv(alert)
            try:
                asyncio.run(send_telegram_alert(alert))
            except Exception:
                logger.exception("Error running async Telegram send for alert %s", alert)
    else:
        logger.info("No signals in current regime.")

if __name__ == "__main__":
    logger.info("SMART Options Screener starting. Log file: %s | CSV: %s", LOG_FILE, CSV_FILE)

    job()
    schedule.every(60).seconds.do(job)

    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping screener (KeyboardInterrupt).")
            break
        except Exception:
            logger.exception("Unexpected error in scheduler loop")