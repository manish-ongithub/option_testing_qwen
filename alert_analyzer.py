"""
Options Alert Analysis Framework v1.0
=====================================
A systematic approach to analyze any options alert before trading.

This script provides:
1. Complete analysis framework
2. Greeks-based scenarios
3. Risk/Reward calculation
4. Entry/Exit rules
5. Position sizing
"""

import math
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta

# ================== BLACK-SCHOLES FUNCTIONS ==================

def black_scholes_greeks(S, K, T, r, sigma, option_type='CE'):
    """Calculate Option Greeks using Black-Scholes model."""
    if T <= 0:
        T = 0.0001
    if sigma <= 0:
        sigma = 0.01
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    N_d1 = norm.cdf(d1)
    N_d2 = norm.cdf(d2)
    N_neg_d1 = norm.cdf(-d1)
    N_neg_d2 = norm.cdf(-d2)
    n_d1 = norm.pdf(d1)
    
    if option_type.upper() == 'CE':
        price = S * N_d1 - K * math.exp(-r * T) * N_d2
        delta = N_d1
        theta = (-S * n_d1 * sigma / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * N_d2) / 365
    else:
        price = K * math.exp(-r * T) * N_neg_d2 - S * N_neg_d1
        delta = N_d1 - 1
        theta = (-S * n_d1 * sigma / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * N_neg_d2) / 365
    
    gamma = n_d1 / (S * sigma * math.sqrt(T))
    vega = S * n_d1 * math.sqrt(T) / 100
    
    # Probability of profit at expiry (for buyers)
    if option_type.upper() == 'CE':
        prob_itm = N_d2 * 100  # Probability of S > K at expiry
    else:
        prob_itm = N_neg_d2 * 100  # Probability of S < K at expiry
    
    return {
        'price': round(price, 2),
        'delta': round(delta, 4),
        'gamma': round(gamma, 6),
        'theta': round(theta, 2),
        'vega': round(vega, 2),
        'prob_itm': round(prob_itm, 1),
        'd1': round(d1, 4),
        'd2': round(d2, 4)
    }


def analyze_alert(
    symbol,
    spot,
    strike,
    premium,
    option_type,  # 'CE' or 'PE'
    dte,
    iv,
    iv_percentile,
    volume,
    oi,
    lot_size,
    capital=50000,
    risk_per_trade_pct=2
):
    """
    Comprehensive analysis of an options alert.
    
    Parameters:
    -----------
    symbol : str - Underlying symbol
    spot : float - Current spot price
    strike : float - Strike price
    premium : float - Option premium (ask price)
    option_type : str - 'CE' for Call, 'PE' for Put
    dte : int - Days to expiry
    iv : float - Implied Volatility (as %)
    iv_percentile : float - IV Percentile (0-100)
    volume : int - Trading volume
    oi : int - Open Interest
    lot_size : int - Contract lot size
    capital : float - Your trading capital
    risk_per_trade_pct : float - Max % of capital to risk
    """
    
    r = 0.065  # Risk-free rate
    T = dte / 365
    sigma = iv / 100
    
    opt_name = "CALL" if option_type == 'CE' else "PUT"
    
    # Calculate Greeks
    greeks = black_scholes_greeks(spot, strike, T, r, sigma, option_type)
    
    # Calculate key metrics
    total_cost = premium * lot_size
    breakeven = strike + premium if option_type == 'CE' else strike - premium
    distance_pct = ((strike - spot) / spot) * 100
    intrinsic = max(0, spot - strike) if option_type == 'CE' else max(0, strike - spot)
    time_value = premium - intrinsic
    time_value_pct = (time_value / premium) * 100 if premium > 0 else 0
    
    # Position Greeks
    pos_delta = greeks['delta'] * lot_size
    pos_gamma = greeks['gamma'] * lot_size
    pos_theta = greeks['theta'] * lot_size
    pos_vega = greeks['vega'] * lot_size
    
    # Risk metrics
    max_loss = total_cost
    risk_amount = capital * (risk_per_trade_pct / 100)
    max_lots = int(risk_amount / (total_cost * 0.5))  # Assuming 50% stop loss
    
    # Moneyness
    if option_type == 'CE':
        if strike < spot * 0.98:
            moneyness = "ITM"
        elif strike > spot * 1.02:
            moneyness = "OTM"
        else:
            moneyness = "ATM"
    else:
        if strike > spot * 1.02:
            moneyness = "ITM"
        elif strike < spot * 0.98:
            moneyness = "OTM"
        else:
            moneyness = "ATM"
    
    print("\n")
    print("█" * 90)
    print("█" + " " * 88 + "█")
    print("█" + f"  COMPREHENSIVE ALERT ANALYSIS: {symbol} {strike} {opt_name}".ljust(88) + "█")
    print("█" + " " * 88 + "█")
    print("█" * 90)
    
    # ==================== SECTION 1: BASIC INFO ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  📋 SECTION 1: BASIC INFORMATION".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    print("│" + f"  Symbol:        {symbol}".ljust(88) + "│")
    print("│" + f"  Spot Price:    ₹{spot:,.2f}".ljust(88) + "│")
    print("│" + f"  Strike:        ₹{strike:,.2f}".ljust(88) + "│")
    print("│" + f"  Option Type:   {opt_name}".ljust(88) + "│")
    print("│" + f"  Premium:       ₹{premium:.2f}".ljust(88) + "│")
    print("│" + f"  Moneyness:     {moneyness} ({distance_pct:+.1f}% from spot)".ljust(88) + "│")
    print("│" + f"  Days to Expiry: {dte} days".ljust(88) + "│")
    print("│" + f"  Lot Size:      {lot_size}".ljust(88) + "│")
    print("│" + f"  Total Cost:    ₹{total_cost:,.2f} (1 lot)".ljust(88) + "│")
    print("│" + f"  Volume:        {volume:,}".ljust(88) + "│")
    print("│" + f"  Open Interest: {oi:,}".ljust(88) + "│")
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 2: IV ANALYSIS ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  📊 SECTION 2: IMPLIED VOLATILITY ANALYSIS".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    print("│" + f"  Current IV:      {iv:.1f}%".ljust(88) + "│")
    print("│" + f"  IV Percentile:   {iv_percentile:.0f}%".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    
    # IV interpretation
    if iv_percentile < 30:
        iv_rating = "🟢 LOW (Favorable for buying)"
        iv_advice = "Good! Premiums are relatively cheap. Room for IV expansion."
    elif iv_percentile < 50:
        iv_rating = "🟡 BELOW AVERAGE"
        iv_advice = "Acceptable. Premiums are reasonable."
    elif iv_percentile < 70:
        iv_rating = "🟠 ABOVE AVERAGE"
        iv_advice = "Caution. Premiums are somewhat expensive."
    else:
        iv_rating = "🔴 HIGH (Unfavorable for buying)"
        iv_advice = "Warning! Premiums are expensive. Risk of IV crush."
    
    print("│" + f"  IV Assessment:   {iv_rating}".ljust(88) + "│")
    print("│" + f"  Advice:          {iv_advice}".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    
    # IV scale visualization
    print("│" + "  IV Percentile Scale:".ljust(88) + "│")
    iv_bar = "  [" + "█" * int(iv_percentile / 5) + "░" * (20 - int(iv_percentile / 5)) + "]"
    print("│" + f"  0%{iv_bar}100%  ← You are here: {iv_percentile:.0f}%".ljust(88) + "│")
    print("│" + "     LOW         NORMAL         HIGH".ljust(88) + "│")
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 3: GREEKS ANALYSIS ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  🔢 SECTION 3: OPTIONS GREEKS".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    print("│" + "  Per Unit Greeks:".ljust(88) + "│")
    print("│" + f"    Delta:  {greeks['delta']:+.4f}".ljust(88) + "│")
    print("│" + f"    Gamma:  {greeks['gamma']:.6f}".ljust(88) + "│")
    print("│" + f"    Theta:  ₹{greeks['theta']:.2f}/day".ljust(88) + "│")
    print("│" + f"    Vega:   ₹{greeks['vega']:.2f} per 1% IV".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    print("│" + f"  Position Greeks (1 lot = {lot_size} units):".ljust(88) + "│")
    print("│" + f"    Position Delta:  {pos_delta:+.2f}".ljust(88) + "│")
    print("│" + f"    Position Gamma:  {pos_gamma:.4f}".ljust(88) + "│")
    print("│" + f"    Position Theta:  ₹{pos_theta:.2f}/day".ljust(88) + "│")
    print("│" + f"    Position Vega:   ₹{pos_vega:.2f} per 1% IV".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    print("│" + f"  Probability of ITM at Expiry: {greeks['prob_itm']:.1f}%".ljust(88) + "│")
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 4: GREEKS INTERPRETATION ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  📖 SECTION 4: WHAT THE GREEKS MEAN FOR YOU".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    
    # Delta interpretation
    print("│" + " ".ljust(88) + "│")
    print("│" + "  DELTA INTERPRETATION:".ljust(88) + "│")
    if option_type == 'PE':
        print("│" + f"    • Your position gains ₹{abs(pos_delta):.0f} for every 1 point FALL in {symbol}".ljust(88) + "│")
        print("│" + f"    • Your position loses ₹{abs(pos_delta):.0f} for every 1 point RISE in {symbol}".ljust(88) + "│")
    else:
        print("│" + f"    • Your position gains ₹{abs(pos_delta):.0f} for every 1 point RISE in {symbol}".ljust(88) + "│")
        print("│" + f"    • Your position loses ₹{abs(pos_delta):.0f} for every 1 point FALL in {symbol}".ljust(88) + "│")
    
    delta_quality = "Good" if 0.25 <= abs(greeks['delta']) <= 0.60 else "Caution"
    print("│" + f"    • Delta magnitude: {abs(greeks['delta']):.2f} ({delta_quality})".ljust(88) + "│")
    
    # Theta interpretation
    print("│" + " ".ljust(88) + "│")
    print("│" + "  THETA INTERPRETATION (Time Decay):".ljust(88) + "│")
    print("│" + f"    • You lose ₹{abs(pos_theta):.0f} EVERY DAY just from time passing".ljust(88) + "│")
    print("│" + f"    • Weekly loss (5 trading days): ₹{abs(pos_theta * 5):.0f}".ljust(88) + "│")
    print("│" + f"    • Weekend decay (Sat+Sun): ₹{abs(pos_theta * 2):.0f}".ljust(88) + "│")
    print("│" + f"    • If held to expiry: Up to ₹{abs(pos_theta * dte):.0f} lost to theta".ljust(88) + "│")
    
    theta_pct = (abs(pos_theta) / total_cost) * 100
    theta_quality = "Acceptable" if theta_pct < 2 else "High - Be cautious"
    print("│" + f"    • Daily decay as % of cost: {theta_pct:.2f}% ({theta_quality})".ljust(88) + "│")
    
    # Vega interpretation
    print("│" + " ".ljust(88) + "│")
    print("│" + "  VEGA INTERPRETATION (Volatility Sensitivity):".ljust(88) + "│")
    print("│" + f"    • If IV rises 2%: You gain ₹{pos_vega * 2:.0f}".ljust(88) + "│")
    print("│" + f"    • If IV drops 2%: You lose ₹{pos_vega * 2:.0f}".ljust(88) + "│")
    print("│" + f"    • IV Crush risk (5% IV drop): -₹{pos_vega * 5:.0f}".ljust(88) + "│")
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 5: BREAKEVEN ANALYSIS ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  🎯 SECTION 5: BREAKEVEN & PROFIT ANALYSIS".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    print("│" + f"  Breakeven Price: ₹{breakeven:,.2f}".ljust(88) + "│")
    
    be_distance = ((breakeven - spot) / spot) * 100
    if option_type == 'PE':
        print("│" + f"  {symbol} must FALL to ₹{breakeven:,.2f} ({be_distance:+.2f}%) to breakeven".ljust(88) + "│")
        profit_direction = "below"
    else:
        print("│" + f"  {symbol} must RISE to ₹{breakeven:,.2f} ({be_distance:+.2f}%) to breakeven".ljust(88) + "│")
        profit_direction = "above"
    
    print("│" + " ".ljust(88) + "│")
    print("│" + "  Premium Composition:".ljust(88) + "│")
    print("│" + f"    Intrinsic Value: ₹{intrinsic:.2f} ({(intrinsic/premium)*100 if premium > 0 else 0:.0f}%)".ljust(88) + "│")
    print("│" + f"    Time Value:      ₹{time_value:.2f} ({time_value_pct:.0f}%)".ljust(88) + "│")
    
    if time_value_pct > 80:
        print("│" + "    ⚠️ High time value - most of premium is at risk from theta".ljust(88) + "│")
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 6: SCENARIO ANALYSIS ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  🔮 SECTION 6: SCENARIO ANALYSIS (What If?)".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    
    # Scenario 1: Spot price moves
    print("│" + " ".ljust(88) + "│")
    print("│" + f"  SCENARIO A: {symbol} PRICE MOVES (in 5 days, IV unchanged)".ljust(88) + "│")
    print("│" + "  ─" * 42 + "│")
    
    moves = [-500, -300, -200, -100, 0, 100, 200, 300, 500] if symbol in ['NIFTY', 'BANKNIFTY'] else [-50, -30, -20, -10, 0, 10, 20, 30, 50]
    
    print("│" + f"  {'Move':<12} {'New Spot':<12} {'Est. P&L':<15} {'Return':<12}".ljust(88) + "│")
    
    for move in moves:
        new_spot = spot + move
        # Simple delta-based estimate + theta
        pnl = (move * pos_delta) + (pos_theta * 5)  # 5 days of theta
        pnl_pct = (pnl / total_cost) * 100
        
        if pnl >= 0:
            pnl_str = f"₹{pnl:+,.0f}"
        else:
            pnl_str = f"₹{pnl:,.0f}"
        
        print("│" + f"  {move:+,} pts".ljust(12) + f"₹{new_spot:,.0f}".ljust(12) + f"{pnl_str}".ljust(15) + f"{pnl_pct:+.1f}%".ljust(12) + "│")
    
    # Scenario 2: Time passes
    print("│" + " ".ljust(88) + "│")
    print("│" + f"  SCENARIO B: TIME PASSES ({symbol} stays at ₹{spot:,.0f})".ljust(88) + "│")
    print("│" + "  ─" * 42 + "│")
    print("│" + f"  {'Days':<12} {'Theta Loss':<15} {'Remaining Value':<20} {'% of Cost':<12}".ljust(88) + "│")
    
    for days in [1, 3, 5, 7, 14, 21, 30]:
        if days <= dte:
            theta_loss = abs(pos_theta) * days
            remaining = total_cost - theta_loss
            remaining_pct = (remaining / total_cost) * 100
            print("│" + f"  {days} days".ljust(12) + f"-₹{theta_loss:,.0f}".ljust(15) + f"₹{max(0, remaining):,.0f}".ljust(20) + f"{remaining_pct:.0f}%".ljust(12) + "│")
    
    # Scenario 3: IV changes
    print("│" + " ".ljust(88) + "│")
    print("│" + f"  SCENARIO C: IV CHANGES ({symbol} stays flat, no time decay)".ljust(88) + "│")
    print("│" + "  ─" * 42 + "│")
    print("│" + f"  {'IV Change':<12} {'New IV':<12} {'P&L from Vega':<15} {'Return':<12}".ljust(88) + "│")
    
    for iv_change in [-5, -3, -2, -1, 0, 1, 2, 3, 5]:
        new_iv = iv + iv_change
        vega_pnl = iv_change * pos_vega
        vega_pnl_pct = (vega_pnl / total_cost) * 100
        print("│" + f"  {iv_change:+}%".ljust(12) + f"{new_iv:.1f}%".ljust(12) + f"₹{vega_pnl:+,.0f}".ljust(15) + f"{vega_pnl_pct:+.1f}%".ljust(12) + "│")
    
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 7: RISK/REWARD ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  ⚖️ SECTION 7: RISK / REWARD ANALYSIS".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    
    # Calculate target prices
    target_50_pct = premium * 1.5  # 50% profit target
    target_100_pct = premium * 2.0  # 100% profit target
    stop_loss_50_pct = premium * 0.5  # 50% loss stop
    
    print("│" + " ".ljust(88) + "│")
    print("│" + "  ENTRY:".ljust(88) + "│")
    print("│" + f"    Premium: ₹{premium:.2f}".ljust(88) + "│")
    print("│" + f"    Cost (1 lot): ₹{total_cost:,.2f}".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    print("│" + "  PROFIT TARGETS:".ljust(88) + "│")
    print("│" + f"    Target 1 (+50%): Exit at ₹{target_50_pct:.2f} → Profit: ₹{(target_50_pct - premium) * lot_size:,.0f}".ljust(88) + "│")
    print("│" + f"    Target 2 (+100%): Exit at ₹{target_100_pct:.2f} → Profit: ₹{(target_100_pct - premium) * lot_size:,.0f}".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    print("│" + "  STOP LOSS:".ljust(88) + "│")
    print("│" + f"    Stop Loss (-50%): Exit at ₹{stop_loss_50_pct:.2f} → Loss: ₹{(premium - stop_loss_50_pct) * lot_size:,.0f}".ljust(88) + "│")
    print("│" + f"    Max Loss (-100%): ₹{total_cost:,.0f} (if option expires worthless)".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    print("│" + "  RISK/REWARD RATIOS:".ljust(88) + "│")
    
    # R:R for 50% target with 50% stop
    risk = premium * 0.5
    reward_50 = premium * 0.5
    rr_50 = reward_50 / risk
    print("│" + f"    Target 50% / Stop 50%: R:R = 1:{rr_50:.1f}".ljust(88) + "│")
    
    reward_100 = premium * 1.0
    rr_100 = reward_100 / risk
    print("│" + f"    Target 100% / Stop 50%: R:R = 1:{rr_100:.1f}".ljust(88) + "│")
    
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 8: POSITION SIZING ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  💰 SECTION 8: POSITION SIZING".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    print("│" + f"  Your Capital: ₹{capital:,}".ljust(88) + "│")
    print("│" + f"  Risk per Trade: {risk_per_trade_pct}% = ₹{risk_amount:,.0f}".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    print("│" + "  If Stop Loss = 50% of Premium:".ljust(88) + "│")
    print("│" + f"    Risk per lot = ₹{total_cost * 0.5:,.0f}".ljust(88) + "│")
    print("│" + f"    Max lots you can trade = {max_lots} lot(s)".ljust(88) + "│")
    print("│" + f"    Total position size = ₹{max_lots * total_cost:,.0f}".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    
    if max_lots == 0:
        print("│" + "  ⚠️ WARNING: This trade is TOO RISKY for your capital!".ljust(88) + "│")
        print("│" + "     Either increase capital or find a cheaper option.".ljust(88) + "│")
    elif max_lots == 1:
        print("│" + "  ✓ RECOMMENDATION: Trade 1 lot maximum".ljust(88) + "│")
    else:
        print("│" + f"  ✓ RECOMMENDATION: Start with 1 lot, scale up to {min(max_lots, 3)} lots".ljust(88) + "│")
    
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 9: LIQUIDITY CHECK ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  🌊 SECTION 9: LIQUIDITY ASSESSMENT".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    print("│" + f"  Volume: {volume:,}".ljust(88) + "│")
    print("│" + f"  Open Interest: {oi:,}".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    
    # Volume assessment
    if volume >= 1000:
        vol_rating = "🟢 EXCELLENT - Very liquid"
    elif volume >= 500:
        vol_rating = "🟢 GOOD - Adequate liquidity"
    elif volume >= 100:
        vol_rating = "🟡 MODERATE - Watch bid-ask spread"
    else:
        vol_rating = "🔴 LOW - May face slippage"
    
    # OI assessment
    if oi >= 5000:
        oi_rating = "🟢 HIGH - Strong market interest"
    elif oi >= 1000:
        oi_rating = "🟢 GOOD - Sufficient interest"
    elif oi >= 500:
        oi_rating = "🟡 MODERATE - Acceptable"
    else:
        oi_rating = "🔴 LOW - Limited interest"
    
    print("│" + f"  Volume Rating: {vol_rating}".ljust(88) + "│")
    print("│" + f"  OI Rating: {oi_rating}".ljust(88) + "│")
    
    # Overall liquidity
    if volume >= 500 and oi >= 1000:
        print("│" + "  Overall: ✓ LIQUID - Easy to enter and exit".ljust(88) + "│")
    else:
        print("│" + "  Overall: ⚠️ CHECK BID-ASK SPREAD before trading".ljust(88) + "│")
    
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 10: TRADE CHECKLIST ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  ✅ SECTION 10: PRE-TRADE CHECKLIST".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    
    checks = []
    
    # Check 1: Moneyness
    if moneyness in ['ATM', 'ITM'] or (moneyness == 'OTM' and abs(distance_pct) <= 5):
        checks.append(("Strike within 5% of spot", True, "Good probability"))
    else:
        checks.append(("Strike within 5% of spot", False, f"{abs(distance_pct):.1f}% away - lower probability"))
    
    # Check 2: DTE
    if dte >= 14:
        checks.append(("DTE >= 14 days", True, f"{dte} days - enough time"))
    else:
        checks.append(("DTE >= 14 days", False, f"Only {dte} days - high theta risk"))
    
    # Check 3: IV Percentile
    if iv_percentile <= 50:
        checks.append(("IV Percentile <= 50%", True, f"{iv_percentile:.0f}% - reasonable premiums"))
    else:
        checks.append(("IV Percentile <= 50%", False, f"{iv_percentile:.0f}% - expensive premiums"))
    
    # Check 4: Volume
    if volume >= 500:
        checks.append(("Volume >= 500", True, f"{volume:,} - liquid"))
    else:
        checks.append(("Volume >= 500", False, f"{volume:,} - illiquid"))
    
    # Check 5: Position size
    if max_lots >= 1:
        checks.append(("Within risk limits", True, f"Can trade {max_lots} lot(s)"))
    else:
        checks.append(("Within risk limits", False, "Too expensive for your capital"))
    
    # Check 6: Theta decay
    if theta_pct < 2:
        checks.append(("Daily theta < 2%", True, f"{theta_pct:.2f}%/day - manageable"))
    else:
        checks.append(("Daily theta < 2%", False, f"{theta_pct:.2f}%/day - high decay"))
    
    passed = sum(1 for _, status, _ in checks if status)
    total = len(checks)
    
    for check_name, status, comment in checks:
        icon = "✓" if status else "✗"
        status_str = "PASS" if status else "FAIL"
        print("│" + f"  {icon} {check_name}: {status_str}".ljust(50) + f"({comment})".ljust(38) + "│")
    
    print("│" + " ".ljust(88) + "│")
    print("│" + f"  SCORE: {passed}/{total} checks passed".ljust(88) + "│")
    
    if passed == total:
        print("│" + "  VERDICT: 🟢 ALL CLEAR - Proceed with trade".ljust(88) + "│")
    elif passed >= total - 1:
        print("│" + "  VERDICT: 🟡 MOSTLY GOOD - Proceed with caution".ljust(88) + "│")
    elif passed >= total // 2:
        print("│" + "  VERDICT: 🟠 MIXED - Consider alternatives".ljust(88) + "│")
    else:
        print("│" + "  VERDICT: 🔴 HIGH RISK - Reconsider this trade".ljust(88) + "│")
    
    print("└" + "─" * 88 + "┘")
    
    # ==================== SECTION 11: TRADE PLAN ====================
    print("\n")
    print("┌" + "─" * 88 + "┐")
    print("│" + "  📝 SECTION 11: SUGGESTED TRADE PLAN".ljust(88) + "│")
    print("├" + "─" * 88 + "┤")
    print("│" + " ".ljust(88) + "│")
    print("│" + "  ENTRY:".ljust(88) + "│")
    print("│" + f"    • Buy {symbol} {strike} {opt_name} @ ₹{premium:.2f}".ljust(88) + "│")
    print("│" + f"    • Quantity: 1 lot ({lot_size} units)".ljust(88) + "│")
    print("│" + f"    • Total Investment: ₹{total_cost:,.2f}".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    print("│" + "  EXIT RULES:".ljust(88) + "│")
    print("│" + f"    • Stop Loss: Exit if premium falls to ₹{stop_loss_50_pct:.2f} (-50%)".ljust(88) + "│")
    print("│" + f"    • Target 1: Book 50% profit at ₹{target_50_pct:.2f}".ljust(88) + "│")
    print("│" + f"    • Target 2: Book remaining at ₹{target_100_pct:.2f} (100%)".ljust(88) + "│")
    print("│" + f"    • Time Stop: Exit if DTE < 7 days (unless ITM)".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    print("│" + "  TRAILING STOP (Optional):".ljust(88) + "│")
    print("│" + f"    • After +30% gain: Move stop to breakeven (₹{premium:.2f})".ljust(88) + "│")
    print("│" + f"    • After +50% gain: Move stop to +25% (₹{premium * 1.25:.2f})".ljust(88) + "│")
    print("│" + " ".ljust(88) + "│")
    print("│" + "  WHAT TO MONITOR:".ljust(88) + "│")
    print("│" + f"    • {symbol} spot price (daily)".ljust(88) + "│")
    print("│" + "    • IV changes (watch for crush after events)".ljust(88) + "│")
    print("│" + "    • Option premium on your broker".ljust(88) + "│")
    print("│" + "    • News/events that could impact the underlying".ljust(88) + "│")
    print("└" + "─" * 88 + "┘")
    
    # ==================== FINAL SUMMARY ====================
    print("\n")
    print("█" * 90)
    print("█" + " " * 88 + "█")
    print("█" + "  ANALYSIS COMPLETE".center(88) + "█")
    print("█" + " " * 88 + "█")
    print("█" + f"  {symbol} {strike} {opt_name} @ ₹{premium:.2f}".center(88) + "█")
    print("█" + f"  Cost: ₹{total_cost:,.0f} | Max Loss: ₹{total_cost:,.0f} | Prob ITM: {greeks['prob_itm']:.0f}%".center(88) + "█")
    print("█" + " " * 88 + "█")
    print("█" * 90)
    
    return {
        'greeks': greeks,
        'breakeven': breakeven,
        'total_cost': total_cost,
        'max_lots': max_lots,
        'checks_passed': passed,
        'checks_total': total
    }


# ================== EXAMPLE USAGE ====================

if __name__ == "__main__":
    
    print("\n" + "=" * 90)
    print("  OPTIONS ALERT ANALYSIS FRAMEWORK")
    print("  Analyzing: NIFTY 25500 PUT (Your Alert #5)")
    print("=" * 90)
    
    # Analyze Alert #5 from your screener
    result = analyze_alert(
        symbol="NIFTY",
        spot=26200,           # Approximate current spot
        strike=25500,
        premium=177.55,
        option_type="PE",
        dte=85,
        iv=15.5,              # From Opstra
        iv_percentile=35,     # Estimate based on current levels
        volume=1450,
        oi=5000,              # Estimate
        lot_size=25,
        capital=50000,        # Your trading capital
        risk_per_trade_pct=2  # Risk 2% per trade
    )
    
    print("\n\n")
    print("=" * 90)
    print("  To analyze another alert, modify the parameters and run again!")
    print("=" * 90)
