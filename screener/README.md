# Smart Options Screener v3.3

A modular Python package for scanning NSE options with support for 6 trading strategies, real-time IV data, and intelligent filtering.

## Features

- **6 Options Strategies**: Long Call, Long Put, Bull Call Spread, Bear Put Spread, Long Straddle, Long Strangle
- **Real-time IV Data**: Integration with Opstra API for accurate Implied Volatility metrics
- **Historical Volatility Fallback**: Automatic fallback to calculated HV when Opstra data is unavailable
- **Tiered Stock Classification**: Different filtering thresholds for liquid vs. less liquid stocks
- **Technical Analysis**: RSI and EMA-based trend bias for directional filtering
- **Market Regime Awareness**: VIX-based regime classification
- **After-Hours Mode**: Relaxed OI-only filters for scanning outside market hours
- **Multi-Leg Strategy Support**: Calculates max profit, max loss, breakeven, and reward/risk ratio
- **NSE API v3 Integration**: Uses latest NSE API endpoints for reliable option chain data

## Installation

The package uses the existing virtual environment in the project:

```bash
cd /Users/manishkumarsingh/Documents/option_testing_qwen
source venv_qwen/bin/activate
```

### Dependencies

- pandas
- numpy
- yfinance
- requests
- schedule
- pytz

## Quick Start

### Run the Screener

```bash
# From the project root directory
python -m screener.main
```

### Import and Use Programmatically

```python
from screener import job, scan_stock, scan_index
from screener.config import STOCK_SYMBOLS, INDEX_SYMBOLS
from screener.iv import set_opstra_cookies

# Configure Opstra cookies for accurate IV data
set_opstra_cookies('your_jsessionid', 'your_dsessionid')

# Run a single scan
job()

# Or scan individual symbols
from screener.api import is_market_hours, get_india_vix, determine_market_regime

vix = get_india_vix()
regime = determine_market_regime(vix)
market_open = is_market_hours()

alerts = scan_stock('RELIANCE', regime, vix, market_open)
```

## Package Structure

```
screener/
├── __init__.py                 # Package exports
├── main.py                     # Entry point, job(), run_scheduler()
├── config.py                   # All configuration constants
├── README.md                   # This file
│
├── api/                        # NSE API integration
│   ├── __init__.py
│   ├── nse_session.py          # Session management with cookies
│   ├── option_chain.py         # fetch_nse_option_chain()
│   └── market_status.py        # is_market_hours(), get_india_vix()
│
├── iv/                         # Implied Volatility data
│   ├── __init__.py
│   ├── opstra.py               # Opstra API integration
│   ├── historical.py           # Historical volatility calculation
│   └── provider.py             # Unified get_iv_data() interface
│
├── strategies/                 # Trading strategies
│   ├── __init__.py
│   ├── helpers.py              # Spread metrics calculations
│   ├── bull_call_spread.py
│   ├── bear_put_spread.py
│   ├── long_straddle.py
│   └── long_strangle.py
│
├── scanners/                   # Main scanning logic
│   ├── __init__.py
│   ├── stock.py                # scan_stock()
│   └── index.py                # scan_index()
│
├── output/                     # Logging and output
│   ├── __init__.py
│   ├── csv_logger.py           # CSV file logging
│   └── json_logger.py          # JSON file logging
│
└── utils/                      # Utilities
    ├── __init__.py
    ├── logging_setup.py        # Logger configuration
    └── helpers.py              # Helper functions
```

## Configuration

### Opstra Cookies Setup

For accurate IV data, configure Opstra session cookies:

1. Login to https://opstra.definedge.com in Chrome
2. Press F12 → Application → Cookies → opstra.definedge.com
3. Copy `JSESSIONID` and `DSESSIONID` values

```python
from screener.iv import set_opstra_cookies
set_opstra_cookies('your_jsessionid', 'your_dsessionid')
```

Or edit `screener/config.py` directly:

```python
OPSTRA_COOKIES = {
    'JSESSIONID': 'your_jsessionid_here',
    'DSESSIONID': 'your_dsessionid_here',
}
```

### Key Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ALLOW_AFTER_HOURS_SCAN` | True | Enable scanning when market is closed |
| `STRIKE_RANGE_MULTIPLIER` | 3 | Strikes above/below ATM to scan |
| `MAX_SPREAD_PCT_STOCK` | 15% | Max bid-ask spread for stocks |
| `MIN_PREMIUM` | ₹5 | Minimum option premium |
| `IV_VERY_HIGH` | 80 | Skip when IV percentile above this |

### Stock Tiers

Stocks are classified into three tiers based on liquidity:

| Tier | Volume Threshold | OI Threshold | Examples |
|------|------------------|--------------|----------|
| TIER_1 | 1,000 | 5,000 | RELIANCE, HDFCBANK, TCS, INFY |
| TIER_2 | 500 | 2,000 | TATASTEEL, BAJAJ-AUTO, BEL |
| TIER_3 | 200 | 1,000 | ONGC, DABUR, COALINDIA |

## Strategies Supported

### Single-Leg Strategies

| Strategy | Direction | Trigger |
|----------|-----------|---------|
| Long Call | Bullish | RSI < 40 or Uptrend |
| Long Put | Bearish | RSI > 60 or Downtrend |

### Multi-Leg Strategies

| Strategy | Direction | IV Trigger | Structure |
|----------|-----------|------------|-----------|
| Bull Call Spread | Bullish | IVP < 65% | Buy ATM Call + Sell OTM Call |
| Bear Put Spread | Bearish | IVP < 65% | Buy ATM Put + Sell OTM Put |
| Long Straddle | Neutral | IVP < 35% | Buy ATM Call + Buy ATM Put |
| Long Strangle | Neutral | IVP < 25% | Buy OTM Call + Buy OTM Put |

## Operating Modes

### Live Market Mode (9:15 AM - 3:30 PM IST)

- Strict volume/OI filters
- Ask price preferred for entries
- Full technical analysis

### After-Hours Mode

- OI-only filters (no volume requirement)
- LTP price preferred
- Higher OI thresholds for liquidity

| Filter | Live | After-Hours |
|--------|------|-------------|
| Volume Required | Yes | No |
| OI Threshold (Stocks) | 1,000-5,000 | 8,000 |
| OI Threshold (Indices) | 50,000 | 75,000 |
| Price Priority | Ask first | LTP first |

## Output Files

### CSV Output

Location: `new_screener_options_scan_log_v3_3.csv`

Contains 33 columns including:
- Symbol, Strategy, Strike, Premium
- Volume, OI, IV, IV Percentile
- Max Profit, Max Loss, Reward Ratio (for spreads)

### JSON Output

Location: `new_screener_alerts_v3_3.json`

Top 15 alerts by volume in JSON format for integration with other systems.

### Log File

Location: `screener.log`

- Max Size: 5 MB with 3 backup rotations
- Format: `YYYY-MM-DD HH:MM:SS LEVEL - MESSAGE`

## API Reference

### Main Functions

```python
from screener import job, run_scheduler

# Run single scan
job()

# Run with scheduler (every 5 minutes)
run_scheduler(interval_seconds=300)
```

### Scanners

```python
from screener.scanners import scan_stock, scan_index

# Scan a stock
alerts = scan_stock('RELIANCE', 'NORMAL_VOL', 15.5, market_open=True)

# Scan an index
alerts = scan_index('NIFTY', 60, 'NORMAL_VOL', 15.5, market_open=True)
```

### IV Data

```python
from screener.iv import get_iv_data, set_opstra_cookies, is_opstra_configured

# Check if Opstra is configured
if not is_opstra_configured():
    set_opstra_cookies('jsessionid', 'dsessionid')

# Get IV data for a symbol
iv_data = get_iv_data('RELIANCE')
# Returns: {'iv': 28.5, 'iv_percentile': 65, 'iv_rank': 55, 'source': 'opstra'}
```

### Market Status

```python
from screener.api import is_market_hours, get_india_vix, determine_market_regime

market_open = is_market_hours()
vix = get_india_vix()
regime = determine_market_regime(vix)  # 'LOW_VOL', 'NORMAL_VOL', or 'HIGH_VOL'
```

## Interpreting Alerts

### High-Confidence Alert Characteristics

- IV Source: `opstra` (reliable IV data)
- IV Percentile: < 50% (cheap premiums)
- Volume: High relative to tier threshold
- Spread: Low (< 10%)
- Moneyness: ATM or slightly OTM

### Caution Indicators

- IV Source: `default` (no reliable data)
- IV Percentile: > 70% (expensive premiums)
- Volume: Near minimum threshold
- Price Source: `bid` (may have liquidity issues)

## Debugging

Enable debug logging to see filter decisions:

```python
# In screener/utils/logging_setup.py
logger.setLevel(logging.DEBUG)
```

This shows detailed skip reasons:
```
[SKIP] RELIANCE 1600 CE: oi=350 < 500 (after-hours)
[SKIP] TCS 3400 CE: spread=0.35 > 0.30
[SKIP] NIFTY 24000 CE: vol=10 < 500 and oi=5000 < 10000
```

## Data Sources

| Source | Data Provided |
|--------|---------------|
| NSE API v3 | Option chain (strikes, premiums, volume, OI) |
| Yahoo Finance | Spot price, historical OHLC for RSI/EMA |
| Opstra API | Implied Volatility, IV Percentile, IV Rank |
| NSE India | India VIX for market regime |

## Changelog

### v3.3.0 (December 2024)

- Modular package structure (25 files from 1 monolithic file)
- 6 strategy support (added spreads, straddles, strangles)
- After-hours scanning mode
- NSE API v3 integration
- Opstra IV with HV fallback
- Smart price priority based on market status

## License

Internal use only.

---

*Package Version: 3.3.0 | Last Updated: December 2024*

