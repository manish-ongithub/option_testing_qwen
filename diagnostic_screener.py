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
import logging
from logging.handlers import RotatingFileHandler

# Setup logging
LOG_FILE = "screener_diagnostic.log"
logger = logging.getLogger("diagnostic_screener")
logger.setLevel(logging.DEBUG)  # Set to DEBUG for verbose output
formatter = logging.Formatter("%(asctime)s %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

# ================== CONFIGURATION ==================
INDEX_SYMBOLS = ["NIFTY", "BANKNIFTY"]

# Test with just a few liquid stocks first
TEST_STOCKS = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS",
    "SBIN", "TATAMOTORS", "BAJFINANCE", "AXISBANK", "LT"
]

SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}
for stock in TEST_STOCKS:
    SYMBOL_MAP[stock] = f"{stock}.NS"

# ================== VERY RELAXED THRESHOLDS FOR DIAGNOSIS ==================
VOLUME_THRESHOLD = 10        # Very low - almost any option should pass
OI_CHANGE_THRESHOLD = 0      # Accept any OI change (even 0)
MAX_SPREAD_PCT = 0.50        # 50% spread - very permissive
MAX_PREMIUM_RATIO = 0.20     # 20% of spot
STRIKE_RANGE_MULTIPLIER = 5  # 5 strikes each side
MIN_STOCK_PRICE = 100        # Low minimum

IST = pytz.timezone("Asia/Kolkata")
CSV_FILE = "diagnostic_scan_log.csv"

# Opstra cookies (optional)
OPSTRA_COOKIES = {
    'JSESSIONID': '',
    'DSESSIONID': '',
}

def get_iv_data(symbol):
    """Return default IV data for diagnosis"""
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
        
        delta = hist['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50
        
        ema20 = hist['Close'].ewm(span=20).mean().iloc[-1]
        current_price = hist['Close'].iloc[-1]
        
        if current_price > ema20 * 1.01:
            bias = "BULLISH"
        elif current_price < ema20 * 0.99:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
        
        return {'bias': bias, 'rsi': current_rsi, 'adx': 0}
    except Exception as e:
        return {'bias': 'NEUTRAL', 'rsi': 50, 'adx': 0}

def find_atm_strike(strikes, spot):
    return min(strikes, key=lambda x: abs(x - spot))

def diagnose_stock(symbol):
    """Diagnostic scan for a single stock with verbose logging"""
    logger.info("=" * 70)
    logger.info("DIAGNOSING: %s", symbol)
    logger.info("=" * 70)
    
    alerts = []
    filter_stats = {
        'total_options': 0,
        'passed_all': 0,
        'failed_ask_zero': 0,
        'failed_volume_oi': 0,
        'failed_spread': 0,
        'failed_premium_ratio': 0,
        'failed_out_of_range': 0
    }
    
    try:
        # Step 1: Fetch spot price
        spot = get_underlying_price(symbol)
        if not spot:
            logger.error("  ❌ FAILED: Could not fetch spot price")
            return [], filter_stats
        logger.info("  ✓ Spot price: ₹%.2f", spot)
        
        if spot < MIN_STOCK_PRICE:
            logger.info("  ⚠️ SKIPPED: Spot ₹%.2f below minimum ₹%d", spot, MIN_STOCK_PRICE)
            return [], filter_stats
        
        # Step 2: Fetch option chain
        logger.info("  Fetching option chain from NSE...")
        try:
            oc = nse_optionchain_scrapper(symbol)
        except Exception as e:
            logger.error("  ❌ FAILED: Option chain fetch error: %s", e)
            return [], filter_stats
        
        if not oc:
            logger.error("  ❌ FAILED: Option chain returned None")
            return [], filter_stats
        
        if 'records' not in oc:
            logger.error("  ❌ FAILED: No 'records' in option chain. Keys: %s", list(oc.keys()))
            return [], filter_stats
        
        records = oc['records'].get('data', [])
        if not records:
            logger.error("  ❌ FAILED: No data in records")
            return [], filter_stats
        
        logger.info("  ✓ Option chain fetched: %d records", len(records))
        
        # Step 3: Parse strikes
        calls, puts = {}, {}
        strikes = set()
        
        for rec in records:
            strike = rec.get('strikePrice')
            if strike:
                strikes.add(strike)
                if 'CE' in rec:
                    calls[strike] = rec['CE']
                if 'PE' in rec:
                    puts[strike] = rec['PE']
        
        strikes = sorted(strikes)
        logger.info("  ✓ Found %d unique strikes", len(strikes))
        logger.info("  ✓ Calls: %d, Puts: %d", len(calls), len(puts))
        
        if not strikes:
            logger.error("  ❌ FAILED: No strikes found")
            return [], filter_stats
        
        # Step 4: Find ATM and range
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else 50
        max_distance = step * STRIKE_RANGE_MULTIPLIER
        
        logger.info("  ATM Strike: %s | Step: %s | Range: ±%s", atm, step, max_distance)
        
        # Get strikes in range
        strikes_in_range = [s for s in strikes if abs(s - atm) <= max_distance]
        logger.info("  Strikes in range: %s", strikes_in_range)
        
        # Step 5: Analyze each option
        logger.info("")
        logger.info("  ANALYZING CALLS:")
        logger.info("  " + "-" * 60)
        
        for strike in strikes_in_range:
            if strike not in calls:
                continue
            
            opt = calls[strike]
            filter_stats['total_options'] += 1
            
            bid = opt.get('bidprice', 0) or opt.get('bidPrice', 0) or 0
            ask = opt.get('askprice', 0) or opt.get('askPrice', 0) or 0
            ltp = opt.get('lastPrice', 0) or 0
            vol = opt.get('totalTradedVolume', 0) or 0
            oi = opt.get('openInterest', 0) or 0
            prev_oi = opt.get('pchangeinOpenInterest', 0) or 0  # Check different key names
            oi_chg = opt.get('changeinOpenInterest', 0) or 0
            
            # If oi_chg is not directly available, try to compute
            if oi_chg == 0 and 'pchangeinOpenInterest' in opt:
                oi_chg = int(oi * opt.get('pchangeinOpenInterest', 0) / 100) if opt.get('pchangeinOpenInterest') else 0
            
            logger.info("  Strike %s CE: Bid=%.2f Ask=%.2f LTP=%.2f Vol=%d OI=%d OI_Chg=%d",
                       strike, bid, ask, ltp, vol, oi, oi_chg)
            
            # Check each filter
            if ask <= 0:
                if ltp > 0:
                    ask = ltp  # Use LTP as fallback
                    logger.info("    → Using LTP as ask price: %.2f", ask)
                else:
                    logger.info("    ❌ FILTERED: ask=0 and ltp=0")
                    filter_stats['failed_ask_zero'] += 1
                    continue
            
            if vol < VOLUME_THRESHOLD and abs(oi_chg) < OI_CHANGE_THRESHOLD:
                logger.info("    ❌ FILTERED: Vol=%d < %d AND |OI_Chg|=%d < %d",
                           vol, VOLUME_THRESHOLD, abs(oi_chg), OI_CHANGE_THRESHOLD)
                filter_stats['failed_volume_oi'] += 1
                continue
            
            spread_pct = (ask - bid) / ask if ask > 0 else 1
            if spread_pct > MAX_SPREAD_PCT:
                logger.info("    ❌ FILTERED: Spread %.1f%% > %.1f%%",
                           spread_pct * 100, MAX_SPREAD_PCT * 100)
                filter_stats['failed_spread'] += 1
                continue
            
            premium_ratio = ask / spot
            if premium_ratio > MAX_PREMIUM_RATIO:
                logger.info("    ❌ FILTERED: Premium ratio %.1f%% > %.1f%%",
                           premium_ratio * 100, MAX_PREMIUM_RATIO * 100)
                filter_stats['failed_premium_ratio'] += 1
                continue
            
            # PASSED ALL FILTERS!
            logger.info("    ✓ PASSED! Creating alert...")
            filter_stats['passed_all'] += 1
            
            alerts.append({
                'symbol': symbol,
                'type': 'CE',
                'strike': strike,
                'premium': ask,
                'volume': vol,
                'oi_change': oi_chg,
                'spot': spot
            })
        
        # Repeat for PUTS
        logger.info("")
        logger.info("  ANALYZING PUTS:")
        logger.info("  " + "-" * 60)
        
        for strike in strikes_in_range:
            if strike not in puts:
                continue
            
            opt = puts[strike]
            filter_stats['total_options'] += 1
            
            bid = opt.get('bidprice', 0) or opt.get('bidPrice', 0) or 0
            ask = opt.get('askprice', 0) or opt.get('askPrice', 0) or 0
            ltp = opt.get('lastPrice', 0) or 0
            vol = opt.get('totalTradedVolume', 0) or 0
            oi = opt.get('openInterest', 0) or 0
            oi_chg = opt.get('changeinOpenInterest', 0) or 0
            
            if oi_chg == 0 and 'pchangeinOpenInterest' in opt:
                oi_chg = int(oi * opt.get('pchangeinOpenInterest', 0) / 100) if opt.get('pchangeinOpenInterest') else 0
            
            logger.info("  Strike %s PE: Bid=%.2f Ask=%.2f LTP=%.2f Vol=%d OI=%d OI_Chg=%d",
                       strike, bid, ask, ltp, vol, oi, oi_chg)
            
            if ask <= 0:
                if ltp > 0:
                    ask = ltp
                    logger.info("    → Using LTP as ask price: %.2f", ask)
                else:
                    logger.info("    ❌ FILTERED: ask=0 and ltp=0")
                    filter_stats['failed_ask_zero'] += 1
                    continue
            
            if vol < VOLUME_THRESHOLD and abs(oi_chg) < OI_CHANGE_THRESHOLD:
                logger.info("    ❌ FILTERED: Vol=%d < %d AND |OI_Chg|=%d < %d",
                           vol, VOLUME_THRESHOLD, abs(oi_chg), OI_CHANGE_THRESHOLD)
                filter_stats['failed_volume_oi'] += 1
                continue
            
            spread_pct = (ask - bid) / ask if ask > 0 else 1
            if spread_pct > MAX_SPREAD_PCT:
                logger.info("    ❌ FILTERED: Spread %.1f%% > %.1f%%",
                           spread_pct * 100, MAX_SPREAD_PCT * 100)
                filter_stats['failed_spread'] += 1
                continue
            
            premium_ratio = ask / spot
            if premium_ratio > MAX_PREMIUM_RATIO:
                logger.info("    ❌ FILTERED: Premium ratio %.1f%% > %.1f%%",
                           premium_ratio * 100, MAX_PREMIUM_RATIO * 100)
                filter_stats['failed_premium_ratio'] += 1
                continue
            
            logger.info("    ✓ PASSED! Creating alert...")
            filter_stats['passed_all'] += 1
            
            alerts.append({
                'symbol': symbol,
                'type': 'PE',
                'strike': strike,
                'premium': ask,
                'volume': vol,
                'oi_change': oi_chg,
                'spot': spot
            })
    
    except Exception as e:
        logger.exception("  ❌ EXCEPTION: %s", e)
    
    return alerts, filter_stats

def dump_raw_option_chain(symbol):
    """Dump raw option chain data for inspection"""
    logger.info("=" * 70)
    logger.info("RAW OPTION CHAIN DUMP: %s", symbol)
    logger.info("=" * 70)
    
    try:
        oc = nse_optionchain_scrapper(symbol)
        
        if not oc:
            logger.error("Option chain is None")
            return
        
        logger.info("Top-level keys: %s", list(oc.keys()))
        
        if 'records' in oc:
            records = oc['records']
            logger.info("Records keys: %s", list(records.keys()))
            
            if 'underlyingValue' in records:
                logger.info("Underlying value: %s", records['underlyingValue'])
            
            if 'data' in records:
                data = records['data']
                logger.info("Number of data records: %d", len(data))
                
                if data:
                    # Show first record structure
                    first = data[0]
                    logger.info("First record keys: %s", list(first.keys()))
                    
                    # Show a few sample records
                    for i, rec in enumerate(data[:3]):
                        logger.info("")
                        logger.info("Sample record %d:", i+1)
                        logger.info("  strikePrice: %s", rec.get('strikePrice'))
                        
                        if 'CE' in rec:
                            ce = rec['CE']
                            logger.info("  CE keys: %s", list(ce.keys()))
                            logger.info("  CE sample: bid=%s ask=%s ltp=%s vol=%s oi=%s",
                                       ce.get('bidprice'), ce.get('askprice'), 
                                       ce.get('lastPrice'), ce.get('totalTradedVolume'),
                                       ce.get('openInterest'))
                        
                        if 'PE' in rec:
                            pe = rec['PE']
                            logger.info("  PE keys: %s", list(pe.keys()))
                            logger.info("  PE sample: bid=%s ask=%s ltp=%s vol=%s oi=%s",
                                       pe.get('bidprice'), pe.get('askprice'),
                                       pe.get('lastPrice'), pe.get('totalTradedVolume'),
                                       pe.get('openInterest'))
    
    except Exception as e:
        logger.exception("Error dumping option chain: %s", e)

def main():
    logger.info("=" * 70)
    logger.info("OPTIONS SCREENER DIAGNOSTIC TOOL")
    logger.info("=" * 70)
    logger.info("")
    
    # First, dump raw data for one symbol to see the structure
    logger.info("STEP 1: Dumping raw option chain structure for RELIANCE")
    dump_raw_option_chain("RELIANCE")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info("STEP 2: Running diagnostic scan on test stocks")
    logger.info("=" * 70)
    logger.info("")
    
    total_stats = {
        'total_options': 0,
        'passed_all': 0,
        'failed_ask_zero': 0,
        'failed_volume_oi': 0,
        'failed_spread': 0,
        'failed_premium_ratio': 0,
    }
    
    all_alerts = []
    
    for symbol in TEST_STOCKS:
        alerts, stats = diagnose_stock(symbol)
        all_alerts.extend(alerts)
        
        for key in total_stats:
            total_stats[key] += stats.get(key, 0)
        
        time.sleep(0.5)  # Rate limiting
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Total options analyzed: %d", total_stats['total_options'])
    logger.info("Passed all filters: %d", total_stats['passed_all'])
    logger.info("")
    logger.info("Filter breakdown:")
    logger.info("  - Failed (ask=0): %d", total_stats['failed_ask_zero'])
    logger.info("  - Failed (volume/OI): %d", total_stats['failed_volume_oi'])
    logger.info("  - Failed (spread): %d", total_stats['failed_spread'])
    logger.info("  - Failed (premium ratio): %d", total_stats['failed_premium_ratio'])
    logger.info("")
    
    if all_alerts:
        logger.info("ALERTS GENERATED: %d", len(all_alerts))
        for alert in all_alerts[:10]:
            logger.info("  %s %s @ %s | Premium=₹%.2f | Vol=%d",
                       alert['symbol'], alert['type'], alert['strike'],
                       alert['premium'], alert['volume'])
    else:
        logger.info("NO ALERTS GENERATED!")
        logger.info("")
        logger.info("Possible causes:")
        logger.info("  1. NSE option chain API may have changed field names")
        logger.info("  2. All options have bid/ask = 0 (market closed?)")
        logger.info("  3. Volume/OI data not being returned")
        logger.info("")
        logger.info("Check the detailed log file: %s", LOG_FILE)

if __name__ == "__main__":
    main()
