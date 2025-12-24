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
TELEGRAM_BOT_TOKEN = "#"  # ← REPLACE THIS
TELEGRAM_CHAT_ID = "#"              # ← REPLACE THIS

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
# ==================================================

# GLOBAL: Store your session cookies here after logging in via browser
OPSTRA_COOKIES = {
    # NOTE: These are placeholders – set real values at runtime via set_opstra_cookies()
    'JSESSIONID': 'CD592873F7F5AD0747F790EED66769F4',
    'DSESSIONID': 'A589EEDA716886E4C14D1C0329F79BA9',
    '_ga': 'GA1.1.703791765.1764073625',
    '_ga_6D0ZQ437SD': 'GS2.1.s1764145134$o4$g1$t1764145153$j41$l0$h0'
}
"""
_ga=; DSESSIONID=; JSESSIONID=; _ga_6D0ZQ437SD=
"""


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
    "Market_Regime", "VIX"
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
            alert.get('vix', 0)
        ])

class OpstraSession:
    """
    Reusable Opstra session that logs in once and stores cookies.
    Use this to avoid logging in for every symbol.
    """
    def __init__(self, google_email, google_password):
        self.session = None
        self.login(google_email, google_password)
    
    def login(self, google_email, google_password):
        """Perform one-time login and store session cookies"""
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        import time
        import requests
        
        driver = None
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
            
            wait = WebDriverWait(driver, 20)
            
            logger.info("Logging in to Opstra via Google for user: %s", google_email)
            driver.get("https://opstra.definedge.com/login")
            time.sleep(2)
            
            # Click Google Sign-In
            google_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(., 'Google') or contains(@class, 'google')]")
            ))
            google_btn.click()
            time.sleep(3)
            
            # Handle popup if needed
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
            
            # Enter email
            email_field = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='email']")
            ))
            email_field.send_keys(google_email)
            
            next_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[text()='Next'] or @id='identifierNext']")
            ))
            next_btn.click()
            time.sleep(2)
            
            # Enter password
            password_field = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='password']")
            ))
            password_field.send_keys(google_password)
            
            next_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[.//span[text()='Next'] or @id='passwordNext']")
            ))
            next_btn.click()
            time.sleep(3)
            
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[0])
            
            wait.until(lambda d: "opstra.definedge.com" in d.current_url 
                       and "/login" not in d.current_url)
            time.sleep(2)
            
            # Store cookies in requests session
            cookies = driver.get_cookies()
            self.session = requests.Session()
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            logger.info("Login to Opstra successful, session cookies captured")
        
        finally:
            if driver:
                driver.quit()
                logger.debug("Selenium driver for Opstra login closed")
    
    def get_iv_data(self, symbol):
        """Fetch IV data using stored session"""
        import numpy as np
        
        if not self.session:
            logger.error("OpstraSession.get_iv_data called without active session")
            return None
        
        try:
            symbol_upper = symbol.upper()
            url = f"https://opstra.definedge.com/api/ivcharts/{symbol_upper}"
            
            headers = {
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://opstra.definedge.com/ivchart",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error("OpstraSession.get_iv_data HTTP error for %s: status %s", symbol, response.status_code)
                return None
            
            data = response.json()
            ivchart = data.get("ivchart", [])
            
            if not ivchart:
                logger.error("OpstraSession.get_iv_data no IV data for %s", symbol)
                return None
            
            iv_values = [float(p.get("ImpVol")) for p in ivchart 
                        if p.get("ImpVol") is not None and p.get("ImpVol") > 0]
            
            if len(iv_values) < 30:
                logger.warning("OpstraSession.get_iv_data insufficient IV history for %s (len=%d)", symbol, len(iv_values))
                return None
            
            window = iv_values[-252:]
            current_iv = window[-1]
            
            iv_percentile = int((np.sum(np.array(window) <= current_iv) / len(window)) * 100)
            
            iv_min = min(window)
            iv_max = max(window)
            iv_rank = 50 if iv_max == iv_min else int(((current_iv - iv_min) / (iv_max - iv_min)) * 100)
            
            result = {
                'iv': current_iv,
                'iv_percentile': iv_percentile,
                'iv_rank': iv_rank
            }
            logger.debug(
                "OpstraSession.get_iv_data result for %s: IV=%.2f, IV%%=%d, IVR=%d",
                symbol, current_iv, iv_percentile, iv_rank
            )
            return result
        
        except Exception as e:
            logger.exception("OpstraSession.get_iv_data exception for %s: %s", symbol, e)
            return None




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

def get_iv_data_V1(symbol):
    url_map = {
        "NIFTY": "https://opstra.definedge.com/api/optionsnapshot/nifty",
        "BANKNIFTY": "https://opstra.definedge.com/api/optionsnapshot/banknifty"
    }
    if symbol in STOCK_SYMBOLS:
        return None
    url = url_map.get(symbol.upper())
    if not url:
        return None
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {
                'iv': float(data.get('iv', 0)),
                'iv_percentile': int(data.get('ivp', 0)),
                'iv_rank': int(data.get('ivr', 0))
            }
    except Exception as e:
        print(f"[IV ERROR] {symbol}: {e}")
    return None

def get_iv_data(symbol):
    """
    Fetch historical IV data from Opstra's ivcharts API and compute:
    - Current IV (last ImpVol)
    - IV Percentile (over last 252 days)
    - IV Rank (over last 252 days)
    """
    import time
    # set_opstra_cookies()
    # Check if cookies are set
    if not OPSTRA_COOKIES.get('JSESSIONID') or not OPSTRA_COOKIES.get('DSESSIONID'):
        logger.error("Opstra cookies not set. Call set_opstra_cookies() before get_iv_data for %s", symbol)
        logger.info(
            "Opstra IV instructions: login to https://opstra.definedge.com, "
            "copy JSESSIONID & DSESSIONID cookies, and call set_opstra_cookies()"
        )
        return None

    # Start from the homepage to establish session
    home_url = "https://opstra.definedge.com/"
    ivchart_url = "https://opstra.definedge.com/ivchart"
    
    # Headers for initial homepage visit
    home_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Headers for ivchart page
    page_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Referer": "https://opstra.definedge.com/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Headers for API request
    api_headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Referer": "https://opstra.definedge.com/ivchart",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    # Headers from your browser inspection
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
        # Make request with stored cookies
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

# def get_underlying_price(symbol):
#     try:
#         ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
#         data = yf.Ticker(ticker).history(period="1m")
#         return data['Close'][-1] if not data.empty else None
#     except:
#         return None

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
            # Use 5-minute data for indices (more responsive)
            data = yf.Ticker(ticker).history(period="1d", interval="5m")
            if not data.empty:
                price = data['Close'].iloc[-1]
                logger.debug("Underlying price for %s (index): %.2f", symbol, price)
                return price
            logger.warning("Empty intraday price data for index %s", symbol)
        else:
            # For stocks: use daily close (intraday often not available)
            data = yf.Ticker(ticker).history(period="1d")
            if not data.empty:
                price = data['Close'].iloc[-1]
                logger.debug("Underlying price for %s (stock): %.2f", symbol, price)
                return price
            logger.warning("Empty daily price data for stock %s", symbol)
                
    except Exception as e:
        logger.exception("[PRICE ERROR] Error fetching underlying price for %s: %s", symbol, e)
    
    # Fallback: return None if all fails
    logger.error("Failed to fetch underlying price for %s, returning None", symbol)
    return None


def is_market_hours():
    now = datetime.now(IST).time()
    in_hours = MARKET_START <= now <= MARKET_END
    logger.debug(
        "Market hours check: now=%s, start=%s, end=%s, in_hours=%s",
        now, MARKET_START, MARKET_END, in_hours
    )
    return in_hours

def find_atm_strike(strikes, spot):
    return min(strikes, key=lambda x: abs(x - spot))

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
            'vix': vix
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
                    logger.debug(
                        "Bull Call Spread candidate on %s: %s (debit=%.2f, max_profit=%.2f)",
                        symbol, alert['strike'], net_debit, max_profit
                    )

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
                    logger.debug(
                        "Bear Put Spread candidate on %s: %s (debit=%.2f, max_profit=%.2f)",
                        symbol, alert['strike'], net_debit, max_profit
                    )

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
                        logger.debug(
                            "Long Straddle candidate on %s: strike=%s, total=%.2f, cost_pct=%.4f, max_cost=%.4f",
                            symbol, atm, total, cost_pct, max_cost
                        )

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
                        logger.debug(
                            "Long Strangle candidate on %s: strikes=%s, total=%.2f, cost_pct=%.4f, max_cost=%.4f",
                            symbol, alert['strike'], total, cost_pct, max_cost
                        )

    except Exception as e:
        logger.exception("[INDEX SCAN ERROR] %s: %s", symbol, e)
    logger.info("Index scan completed for %s, total alerts: %d", symbol, len(alerts))
    return alerts

def scan_stock(symbol, market_regime, vix):
    logger.info("Starting stock scan for %s | regime=%s, vix=%.2f", symbol, market_regime, vix)
    alerts = []
    try:
        oc = nse_optionchain_scrapper(symbol)
        records = oc['records']['data']
        spot_nse = oc['records']['underlyingValue']
        spot = get_underlying_price(symbol) or spot_nse
        logger.info("Stock %s spot from NSE=%.2f, yfinance/underlying=%.2f", symbol, spot_nse, spot)
        if spot < 100:
            logger.info("[SKIP] %s: Spot price ₹%.2f below ₹100", symbol, spot)
            return []

        vol_thresh = VOLUME_THRESHOLD_STOCK
        oi_thresh = OI_CHANGE_THRESHOLD_STOCK
        if market_regime == "HIGH_VOL":
            vol_thresh = 2000
            oi_thresh = 500

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
        logger.info("Stock %s: spot=%s atm=%s step=%s", symbol, spot, atm, step)
        base_alert = {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'instrument_type': 'STOCK',
            'spot': spot,
            'iv': 0,
            'iv_percentile': 0,
            'iv_rank': 0,
            'market_regime': market_regime,
            'vix': vix
        }
        logger.info("Stock %s: base_alert=%s", symbol, base_alert)
        for opt_type, opt_dict in [("CE", calls), ("PE", puts)]:
            for strike, opt in opt_dict.items():
                if abs(strike - atm) > step:
                    logger.info("Stock %s: skipping strike=%s because it's out of step=%s", symbol, strike, step)
                    continue

                bid = opt.get('bidprice', 0)
                ask = opt.get('askprice', 0)
                vol = opt.get('totalTradedVolume', 0)
                oi_chg = opt.get('openInterest', 0) - opt.get('prevOpenInterest', 0)

                if ask <= 0 or vol < vol_thresh or oi_chg < oi_thresh:
                    logger.info("Stock %s: skipping strike=%s because it's out of vol_thresh=%s or oi_chg=%s", symbol, strike, vol_thresh, oi_chg)
                    continue
                if (ask - bid) / ask > MAX_SPREAD_PCT:
                    logger.info("Stock %s: skipping strike=%s because it's out of MAX_SPREAD_PCT=%s", symbol, strike, MAX_SPREAD_PCT)
                    continue
                if ask / spot > MAX_PREMIUM_RATIO:
                    logger.info("Stock %s: skipping strike=%s because it's out of MAX_PREMIUM_RATIO=%s", symbol, strike, MAX_PREMIUM_RATIO)
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

    except Exception as e:
        logger.exception("[STOCK SCAN ERROR] %s: %s", symbol, e)
    logger.info("Stock scan completed for %s, total alerts: %d", symbol, len(alerts))
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
        logger.info(
            "Sending Telegram alert for %s | strategy=%s | strike=%s | premium=%.2f",
            symbol, strategy, strike, premium
        )
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg, parse_mode='Markdown')
    except Exception as e:
        logger.exception("[TELEGRAM ERROR] Failed to send alert for %s: %s", symbol, e)

def job():
    # if not is_market_hours():
    #     print("🕒 Outside market hours.")
    #     return

 
    logger.info("Starting smart scan cycle at %s", datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'))

    vix = get_india_vix()
    regime = determine_market_regime(vix)
    iv_threshold = get_iv_threshold(regime)
    logger.info("Market Regime: %s | India VIX: %.1f | IV%% Threshold: ≤%d", regime, vix, iv_threshold)

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
        logger.info("Total unique alerts this cycle: %d", len(unique_alerts))
        for alert in unique_alerts:
            logger.info(
                "ALERT %s: %s | %s | %s | premium=%.2f | vol=%s | oi_change=%s",
                alert['instrument_type'], alert['strategy'], alert['symbol'],
                alert['strike'], alert['premium'], alert['volume'], alert['oi_change']
            )
            log_to_csv(alert)
            asyncio.run(send_telegram_alert(alert))
    else:
        logger.info("No signals in current regime for this scan cycle.")

if __name__ == "__main__":
    logger.info("SMART Options Screener started: Market Regime + Stocks + IV Adaptation")
    logger.info("Instruments: Nifty, BankNifty + 20 F&O Stocks")
    logger.info("Logging alerts to CSV file: %s", CSV_FILE)

    job()
    schedule.every(60).seconds.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)
