# Smart Options Screener v3.3

A modular Python package for scanning NSE options with support for 6 trading strategies, real-time IV data, intelligent filtering, and a full-featured PyQt6 GUI.

## Features

- **PyQt6 GUI Application**: User-friendly desktop interface for configuring scans and analyzing alerts
- **6 Options Strategies**: Long Call, Long Put, Bull Call Spread, Bear Put Spread, Long Straddle, Long Strangle
- **Real-time IV Data**: Integration with Opstra API for accurate Implied Volatility metrics
- **Historical Volatility Fallback**: Automatic fallback to calculated HV when Opstra data is unavailable
- **Tiered Stock Classification**: Different filtering thresholds for liquid vs. less liquid stocks
- **Technical Analysis**: RSI and EMA-based trend bias for directional filtering
- **Market Regime Awareness**: VIX-based regime classification
- **After-Hours Mode**: Relaxed OI-only filters for scanning outside market hours
- **Multi-Leg Strategy Support**: Calculates max profit, max loss, breakeven, and reward/risk ratio
- **NSE API v3 Integration**: Uses latest NSE API endpoints for reliable option chain data
- **Alert Analyzer Integration**: Built-in basic and enhanced analysis reports for any alert

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
- PyQt6 (for GUI)
- scipy (for Black-Scholes calculations)
- selenium (for Opstra auto-login)
- webdriver-manager (for Opstra auto-login)

## Quick Start

### Run the GUI (Recommended)

```bash
# Launch the graphical interface
python -m screener.ui.screener_gui
```

The GUI provides two tabs:
- **Screener Tab**: Configure symbols, strategies, and time parameters, then run scans
- **Alert Viewer Tab**: Load JSON/CSV alert files and generate detailed analysis reports

### Run the Screener (CLI)

```bash
# From the project root directory
python -m screener.main              # Run with scheduler (auto Opstra refresh)
python -m screener.main --json       # Single scan, JSON output
python -m screener.main --refresh-opstra  # Force Opstra re-login
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
├── main.py                     # Entry point, job(), run_scheduler(), run_scan_with_config()
├── config.py                   # All configuration constants
├── README.md                   # This file
│
├── ui/                         # PyQt6 GUI Application
│   ├── __init__.py
│   └── screener_gui.py         # Main GUI with Screener and Alert Viewer tabs
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
│   ├── opstra_login.py         # Auto-login with persistent Chrome profile
│   ├── historical.py           # Historical volatility calculation (configurable)
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
    └── helpers.py              # Helper functions (configurable trend params)
```

## Configuration

### Opstra Auto-Login (Recommended)

The screener now supports **automatic Opstra login** using a persistent Chrome profile. You only need to login once manually, and subsequent runs will automatically extract fresh cookies.

#### How It Works

1. **First Run**: Browser opens → Login with Google → Profile saved to `~/.opstra_chrome_profile`
2. **Subsequent Runs**: Uses saved profile → No manual login required
3. **Session Expires** (after weeks): Use `--refresh-opstra` to re-login

#### Usage

```bash
# Normal run - auto-refreshes Opstra if needed
python -m screener.main

# Single scan with JSON output
python -m screener.main --json

# Force Opstra re-login (opens browser)
python -m screener.main --refresh-opstra

# Skip Opstra entirely, use Historical Volatility fallback
python -m screener.main --no-opstra

# Custom scan interval (default: 300 seconds)
python -m screener.main --interval 600
```

#### CLI Arguments

| Argument | Description |
|----------|-------------|
| `--json` | Run single scan and exit (no scheduler) |
| `--refresh-opstra` | Force Opstra session refresh (opens browser for login) |
| `--no-opstra` | Skip Opstra IV, use Historical Volatility fallback only |
| `--interval N` | Scan interval in seconds (default: 300) |

#### Programmatic Usage

```python
from screener.iv import refresh_opstra_session, clear_opstra_profile

# Refresh Opstra session (opens browser if needed)
refresh_opstra_session()

# Force re-login
refresh_opstra_session(force_login=True)

# Clear saved profile (for troubleshooting)
clear_opstra_profile()
```

#### Configuration

The Chrome profile path can be customized in `screener/config.py`:

```python
# Default: ~/.opstra_chrome_profile
CHROME_PROFILE_PATH = "/path/to/custom/profile"
```

### Manual Opstra Setup (Alternative)

If you prefer not to use auto-login, you can still set cookies manually:

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
from screener.iv import get_iv_data, set_opstra_cookies, is_opstra_configured, set_skip_opstra

# Check if Opstra is configured
if not is_opstra_configured():
    set_opstra_cookies('jsessionid', 'dsessionid')

# Get IV data for a symbol
iv_data = get_iv_data('RELIANCE')
# Returns: {'iv': 28.5, 'iv_percentile': 65, 'iv_rank': 55, 'source': 'opstra'}

# Skip Opstra and use Historical Volatility only
set_skip_opstra(True)
iv_data = get_iv_data('RELIANCE')
# Returns: {'iv': 25.3, 'iv_percentile': 50, 'iv_rank': 50, 'source': 'historical'}

# Re-enable Opstra
set_skip_opstra(False)
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

## GUI Features

### Screener Tab

The Screener tab provides a visual interface for configuring and running scans:

- **Symbol Selection**: Choose from 2 indices (NIFTY, BANKNIFTY) and 56+ F&O stocks
  - ➕ **Add Stock**: Add custom stock symbols (comma-separated)
  - ➖ **Remove Stock**: Remove unchecked stocks from the list
  - Dynamic stock count with Select All / Clear All buttons
- **Strategy Toggles**: Enable/disable any of the 6 supported strategies
- **Time Configuration**:
  - Historical Data Period (1w, 1mo, 3mo, 6mo, 1y) for RSI/EMA calculations
  - Historical Data Interval (1d, 1h, 5m) for trend analysis
  - HV Calculation Period (3mo, 6mo, 1y, 2y) for volatility lookback
  - HV Rolling Window (10-60 days) for volatility calculation
- **Opstra IV Configuration**:
  - Session Status display (✅ Active / ⚠️ Expired / ❌ Not Configured)
  - 🔄 Check Status button to validate current session
  - 🌐 Refresh Session button (opens browser for auto-login)
  - 🔑 Force Re-Login button (force new login even if profile exists)
  - ✏️ Enter Cookies Manually dialog (for manual JSESSIONID/DSESSIONID entry)
  - ☑️ Skip Opstra checkbox (use Historical Volatility only)
  - 🗑️ Clear Saved Profile button (delete Chrome profile for troubleshooting)

### Alert Viewer Tab

The Alert Viewer tab allows you to load and analyze saved alerts:

- **Load Alert Files**: Supports both JSON and CSV formats
- **Alert Table**: View all alerts with key metrics (Symbol, Strategy, Strike, Premium, etc.)
- **Multi-Leg Strategy Support**: Properly handles strangles, straddles, and spreads with strike formats like "60000/60400"
- **Basic Analysis Report**: Comprehensive report including:
  - Basic information and IV analysis
  - Greeks calculation and interpretation
  - Breakeven and profit analysis
  - Scenario analysis (price moves, time decay, IV changes)
  - Risk/Reward analysis and position sizing
  - Liquidity assessment and trade checklist
  - Suggested trade plan
- **Enhanced Analysis Report**: Advanced report with:
  - Price history analysis (6 months)
  - Technical indicators (RSI, MACD, Bollinger Bands, ATR, EMAs)
  - Support & Resistance level detection
  - Trend verdict with signal alignment check
  - Comprehensive trade scoring (0-100%)
  - Final recommendation (Trade/Avoid/Paper Trade)

## Changelog

### v3.3.2 (January 2026)

- **NEW**: Opstra IV Configuration Panel in GUI
  - Session status display with validation
  - Browser-based session refresh
  - Manual cookie entry dialog
  - Skip Opstra option (use HV only)
  - Clear profile button for troubleshooting
- **NEW**: Dynamic Stock Management in GUI
  - Add custom stock symbols (comma-separated input)
  - Remove unchecked stocks from the list
  - Session-based changes (doesn't modify config.py)
- **FIX**: Multi-leg strategy analysis now works correctly
  - Handle strike formats like "60000/60400" for strangles/straddles
  - Extract leg1/leg2 data for proper analysis
- **NEW**: `set_skip_opstra()` function in `iv/provider.py`
- Improved: Error handling for numeric value conversion in analysis

### v3.3.1 (January 2026)

- **NEW**: PyQt6 GUI application with tabbed interface
- **NEW**: Alert Viewer tab for loading JSON/CSV alert files
- **NEW**: Integrated Basic and Enhanced Analysis reports
- **NEW**: Configurable time parameters for trend and HV calculations
- **NEW**: `run_scan_with_config()` function for programmatic scanning with custom config
- Improved: `set_trend_params()` and `set_hv_params()` for runtime configuration

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

*Package Version: 3.3.2 | Last Updated: January 2026*

