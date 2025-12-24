# Smart Options Screener v3.3 - Complete Documentation

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Architecture](#2-system-architecture)
3. [After-Hours Mode](#3-after-hours-mode)
4. [Symbol Universe Configuration](#4-symbol-universe-configuration)
5. [Implied Volatility (IV) Data Pipeline](#5-implied-volatility-iv-data-pipeline)
6. [Market Regime Classification](#6-market-regime-classification)
7. [Stock Selection Algorithms](#7-stock-selection-algorithms)
8. [Strike Price Selection Logic](#8-strike-price-selection-logic)
9. [Directional Bias Determination](#9-directional-bias-determination)
10. [Alert Generation Pipeline](#10-alert-generation-pipeline)
11. [Output and Logging](#11-output-and-logging)
12. [Configuration Parameters Reference](#12-configuration-parameters-reference)
13. [Usage Guide](#13-usage-guide)

---

## 1. Introduction

### Purpose

The Smart Options Screener v3.3 is an automated options scanning system designed to identify potential trading opportunities in the Indian derivatives market. The screener supports **6 options strategies**: Long Call, Long Put, Bull Call Spread, Bear Put Spread, Long Straddle, and Long Strangle. It analyzes both index options (NIFTY, BANKNIFTY) and stock options across 65+ F&O stocks.

### Key Features

- **6 Options Strategies**: Directional (Long Call/Put), Spreads (Bull Call/Bear Put), Volatility (Straddle/Strangle)
- **Real-time IV Data**: Integration with Opstra API for accurate Implied Volatility metrics
- **Historical Volatility Fallback**: Automatic fallback to calculated HV when Opstra data is unavailable
- **Tiered Stock Classification**: Different filtering thresholds for liquid vs. less liquid stocks
- **Technical Analysis Integration**: RSI and EMA-based trend bias for directional filtering
- **Market Regime Awareness**: VIX-based regime classification affecting strategy selection
- **After-Hours Mode**: Relaxed OI-only filters for scanning outside market hours
- **Smart Price Priority**: LTP-preferred pricing when market is closed
- **Multi-Leg Strategy Support**: Calculates max profit, max loss, breakeven, and reward/risk ratio
- **NSE API v3 Integration**: Uses latest NSE API endpoints for reliable option chain data
- **Comprehensive Logging**: CSV output with 33 data points per alert (including multi-leg fields)

### Data Sources

| Source | Data Provided | Usage |
|--------|---------------|-------|
| NSE Python Library | Option chain data (strikes, premiums, volume, OI) | Primary option data |
| Yahoo Finance | Underlying price, historical OHLC data | Spot price, RSI/EMA calculation |
| Opstra API | Implied Volatility, IV Percentile, IV Rank | Premium valuation |
| NSE India | India VIX | Market regime classification |

---

## 2. System Architecture

### Execution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MAIN JOB EXECUTION                           │
├─────────────────────────────────────────────────────────────────────┤
│  1. Check Market Hours (9:15 AM - 3:30 PM IST)                     │
│     ├─► OPEN: Use LIVE mode (strict volume/OI filters)             │
│     └─► CLOSED: Check ALLOW_AFTER_HOURS_SCAN                       │
│         ├─► True: Use AFTER-HOURS mode (relaxed OI-only filters)   │
│         └─► False: Exit early (no scan)                            │
│                                                                     │
│  2. Fetch India VIX → Determine Market Regime                       │
│  3. Scan Index Options (NIFTY, BANKNIFTY) with mode-aware filters  │
│  4. Scan Stock Options (68 stocks with 0.3s delay between each)    │
│  5. Deduplicate Alerts                                              │
│  6. Sort by Volume (descending)                                     │
│  7. Log to CSV and Console                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Operating Modes

| Mode | Market Status | Volume Required | OI Threshold | Price Priority |
|------|---------------|-----------------|--------------|----------------|
| **LIVE** | 9:15 AM - 3:30 PM | Yes (tier-based) | 1000-10000 | Ask first |
| **AFTER-HOURS** | Outside market hours | No | 500-5000 | LTP first |

### Scheduling

The screener runs automatically every **120 seconds** when started as a scheduled job.

---

## 3. After-Hours Mode

The screener now supports **After-Hours Mode** for scanning when the market is closed (before 9:15 AM, after 3:30 PM, weekends, and holidays). This mode uses relaxed filters since volume data is not available outside market hours.

### Mode Detection

```python
MARKET_START = time(9, 15)   # 9:15 AM IST
MARKET_END = time(15, 30)    # 3:30 PM IST

def is_market_hours():
    now = datetime.now(IST).time()
    return MARKET_START <= now <= MARKET_END
```

### Configuration

```python
# Enable/disable after-hours scanning
ALLOW_AFTER_HOURS_SCAN = True  # Set to False to skip scanning when market closed

# After-hours thresholds (relaxed - use OI only since volume is 0)
AFTER_HOURS_OI_THRESHOLD_STOCK = 500   # Minimum OI for stocks
AFTER_HOURS_OI_THRESHOLD_INDEX = 5000  # Minimum OI for indices
AFTER_HOURS_SPREAD_PCT = 0.30          # Allow wider spreads (30%)
```

### Filter Comparison: Live vs After-Hours

| Filter | Live Market | After-Hours |
|--------|-------------|-------------|
| **Volume Threshold** | TIER_1: 50, TIER_2: 20, TIER_3: 10 | 0 (not required) |
| **OI Threshold (Stocks)** | 1,000 | 500 |
| **OI Threshold (Indices)** | 10,000 | 5,000 |
| **Spread Limit (Stocks)** | 20% | 30% |
| **Spread Limit (Indices)** | 15% | 30% |
| **Price Priority** | Ask → LTP → Bid | LTP → Ask → Bid |

### Price Priority Logic

During market hours, the ask price is preferred (conservative entry). After hours, LTP (Last Traded Price) is preferred since bid/ask may be stale or zero:

```python
def get_option_price(opt, market_open=True):
    ask = opt.get('askprice') or 0
    bid = opt.get('bidprice') or 0
    ltp = opt.get('lastPrice') or 0
    
    if not market_open:
        # After hours: prefer LTP (more reliable)
        if ltp > 0: return ltp, 'ltp'
        elif ask > 0: return ask, 'ask'
        elif bid > 0: return bid, 'bid'
    else:
        # Market hours: prefer ask (conservative)
        if ask > 0: return ask, 'ask'
        elif ltp > 0: return ltp, 'ltp'
        elif bid > 0: return bid, 'bid'
    
    return 0, 'none'
```

### Spread Calculation

After hours, if bid/ask is unavailable, a lenient default spread is assumed:

```python
def get_option_spread(opt, price, market_open=True):
    ask = opt.get('askprice') or 0
    bid = opt.get('bidprice') or 0
    
    if ask > 0 and bid > 0:
        return (ask - bid) / ask
    
    # After hours: assume reasonable spread when data unavailable
    if not market_open:
        return 0.05  # 5% assumed
    return 0.10  # 10% default during market hours
```

### Console Output in After-Hours Mode

```
====================================================================================================
Starting scan at 2024-12-21 00:34:41
Market: CLOSED | Mode: AFTER-HOURS (relaxed filters) | Opstra: ✓ CONFIGURED
📋 After-Hours Mode: Using OI-only filters (OI >= 500 for stocks, >= 5000 for indices)
VIX=9.5 | Regime=LOW_VOL
====================================================================================================

--- Scanning Indices ---
Index NIFTY: Spot=25961 | IV=9.5% IVP=0% [OPSTRA] | Mode=AFTER-HOURS
  → 8 alerts generated

--- Scanning Stocks (68) ---
Stock RELIANCE: Spot=1565 | IV=13.2% IVP=0% [OPSTRA] | RSI=50 BULLISH [AFTER-HOURS]
  → 12 alerts generated
```

### Debug Logging

When `logger.setLevel(logging.DEBUG)` is enabled, detailed filter decisions are logged:

```
[SKIP] RELIANCE 1600 CE: oi=350 < 500 (after-hours)
[SKIP] RELIANCE 1620 CE: spread=0.35 > 0.30
[SKIP] TCS 3400 CE: price=0 (no quote)
```

---

## 4. Symbol Universe Configuration

### Index Symbols

The screener monitors 2 major indices:

| Index | Yahoo Symbol | Lot Size |
|-------|--------------|----------|
| NIFTY | ^NSEI | 25 |
| BANKNIFTY | ^NSEBANK | 15 |

### Stock Symbols

The screener monitors **65 unique F&O stocks** organized by sector:

#### Banking & Financial Services (18 stocks)
- **Large Banks**: HDFCBANK, ICICIBANK, AXISBANK, KOTAKBANK, SBIN
- **Mid-size Banks**: INDUSINDBK, FEDERALBNK, CANBK, PNB, BANKBARODA
- **NBFCs & Insurance**: BAJFINANCE, BAJAJFINSV, HDFCLIFE, SBILIFE, SBICARD, HDFCAMC, CHOLAFIN, MUTHOOTFIN

#### Information Technology (9 stocks)
- **Large Cap**: TCS, INFY, HCLTECH, WIPRO, TECHM, LTIM
- **Mid Cap**: PERSISTENT, COFORGE, MPHASIS

#### Automobiles (5 stocks)
- MARUTI, M&M, TATAMOTORS, HEROMOTOCO, EICHERMOT, BAJAJ-AUTO

#### Pharmaceuticals (6 stocks)
- SUNPHARMA, DRREDDY, CIPLA, AUROPHARMA, LUPIN, DIVISLAB, APOLLOHOSP

#### FMCG & Consumer (8 stocks)
- HINDUNILVR, ITC, BRITANNIA, NESTLEIND, TITAN, DABUR, PIDILITE, TATACONSUM, DMART, TRENT

#### Infrastructure & Engineering (2 stocks)
- LT, ASIANPAINT

#### Metals & Mining (5 stocks)
- TATASTEEL, JSWSTEEL, HINDALCO, JINDALSTEL, COALINDIA

#### Energy & Utilities (5 stocks)
- RELIANCE, ONGC, BPCL, TATAPOWER, NTPC, POWERGRID

#### Telecom (1 stock)
- BHARTIARTL

#### Conglomerates (2 stocks)
- ADANIPORTS, ADANIENT

#### Defence (2 stocks)
- BEL, HAL

### Stock Tier Classification

Stocks are classified into three tiers based on **liquidity and trading volume**. This classification determines the minimum volume/OI thresholds required for an alert to be generated.

#### TIER_1 (Most Liquid - 28 stocks)
**Volume Threshold: 50 contracts | OI Change Threshold: 0**

```
HDFCBANK, ICICIBANK, AXISBANK, KOTAKBANK, SBIN, RELIANCE, TCS, 
INFY, HCLTECH, WIPRO, TECHM, LTIM, MARUTI, M&M, LT, TATAMOTORS,
SUNPHARMA, DRREDDY, HINDUNILVR, ITC, BRITANNIA, TITAN, BHARTIARTL,
BAJFINANCE, BAJAJFINSV, HDFCLIFE, NTPC, POWERGRID
```

#### TIER_2 (Moderately Liquid - 25 stocks)
**Volume Threshold: 20 contracts | OI Change Threshold: 0**

```
INDUSINDBK, FEDERALBNK, CANBK, PNB, BANKBARODA, CHOLAFIN,
PERSISTENT, COFORGE, MPHASIS, TATASTEEL, HEROMOTOCO, EICHERMOT,
BAJAJ-AUTO, CIPLA, AUROPHARMA, LUPIN, DIVISLAB, APOLLOHOSP,
ADANIPORTS, ADANIENT, JSWSTEEL, HINDALCO, JINDALSTEL, BEL, HAL
```

#### TIER_3 (Less Liquid - Remaining stocks)
**Volume Threshold: 10 contracts | OI Change Threshold: 0**

```
DABUR, PIDILITE, ASIANPAINT, TATACONSUM, DMART, TRENT,
ONGC, BPCL, TATAPOWER, SBILIFE, SBICARD, HDFCAMC, MUTHOOTFIN,
NESTLEIND, COALINDIA
```

### Lot Sizes

The screener maintains a comprehensive lot size mapping for calculating total position cost:

| Symbol | Lot Size | Symbol | Lot Size | Symbol | Lot Size |
|--------|----------|--------|----------|--------|----------|
| NIFTY | 25 | RELIANCE | 250 | HDFCBANK | 550 |
| BANKNIFTY | 15 | TCS | 175 | ICICIBANK | 700 |
| INFY | 400 | SBIN | 750 | BHARTIARTL | 475 |
| TATAMOTORS | 1400 | ITC | 1600 | WIPRO | 1500 |

*Default lot size for unlisted symbols: 500*

---

## 5. Implied Volatility (IV) Data Pipeline

The screener uses a **three-tier fallback system** for obtaining IV data:

### Tier 1: Opstra API (Primary Source)

**Endpoint**: `https://opstra.definedge.com/api/ivcharts/{SYMBOL}`

#### Authentication
Opstra requires authenticated session cookies:
- `JSESSIONID`: Session identifier
- `DSESSIONID`: Domain session identifier

#### Data Extraction Algorithm

```python
# 1. Fetch IV chart data from Opstra API
response = requests.get(url, headers=headers, cookies=OPSTRA_COOKIES)
ivchart = response.json().get("ivchart", [])

# 2. Extract non-null IV values
iv_values = [point["ImpVol"] for point in ivchart if point["ImpVol"] > 0]

# 3. Use last 252 trading days (1 year window)
window = iv_values[-252:]
current_iv = window[-1]

# 4. Calculate IV Percentile
# Definition: Percentage of days where IV was LOWER than or equal to current
iv_percentile = (count of days where IV <= current_iv) / total_days × 100

# 5. Calculate IV Rank
# Definition: Where current IV stands between the min and max of the period
iv_rank = (current_iv - min_iv) / (max_iv - min_iv) × 100
```

#### IV Metrics Explained

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **IV** | Current implied volatility from ATM options | Higher = more expensive premiums |
| **IV Percentile** | `(days_IV_lower / total_days) × 100` | 80% means IV is higher than 80% of historical readings |
| **IV Rank** | `(current - min) / (max - min) × 100` | 80% means IV is 80% of the way from yearly low to high |

#### Caching
- **Cache Duration**: 300 seconds (5 minutes)
- **Cache Key**: Symbol name (uppercase)

### Tier 2: Historical Volatility (Fallback)

When Opstra data is unavailable, the screener calculates **Historical Volatility (HV)** as a proxy:

```python
# 1. Fetch 1 year of daily OHLC data from Yahoo Finance
hist = yf.Ticker(ticker).history(period="1y", interval="1d")

# 2. Calculate daily log returns
returns = ln(Close_today / Close_yesterday)

# 3. Calculate 30-day rolling standard deviation
rolling_std = returns.rolling(window=30).std()

# 4. Annualize the volatility
HV = rolling_std × √252 × 100  # √252 = annualization factor for trading days

# 5. Calculate HV Percentile and Rank (same formulas as IV)
```

**Important Note**: HV is NOT the same as IV. HV measures past price volatility while IV reflects market expectations. The screener clearly marks HV-based data with source = `hv_calculated`.

### Tier 3: Default Values (Last Resort)

When no volatility data is available:
- **IV**: 0
- **IV Percentile**: 50 (assumed middle of range)
- **IV Rank**: 50
- **Source**: `default`

---

## 6. Market Regime Classification

The screener determines the overall market volatility regime using **India VIX**:

### VIX Fetching

```python
# Source: NSE India API
url = "https://www.nseindia.com/api/allIndices"
# Extracts 'INDIA VIX' from the indices list
# Default fallback: 16.0 (if API fails)
```

### Regime Thresholds

| VIX Range | Regime | Characteristics |
|-----------|--------|-----------------|
| VIX < 14 | `LOW_VOL` | Cheap premiums, range-bound markets |
| 14 ≤ VIX ≤ 20 | `NORMAL_VOL` | Standard market conditions |
| VIX > 20 | `HIGH_VOL` | Expensive premiums, trending/volatile markets |

### Regime Impact on Strategy

While the current implementation logs the regime, it can be extended to:
- Prefer **buying options** in LOW_VOL regime (cheap premiums)
- Prefer **selling options** in HIGH_VOL regime (expensive premiums)
- Adjust strike selection based on expected movement

---

## 7. Stock Selection Algorithms

### Pre-Scan Filters

Before scanning any stock's option chain, the screener applies these filters:

#### 1. Minimum Price Filter
```python
MIN_STOCK_PRICE = 100

if spot < MIN_STOCK_PRICE:
    skip_stock()  # Avoid penny stocks with illiquid options
```

#### 2. IV-Based Filtering (Opstra data only)
```python
IV_VERY_HIGH = 85  # 85th percentile

if iv_source == 'opstra' and iv_percentile > IV_VERY_HIGH:
    skip_stock()  # Premiums too expensive for buying
```

**Rationale**: When IV Percentile > 85%, option premiums are historically expensive. Buying options in this environment has a statistical disadvantage as IV tends to mean-revert.

### Tier-Based Volume/OI Thresholds

The screener requires minimum activity levels based on stock tier:

| Tier | Volume Threshold | OI Threshold | Min OI |
|------|------------------|--------------|--------|
| TIER_1 | 50 | 0 | 1000 |
| TIER_2 | 20 | 0 | 1000 |
| TIER_3 | 10 | 0 | 1000 |
| INDEX | 500 | 0 | 10000 |

An option passes the activity filter if:
```python
(volume >= vol_threshold) OR (abs(oi_change) >= oi_threshold) OR (oi >= min_oi)
```

---

## 8. Strike Price Selection Logic

### ATM Strike Identification

The At-The-Money (ATM) strike is the strike price closest to the current spot price:

```python
def find_atm_strike(strikes, spot):
    return min(strikes, key=lambda x: abs(x - spot))
```

### Strike Range Calculation

The screener only analyzes strikes within a defined range around ATM:

```python
STRIKE_RANGE_MULTIPLIER = 5

# Calculate step size from option chain
step = strikes[1] - strikes[0]  # e.g., 50 for NIFTY, 100 for BANKNIFTY

# Maximum distance from ATM
max_distance = step × STRIKE_RANGE_MULTIPLIER

# Valid strikes
strikes_in_range = [s for s in strikes if abs(s - ATM) <= max_distance]
```

#### Example: NIFTY at 24,500

| Parameter | Value |
|-----------|-------|
| Spot | 24,500 |
| ATM Strike | 24,500 |
| Step Size | 50 |
| Max Distance | 50 × 5 = 250 |
| Valid Strikes | 24,250 to 24,750 |

This results in **11 strikes** being analyzed (5 below ATM + ATM + 5 above ATM).

### Spread Percentage Filter

The screener filters out illiquid options with wide bid-ask spreads:

```python
MAX_SPREAD_PCT = 0.15       # 15% for indices
MAX_SPREAD_PCT_STOCK = 0.20 # 20% for stocks

def get_option_spread(opt, price):
    if ask > 0 and bid > 0:
        return (ask - bid) / ask
    return 0.10  # Default assumption

if spread_pct > MAX_SPREAD_PCT_STOCK:
    skip_option()  # Too illiquid
```

### Premium Ratio Filter

Options with premiums too high relative to spot are excluded:

```python
MAX_PREMIUM_RATIO = 0.15        # 15% for indices
MAX_PREMIUM_RATIO_STOCK = 0.15  # 15% for stocks

if premium / spot > MAX_PREMIUM_RATIO:
    skip_option()  # Premium too expensive relative to underlying
```

### Moneyness Classification

Each option is classified based on its distance from spot:

```python
def get_moneyness(strike, spot, opt_type):
    pct_diff = (strike - spot) / spot × 100
    
    # CALL OPTIONS
    if opt_type == "CE":
        if pct_diff < -2%: return "ITM"   # Strike below spot
        if pct_diff > +2%: return "OTM"   # Strike above spot
        else: return "ATM"                 # Within ±2%
    
    # PUT OPTIONS
    if opt_type == "PE":
        if pct_diff > +2%: return "ITM"   # Strike above spot
        if pct_diff < -2%: return "OTM"   # Strike below spot
        else: return "ATM"                 # Within ±2%
```

---

## 9. Directional Bias Determination

The screener uses technical analysis to determine which direction to scan:

### RSI Calculation (14-Period)

```python
def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi
```

### RSI Thresholds

```python
RSI_OVERSOLD = 45   # Below this, consider bullish reversal
RSI_OVERBOUGHT = 55 # Above this, consider bearish reversal
```

### EMA-20 Trend Determination

```python
def determine_bias(current_price, ema20):
    if current_price > ema20 × 1.01:  # +1% above EMA
        return "BULLISH"
    elif current_price < ema20 × 0.99:  # -1% below EMA
        return "BEARISH"
    else:
        return "NEUTRAL"
```

### Directional Scanning Rules

| Bias | RSI | Scan Calls? | Scan Puts? |
|------|-----|-------------|------------|
| BULLISH | Any | ✓ Yes | ✗ No |
| BEARISH | Any | ✗ No | ✓ Yes |
| NEUTRAL | Any | ✓ Yes | ✓ Yes |
| Any | < 45 | ✓ Yes | - |
| Any | > 55 | - | ✓ Yes |

**Complete Logic**:
```python
scan_calls = (bias in ["BULLISH", "NEUTRAL"]) OR (rsi < RSI_OVERSOLD)
scan_puts = (bias in ["BEARISH", "NEUTRAL"]) OR (rsi > RSI_OVERBOUGHT)
```

This means:
- **Bullish** or **Neutral** bias → Scan Calls
- **Bearish** or **Neutral** bias → Scan Puts
- **Oversold** RSI (< 45) → Also scan Calls (reversal opportunity)
- **Overbought** RSI (> 55) → Also scan Puts (reversal opportunity)

---

## 10. Alert Generation Pipeline

### Complete Filtering Flowchart

```
START: Job Execution
    │
    ├─► Check Market Hours
    │   ├─► OPEN → Use LIVE mode (strict filters)
    │   └─► CLOSED → Check ALLOW_AFTER_HOURS_SCAN
    │       ├─► False → Exit (skip scan)
    │       └─► True → Use AFTER-HOURS mode (relaxed filters)
    │
    └─► FOR each symbol in watchlist:
            │
            ├─► Get Spot Price (Yahoo Finance)
            │   └─► FAIL → Skip symbol
            │
            ├─► Check MIN_STOCK_PRICE (100)
            │   └─► FAIL → Skip symbol
            │
            ├─► Get IV Data (Opstra → HV → Default)
            │
            ├─► Check IV_VERY_HIGH (85%)
            │   └─► FAIL (Opstra only) → Skip symbol
            │
            ├─► Get Option Chain (NSE Python)
            │   └─► FAIL → Skip symbol
            │
            ├─► Calculate Technical Indicators (RSI, EMA20)
            │
            ├─► Determine Directional Bias
            │
            ├─► Calculate Strike Range (ATM ± 5×step)
            │
            └─► FOR each strike in range:
                    │
                    ├─► Get Option Data (CE/PE)
                    │
                    ├─► Get Price (mode-dependent priority)
                    │   ├─► LIVE: Ask → LTP → Bid
                    │   └─► AFTER-HOURS: LTP → Ask → Bid
                    │   └─► price <= 0 → Skip (debug logged)
                    │
                    ├─► Check Volume/OI Threshold (mode-dependent)
                    │   ├─► LIVE: vol >= tier_thresh OR oi >= min_oi
                    │   └─► AFTER-HOURS: oi >= AFTER_HOURS_OI_THRESHOLD
                    │   └─► FAIL → Skip (debug logged)
                    │
                    ├─► Check Spread Percentage (mode-dependent)
                    │   ├─► LIVE: 15-20% max
                    │   └─► AFTER-HOURS: 30% max
                    │   └─► FAIL → Skip (debug logged)
                    │
                    ├─► Check Premium Ratio (15% max)
                    │   └─► FAIL → Skip (debug logged)
                    │
                    └─► PASS → Generate Alert
```

### Option Price Priority

The screener uses market-status-dependent priority for determining option price:

```python
def get_option_price(opt, market_open=True):
    ask = opt.get('askprice') or 0
    bid = opt.get('bidprice') or 0
    ltp = opt.get('lastPrice') or 0
    
    if not market_open:
        # AFTER-HOURS: Prefer LTP (bid/ask may be stale or zero)
        if ltp > 0: return ltp, 'ltp'
        elif ask > 0: return ask, 'ask'
        elif bid > 0: return bid, 'bid'
    else:
        # LIVE MARKET: Prefer Ask (conservative entry price)
        if ask > 0: return ask, 'ask'
        elif ltp > 0: return ltp, 'ltp'
        elif bid > 0: return bid, 'bid'
    
    return 0, 'none'
```

| Market Status | Priority Order | Rationale |
|---------------|----------------|-----------|
| **LIVE** | Ask → LTP → Bid | Ask is what you'd pay to enter |
| **AFTER-HOURS** | LTP → Ask → Bid | LTP is from last trading session |

### Alert Data Structure

Each alert contains 24 data points:

| Field | Description | Example |
|-------|-------------|---------|
| `timestamp` | Alert generation time | 2024-01-15 10:30:45 |
| `symbol` | Underlying symbol | RELIANCE |
| `instrument_type` | INDEX or STOCK | STOCK |
| `strategy` | Long Call or Long Put | Long Call |
| `strike` | Strike price | 2500 |
| `premium` | Option price | 45.50 |
| `price_source` | ask/ltp/bid | ask |
| `spot` | Underlying price | 2485.30 |
| `volume` | Contracts traded today | 1250 |
| `open_interest` | Total open contracts | 45000 |
| `oi_change` | Change in OI today | +5000 |
| `iv` | Implied Volatility | 28.5 |
| `iv_percentile` | IV Percentile | 65 |
| `iv_rank` | IV Rank | 55 |
| `iv_source` | opstra/hv_calculated/default | opstra |
| `market_regime` | VIX-based regime | NORMAL_VOL |
| `rsi` | 14-period RSI | 52.3 |
| `tier` | Stock tier | TIER_1 |
| `moneyness` | ITM/ATM/OTM | ATM |
| `expiry` | Expiry date | 25-Jan-2024 |
| `days_to_expiry` | Days until expiry | 10 |
| `lot_size` | Contract lot size | 250 |
| `total_cost` | premium × lot_size | 11,375 |
| `breakeven` | Strike ± Premium | 2545.50 |
| `distance_from_spot` | Percentage distance | +0.6% OTM |

### Breakeven Calculation

```python
def calculate_breakeven(strike, premium, opt_type):
    if opt_type == "CE":  # Call
        return strike + premium  # Need price above this to profit
    else:  # Put
        return strike - premium  # Need price below this to profit
```

### Distance from Spot Calculation

```python
def calculate_distance_from_spot(strike, spot, opt_type):
    diff = strike - spot
    pct = abs(diff) / spot × 100
    
    # CALL: Strike > Spot = OTM, Strike < Spot = ITM
    if opt_type == "CE":
        if diff > 0: return f"+{pct:.1f}% OTM"
        elif diff < 0: return f"-{pct:.1f}% ITM"
        else: return "ATM"
    
    # PUT: Strike < Spot = OTM, Strike > Spot = ITM
    else:
        if diff < 0: return f"-{pct:.1f}% OTM"
        elif diff > 0: return f"+{pct:.1f}% ITM"
        else: return "ATM"
```

---

## 11. Output and Logging

### CSV Output File

**Filename**: `new_screener_options_scan_log_v3_3.csv`

**Columns** (24 total):
```
Timestamp, Symbol, Type, Strategy, Strike, Premium, PriceSource,
Spot, Volume, OI, OI_Change, IV, IV_Percentile, IV_Rank, IV_Source,
Market_Regime, RSI, Tier, Moneyness, Expiry, DaysToExpiry,
LotSize, TotalCost, Breakeven, DistanceFromSpot
```

### Console Output

The screener provides detailed console logging:

#### Scan Progress
```
Stock RELIANCE: Spot=2485 | IV=28.5% IVP=65% [OPSTRA] | RSI=52 NEUTRAL
  → 8 alerts generated
```

#### IV Source Warnings
```
⚠️ Skipping TATASTEEL: IV Percentile 87% > 85% (expensive premiums)
```

#### Top 15 Alerts Summary
```
====================================================
TOP 15 ALERTS BY VOLUME
====================================================
#   SYMBOL     TYPE   MON  STRIKE     PREMIUM   VOL     COST        BREAKEVEN  DTE  DISTANCE     IV_SRC
----------------------------------------------------
1   NIFTY      Call   ATM  24500      ₹125.50   15000   ₹3137.50    24625.50   3    +0.2% OTM    OPS
2   BANKNIFTY  Put    OTM  51000      ₹85.25    12500   ₹1278.75    50914.75   3    -2.1% OTM    OPS
...
```

#### IV Source Summary
```
IV Data Sources: Opstra=45 | HV Calculated=18 | Default=2
⚠️  WARNING: 2 alerts have no reliable IV data
```

### Log File

**Filename**: `screener.log`
- **Max Size**: 5 MB
- **Backup Count**: 3 (rotates to screener.log.1, .2, .3)
- **Format**: `YYYY-MM-DD HH:MM:SS LEVEL NAME - MESSAGE`

### Alert Deduplication

Before logging, alerts are deduplicated by unique key:

```python
key = (strategy, symbol, strike)
# Only first occurrence of each unique combination is kept
```

Alerts are then sorted by **volume (descending)** to prioritize the most liquid opportunities.

---

## 12. Configuration Parameters Reference

### Core Thresholds (Tuned for Realistic Alerts)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_STOCK_PRICE` | 100 | Minimum underlying price to scan |
| `STRIKE_RANGE_MULTIPLIER` | 3 | Number of steps above/below ATM to scan |
| `MAX_SPREAD_PCT` | 0.10 | Max bid-ask spread for indices (10%) |
| `MAX_SPREAD_PCT_STOCK` | 0.15 | Max bid-ask spread for stocks (15%) |
| `MAX_PREMIUM_RATIO` | 0.08 | Max premium/spot ratio for indices (8%) |
| `MAX_PREMIUM_RATIO_STOCK` | 0.10 | Max premium/spot ratio for stocks (10%) |
| `MIN_PREMIUM` | 5 | Minimum premium for stocks (₹5) |
| `MIN_PREMIUM_INDEX` | 10 | Minimum premium for indices (₹10) |

### After-Hours Mode Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ALLOW_AFTER_HOURS_SCAN` | True | Enable scanning when market is closed |
| `AFTER_HOURS_OI_THRESHOLD_STOCK` | 8,000 | Minimum OI for stocks after hours |
| `AFTER_HOURS_OI_THRESHOLD_INDEX` | 75,000 | Minimum OI for indices after hours |
| `AFTER_HOURS_SPREAD_PCT` | 0.20 | Max spread allowed after hours (20%) |

### Volume/OI Thresholds

#### Live Market Mode

| Parameter | Index | TIER_1 | TIER_2 | TIER_3 |
|-----------|-------|--------|--------|--------|
| Volume Threshold | 10,000 | 1,000 | 500 | 200 |
| OI Threshold | 50,000 | 5,000 | 2,000 | 1,000 |
| Spread Limit | 10% | 15% | 15% | 15% |

#### After-Hours Mode

| Parameter | Index | All Stock Tiers |
|-----------|-------|-----------------|
| Volume Threshold | 0 (not required) | 0 (not required) |
| Min OI | 75,000 | 8,000 |
| Spread Limit | 20% | 20% |
| Price Priority | LTP first | LTP first |

### Technical Analysis Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RSI_OVERSOLD` | 40 | RSI below this triggers bullish bias |
| `RSI_OVERBOUGHT` | 60 | RSI above this triggers bearish bias |
| RSI Period | 14 | Days for RSI calculation |
| EMA Period | 20 | Days for trend EMA |
| EMA Buffer | ±1% | Neutral zone around EMA |

### IV Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `IV_VERY_HIGH` | 80 | Skip buying when IVP above this |
| `IV_HIGH` | 65 | Caution zone (logged, not filtered) |
| `IV_LOW` | 30 | Cheap premiums zone |
| `IV_CACHE_DURATION` | 300 | Seconds to cache Opstra data |

### Spread Strategy Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `SPREAD_WIDTH_STOCKS` | 1 | Strike width for stock spreads |
| `SPREAD_WIDTH_INDEX` | 2 | Strike width for index spreads |
| `IV_PERCENTILE_LOW` | 35 | Trigger for Long Straddle |
| `IV_PERCENTILE_VERY_LOW` | 25 | Trigger for Long Strangle |
| `MIN_SPREAD_REWARD_RATIO` | 0.50 | Minimum reward/risk ratio (50%) |
| `MAX_STRADDLE_COST_PCT` | 0.04 | Max 4% of spot for straddle cost |
| `MAX_STRANGLE_COST_PCT` | 0.025 | Max 2.5% of spot for strangle cost |
| `MIN_DAYS_TO_EXPIRY_VOLATILITY` | 5 | Min DTE for volatility plays |
| `MIN_OI_PER_LEG_STOCK` | 500 | Min OI per leg for stock spreads |
| `MIN_OI_PER_LEG_INDEX` | 5,000 | Min OI per leg for index spreads |

### Market Regime Thresholds

| Parameter | Value | Resulting Regime |
|-----------|-------|------------------|
| VIX < | 14 | LOW_VOL |
| VIX <= | 20 | NORMAL_VOL |
| VIX > | 20 | HIGH_VOL |

### Timing Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MARKET_START` | 09:15 | Market open time (IST) |
| `MARKET_END` | 15:30 | Market close time (IST) |
| Scan Interval | 120s | Time between scans |
| Stock Scan Delay | 0.3s | Delay between stocks (rate limiting) |

---

## 12.1 Options Strategies Supported

### Strategy Overview

| Strategy | Direction | Risk | Reward | IV Preference | Trigger |
|----------|-----------|------|--------|---------------|---------|
| Long Call | Bullish | Limited | Unlimited | Low IV | RSI < 40 or Uptrend |
| Long Put | Bearish | Limited | High | Low IV | RSI > 60 or Downtrend |
| Bull Call Spread | Bullish | Limited | Limited | Low-Medium IV | Bullish/Neutral bias |
| Bear Put Spread | Bearish | Limited | Limited | Low-Medium IV | Bearish/Neutral bias |
| Long Straddle | Neutral | Limited | Unlimited | Low IV (< 35%) | Big move expected |
| Long Strangle | Neutral | Limited | Unlimited | Very Low IV (< 25%) | Big move expected |

### Strategy Details

#### Bull Call Spread
- **Structure**: Buy ATM Call + Sell OTM Call (same expiry)
- **When**: Moderately bullish, want defined risk
- **Max Profit**: (Sell Strike - Buy Strike) - Net Debit
- **Max Loss**: Net Debit paid
- **Breakeven**: Buy Strike + Net Debit

#### Bear Put Spread
- **Structure**: Buy ATM Put + Sell OTM Put (same expiry)
- **When**: Moderately bearish, want defined risk
- **Max Profit**: (Buy Strike - Sell Strike) - Net Debit
- **Max Loss**: Net Debit paid
- **Breakeven**: Buy Strike - Net Debit

#### Long Straddle
- **Structure**: Buy ATM Call + Buy ATM Put (same strike, same expiry)
- **When**: Expecting big move, direction unknown, IV is low
- **Max Profit**: Unlimited (either direction)
- **Max Loss**: Total premium paid
- **Breakeven**: Strike ± Total Premium

#### Long Strangle
- **Structure**: Buy OTM Call + Buy OTM Put (different strikes, same expiry)
- **When**: Expecting big move, want cheaper entry, IV is very low
- **Max Profit**: Unlimited (either direction)
- **Max Loss**: Total premium paid
- **Breakeven**: Call Strike + Premium (up) / Put Strike - Premium (down)

---

## 13. Usage Guide

### Basic Execution

```bash
python new_screener_v_3.3.py
```

### Configuring Opstra Cookies

For accurate IV data, configure Opstra session cookies:

1. **Login to Opstra**: Visit https://opstra.definedge.com and login
2. **Get Cookies**: Press F12 → Application → Cookies → opstra.definedge.com
3. **Update Code**: 

```python
OPSTRA_COOKIES = {
    'JSESSIONID': 'your_jsessionid_here',
    'DSESSIONID': 'your_dsessionid_here',
    '_ga': '...',
    '_ga_6D0ZQ437SD': '...'
}
```

Or use the helper function at runtime:
```python
set_opstra_cookies('your_jsessionid', 'your_dsessionid')
```

### Interpreting Alerts

#### High-Confidence Alert Characteristics
- **IV Source**: `opstra` (reliable IV data)
- **IV Percentile**: < 50% (cheap premiums)
- **Volume**: High relative to tier threshold
- **Spread**: Low (< 10%)
- **Moneyness**: ATM or slightly OTM

#### Caution Indicators
- **IV Source**: `default` (no reliable data)
- **IV Percentile**: > 70% (expensive premiums)
- **Volume**: Near minimum threshold
- **Price Source**: `bid` (may have liquidity issues)

### Customizing the Screener

#### Adding New Stocks
```python
STOCK_SYMBOLS.append("NEWSTOCK")
LOT_SIZES["NEWSTOCK"] = 100
STOCK_TIERS['TIER_2'].append("NEWSTOCK")  # Choose appropriate tier
```

#### Adjusting Sensitivity
```python
# More alerts (looser filters)
VOLUME_THRESHOLDS = {'TIER_1': 25, 'TIER_2': 10, 'TIER_3': 5}
MAX_SPREAD_PCT_STOCK = 0.25

# Fewer alerts (stricter filters)
VOLUME_THRESHOLDS = {'TIER_1': 100, 'TIER_2': 50, 'TIER_3': 25}
MAX_SPREAD_PCT_STOCK = 0.15
```

### Enabling Debug Logging

To see detailed filter decisions (why options are being skipped), enable debug logging:

```python
# At the top of the file, change:
logger.setLevel(logging.INFO)

# To:
logger.setLevel(logging.DEBUG)
```

This will show messages like:
```
[SKIP] RELIANCE 1600 CE: oi=350 < 500 (after-hours)
[SKIP] RELIANCE 1620 CE: spread=0.35 > 0.30
[SKIP] TCS 3400 CE: price=0 (no quote)
[SKIP] NIFTY 24000 CE: vol=10 < 500 and oi=5000 < 10000
```

### Configuring After-Hours Mode

To control after-hours scanning behavior:

```python
# Enable after-hours scanning (default)
ALLOW_AFTER_HOURS_SCAN = True

# Disable after-hours scanning
ALLOW_AFTER_HOURS_SCAN = False

# Adjust after-hours thresholds
AFTER_HOURS_OI_THRESHOLD_STOCK = 500   # Lower = more alerts
AFTER_HOURS_OI_THRESHOLD_INDEX = 5000  # Lower = more alerts
AFTER_HOURS_SPREAD_PCT = 0.30          # Higher = more alerts
```

### Telegram Integration

The screener includes Telegram bot configuration for sending alerts:

```python
TELEGRAM_BOT_TOKEN = "your_bot_token"
TELEGRAM_CHAT_ID = "@your_channel"
```

*Note: Telegram sending functionality needs to be implemented in the alert logging section.*

---

## Appendix: Algorithm Summary

### Stock Alert Generation Formula

An alert is generated when ALL conditions are met:

#### Live Market Mode
```
ALERT = (
    spot >= MIN_STOCK_PRICE
    AND (iv_source != 'opstra' OR iv_percentile <= IV_VERY_HIGH)
    AND option_chain_available
    AND strike IN valid_range
    AND price > 0  (priority: ask → ltp → bid)
    AND (volume >= tier_threshold OR abs(oi_change) >= tier_oi_threshold OR oi >= 1000)
    AND spread_pct <= MAX_SPREAD_PCT_STOCK (20%)
    AND premium_ratio <= MAX_PREMIUM_RATIO_STOCK (15%)
    AND directional_bias_allows_option_type
)
```

#### After-Hours Mode
```
ALERT = (
    ALLOW_AFTER_HOURS_SCAN == True
    AND spot >= MIN_STOCK_PRICE
    AND (iv_source != 'opstra' OR iv_percentile <= IV_VERY_HIGH)
    AND option_chain_available
    AND strike IN valid_range
    AND price > 0  (priority: ltp → ask → bid)
    AND oi >= AFTER_HOURS_OI_THRESHOLD_STOCK (500)
    AND spread_pct <= AFTER_HOURS_SPREAD_PCT (30%)
    AND premium_ratio <= MAX_PREMIUM_RATIO_STOCK (15%)
    AND directional_bias_allows_option_type
)
```

### Index Alert Generation Formula

#### Live Market Mode
```
ALERT = (
    spot_available
    AND option_chain_available
    AND strike IN valid_range
    AND price > 0  (priority: ask → ltp → bid)
    AND (volume >= VOLUME_THRESHOLD_INDEX (500) OR oi >= 10000)
    AND spread_pct <= MAX_SPREAD_PCT (15%)
    AND premium_ratio <= MAX_PREMIUM_RATIO (15%)
)
```

#### After-Hours Mode
```
ALERT = (
    ALLOW_AFTER_HOURS_SCAN == True
    AND spot_available
    AND option_chain_available
    AND strike IN valid_range
    AND price > 0  (priority: ltp → ask → bid)
    AND oi >= AFTER_HOURS_OI_THRESHOLD_INDEX (5000)
    AND spread_pct <= AFTER_HOURS_SPREAD_PCT (30%)
    AND premium_ratio <= MAX_PREMIUM_RATIO (15%)
)
```

---

## Changelog

### v3.3.1 (December 2024)
- **Added After-Hours Mode**: Screener can now run outside market hours with relaxed OI-only filters
- **Smart Price Priority**: LTP is preferred over ask/bid when market is closed
- **Configurable After-Hours Thresholds**: New parameters for after-hours OI and spread limits
- **Debug Logging**: Added detailed filter decision logging for troubleshooting
- **Market Hours Gate**: Optional `ALLOW_AFTER_HOURS_SCAN` flag to enable/disable after-hours scanning

### v3.3.0 (December 2024)
- Initial release with Opstra IV integration
- Historical Volatility fallback
- Tiered stock classification
- RSI/EMA directional bias

---

*Document Version: 3.3.1 | Last Updated: December 2024*

