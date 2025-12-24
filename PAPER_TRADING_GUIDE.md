# Paper Trading Tracker Guide

A comprehensive tool for tracking paper trades with Options Greeks analysis.

## Quick Start

### Option 1: Interactive Mode
```bash
python paper_trade_tracker.py
```

### Option 2: Demo Mode (See Examples)
```bash
python paper_trade_tracker.py demo
```

### Option 3: Manual Tracking (Excel/CSV)
Use the `paper_trades_template.csv` file in Excel or Google Sheets.

---

## Features

| Feature | Description |
|---------|-------------|
| **Trade Logging** | Add, update, and close paper trades |
| **Greeks Calculation** | Delta, Gamma, Theta, Vega using Black-Scholes |
| **IV Calculation** | Calculates IV from premium using Newton-Raphson |
| **Portfolio Greeks** | Aggregate Greeks for all open positions |
| **Trade History** | Tracks daily changes in premium and Greeks |
| **Educational Tools** | Learn what Greeks mean and how they impact your trade |

---

## Understanding Options Greeks

### Delta (Δ) - Directional Risk

**What it measures**: How much the option price changes per ₹1 move in the underlying.

| Option Type | Delta Range | Meaning |
|-------------|-------------|---------|
| Call | 0 to +1 | Gains when stock rises |
| Put | -1 to 0 | Gains when stock falls |
| ATM Call | ~+0.50 | 50₹ gain per 100₹ stock rise |
| ATM Put | ~-0.50 | 50₹ gain per 100₹ stock fall |

**Practical Use**:
```
Your trade: NIFTY 25500 PE with Delta = -0.28
Lot size: 25 units
Position Delta: -0.28 × 25 = -7

If NIFTY falls 100 points:
  Estimated P&L = 7 × 100 = ₹700 profit

If NIFTY rises 100 points:
  Estimated P&L = -7 × 100 = ₹700 loss
```

**Delta also indicates probability**:
- Delta 0.30 ≈ 30% chance of expiring ITM
- Delta 0.50 ≈ ATM option
- Delta 0.80 ≈ Deep ITM

---

### Gamma (Γ) - Delta's Acceleration

**What it measures**: How much Delta changes per ₹1 move in the underlying.

**Key Points**:
- Highest for ATM options
- Near zero for deep ITM/OTM
- Makes Delta "accelerate" in your favor (if right)

**Practical Use**:
```
Your trade: Delta = -0.28, Gamma = 0.0001

If NIFTY falls 200 points:
  New Delta ≈ -0.28 + (200 × 0.0001) = -0.30
  
The option becomes MORE sensitive to further moves!
```

**Why it matters for buyers**:
- High Gamma = potential for big gains if market moves your way
- But also means Delta changes quickly against you if wrong

---

### Theta (Θ) - Time Decay (YOUR ENEMY!)

**What it measures**: How much option value erodes per day.

**Critical for buyers**:
```
Your trade: NIFTY 25500 PE @ ₹177.55
Theta: -₹2.85/day per unit
Lot size: 25 units
Daily decay: 2.85 × 25 = ₹71.25/day

Even if NIFTY stays EXACTLY the same:
  After 1 week: -₹499 (lost to time)
  After 2 weeks: -₹998 (lost to time)
  After 1 month: -₹2,137 (lost to time)
```

**Theta acceleration**:
```
DTE    | Theta (per day)
90     | Low (~₹2-3)
30     | Medium (~₹5-7)  
7      | High (~₹15-20)
1      | Extreme (premium → 0)
```

**Key Insight**: Time decay accelerates as expiry approaches. The last week is brutal!

---

### Vega (ν) - Volatility Sensitivity

**What it measures**: How much option price changes per 1% change in IV.

**Practical Use**:
```
Your trade: NIFTY 25500 PE @ ₹177.55
Vega: ₹12.50 per 1% IV change
Lot size: 25 units
Position Vega: 12.50 × 25 = ₹312.50 per 1% IV

If IV increases from 15% to 18% (+3%):
  P&L from Vega = 3 × 312.50 = +₹937.50

If IV drops from 15% to 12% (-3%):
  P&L from Vega = -3 × 312.50 = -₹937.50
```

**IV Crush Warning**:
After major events (earnings, elections, budget), IV typically drops sharply:
- Pre-event IV: 25%
- Post-event IV: 15%
- Your loss from IV crush: 10% × Vega

---

## Greeks Summary for Buyers

| Greek | What You Want | Why |
|-------|---------------|-----|
| **Delta** | 0.3 to 0.6 | High enough to profit from moves |
| **Gamma** | Higher is better | Accelerates gains if you're right |
| **Theta** | As low as possible | Every day costs you money |
| **Vega** | High at entry if IV is low | Benefit from IV expansion |

---

## Using the Tracker

### 1. Adding a Trade

```python
from paper_trade_tracker import PaperTradeTracker

tracker = PaperTradeTracker()

# Add trade from your screener alert
tracker.add_trade(
    symbol="NIFTY",
    strike=25500,
    option_type="PE",
    entry_premium=177.55,
    iv=15.5,           # From screener (Opstra)
    dte=85,            # Days to expiry
    notes="Alert #5 from screener - bearish view"
)
```

### 2. Daily Update

```python
# Update with current premium (check your broker or NSE)
tracker.update_trade(
    trade_id=1,
    current_premium=165.00,  # Today's premium
    notes="NIFTY fell 150 points"
)
```

### 3. Viewing Greeks Impact

```python
from paper_trade_tracker import show_greeks_impact

show_greeks_impact(
    spot=26200,
    strike=25500,
    premium=177.55,
    dte=85,
    iv=15.5,
    option_type='PE'
)
```

Output shows:
- What happens if spot moves ±50, ±100, ±200 points
- Daily theta decay impact
- What happens if IV changes ±1%, ±3%, ±5%

### 4. Portfolio Summary

```python
tracker.view_all_trades()
tracker.calculate_portfolio_greeks()
```

---

## Sample Workflow

### Day 1: Entry
```
1. Run screener → Get alerts
2. Pick Alert #5: NIFTY 25500 PE @ ₹177.55
3. Add to tracker:
   - Record entry price, spot, IV
   - Note your rationale
   - Set mental stop loss and target
4. Check Greeks:
   - Delta: -0.28 (need market to fall)
   - Theta: -₹71/day (time is enemy)
```

### Day 2-7: Monitor
```
1. Check NIFTY spot price
2. Check current option premium (NSE or broker)
3. Update tracker with new premium
4. Review P&L and updated Greeks
5. Ask yourself:
   - Has my thesis changed?
   - Should I exit (stop loss or target hit)?
```

### Exit Day: Close Trade
```
1. Decide to exit (target hit, stop loss, or time stop)
2. Note exit premium
3. Close trade in tracker
4. Review:
   - What worked?
   - What didn't?
   - Lessons learned
```

---

## Risk Management Rules

### Position Sizing
```
Capital: ₹50,000

Rule: Risk max 2% per trade = ₹1,000

If stop loss is 50% of premium:
  Max position = ₹1,000 / 50% = ₹2,000

Example: NIFTY 25500 PE @ ₹177.55
  Cost per lot: ₹4,439
  
  This exceeds ₹2,000 limit!
  
  Options:
  1. Skip this trade
  2. Wait for better entry (lower premium)
  3. Choose cheaper strike (25200 PE @ ₹3,138)
```

### Stop Loss Rules
```
Time-based:
  - Exit if no significant move in 7 days
  - Exit when DTE < 7 (theta accelerates)

Premium-based:
  - Exit if premium drops 50% from entry
  - Trail stop: If up 50%, move stop to breakeven

Spot-based:
  - Exit if NIFTY closes above 26500 (for puts)
```

### Exit Rules
```
Target Hit:
  - Take profits at 50% gain
  - Or use trailing stop after 30% gain

Stop Loss Hit:
  - Exit immediately at predetermined level
  - Don't hope for recovery

Time Stop:
  - Exit before last week of expiry
  - Theta decay is brutal in final days
```

---

## Manual Tracking Template (Excel/CSV)

Use `paper_trades_template.csv` with these columns:

| Column | Description | Example |
|--------|-------------|---------|
| Trade_ID | Unique identifier | 1 |
| Symbol | Underlying | NIFTY |
| Strike | Strike price | 25500 |
| Type | CALL or PUT | PUT |
| Entry_Date | When you entered | 2025-12-01 |
| Entry_Premium | Price paid | 177.55 |
| Entry_Spot | Spot at entry | 26200 |
| Entry_IV | IV at entry | 15.5 |
| DTE_Entry | Days to expiry | 85 |
| Lot_Size | Contract size | 25 |
| Total_Cost | Premium × Lot | 4438.75 |
| Expiry_Date | Option expiry | 2025-02-24 |
| Delta | Entry delta | -0.28 |
| Gamma | Entry gamma | 0.00012 |
| Theta_Daily | Daily decay (₹) | -2.85 |
| Vega | Per 1% IV | 12.50 |
| Notes | Your rationale | "Support test" |
| Status | OPEN/CLOSED | OPEN |
| Exit_Date | When closed | - |
| Exit_Premium | Exit price | - |
| Exit_Spot | Spot at exit | - |
| Final_PnL | Profit/Loss (₹) | - |
| Final_PnL_Pct | P&L percentage | - |

---

## Files Included

| File | Description |
|------|-------------|
| `paper_trade_tracker.py` | Main tracker with Greeks calculation |
| `paper_trades_template.csv` | Excel/CSV template for manual tracking |
| `PAPER_TRADING_GUIDE.md` | This guide |
| `paper_trades.json` | Your saved trades (auto-created) |

---

## Requirements

```bash
pip install pandas numpy scipy yfinance
```

---

## Tips for Beginners

1. **Start with 1-2 trades only** - Don't overwhelm yourself
2. **Track daily** - Even 5 minutes is enough
3. **Note your emotions** - Were you scared? Greedy? 
4. **Learn from losers** - Every losing trade is a lesson
5. **Focus on process** - Right process > lucky outcome
6. **Paper trade for 1 month minimum** before real money

---

## Common Mistakes to Avoid

| Mistake | Why It's Bad | How to Avoid |
|---------|--------------|--------------|
| Buying far OTM | Low probability, lottery ticket | Stay within 3% of spot |
| Ignoring theta | Time eats your premium daily | Check theta before entry |
| Holding to expiry | Last week theta is brutal | Exit with 7+ DTE remaining |
| No stop loss | Small loss becomes big loss | Set stop at entry |
| Averaging down | Throwing good money after bad | Accept loss, move on |
| Ignoring IV | High IV = expensive premiums | Buy when IVP < 30% |

---

Good luck with your paper trading journey! 📈


python paper_trade_tracker.py
```

### Step 2: Select "1. Add new paper trade"

### Step 3: Enter these details:
```
Symbol: NIFTY
Strike: 25500
Option type: PE
Entry premium: 177.55
Days to expiry: 85
IV: 15.5 (or press Enter to calculate)
Notes: Alert #5 - Bearish view, testing 25000 support
```

### Step 4: You'll see output like:
```
══════════════════════════════════════════════════════════════════════
  NEW TRADE ADDED
══════════════════════════════════════════════════════════════════════
  Trade ID: #1
  NIFTY 25500 PUT
  Entry: ₹177.55 | Spot: ₹26,200
  Total Cost: ₹4,439 (25 units)
  Expiry: 2025-02-24 (85 days)
  IV at Entry: 15.5%
──────────────────────────────────────────────────────────────────────
  ENTRY GREEKS:
    Delta: -0.2850 | Gamma: 0.000120
    Theta: ₹-2.85/day | Vega: ₹12.50/1% IV
══════════════════════════════════════════════════════════════════════
```

---

## Understanding Your Trade's Greeks

For **NIFTY 25500 PE @ ₹177.55**:

| Greek | Value | What It Means |
|-------|-------|---------------|
| **Delta** | -0.285 | Gains ₹7.12 per 1 point NIFTY falls (per lot) |
| **Gamma** | 0.00012 | Delta will increase as NIFTY falls |
| **Theta** | -₹71/day | Loses ₹71 every day from time decay |
| **Vega** | ₹312/1% IV | Gains/loses ₹312 per 1% IV change |

### Scenario Analysis:
```
IF NIFTY FALLS 500 points (to 25,700):
├── Delta P&L: 500 × 7.12 = +₹3,560
├── Theta loss (5 days): 5 × 71 = -₹355
└── Net P&L: ~₹3,200 profit (+72%)

IF NIFTY STAYS FLAT for 2 weeks:
├── Delta P&L: ₹0
├── Theta loss: 14 × 71 = -₹994
└── Net P&L: ~₹1,000 loss (-22%)

IF NIFTY RISES 300 points (to 26,500):
├── Delta P&L: -300 × 7.12 = -₹2,136
├── Theta loss (5 days): 5 × 71 = -₹355
└── Net P&L: ~₹2,500 loss (-56%)
```

---

## Your Action Plan

### Week 1: Set Up & Learn

| Day | Action |
|-----|--------|
| **Day 1** | Install tracker, add 2-3 paper trades from your alerts |
| **Day 2** | Learn about Greeks using option 8 in menu |
| **Day 3-5** | Update trades daily, observe how premium changes |
| **Weekend** | Review: What moved? Why? Note theta decay over weekend |

### Suggested Paper Trades from Your Alerts

| Trade | Alert | Why |
|-------|-------|-----|
| **Trade 1** | #5 NIFTY 25500 PE | Closest to ATM, best risk/reward |
| **Trade 2** | #6 NIFTY 27500 CE | Opposite view - learn both sides |
| **Trade 3** | #11 ONGC 246.5 CE | Stock option - different behavior |

### Daily Routine (5 minutes)
```
1. Check NIFTY/stock spot price
2. Check current option premium (NSE website or broker)
3. Run tracker → Option 2 (Update trade)
4. Note the P&L and how Greeks changed
5. Ask: Should I exit? (target/stop loss hit?)
```

---

## Key Takeaways
```
╔═══════════════════════════════════════════════════════════════════╗
║  TOP 5 LESSONS FOR OPTIONS BUYERS                                 ║
╠═══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║  1. THETA IS YOUR ENEMY                                          ║
║     → You lose money every day, even if you're right on direction║
║     → Exit before last week of expiry                            ║
║                                                                   ║
║  2. DELTA TELLS YOU DIRECTION EXPOSURE                           ║
║     → Higher delta = more profit if right, more loss if wrong    ║
║     → ATM options have ~0.50 delta                               ║
║                                                                   ║
║  3. IV MATTERS MORE THAN YOU THINK                               ║
║     → High IV = expensive premiums = harder to profit            ║
║     → Buy when IVP < 30%, avoid when IVP > 70%                   ║
║                                                                   ║
║  4. TIME IS NOT ON YOUR SIDE                                     ║
║     → Options lose 70% of time value in last 30 days             ║
║     → Don't hold weekly options overnight unless necessary       ║
║                                                                   ║
║  5. HAVE AN EXIT PLAN BEFORE ENTRY                               ║
║     → Stop loss: -50% of premium                                 ║
║     → Target: +50-100% of premium                                ║
║     → Time stop: Exit with 7+ DTE remaining                      ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
