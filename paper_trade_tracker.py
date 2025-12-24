"""
Options Paper Trading Tracker v1.0
==================================
A comprehensive tool for tracking paper trades with Greeks analysis.

Features:
- Track multiple paper trades
- Calculate Options Greeks (Delta, Gamma, Theta, Vega)
- Daily P&L tracking
- Trade journal with notes
- Performance analytics

Author: Options Screener Project
"""

import os
import json
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.stats import norm
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

# ================== CONFIGURATION ==================
TRADES_FILE = "paper_trades.json"
HISTORY_FILE = "trade_history.csv"
RISK_FREE_RATE = 0.065  # 6.5% (approximate Indian risk-free rate)

# Symbol to Yahoo Finance ticker mapping
SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}

# Lot sizes
LOT_SIZES = {
    "NIFTY": 25, "BANKNIFTY": 15,
    "RELIANCE": 250, "HDFCBANK": 550, "ICICIBANK": 700,
    "SBIN": 750, "TCS": 175, "INFY": 400, "TATAMOTORS": 1400,
    "BAJFINANCE": 125, "KOTAKBANK": 400, "AXISBANK": 625,
    "ONGC": 3850, "BPCL": 1800, "MUTHOOTFIN": 375,
}

# ================== BLACK-SCHOLES GREEKS ==================

def black_scholes_greeks(S, K, T, r, sigma, option_type='CE'):
    """
    Calculate Option Greeks using Black-Scholes model.
    
    Parameters:
    -----------
    S : float - Current spot price
    K : float - Strike price
    T : float - Time to expiry in years (DTE/365)
    r : float - Risk-free interest rate (e.g., 0.065 for 6.5%)
    sigma : float - Implied Volatility (e.g., 0.20 for 20%)
    option_type : str - 'CE' for Call, 'PE' for Put
    
    Returns:
    --------
    dict with: price, delta, gamma, theta, vega, rho
    """
    
    if T <= 0:
        T = 0.0001  # Avoid division by zero
    
    if sigma <= 0:
        sigma = 0.01  # Minimum volatility
    
    # Calculate d1 and d2
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    # Standard normal CDF and PDF
    N_d1 = norm.cdf(d1)
    N_d2 = norm.cdf(d2)
    N_neg_d1 = norm.cdf(-d1)
    N_neg_d2 = norm.cdf(-d2)
    n_d1 = norm.pdf(d1)  # Standard normal PDF
    
    if option_type.upper() == 'CE':
        # Call option
        price = S * N_d1 - K * math.exp(-r * T) * N_d2
        delta = N_d1
        theta = (-S * n_d1 * sigma / (2 * math.sqrt(T)) 
                 - r * K * math.exp(-r * T) * N_d2) / 365  # Daily theta
        rho = K * T * math.exp(-r * T) * N_d2 / 100  # Per 1% change
    else:
        # Put option
        price = K * math.exp(-r * T) * N_neg_d2 - S * N_neg_d1
        delta = N_d1 - 1  # Negative for puts
        theta = (-S * n_d1 * sigma / (2 * math.sqrt(T)) 
                 + r * K * math.exp(-r * T) * N_neg_d2) / 365  # Daily theta
        rho = -K * T * math.exp(-r * T) * N_neg_d2 / 100
    
    # Greeks common to both
    gamma = n_d1 / (S * sigma * math.sqrt(T))
    vega = S * n_d1 * math.sqrt(T) / 100  # Per 1% change in IV
    
    return {
        'theoretical_price': round(price, 2),
        'delta': round(delta, 4),
        'gamma': round(gamma, 6),
        'theta': round(theta, 2),  # Daily theta in ₹
        'vega': round(vega, 2),    # Change per 1% IV move
        'rho': round(rho, 4),
        'd1': round(d1, 4),
        'd2': round(d2, 4)
    }

def calculate_iv_from_premium(S, K, T, r, market_price, option_type='CE'):
    """
    Calculate Implied Volatility from market price using Newton-Raphson method.
    """
    sigma = 0.3  # Initial guess
    
    for _ in range(100):
        greeks = black_scholes_greeks(S, K, T, r, sigma, option_type)
        price = greeks['theoretical_price']
        vega = greeks['vega'] * 100  # Convert back
        
        if vega < 0.0001:
            break
            
        diff = market_price - price
        if abs(diff) < 0.01:
            break
            
        sigma = sigma + diff / vega
        sigma = max(0.01, min(sigma, 3.0))  # Bound between 1% and 300%
    
    return round(sigma * 100, 2)  # Return as percentage

# ================== PAPER TRADE TRACKER CLASS ==================

class PaperTradeTracker:
    """
    Comprehensive paper trading tracker with Greeks analysis.
    """
    
    def __init__(self):
        self.trades = []
        self.load_trades()
    
    def load_trades(self):
        """Load trades from JSON file"""
        if os.path.exists(TRADES_FILE):
            with open(TRADES_FILE, 'r') as f:
                self.trades = json.load(f)
            print(f"✓ Loaded {len(self.trades)} existing trades")
        else:
            self.trades = []
    
    def save_trades(self):
        """Save trades to JSON file"""
        with open(TRADES_FILE, 'w') as f:
            json.dump(self.trades, f, indent=2, default=str)
        print(f"✓ Saved {len(self.trades)} trades to {TRADES_FILE}")
    
    def get_spot_price(self, symbol):
        """Fetch current spot price"""
        try:
            ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
            data = yf.Ticker(ticker).history(period="1d", interval="5m")
            if not data.empty:
                return round(data['Close'].iloc[-1], 2)
        except Exception as e:
            print(f"Error fetching price for {symbol}: {e}")
        return None
    
    def get_lot_size(self, symbol):
        """Get lot size for symbol"""
        return LOT_SIZES.get(symbol, 500)
    
    def add_trade(self, symbol, strike, option_type, entry_premium, 
                  iv=None, dte=None, notes=""):
        """
        Add a new paper trade.
        
        Parameters:
        -----------
        symbol : str - e.g., 'NIFTY', 'RELIANCE'
        strike : float - Strike price
        option_type : str - 'CE' or 'PE'
        entry_premium : float - Premium paid
        iv : float - Implied Volatility (optional, will calculate if not provided)
        dte : int - Days to expiry
        notes : str - Trade notes/rationale
        """
        spot = self.get_spot_price(symbol)
        if not spot:
            print(f"❌ Could not fetch spot price for {symbol}")
            return None
        
        lot_size = self.get_lot_size(symbol)
        
        # Calculate expiry date
        if dte:
            expiry_date = (datetime.now() + timedelta(days=dte)).strftime('%Y-%m-%d')
        else:
            dte = 30  # Default
            expiry_date = (datetime.now() + timedelta(days=dte)).strftime('%Y-%m-%d')
        
        # Calculate IV if not provided
        T = dte / 365
        if iv is None:
            iv = calculate_iv_from_premium(spot, strike, T, RISK_FREE_RATE, 
                                          entry_premium, option_type)
        
        # Calculate entry Greeks
        greeks = black_scholes_greeks(spot, strike, T, RISK_FREE_RATE, 
                                      iv/100, option_type)
        
        trade = {
            'id': len(self.trades) + 1,
            'symbol': symbol.upper(),
            'strike': strike,
            'option_type': option_type.upper(),
            'entry_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'entry_premium': entry_premium,
            'entry_spot': spot,
            'entry_iv': iv,
            'dte_at_entry': dte,
            'expiry_date': expiry_date,
            'lot_size': lot_size,
            'total_cost': round(entry_premium * lot_size, 2),
            'status': 'OPEN',
            'exit_date': None,
            'exit_premium': None,
            'exit_spot': None,
            'pnl': 0,
            'pnl_pct': 0,
            'notes': notes,
            'entry_greeks': greeks,
            'history': [{
                'date': datetime.now().strftime('%Y-%m-%d'),
                'spot': spot,
                'premium': entry_premium,
                'iv': iv,
                'dte': dte,
                'greeks': greeks
            }]
        }
        
        self.trades.append(trade)
        self.save_trades()
        
        self._print_trade_summary(trade, "NEW TRADE ADDED")
        return trade
    
    def update_trade(self, trade_id, current_premium=None, notes=None):
        """Update an existing trade with current market data"""
        trade = self._get_trade(trade_id)
        if not trade:
            print(f"❌ Trade #{trade_id} not found")
            return
        
        if trade['status'] != 'OPEN':
            print(f"❌ Trade #{trade_id} is already closed")
            return
        
        spot = self.get_spot_price(trade['symbol'])
        if not spot:
            print(f"❌ Could not fetch spot price")
            return
        
        # Calculate current DTE
        expiry = datetime.strptime(trade['expiry_date'], '%Y-%m-%d')
        dte = max(0, (expiry - datetime.now()).days)
        T = max(dte, 1) / 365
        
        # If premium not provided, estimate from Greeks
        if current_premium is None:
            # Use last known premium + estimated change
            last_premium = trade['entry_premium']
            spot_change = spot - trade['entry_spot']
            delta = trade['entry_greeks']['delta']
            current_premium = max(0.05, last_premium + (spot_change * delta))
        
        # Calculate current IV
        iv = calculate_iv_from_premium(spot, trade['strike'], T, RISK_FREE_RATE,
                                       current_premium, trade['option_type'])
        
        # Calculate current Greeks
        greeks = black_scholes_greeks(spot, trade['strike'], T, RISK_FREE_RATE,
                                      iv/100, trade['option_type'])
        
        # Calculate P&L
        pnl_per_unit = current_premium - trade['entry_premium']
        pnl = round(pnl_per_unit * trade['lot_size'], 2)
        pnl_pct = round((pnl_per_unit / trade['entry_premium']) * 100, 2)
        
        # Update trade
        trade['pnl'] = pnl
        trade['pnl_pct'] = pnl_pct
        if notes:
            trade['notes'] = notes
        
        # Add to history
        trade['history'].append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'spot': spot,
            'premium': round(current_premium, 2),
            'iv': iv,
            'dte': dte,
            'greeks': greeks,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        })
        
        self.save_trades()
        self._print_trade_update(trade, spot, current_premium, iv, dte, greeks, pnl, pnl_pct)
        return trade
    
    def close_trade(self, trade_id, exit_premium, notes=""):
        """Close an open trade"""
        trade = self._get_trade(trade_id)
        if not trade:
            print(f"❌ Trade #{trade_id} not found")
            return
        
        if trade['status'] != 'OPEN':
            print(f"❌ Trade #{trade_id} is already closed")
            return
        
        spot = self.get_spot_price(trade['symbol'])
        
        pnl_per_unit = exit_premium - trade['entry_premium']
        pnl = round(pnl_per_unit * trade['lot_size'], 2)
        pnl_pct = round((pnl_per_unit / trade['entry_premium']) * 100, 2)
        
        trade['status'] = 'CLOSED'
        trade['exit_date'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        trade['exit_premium'] = exit_premium
        trade['exit_spot'] = spot
        trade['pnl'] = pnl
        trade['pnl_pct'] = pnl_pct
        trade['notes'] = trade['notes'] + f" | EXIT: {notes}" if notes else trade['notes']
        
        self.save_trades()
        self._print_trade_close(trade)
        return trade
    
    def view_trade(self, trade_id):
        """View detailed trade information"""
        trade = self._get_trade(trade_id)
        if not trade:
            print(f"❌ Trade #{trade_id} not found")
            return
        
        self._print_trade_details(trade)
    
    def view_all_trades(self, status='ALL'):
        """View all trades"""
        if status == 'ALL':
            trades = self.trades
        else:
            trades = [t for t in self.trades if t['status'] == status.upper()]
        
        if not trades:
            print("No trades found")
            return
        
        print("\n" + "=" * 100)
        print("PAPER TRADE PORTFOLIO")
        print("=" * 100)
        print(f"\n{'#':<3} {'SYMBOL':<12} {'TYPE':<6} {'STRIKE':<10} {'ENTRY':<10} {'CURRENT P&L':<15} {'STATUS':<8} {'DTE':<5}")
        print("-" * 100)
        
        total_pnl = 0
        for trade in trades:
            expiry = datetime.strptime(trade['expiry_date'], '%Y-%m-%d')
            dte = max(0, (expiry - datetime.now()).days)
            
            pnl_str = f"₹{trade['pnl']:+,.0f} ({trade['pnl_pct']:+.1f}%)"
            opt_type = "Call" if trade['option_type'] == 'CE' else "Put"
            
            print(f"{trade['id']:<3} {trade['symbol']:<12} {opt_type:<6} {trade['strike']:<10} "
                  f"₹{trade['entry_premium']:<9} {pnl_str:<15} {trade['status']:<8} {dte:<5}")
            
            if trade['status'] == 'OPEN':
                total_pnl += trade['pnl']
        
        print("-" * 100)
        print(f"Total Open P&L: ₹{total_pnl:+,.0f}")
        print("=" * 100)
    
    def calculate_portfolio_greeks(self):
        """Calculate aggregate Greeks for all open positions"""
        open_trades = [t for t in self.trades if t['status'] == 'OPEN']
        
        if not open_trades:
            print("No open trades")
            return
        
        total_delta = 0
        total_gamma = 0
        total_theta = 0
        total_vega = 0
        
        print("\n" + "=" * 100)
        print("PORTFOLIO GREEKS SUMMARY")
        print("=" * 100)
        print(f"\n{'SYMBOL':<12} {'TYPE':<6} {'STRIKE':<10} {'LOTS':<6} {'DELTA':<10} {'GAMMA':<10} {'THETA':<10} {'VEGA':<10}")
        print("-" * 100)
        
        for trade in open_trades:
            spot = self.get_spot_price(trade['symbol'])
            if not spot:
                continue
            
            expiry = datetime.strptime(trade['expiry_date'], '%Y-%m-%d')
            dte = max(1, (expiry - datetime.now()).days)
            T = dte / 365
            
            iv = trade.get('entry_iv', 25) / 100
            greeks = black_scholes_greeks(spot, trade['strike'], T, 
                                          RISK_FREE_RATE, iv, trade['option_type'])
            
            lot_size = trade['lot_size']
            
            # Position Greeks (multiply by lot size)
            pos_delta = greeks['delta'] * lot_size
            pos_gamma = greeks['gamma'] * lot_size
            pos_theta = greeks['theta'] * lot_size
            pos_vega = greeks['vega'] * lot_size
            
            total_delta += pos_delta
            total_gamma += pos_gamma
            total_theta += pos_theta
            total_vega += pos_vega
            
            opt_type = "Call" if trade['option_type'] == 'CE' else "Put"
            print(f"{trade['symbol']:<12} {opt_type:<6} {trade['strike']:<10} {lot_size:<6} "
                  f"{pos_delta:<10.2f} {pos_gamma:<10.4f} {pos_theta:<10.2f} {pos_vega:<10.2f}")
        
        print("-" * 100)
        print(f"{'TOTAL':<12} {'':<6} {'':<10} {'':<6} "
              f"{total_delta:<10.2f} {total_gamma:<10.4f} {total_theta:<10.2f} {total_vega:<10.2f}")
        print("=" * 100)
        
        # Interpretation
        print("\n📊 GREEKS INTERPRETATION:")
        print("-" * 50)
        
        if total_delta > 0:
            print(f"  DELTA: {total_delta:+.2f} → Portfolio gains ₹{abs(total_delta):.0f} per 1 point UP move")
        else:
            print(f"  DELTA: {total_delta:+.2f} → Portfolio gains ₹{abs(total_delta):.0f} per 1 point DOWN move")
        
        print(f"  GAMMA: {total_gamma:+.4f} → Delta changes by {total_gamma:.4f} per 1 point move")
        print(f"  THETA: {total_theta:+.2f} → Portfolio loses ₹{abs(total_theta):.0f} per day (time decay)")
        print(f"  VEGA:  {total_vega:+.2f} → Portfolio {'gains' if total_vega > 0 else 'loses'} ₹{abs(total_vega):.0f} per 1% IV increase")
    
    def _get_trade(self, trade_id):
        """Get trade by ID"""
        for trade in self.trades:
            if trade['id'] == trade_id:
                return trade
        return None
    
    def _print_trade_summary(self, trade, title):
        """Print trade summary"""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)
        print(f"  Trade ID: #{trade['id']}")
        print(f"  {trade['symbol']} {trade['strike']} {'CALL' if trade['option_type'] == 'CE' else 'PUT'}")
        print(f"  Entry: ₹{trade['entry_premium']} | Spot: ₹{trade['entry_spot']}")
        print(f"  Total Cost: ₹{trade['total_cost']:,.0f} ({trade['lot_size']} units)")
        print(f"  Expiry: {trade['expiry_date']} ({trade['dte_at_entry']} days)")
        print(f"  IV at Entry: {trade['entry_iv']:.1f}%")
        print("-" * 70)
        print("  ENTRY GREEKS:")
        g = trade['entry_greeks']
        print(f"    Delta: {g['delta']:+.4f} | Gamma: {g['gamma']:.6f}")
        print(f"    Theta: ₹{g['theta']:.2f}/day | Vega: ₹{g['vega']:.2f}/1% IV")
        if trade['notes']:
            print(f"  Notes: {trade['notes']}")
        print("=" * 70)
    
    def _print_trade_update(self, trade, spot, premium, iv, dte, greeks, pnl, pnl_pct):
        """Print trade update"""
        print("\n" + "-" * 70)
        print(f"  TRADE #{trade['id']} UPDATE: {trade['symbol']} {trade['strike']} {'CALL' if trade['option_type'] == 'CE' else 'PUT'}")
        print("-" * 70)
        print(f"  Spot: ₹{trade['entry_spot']} → ₹{spot} ({((spot/trade['entry_spot'])-1)*100:+.2f}%)")
        print(f"  Premium: ₹{trade['entry_premium']} → ₹{premium:.2f} ({pnl_pct:+.1f}%)")
        print(f"  IV: {trade['entry_iv']:.1f}% → {iv:.1f}%")
        print(f"  DTE: {trade['dte_at_entry']} → {dte} days")
        print(f"  P&L: ₹{pnl:+,.0f} ({pnl_pct:+.1f}%)")
        print("-" * 70)
        print("  CURRENT GREEKS:")
        print(f"    Delta: {greeks['delta']:+.4f} | Gamma: {greeks['gamma']:.6f}")
        print(f"    Theta: ₹{greeks['theta']:.2f}/day | Vega: ₹{greeks['vega']:.2f}/1% IV")
        print("-" * 70)
    
    def _print_trade_close(self, trade):
        """Print trade close summary"""
        print("\n" + "=" * 70)
        print(f"  TRADE #{trade['id']} CLOSED")
        print("=" * 70)
        print(f"  {trade['symbol']} {trade['strike']} {'CALL' if trade['option_type'] == 'CE' else 'PUT'}")
        print(f"  Entry: ₹{trade['entry_premium']} → Exit: ₹{trade['exit_premium']}")
        print(f"  Spot: ₹{trade['entry_spot']} → ₹{trade['exit_spot']}")
        print(f"  Duration: {trade['entry_date']} to {trade['exit_date']}")
        
        pnl_color = "🟢" if trade['pnl'] > 0 else "🔴"
        print(f"  {pnl_color} P&L: ₹{trade['pnl']:+,.0f} ({trade['pnl_pct']:+.1f}%)")
        print("=" * 70)
    
    def _print_trade_details(self, trade):
        """Print detailed trade information"""
        print("\n" + "=" * 80)
        print(f"  TRADE #{trade['id']} DETAILS")
        print("=" * 80)
        print(f"  Symbol: {trade['symbol']}")
        print(f"  Type: {trade['strike']} {'CALL' if trade['option_type'] == 'CE' else 'PUT'}")
        print(f"  Status: {trade['status']}")
        print("-" * 80)
        print("  ENTRY:")
        print(f"    Date: {trade['entry_date']}")
        print(f"    Premium: ₹{trade['entry_premium']}")
        print(f"    Spot: ₹{trade['entry_spot']}")
        print(f"    IV: {trade['entry_iv']:.1f}%")
        print(f"    DTE: {trade['dte_at_entry']} days")
        print(f"    Cost: ₹{trade['total_cost']:,.0f} ({trade['lot_size']} units)")
        
        if trade['status'] == 'CLOSED':
            print("-" * 80)
            print("  EXIT:")
            print(f"    Date: {trade['exit_date']}")
            print(f"    Premium: ₹{trade['exit_premium']}")
            print(f"    Spot: ₹{trade['exit_spot']}")
        
        print("-" * 80)
        print(f"  P&L: ₹{trade['pnl']:+,.0f} ({trade['pnl_pct']:+.1f}%)")
        print("-" * 80)
        print("  ENTRY GREEKS:")
        g = trade['entry_greeks']
        print(f"    Delta: {g['delta']:+.4f}")
        print(f"    Gamma: {g['gamma']:.6f}")
        print(f"    Theta: ₹{g['theta']:.2f}/day")
        print(f"    Vega: ₹{g['vega']:.2f}/1% IV")
        
        if trade['notes']:
            print("-" * 80)
            print(f"  Notes: {trade['notes']}")
        
        print("=" * 80)
        
        # Print history
        if len(trade['history']) > 1:
            print("\n  TRADE HISTORY:")
            print("-" * 80)
            print(f"  {'DATE':<12} {'SPOT':<10} {'PREMIUM':<10} {'IV':<8} {'DTE':<5} {'P&L':<12}")
            print("-" * 80)
            for h in trade['history']:
                pnl_str = f"₹{h.get('pnl', 0):+,.0f}" if 'pnl' in h else "-"
                print(f"  {h['date']:<12} ₹{h['spot']:<9} ₹{h['premium']:<9} {h['iv']:<7.1f}% {h['dte']:<5} {pnl_str:<12}")
            print("-" * 80)


# ================== GREEKS EDUCATION ==================

def explain_greeks():
    """Print educational information about Greeks"""
    
    explanation = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                        UNDERSTANDING OPTIONS GREEKS                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  DELTA (Δ) - Directional Risk                                                ║
║  ═══════════════════════════════════════════════════════════════════════════ ║
║  • Measures how much option price changes per ₹1 move in underlying         ║
║  • Call Delta: 0 to +1 (positive, gains when stock rises)                   ║
║  • Put Delta:  -1 to 0 (negative, gains when stock falls)                   ║
║                                                                              ║
║  Example: Delta = 0.50                                                       ║
║  → If NIFTY moves up ₹100, option gains ₹50                                 ║
║                                                                              ║
║  Delta also approximates probability of expiring ITM:                        ║
║  • Delta 0.30 ≈ 30% chance of profit at expiry                              ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  GAMMA (Γ) - Delta's Rate of Change                                          ║
║  ═══════════════════════════════════════════════════════════════════════════ ║
║  • Measures how much Delta changes per ₹1 move                              ║
║  • Highest for ATM options, near zero for deep ITM/OTM                      ║
║  • High Gamma = Delta changes rapidly (good for buyers if right)            ║
║                                                                              ║
║  Example: Delta = 0.50, Gamma = 0.02                                         ║
║  → If NIFTY moves up ₹50, new Delta ≈ 0.50 + (50 × 0.02) = 0.60             ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  THETA (Θ) - Time Decay                                                      ║
║  ═══════════════════════════════════════════════════════════════════════════ ║
║  • Measures how much option loses per day (time value erosion)              ║
║  • Always NEGATIVE for long options (you lose money each day)               ║
║  • Accelerates as expiry approaches (highest in last week)                  ║
║                                                                              ║
║  Example: Theta = -₹5                                                        ║
║  → Your option loses ₹5 per day just from time passing                      ║
║  → Over weekend (3 days): lose ₹15 even if market unchanged                 ║
║                                                                              ║
║  ⚠️ KEY INSIGHT: Theta is your ENEMY as an option buyer!                    ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  VEGA (ν) - Volatility Sensitivity                                           ║
║  ═══════════════════════════════════════════════════════════════════════════ ║
║  • Measures how much option price changes per 1% change in IV               ║
║  • Always POSITIVE for long options (higher IV = higher premium)            ║
║  • Highest for ATM options with longer time to expiry                       ║
║                                                                              ║
║  Example: Vega = ₹15, IV = 20%                                               ║
║  → If IV rises to 22% (+2%), option gains ₹30                               ║
║  → If IV drops to 18% (-2%), option loses ₹30                               ║
║                                                                              ║
║  ⚠️ IV CRUSH: After events (earnings, elections), IV drops sharply!         ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  QUICK REFERENCE FOR OPTION BUYERS                                           ║
║  ═══════════════════════════════════════════════════════════════════════════ ║
║                                                                              ║
║  You WANT:                                                                   ║
║  ✓ High Delta (0.4-0.6) - More responsive to price moves                    ║
║  ✓ Low Theta - Less time decay eating your premium                          ║
║  ✓ Low IV at entry - Cheap premiums, room for IV expansion                  ║
║                                                                              ║
║  You FEAR:                                                                   ║
║  ✗ Theta decay - Every day costs you money                                  ║
║  ✗ IV Crush - Post-event IV drop kills your position                        ║
║  ✗ Wrong direction - Delta works against you                                ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    print(explanation)


def show_greeks_impact(spot, strike, premium, dte, iv, option_type='PE'):
    """
    Show how Greeks impact your position in different scenarios.
    """
    T = dte / 365
    greeks = black_scholes_greeks(spot, strike, T, RISK_FREE_RATE, iv/100, option_type)
    lot_size = LOT_SIZES.get("NIFTY", 25)
    
    opt_name = "CALL" if option_type == 'CE' else "PUT"
    
    print(f"\n{'='*80}")
    print(f"  GREEKS IMPACT ANALYSIS: {strike} {opt_name}")
    print(f"  Spot: ₹{spot} | Premium: ₹{premium} | IV: {iv}% | DTE: {dte}")
    print(f"{'='*80}")
    
    print(f"\n  CURRENT GREEKS (per unit):")
    print(f"  {'─'*40}")
    print(f"  Delta: {greeks['delta']:+.4f}")
    print(f"  Gamma: {greeks['gamma']:.6f}")
    print(f"  Theta: ₹{greeks['theta']:.2f}/day")
    print(f"  Vega:  ₹{greeks['vega']:.2f}/1% IV")
    
    print(f"\n  SCENARIO ANALYSIS (1 lot = {lot_size} units):")
    print(f"  {'─'*70}")
    
    # Scenario 1: Spot moves
    print(f"\n  📈 IF SPOT MOVES (assuming IV unchanged):")
    for move in [-200, -100, -50, +50, +100, +200]:
        pnl = greeks['delta'] * move * lot_size
        print(f"      Spot {move:+4d} points → P&L: ₹{pnl:+,.0f}")
    
    # Scenario 2: Time passes
    print(f"\n  ⏰ IF TIME PASSES (assuming spot unchanged):")
    daily_decay = greeks['theta'] * lot_size
    for days in [1, 3, 5, 7, 14]:
        if days <= dte:
            pnl = daily_decay * days
            print(f"      After {days:2d} days → P&L: ₹{pnl:+,.0f} (theta decay)")
    
    # Scenario 3: IV changes
    print(f"\n  📊 IF IV CHANGES (assuming spot unchanged):")
    iv_impact = greeks['vega'] * lot_size
    for iv_change in [-5, -3, -1, +1, +3, +5]:
        pnl = iv_change * iv_impact
        print(f"      IV {iv_change:+2d}% → P&L: ₹{pnl:+,.0f}")
    
    print(f"\n  {'─'*70}")
    print(f"  💡 KEY TAKEAWAYS:")
    print(f"  {'─'*70}")
    
    if option_type == 'PE':
        print(f"  • Need spot to FALL below {strike - premium:.0f} (breakeven) to profit at expiry")
    else:
        print(f"  • Need spot to RISE above {strike + premium:.0f} (breakeven) to profit at expiry")
    
    print(f"  • Losing ₹{abs(daily_decay):.0f}/day to theta decay")
    print(f"  • {dte} days left = ₹{abs(daily_decay * dte):.0f} max theta loss if held to expiry")
    
    print(f"{'='*80}")


# ================== MAIN MENU ==================

def main():
    """Main interactive menu"""
    tracker = PaperTradeTracker()
    
    while True:
        print("\n" + "=" * 50)
        print("  PAPER TRADING TRACKER - MAIN MENU")
        print("=" * 50)
        print("  1. Add new paper trade")
        print("  2. Update existing trade")
        print("  3. Close a trade")
        print("  4. View all trades")
        print("  5. View trade details")
        print("  6. Portfolio Greeks summary")
        print("  7. Analyze Greeks impact")
        print("  8. Learn about Greeks")
        print("  9. Exit")
        print("-" * 50)
        
        choice = input("  Enter choice (1-9): ").strip()
        
        if choice == '1':
            print("\n  ADD NEW PAPER TRADE")
            print("-" * 40)
            symbol = input("  Symbol (e.g., NIFTY, RELIANCE): ").strip().upper()
            strike = float(input("  Strike price: "))
            opt_type = input("  Option type (CE/PE): ").strip().upper()
            premium = float(input("  Entry premium: ₹"))
            dte = int(input("  Days to expiry: "))
            iv = input("  IV % (press Enter to calculate): ").strip()
            iv = float(iv) if iv else None
            notes = input("  Trade notes/rationale: ").strip()
            
            tracker.add_trade(symbol, strike, opt_type, premium, iv, dte, notes)
        
        elif choice == '2':
            tracker.view_all_trades('OPEN')
            trade_id = int(input("\n  Enter trade ID to update: "))
            premium = input("  Current premium (Enter to estimate): ").strip()
            premium = float(premium) if premium else None
            notes = input("  Update notes: ").strip()
            tracker.update_trade(trade_id, premium, notes if notes else None)
        
        elif choice == '3':
            tracker.view_all_trades('OPEN')
            trade_id = int(input("\n  Enter trade ID to close: "))
            premium = float(input("  Exit premium: ₹"))
            notes = input("  Exit notes: ").strip()
            tracker.close_trade(trade_id, premium, notes)
        
        elif choice == '4':
            status = input("  Filter by status (ALL/OPEN/CLOSED): ").strip().upper() or 'ALL'
            tracker.view_all_trades(status)
        
        elif choice == '5':
            trade_id = int(input("  Enter trade ID: "))
            tracker.view_trade(trade_id)
        
        elif choice == '6':
            tracker.calculate_portfolio_greeks()
        
        elif choice == '7':
            print("\n  GREEKS IMPACT ANALYSIS")
            print("-" * 40)
            spot = float(input("  Current spot price: ₹"))
            strike = float(input("  Strike price: "))
            premium = float(input("  Premium: ₹"))
            dte = int(input("  Days to expiry: "))
            iv = float(input("  IV %: "))
            opt_type = input("  Option type (CE/PE): ").strip().upper()
            show_greeks_impact(spot, strike, premium, dte, iv, opt_type)
        
        elif choice == '8':
            explain_greeks()
        
        elif choice == '9':
            print("\n  Goodbye! Happy paper trading! 📈")
            break
        
        else:
            print("  Invalid choice. Please try again.")


# ================== QUICK START EXAMPLES ==================

def quick_start_demo():
    """
    Quick start demo showing how to use the tracker programmatically.
    Run this to see example usage.
    """
    print("\n" + "=" * 60)
    print("  PAPER TRADING TRACKER - QUICK START DEMO")
    print("=" * 60)
    
    tracker = PaperTradeTracker()
    
    # Example 1: Add a NIFTY Put trade
    print("\n📝 Adding example trade: NIFTY 25500 PUT...")
    tracker.add_trade(
        symbol="NIFTY",
        strike=25500,
        option_type="PE",
        entry_premium=177.55,
        iv=15.5,
        dte=85,
        notes="Bearish view, support at 25000"
    )
    
    # Show Greeks education
    print("\n📚 Explaining Greeks...")
    explain_greeks()
    
    # Show Greeks impact
    print("\n🔍 Analyzing Greeks impact...")
    show_greeks_impact(
        spot=26200, 
        strike=25500, 
        premium=177.55, 
        dte=85, 
        iv=15.5, 
        option_type='PE'
    )
    
    # View portfolio
    print("\n📊 Portfolio summary...")
    tracker.view_all_trades()
    
    print("\n✅ Demo complete! Run main() for interactive menu.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'demo':
        quick_start_demo()
    else:
        main()
