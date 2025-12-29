"""
Configuration constants for the Smart Options Screener.

Contains all thresholds, stock lists, lot sizes, and other settings.
"""

import pytz
from datetime import time as dtime

# ================== TELEGRAM CONFIGURATION ==================
TELEGRAM_BOT_TOKEN = "8554491299:AAEYVxPF-THCg5f37JsDBHGUI3kTON2idPM"
TELEGRAM_CHAT_ID = "@manish_private_bot"

# ================== SYMBOL LISTS ==================
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

# Symbol mapping for yfinance
SYMBOL_MAP = {"NIFTY": "^NSEI", "BANKNIFTY": "^NSEBANK"}
for stock in STOCK_SYMBOLS:
    SYMBOL_MAP[stock] = f"{stock}.NS"

# ================== OPSTRA CONFIGURATION ==================
# To get cookies:
# 1. Login to https://opstra.definedge.com in Chrome
# 2. Press F12 → Application tab → Cookies → opstra.definedge.com
# 3. Copy JSESSIONID and DSESSIONID values below

OPSTRA_COOKIES = {
    'JSESSIONID': '9DCB9574F3DEF1073EC92D2329E8CC4E',
    'DSESSIONID': '718F8911E954CE00C69A6EF33AEC2388',
    '_ga': 'GA1.1.703791765.1764073625',
    '_ga_6D0ZQ437SD': 'GS2.1.s1764145134$o4$g1$t1764145153$j41$l0$h0'
}

# Set to True to require Opstra (will skip stocks without IV data)
# Set to False to use Historical Volatility fallback
REQUIRE_OPSTRA_IV = False

# Cache IV data to reduce API calls (symbol -> {data, timestamp})
IV_CACHE = {}
IV_CACHE_DURATION = 300  # 5 minutes

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

# ================== STOCK TIERS ==================
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

# ================== VOLUME/OI THRESHOLDS ==================
# Live market thresholds (require significant volume activity)
VOLUME_THRESHOLDS = {'TIER_1': 1000, 'TIER_2': 500, 'TIER_3': 200}
OI_THRESHOLDS = {'TIER_1': 5000, 'TIER_2': 2000, 'TIER_3': 1000}
VOLUME_THRESHOLD_INDEX = 10000
OI_THRESHOLD_INDEX = 50000

# After-hours thresholds (stricter - only show highly liquid options)
AFTER_HOURS_OI_THRESHOLD_STOCK = 8000
AFTER_HOURS_OI_THRESHOLD_INDEX = 75000
AFTER_HOURS_SPREAD_PCT = 0.20

# Set to True to allow scanning during non-market hours with relaxed filters
ALLOW_AFTER_HOURS_SCAN = True

# ================== STRIKE & PREMIUM FILTERS ==================
STRIKE_RANGE_MULTIPLIER = 3      # Scan ATM ± 3 strikes only
MAX_SPREAD_PCT = 0.10            # Max 10% spread for indices
MAX_SPREAD_PCT_STOCK = 0.15      # Max 15% spread for stocks
MAX_PREMIUM_RATIO = 0.08         # Premium < 8% of spot
MAX_PREMIUM_RATIO_STOCK = 0.10   # Premium < 10% of spot for stocks
MIN_STOCK_PRICE = 100
MIN_PREMIUM = 5                  # Minimum ₹5 premium (avoid penny options)
MIN_PREMIUM_INDEX = 10           # Minimum ₹10 premium for indices

# ================== RSI THRESHOLDS ==================
RSI_OVERSOLD = 40
RSI_OVERBOUGHT = 60

# ================== IV THRESHOLDS ==================
IV_VERY_HIGH = 80    # Skip buying options above this percentile
IV_HIGH = 65         # Caution zone
IV_LOW = 30          # Cheap premiums - good for buying

# ================== SPREAD STRATEGY CONFIGURATION ==================
SPREAD_WIDTH_STOCKS = 1       # 1 strike away for stock spreads
SPREAD_WIDTH_INDEX = 2        # 2 strikes away for index spreads

# IV thresholds for volatility strategies
IV_PERCENTILE_LOW = 35        # Long Straddle trigger
IV_PERCENTILE_VERY_LOW = 25   # Long Strangle trigger

# Spread strategy filters
MIN_SPREAD_REWARD_RATIO = 0.5
MAX_SPREAD_COST_RATIO = 0.70
MIN_OI_PER_LEG_STOCK = 500
MIN_OI_PER_LEG_INDEX = 5000

# Straddle/Strangle filters
MAX_STRADDLE_COST_PCT = 0.04
MAX_STRANGLE_COST_PCT = 0.025
MIN_DAYS_TO_EXPIRY_VOLATILITY = 5

# ================== MARKET TIMING ==================
MARKET_START = dtime(9, 15)
MARKET_END = dtime(15, 30)
IST = pytz.timezone("Asia/Kolkata")

# ================== OUTPUT FILES ==================
CSV_FILE = "/Users/manishkumarsingh/Documents/option_testing_qwen/new_screener_options_scan_log_v3_3.csv"
JSON_FILE = "/Users/manishkumarsingh/Documents/option_testing_qwen/new_screener_alerts_v3_3.json"

# ================== NSE API CONFIGURATION ==================
NSE_SESSION_TIMEOUT = 300  # Refresh session every 5 minutes

NSE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.nseindia.com/option-chain',
}

# ================== CSV HEADERS ==================
CSV_HEADERS = [
    "Timestamp", "Symbol", "Type", "Strategy", "Strike", "Premium", "PriceSource",
    "Spot", "Volume", "OI", "OI_Change", "IV", "IV_Percentile", "IV_Rank", "IV_Source",
    "Market_Regime", "RSI", "Tier", "Moneyness", "Expiry", "DaysToExpiry", 
    "LotSize", "TotalCost", "Breakeven", "DistanceFromSpot",
    # Multi-leg strategy fields
    "Leg1_Strike", "Leg1_Premium", "Leg1_Action", 
    "Leg2_Strike", "Leg2_Premium", "Leg2_Action",
    "MaxProfit", "MaxLoss", "RewardRatio"
]

