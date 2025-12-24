# Smart Options Screener v3.2

A Python-based options screener for the Indian stock market (NSE) that identifies potential buying opportunities for calls, puts, and straddles based on technical indicators, IV analysis, and market regime detection.

## Overview

This screener is designed for **options buyers only** (no writing/selling strategies). It scans NIFTY, BANKNIFTY, and 60+ F&O stocks to find options with:

- Favorable IV (Implied Volatility) conditions
- Adequate liquidity (volume and open interest)
- Reasonable bid-ask spreads
- Technical confirmation (RSI, EMA trend bias)

### Key Features

| Feature | Description |
|---------|-------------|
| **LTP Fallback** | Works after market hours using Last Traded Price when bid/ask is unavailable |
| **Market Regime Detection** | Adjusts behavior based on VIX levels (Low/Normal/High volatility) |
| **Tiered Stock Classification** | Different thresholds for Tier 1 (liquid), Tier 2, and Tier 3 stocks |
| **Technical Indicators** | RSI and EMA-based trend detection for directional bias |
| **Multi-Strategy Scanning** | Long Calls, Long Puts, and Long Straddles |
| **CSV Logging** | All signals logged for analysis and record-keeping |
| **Days to Expiry** | Shows remaining days until option expiration |
| **Lot Size** | Displays F&O lot size for each symbol |
| **Total Cost** | Calculates premium × lot size = capital required |
| **Breakeven Price** | Shows the price underlying must reach to profit |
| **Distance from Spot** | Shows how far strike is from current price (%) |

---

## Files Included

| File | Description |
|------|-------------|
| `new_screener_v3.2.py` | Main screener script with enhanced output (recommended) |
| `new_screener_v3.1.py` | Previous version without enhanced fields |
| `diagnostic_screener.py` | Debugging tool to analyze why options are filtered |
| `README.md` | This documentation file |

---

## Requirements

### Python Version
- Python 3.8 or higher

### Dependencies

```bash
pip install yfinance pandas numpy requests pytz schedule nsepython
```

### Optional Dependencies

```bash
# For Telegram alerts
pip install python-telegram-bot

# For IV data from Opstra (optional)
# Requires manual cookie setup - see Configuration section
```

---

## Installation

1. **Download** the script files to your local machine

2. **Install dependencies**:
   ```bash
   pip install yfinance pandas numpy requests pytz schedule nsepython
   ```

3. **Run the screener**:
   ```bash
   python new_screener_v3.1.py
   ```

---

## How It Works

### Scanning Flow

```
1. Fetch India VIX → Determine Market Regime
                          ↓
2. For each stock/index:
   ├── Fetch spot price (yfinance)
   ├── Compute trend indicators (RSI, EMA bias)
   ├── Fetch option chain (NSE)
   ├── Parse strikes near ATM
   └── Apply filters → Generate alerts
                          ↓
3. Deduplicate & sort alerts
                          ↓
4. Log to CSV + Display results
```

### Price Selection Logic

The screener uses a **fallback mechanism** for option prices:

```
Priority 1: Ask Price (askprice)  → Best for live market
Priority 2: Last Traded Price (lastPrice) → Used after market hours
Priority 3: Bid Price (bidprice)  → Last resort
```

This ensures the screener works both **during and after market hours**.

### Filter Logic

An option passes if it meets **ALL** of these conditions:

| Filter | Condition | Purpose |
|--------|-----------|---------|
| **Price** | price > 0 | Must have a valid price |
| **Liquidity** | volume ≥ threshold OR \|OI change\| ≥ threshold OR OI ≥ 1000 | Ensures tradeable options |
| **Spread** | (ask - bid) / ask ≤ 20% | Avoids illiquid options with wide spreads |
| **Premium Ratio** | premium / spot ≤ 15% | Avoids extremely expensive options |

---

## Configuration

### Tunable Parameters

Edit these values in the script to adjust sensitivity:

#### Liquidity Thresholds (Lower = More Results)

```python
# Volume thresholds by tier
VOLUME_THRESHOLDS = {
    'TIER_1': 50,   # Large caps (RELIANCE, HDFCBANK, etc.)
    'TIER_2': 20,   # Mid caps
    'TIER_3': 10    # Smaller F&O stocks
}

# OI change thresholds (set to 0 to accept any change)
OI_CHANGE_THRESHOLDS = {
    'TIER_1': 0,
    'TIER_2': 0,
    'TIER_3': 0
}

# Index thresholds
VOLUME_THRESHOLD_INDEX = 500
OI_CHANGE_THRESHOLD_INDEX = 0
```

#### Strike Range

```python
STRIKE_RANGE_MULTIPLIER = 5  # Scans 5 strikes above and below ATM
```

#### Spread & Premium Limits

```python
MAX_SPREAD_PCT = 0.15         # 15% max spread for indices
MAX_SPREAD_PCT_STOCK = 0.20   # 20% max spread for stocks
MAX_PREMIUM_RATIO = 0.15      # Premium can be up to 15% of spot
MAX_PREMIUM_RATIO_STOCK = 0.15
```

#### Minimum Stock Price

```python
MIN_STOCK_PRICE = 100  # Skip stocks trading below ₹100
```

#### Technical Indicator Thresholds

```python
RSI_OVERSOLD = 45    # RSI below this → scan calls (bounce expected)
RSI_OVERBOUGHT = 55  # RSI above this → scan puts (pullback expected)
```

### Stock Tiers

Stocks are classified into tiers based on liquidity:

| Tier | Examples | Characteristics |
|------|----------|-----------------|
| **TIER_1** | RELIANCE, HDFCBANK, TCS, INFY, SBIN | Most liquid, tightest spreads |
| **TIER_2** | TATASTEEL, CIPLA, ADANIPORTS, BEL | Moderately liquid |
| **TIER_3** | DABUR, ONGC, SBILIFE, DMART | Less liquid, wider spreads |

### Adding/Removing Stocks

Edit the `STOCK_SYMBOLS` list:

```python
STOCK_SYMBOLS = list(set([
    "RELIANCE", "HDFCBANK", "TCS",  # Add your stocks here
    # ... more stocks
]))
```

Also update `STOCK_TIERS` to classify new stocks appropriately.

---

## Lot Sizes Reference

The screener includes lot sizes for all major F&O stocks. Here are some common ones:

### Indices
| Symbol | Lot Size | Approx. Margin (₹) |
|--------|----------|-------------------|
| NIFTY | 25 | 1,50,000 |
| BANKNIFTY | 15 | 1,80,000 |

### Popular Stocks
| Symbol | Lot Size | Approx. Value (₹) |
|--------|----------|------------------|
| RELIANCE | 250 | 3,50,000 |
| HDFCBANK | 550 | 9,00,000 |
| TCS | 175 | 6,00,000 |
| INFY | 400 | 7,00,000 |
| SBIN | 750 | 6,00,000 |
| TATAMOTORS | 1400 | 12,00,000 |
| ITC | 1600 | 7,00,000 |
| BAJFINANCE | 125 | 9,00,000 |

### Updating Lot Sizes

Lot sizes change periodically. To update:

1. Visit [NSE F&O Lot Sizes](https://www.nseindia.com/products/content/derivatives/equities/fo_underlying_home.htm)
2. Edit the `LOT_SIZES` dictionary in the script:

```python
LOT_SIZES = {
    "NIFTY": 25,
    "RELIANCE": 250,
    # Add or update lot sizes here
}
```

---

## Usage

### Basic Run

```bash
python new_screener_v3.1.py
```

### What You'll See

```
============================================================
Starting scan at 2025-01-15 10:30:00
Market hours: YES
VIX=14.5 | Regime=NORMAL_VOL
============================================================

--- Scanning Indices ---
Index NIFTY: Spot: 24500.00
Index NIFTY: ATM=24500, 11 strikes in range
Index NIFTY: 18 alerts generated

--- Scanning Stocks (65) ---
Stock RELIANCE: Spot: 2850.50
Stock RELIANCE: Trend data: {'bias': 'BULLISH', 'rsi': 58.2}, IV data: {...}
Stock RELIANCE: ATM=2850, 11 strikes in range, 11 calls, 11 puts
Stock RELIANCE: 8/22 options passed filters, 8 alerts
Progress: 20/65 stocks...
...

============================================================
SCAN COMPLETE: 156 unique alerts
============================================================

Top 15 by Volume:
   1. NIFTY Long Call ATM @ 24500 | ₹185.50 (ask) | Vol=125000 OI=5200000
   2. BANKNIFTY Long Put ATM @ 52000 | ₹320.00 (ask) | Vol=98000 OI=3100000
   3. RELIANCE Long Call ITM @ 2800 | ₹95.25 (ltp) | Vol=15000 OI=450000
   ...
```

### Sample Output (v3.2)

```
================================================================================
TOP 15 ALERTS BY VOLUME
================================================================================

#    SYMBOL       STRATEGY   MON   STRIKE     PREMIUM    VOLUME   TOTAL COST   BREAKEVEN  DTE    DISTANCE
----------------------------------------------------------------------------------------------------
1    NIFTY        Put        OTM   23500      ₹8.05      7408     ₹201         23491.95   2      -3.5% OTM
2    NIFTY        Put        OTM   22900      ₹6.40      6356     ₹160         22893.60   2      -5.9% OTM
3    BANKNIFTY    Put        OTM   52000      ₹320.00    1200     ₹4800        51680.00   2      -2.1% OTM
4    RELIANCE     Call       ATM   1460       ₹25.50     850      ₹6375        1485.50    9      +0.5% OTM
5    HDFCBANK     Put        ITM   1750       ₹45.00     620      ₹24750       1705.00    9      +1.2% ITM
----------------------------------------------------------------------------------------------------

SUMMARY: 156 Alerts | Calls: 45 | Puts: 111 | ATM: 32 | OTM: 98 | ITM: 26
```

### Understanding Each Column

| Column | Description | Example |
|--------|-------------|---------|
| **#** | Rank by volume | 1, 2, 3... |
| **SYMBOL** | Stock/Index name | NIFTY, RELIANCE |
| **STRATEGY** | Call or Put | Call, Put |
| **MON** | Moneyness | ATM, OTM, ITM |
| **STRIKE** | Strike price | 23500 |
| **PREMIUM** | Option price | ₹8.05 |
| **VOLUME** | Contracts traded today | 7408 |
| **TOTAL COST** | Premium × Lot Size | ₹201 |
| **BREAKEVEN** | Price needed to profit | 23491.95 |
| **DTE** | Days to Expiry | 2 |
| **DISTANCE** | How far from spot | -3.5% OTM |

### New Fields Explained

#### Days to Expiry (DTE)
- Shows how many days until the option expires
- **Weekly options**: Usually 0-7 days
- **Monthly options**: Up to 30+ days
- **Rule of thumb**: Avoid DTE < 3 unless you're day trading

#### Total Cost
- **Formula**: Premium × Lot Size
- This is the **maximum you can lose** when buying options
- Example: NIFTY lot = 25, Premium = ₹8.05 → Total Cost = ₹201

#### Breakeven Price
- **For Calls**: Strike + Premium (stock must rise above this)
- **For Puts**: Strike - Premium (stock must fall below this)
- Example: NIFTY 23500 PE @ ₹8.05 → Breakeven = 23491.95

#### Distance from Spot
- Shows how far the strike is from current market price
- **Format**: `±X.X% OTM/ITM/ATM`
- **Negative for Puts OTM**: Strike below spot (e.g., -3.5% OTM)
- **Positive for Calls OTM**: Strike above spot (e.g., +2.0% OTM)

### Price Source Indicators

| Source | Meaning |
|--------|---------|
| `(ask)` | Live ask price (best during market hours) |
| `(ltp)` | Last Traded Price (used after market close) |
| `(bid)` | Bid price (fallback) |

---

## Output Files

### CSV Log File

The script creates `options_scan_log.csv` with these columns:

| Column | Description |
|--------|-------------|
| Timestamp | When the alert was generated |
| Symbol | Stock/Index symbol |
| Type | STOCK or INDEX |
| Strategy | Long Call / Long Put / Long Straddle |
| Strike | Strike price |
| Premium | Option price |
| PriceSource | ask / ltp / bid |
| Spot | Underlying spot price |
| Volume | Option trading volume |
| OI | Open Interest |
| OI_Change | Change in Open Interest |
| IV_Percentile | IV percentile (0-100) |
| Market_Regime | LOW_VOL / NORMAL_VOL / HIGH_VOL |
| RSI | 14-period RSI |
| Tier | TIER_1 / TIER_2 / TIER_3 / INDEX |
| Moneyness | ITM / ATM / OTM |
| **Expiry** | Expiry date (e.g., 28-Nov-2024) |
| **DaysToExpiry** | Days remaining until expiry |
| **LotSize** | F&O lot size for the symbol |
| **TotalCost** | Premium × Lot Size |
| **Breakeven** | Price needed for profit |
| **DistanceFromSpot** | Strike distance as % |

---

## Directional Bias Logic

The screener determines which options to scan based on technical indicators:

### When CALLS are Scanned

- Trend bias is **BULLISH** or **NEUTRAL**
- OR RSI < 45 (oversold → potential bounce)

### When PUTS are Scanned

- Trend bias is **BEARISH** or **NEUTRAL**
- OR RSI > 55 (overbought → potential pullback)

### Trend Bias Determination

```python
if current_price > EMA20 * 1.01:
    bias = "BULLISH"
elif current_price < EMA20 * 0.99:
    bias = "BEARISH"
else:
    bias = "NEUTRAL"
```

---

## Market Regime

The screener adapts to market conditions based on India VIX:

| VIX Range | Regime | Interpretation |
|-----------|--------|----------------|
| < 14 | LOW_VOL | Calm market, good for buying options |
| 14 - 20 | NORMAL_VOL | Standard conditions |
| > 20 | HIGH_VOL | Volatile market, premiums expensive |

---

## Troubleshooting

### No Alerts Generated

**Check 1: Market Hours**
```
Market hours: NO (using LTP fallback)
```
After 3:30 PM, only LTP data is available. This is normal.

**Check 2: Run Diagnostic Script**
```bash
python diagnostic_screener.py
```
This shows exactly why each option is filtered.

**Check 3: Relax Thresholds**

If still no results, try:
```python
VOLUME_THRESHOLDS = {'TIER_1': 10, 'TIER_2': 5, 'TIER_3': 1}
MAX_SPREAD_PCT_STOCK = 0.30  # 30%
```

### NSE API Errors

```
Option chain error for SYMBOL: ...
```

**Solutions:**
- NSE may be rate limiting. Increase `time.sleep(0.3)` to `time.sleep(1.0)`
- NSE website may be down. Try again later.
- Some symbols may not have F&O. Remove them from the list.

### yfinance Errors

```
Price error for SYMBOL: ...
```

**Solutions:**
- Check if the symbol exists on Yahoo Finance
- Some symbols need different tickers (e.g., `M&M` → `M%26M.NS`)
- Try updating yfinance: `pip install --upgrade yfinance`

---

## Diagnostic Script

If the main screener isn't producing results, run:

```bash
python diagnostic_screener.py
```

This will:

1. **Dump raw option chain structure** - Shows exact field names from NSE
2. **Analyze each option** - Shows why each option passed or failed
3. **Provide a summary** - Shows filter breakdown

### Sample Diagnostic Output

```
DIAGNOSING: RELIANCE
======================================================================
  ✓ Spot price: ₹2850.50
  ✓ Option chain fetched: 45 records
  ✓ Found 23 unique strikes
  ✓ Calls: 23, Puts: 23
  ATM Strike: 2850 | Step: 50 | Range: ±250

  ANALYZING CALLS:
  ------------------------------------------------------------
  Strike 2600 CE: Bid=255.00 Ask=260.00 LTP=257.50 Vol=1200 OI=45000 OI_Chg=500
    ✓ PASSED! Creating alert...
  Strike 2650 CE: Bid=0.00 Ask=0.00 LTP=210.00 Vol=800 OI=32000 OI_Chg=200
    → Using LTP as ask price: 210.00
    ✓ PASSED! Creating alert...
  Strike 2700 CE: Bid=165.00 Ask=168.00 LTP=166.50 Vol=5 OI=100 OI_Chg=0
    ❌ FILTERED: Vol=5 < 10 AND |OI_Chg|=0 < 0 AND OI=100 < 1000
```

---

## Best Practices

### For Live Trading

1. **Run during market hours** (9:15 AM - 3:30 PM IST) for live bid/ask data
2. **Focus on Tier 1 stocks** for tightest spreads
3. **Check the `price_source`** - prefer `(ask)` over `(ltp)`
4. **Verify on your broker** before placing orders

### Quick Decision Guide Using New Fields

| Check | Good Sign | Warning Sign |
|-------|-----------|--------------|
| **DTE** | ≥ 5 days | < 3 days (theta decay) |
| **Total Cost** | < 2% of capital | > 5% of capital |
| **Distance** | < 3% OTM | > 5% OTM (low probability) |
| **Volume** | > 500 | < 100 (illiquid) |
| **Breakeven** | Close to spot | Far from spot |

### Example Trade Evaluation

```
Alert: NIFTY Long Put OTM @ 24500 | ₹66.25 | Vol=1288 | Cost=₹1656 | BE=24433.75 | DTE=2 | -1.2% OTM

✓ Good volume (1288)
✓ Close to ATM (-1.2% OTM)
✓ Reasonable cost (₹1656 per lot)
⚠ Short DTE (2 days) - only for quick trades
⚠ Breakeven at 24433.75 - NIFTY must fall ~1.5% to profit

Decision: Suitable for SHORT-TERM bearish bet if you expect immediate downside
```

### For Analysis/Research

1. **After-hours scanning** works fine with LTP data
2. **Use the CSV log** to analyze patterns over time
3. **Adjust thresholds** based on your risk tolerance

### Recommended Workflow

```
1. Run screener → Get alerts
2. Filter by: High volume + ATM/slight OTM + Low IV percentile
3. Check charts for support/resistance levels
4. Verify bid-ask spread on your broker platform
5. Size position appropriately (risk management)
```

---

## Limitations

| Limitation | Details |
|------------|---------|
| **Data Delay** | yfinance and NSE data may have 1-15 minute delays |
| **No Real-time Streaming** | Point-in-time snapshots only |
| **After-hours Data** | Only LTP available, no live bid/ask |
| **No Greeks** | Delta, Gamma, Theta, Vega not calculated |
| **No Backtesting** | This is a live screener, not a backtester |

---

## Disclaimer

⚠️ **This tool is for educational and informational purposes only.**

- Options trading involves significant risk of loss
- Past performance does not guarantee future results
- Always do your own research before trading
- The author is not responsible for any financial losses
- This is not financial advice

---

## Changelog

### v3.2 (Current)
- **Added**: Days to Expiry (DTE) - shows remaining days until expiration
- **Added**: Lot Size - displays F&O lot size for each symbol (75+ symbols covered)
- **Added**: Total Cost - calculates premium × lot size for capital planning
- **Added**: Breakeven Price - shows exact price underlying must reach
- **Added**: Distance from Spot - shows strike distance as percentage with direction
- **Enhanced**: Table output format for better readability
- **Added**: Summary statistics (total calls/puts, ATM/OTM/ITM breakdown)
- **Updated**: CSV output includes all new fields

### v3.1
- **Fixed**: LTP fallback when bid/ask = 0 (after market hours)
- **Fixed**: Flexible field name handling (`askprice` vs `askPrice`)
- **Added**: `price_source` field to track where price came from
- **Added**: `open_interest` field in alerts
- **Relaxed**: Volume thresholds (50/20/10 from 200/100/50)
- **Relaxed**: OI change thresholds (0 - accepts any change)
- **Relaxed**: Spread tolerance (20% from 12%)
- **Added**: Alternative liquidity check (OI > 1000)
- **Improved**: Logging shows options analyzed vs passed
- **Added**: Diagnostic script for troubleshooting

### v3.0
- Relaxed volume/OI thresholds
- Changed filter logic from AND to OR
- Expanded strike range from 2 to 4
- Fixed India VIX fetching (was using US VIX)
- Added fallback for IV data
- Removed duplicate stock symbols
- Added moneyness labeling

### v2.0
- Added IV analysis from Opstra
- Implemented tiered stock classification
- Added market regime detection

### v1.0
- Initial release with basic scanning

---

## Support

If you encounter issues:

1. Run `diagnostic_screener.py` first
2. Check the log file `screener.log` for errors
3. Verify NSE website is accessible
4. Ensure all dependencies are installed

---

Quick Reference for Trading Decisions
Check✓ Good⚠️ CautionDTE≥ 5 days< 3 daysTotal Cost< 2% of your capital> 5% of capitalDistance< 3% OTM> 5% OTMVolume> 500< 100



## Quick Reference Card
```
┌─────────────────────────────────────────────────────────┐
│                  OPTIONS BUYING CHECKLIST               │
├─────────────────────────────────────────────────────────┤
│ □ Clear directional view (bullish/bearish)?            │
│ □ Strike within 2-3% of spot?                          │
│ □ At least 2 weeks to expiry?                          │
│ □ Volume > 500?                                        │
│ □ OI > 1000?                                           │
│ □ Premium affordable (risk only 1-2% of capital)?      │
│ □ Exit plan defined (stop loss + target)?              │
│ □ Verified live price on broker?                       │
└─────────────────────────────────────────────────────────┘

Here's a systematic approach:
1. CONFIRM DIRECTION
   └── Why are you bullish/bearish on this stock?
   └── Check: News, charts, support/resistance levels
   
2. SELECT STRIKE
   └── ATM = Higher premium, higher probability
   └── OTM = Lower premium, needs bigger move
   └── Rule of thumb: Don't go more than 2-3% OTM
   
3. CHECK EXPIRY
   └── At least 2 weeks to expiry for swing trades
   └── Weekly only for quick directional bets
   
4. VERIFY LIQUIDITY
   └── Volume > 500 ✓
   └── Bid-Ask spread < 1% of premium ✓
   └── OI > 1000 (preferred)
   
5. POSITION SIZE
   └── Risk only 1-2% of capital per trade
   └── Example: ₹1L capital → max ₹2,000 per trade
   
6. SET EXIT RULES
   └── Stop loss: Exit if premium drops 50%
   └── Target: Exit at 50-100% profit
   └── Time stop: Exit if no move in 3-5 days
## License

MIT License - Feel free to modify and distribute.
