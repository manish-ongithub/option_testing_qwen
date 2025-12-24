"""
Enhanced Options Alert Analyzer v2.0
====================================
Combines Greeks analysis WITH technical analysis of the underlying.

Features:
1. Greeks calculation (Black-Scholes)
2. Historical price analysis
3. Technical indicators (RSI, MACD, EMA, Bollinger Bands)
4. Support/Resistance detection
5. Trend analysis
6. Volume analysis
7. Comprehensive trade scoring

Author: Options Screener Project
"""

import math
import numpy as np
import pandas as pd
from scipy.stats import norm
from datetime import datetime, timedelta
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

# ================== CONFIGURATION ==================

SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}

LOT_SIZES = {
    "NIFTY": 25, "BANKNIFTY": 15,
    "RELIANCE": 250, "HDFCBANK": 550, "ICICIBANK": 700,
    "SBIN": 750, "TCS": 175, "INFY": 400, "TATAMOTORS": 1400,
    "BAJFINANCE": 125, "KOTAKBANK": 400, "AXISBANK": 625,
    "ONGC": 3850, "BPCL": 1800, "MUTHOOTFIN": 375,
    "ADANIENT": 250, "TITAN": 375, "M&M": 350,
}

# ================== RISK-FREE RATE CONFIGURATION ==================
# 
# The risk-free rate is a key input for Black-Scholes options pricing.
# For Indian markets, you can use one of these sources:
#
# 1. RBI Repo Rate (most common):
#    - Current (Dec 2025): 5.50%
#    - Check: https://www.rbi.org.in
#
# 2. 91-Day T-Bill Yield (best for short-term options):
#    - Current: ~5.8-6.0%
#    - More accurate for options < 90 DTE
#
# 3. 364-Day T-Bill Yield (for longer-term options):
#    - Current: ~6.5-7.0%
#    - Better for options > 180 DTE
#
# Impact on Options Pricing:
# - Higher rate → Slightly higher call prices, slightly lower put prices
# - But effect is MINIMAL for most retail trades (0.1-0.5% difference)
# - Direction and IV matter MUCH more than risk-free rate
#
# UPDATE THIS VALUE periodically based on current RBI rates:
# Last updated: December 2025

RISK_FREE_RATE = 0.055  # 5.50% - Current RBI Repo Rate (Dec 2025)

# Alternative: Use dynamic rate fetching (uncomment to enable)
# def get_risk_free_rate():
#     """Fetch current RBI repo rate from web (requires internet)"""
#     try:
#         # You could scrape RBI website or use an API here
#         return 0.055  # Default fallback
#     except:
#         return 0.055

# ================== TECHNICAL INDICATORS ==================

def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD and Signal line"""
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)
    return upper_band, sma, lower_band

def calculate_atr(high, low, close, period=14):
    """Calculate Average True Range"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def find_support_resistance(prices, window=20):
    """Find support and resistance levels using pivot points"""
    supports = []
    resistances = []
    
    for i in range(window, len(prices) - window):
        # Check for local minimum (support)
        if prices.iloc[i] == prices.iloc[i-window:i+window+1].min():
            supports.append(prices.iloc[i])
        # Check for local maximum (resistance)
        if prices.iloc[i] == prices.iloc[i-window:i+window+1].max():
            resistances.append(prices.iloc[i])
    
    # Cluster nearby levels
    def cluster_levels(levels, threshold_pct=1):
        if not levels:
            return []
        levels = sorted(levels)
        clusters = [[levels[0]]]
        for level in levels[1:]:
            if (level - clusters[-1][-1]) / clusters[-1][-1] * 100 < threshold_pct:
                clusters[-1].append(level)
            else:
                clusters.append([level])
        return [np.mean(c) for c in clusters]
    
    support_levels = cluster_levels(supports)[-3:] if supports else []  # Last 3 supports
    resistance_levels = cluster_levels(resistances)[:3] if resistances else []  # First 3 resistances
    
    return support_levels, resistance_levels

def analyze_volume_trend(volume, period=20):
    """Analyze volume trend"""
    avg_volume = volume.rolling(window=period).mean()
    recent_volume = volume.iloc[-5:].mean()
    volume_ratio = recent_volume / avg_volume.iloc[-1] if avg_volume.iloc[-1] > 0 else 1
    
    if volume_ratio > 1.5:
        return "HIGH", volume_ratio
    elif volume_ratio > 1.0:
        return "ABOVE_AVG", volume_ratio
    elif volume_ratio > 0.7:
        return "NORMAL", volume_ratio
    else:
        return "LOW", volume_ratio

# ================== PRICE HISTORY ANALYSIS ==================

def fetch_price_history(symbol, period="6mo"):
    """Fetch historical price data"""
    try:
        ticker = SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        data = yf.Ticker(ticker).history(period=period, interval="1d")
        if data.empty:
            return None
        return data
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def analyze_price_history(symbol):
    """
    Comprehensive price history analysis.
    Returns dict with all technical indicators and analysis.
    """
    
    data = fetch_price_history(symbol, period="6mo")
    if data is None or len(data) < 50:
        return None
    
    close = data['Close']
    high = data['High']
    low = data['Low']
    volume = data['Volume']
    
    current_price = close.iloc[-1]
    
    # Calculate all indicators
    rsi = calculate_rsi(close)
    macd_line, signal_line, macd_hist = calculate_macd(close)
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close)
    atr = calculate_atr(high, low, close)
    
    # Moving averages
    ema_9 = close.ewm(span=9, adjust=False).mean()
    ema_20 = close.ewm(span=20, adjust=False).mean()
    ema_50 = close.ewm(span=50, adjust=False).mean()
    sma_200 = close.rolling(window=min(200, len(close))).mean()
    
    # Support/Resistance
    supports, resistances = find_support_resistance(close)
    
    # Volume analysis
    vol_trend, vol_ratio = analyze_volume_trend(volume)
    
    # Price changes
    change_1d = ((close.iloc[-1] / close.iloc[-2]) - 1) * 100 if len(close) > 1 else 0
    change_5d = ((close.iloc[-1] / close.iloc[-5]) - 1) * 100 if len(close) > 5 else 0
    change_20d = ((close.iloc[-1] / close.iloc[-20]) - 1) * 100 if len(close) > 20 else 0
    change_60d = ((close.iloc[-1] / close.iloc[-60]) - 1) * 100 if len(close) > 60 else 0
    
    # 52-week high/low
    high_52w = high.iloc[-252:].max() if len(high) >= 252 else high.max()
    low_52w = low.iloc[-252:].min() if len(low) >= 252 else low.min()
    pct_from_high = ((current_price / high_52w) - 1) * 100
    pct_from_low = ((current_price / low_52w) - 1) * 100
    
    # Trend determination
    trend_signals = []
    
    # EMA trend
    if current_price > ema_20.iloc[-1] > ema_50.iloc[-1]:
        trend_signals.append(("EMA", "BULLISH", "Price > EMA20 > EMA50"))
    elif current_price < ema_20.iloc[-1] < ema_50.iloc[-1]:
        trend_signals.append(("EMA", "BEARISH", "Price < EMA20 < EMA50"))
    else:
        trend_signals.append(("EMA", "NEUTRAL", "Mixed EMA signals"))
    
    # RSI signal
    current_rsi = rsi.iloc[-1]
    if current_rsi < 30:
        trend_signals.append(("RSI", "OVERSOLD", f"RSI={current_rsi:.1f} (potential bounce)"))
    elif current_rsi > 70:
        trend_signals.append(("RSI", "OVERBOUGHT", f"RSI={current_rsi:.1f} (potential pullback)"))
    elif current_rsi < 45:
        trend_signals.append(("RSI", "WEAK", f"RSI={current_rsi:.1f}"))
    elif current_rsi > 55:
        trend_signals.append(("RSI", "STRONG", f"RSI={current_rsi:.1f}"))
    else:
        trend_signals.append(("RSI", "NEUTRAL", f"RSI={current_rsi:.1f}"))
    
    # MACD signal
    current_macd = macd_line.iloc[-1]
    current_signal = signal_line.iloc[-1]
    current_hist = macd_hist.iloc[-1]
    prev_hist = macd_hist.iloc[-2]
    
    if current_macd > current_signal and current_hist > 0:
        if current_hist > prev_hist:
            trend_signals.append(("MACD", "BULLISH", "MACD above signal, momentum increasing"))
        else:
            trend_signals.append(("MACD", "BULLISH_WEAK", "MACD above signal, momentum slowing"))
    elif current_macd < current_signal and current_hist < 0:
        if current_hist < prev_hist:
            trend_signals.append(("MACD", "BEARISH", "MACD below signal, momentum increasing"))
        else:
            trend_signals.append(("MACD", "BEARISH_WEAK", "MACD below signal, momentum slowing"))
    else:
        trend_signals.append(("MACD", "NEUTRAL", "MACD crossing signal line"))
    
    # Bollinger Band position
    bb_position = (current_price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) * 100
    if bb_position > 80:
        trend_signals.append(("BB", "UPPER", f"Near upper band ({bb_position:.0f}%)"))
    elif bb_position < 20:
        trend_signals.append(("BB", "LOWER", f"Near lower band ({bb_position:.0f}%)"))
    else:
        trend_signals.append(("BB", "MIDDLE", f"Middle of bands ({bb_position:.0f}%)"))
    
    # Overall trend score
    bullish_count = sum(1 for _, signal, _ in trend_signals if 'BULLISH' in signal or signal in ['OVERSOLD', 'LOWER'])
    bearish_count = sum(1 for _, signal, _ in trend_signals if 'BEARISH' in signal or signal in ['OVERBOUGHT', 'UPPER'])
    
    if bullish_count > bearish_count + 1:
        overall_trend = "BULLISH"
    elif bearish_count > bullish_count + 1:
        overall_trend = "BEARISH"
    else:
        overall_trend = "NEUTRAL"
    
    # Find nearest support and resistance
    nearest_support = max([s for s in supports if s < current_price], default=low_52w)
    nearest_resistance = min([r for r in resistances if r > current_price], default=high_52w)
    
    support_distance = ((current_price - nearest_support) / current_price) * 100
    resistance_distance = ((nearest_resistance - current_price) / current_price) * 100
    
    return {
        'current_price': current_price,
        'rsi': current_rsi,
        'macd': current_macd,
        'macd_signal': current_signal,
        'macd_histogram': current_hist,
        'ema_9': ema_9.iloc[-1],
        'ema_20': ema_20.iloc[-1],
        'ema_50': ema_50.iloc[-1],
        'sma_200': sma_200.iloc[-1] if not pd.isna(sma_200.iloc[-1]) else None,
        'bb_upper': bb_upper.iloc[-1],
        'bb_middle': bb_middle.iloc[-1],
        'bb_lower': bb_lower.iloc[-1],
        'bb_position': bb_position,
        'atr': atr.iloc[-1],
        'atr_pct': (atr.iloc[-1] / current_price) * 100,
        'supports': supports,
        'resistances': resistances,
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'support_distance': support_distance,
        'resistance_distance': resistance_distance,
        'volume_trend': vol_trend,
        'volume_ratio': vol_ratio,
        'change_1d': change_1d,
        'change_5d': change_5d,
        'change_20d': change_20d,
        'change_60d': change_60d,
        'high_52w': high_52w,
        'low_52w': low_52w,
        'pct_from_high': pct_from_high,
        'pct_from_low': pct_from_low,
        'trend_signals': trend_signals,
        'overall_trend': overall_trend,
        'bullish_signals': bullish_count,
        'bearish_signals': bearish_count,
        'price_history': close.iloc[-60:].tolist(),  # Last 60 days for mini chart
        'dates': [d.strftime('%Y-%m-%d') for d in close.iloc[-60:].index]
    }

# ================== BLACK-SCHOLES GREEKS ==================

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
        delta = N_d1
        theta = (-S * n_d1 * sigma / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * N_d2) / 365
        prob_itm = N_d2 * 100
    else:
        delta = N_d1 - 1
        theta = (-S * n_d1 * sigma / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * N_neg_d2) / 365
        prob_itm = N_neg_d2 * 100
    
    gamma = n_d1 / (S * sigma * math.sqrt(T))
    vega = S * n_d1 * math.sqrt(T) / 100
    
    return {
        'delta': round(delta, 4),
        'gamma': round(gamma, 6),
        'theta': round(theta, 2),
        'vega': round(vega, 2),
        'prob_itm': round(prob_itm, 1),
    }

# ================== ENHANCED ANALYZER ==================

def enhanced_alert_analysis(
    symbol,
    strike,
    premium,
    option_type,  # 'CE' or 'PE'
    dte,
    iv,
    iv_percentile,
    volume,
    oi,
    capital=50000,
    risk_per_trade_pct=2,
    capture_output=False
):
    """
    Enhanced analysis combining Greeks + Technical Analysis + Price History.
    
    Args:
        capture_output: If True, captures verbose output for export instead of printing
    
    Returns:
        dict with analysis results. If capture_output=True, includes 'verbose_output' key.
    """
    
    opt_name = "CALL" if option_type == 'CE' else "PUT"
    lot_size = LOT_SIZES.get(symbol, 500)
    
    # Output collector for export
    output_lines = []
    
    def out(text=""):
        """Helper to print and optionally capture output"""
        if capture_output:
            output_lines.append(text)
        print(text)
    
    out("")
    out("█" * 100)
    out("█" + " " * 98 + "█")
    out("█" + f"  ENHANCED ALERT ANALYSIS: {symbol} {strike} {opt_name}".ljust(98) + "█")
    out("█" + "  (Greeks + Technical Analysis + Price History)".ljust(98) + "█")
    out("█" + " " * 98 + "█")
    out("█" * 100)
    
    # ==================== SECTION 1: FETCH PRICE HISTORY ====================
    out("")
    out("┌" + "─" * 98 + "┐")
    out("│" + "  📊 SECTION 1: PRICE HISTORY ANALYSIS".ljust(98) + "│")
    out("├" + "─" * 98 + "┤")
    out("│" + "  Fetching 6 months of price data...".ljust(98) + "│")
    
    tech_data = analyze_price_history(symbol)
    
    if tech_data is None:
        out("│" + "  ❌ Could not fetch price history. Analysis will be limited.".ljust(98) + "│")
        out("└" + "─" * 98 + "┘")
        spot = strike * 1.03 if option_type == 'PE' else strike * 0.97  # Estimate
    else:
        spot = tech_data['current_price']
        out("│" + f"  ✓ Data fetched successfully".ljust(98) + "│")
        out("│" + " ".ljust(98) + "│")
        out("│" + f"  Current Price: ₹{spot:,.2f}".ljust(98) + "│")
        out("│" + " ".ljust(98) + "│")
        
        # Price changes
        out("│" + "  PRICE CHANGES:".ljust(98) + "│")
        out("│" + f"    1 Day:   {tech_data['change_1d']:+.2f}%".ljust(98) + "│")
        out("│" + f"    5 Days:  {tech_data['change_5d']:+.2f}%".ljust(98) + "│")
        out("│" + f"    20 Days: {tech_data['change_20d']:+.2f}%".ljust(98) + "│")
        out("│" + f"    60 Days: {tech_data['change_60d']:+.2f}%".ljust(98) + "│")
        out("│" + " ".ljust(98) + "│")
        
        # 52-week range
        out("│" + "  52-WEEK RANGE:".ljust(98) + "│")
        out("│" + f"    High: ₹{tech_data['high_52w']:,.2f} ({tech_data['pct_from_high']:+.1f}% from current)".ljust(98) + "│")
        out("│" + f"    Low:  ₹{tech_data['low_52w']:,.2f} ({tech_data['pct_from_low']:+.1f}% from current)".ljust(98) + "│")
        
        # Visual price position
        range_52w = tech_data['high_52w'] - tech_data['low_52w']
        position_pct = ((spot - tech_data['low_52w']) / range_52w) * 100 if range_52w > 0 else 50
        bar_pos = int(position_pct / 5)
        price_bar = "░" * bar_pos + "█" + "░" * (20 - bar_pos)
        out("│" + f"    Position: [{price_bar}] {position_pct:.0f}% of range".ljust(98) + "│")
        out("└" + "─" * 98 + "┘")
    
    # ==================== SECTION 2: TECHNICAL INDICATORS ====================
    if tech_data:
        out("")
        out("┌" + "─" * 98 + "┐")
        out("│" + "  📈 SECTION 2: TECHNICAL INDICATORS".ljust(98) + "│")
        out("├" + "─" * 98 + "┤")
        
        # RSI
        rsi = tech_data['rsi']
        if rsi < 30:
            rsi_status = "🟢 OVERSOLD - Potential bounce"
        elif rsi < 45:
            rsi_status = "🟡 WEAK - Below neutral"
        elif rsi < 55:
            rsi_status = "⚪ NEUTRAL"
        elif rsi < 70:
            rsi_status = "🟡 STRONG - Above neutral"
        else:
            rsi_status = "🔴 OVERBOUGHT - Potential pullback"
        
        rsi_bar = "█" * int(rsi / 5) + "░" * (20 - int(rsi / 5))
        out("│" + " ".ljust(98) + "│")
        out("│" + f"  RSI (14): {rsi:.1f}".ljust(98) + "│")
        out("│" + f"    [oversold|{rsi_bar}|overbought]".ljust(98) + "│")
        out("│" + f"    Status: {rsi_status}".ljust(98) + "│")
        
        # MACD
        out("│" + " ".ljust(98) + "│")
        out("│" + f"  MACD:".ljust(98) + "│")
        out("│" + f"    MACD Line: {tech_data['macd']:.2f}".ljust(98) + "│")
        out("│" + f"    Signal Line: {tech_data['macd_signal']:.2f}".ljust(98) + "│")
        out("│" + f"    Histogram: {tech_data['macd_histogram']:.2f}".ljust(98) + "│")
        
        if tech_data['macd'] > tech_data['macd_signal']:
            macd_status = "🟢 BULLISH - MACD above signal"
        else:
            macd_status = "🔴 BEARISH - MACD below signal"
        out("│" + f"    Status: {macd_status}".ljust(98) + "│")
        
        # Moving Averages
        out("│" + " ".ljust(98) + "│")
        out("│" + f"  MOVING AVERAGES:".ljust(98) + "│")
        out("│" + f"    EMA 9:   ₹{tech_data['ema_9']:,.2f} ({'↑ Above' if spot > tech_data['ema_9'] else '↓ Below'})".ljust(98) + "│")
        out("│" + f"    EMA 20:  ₹{tech_data['ema_20']:,.2f} ({'↑ Above' if spot > tech_data['ema_20'] else '↓ Below'})".ljust(98) + "│")
        out("│" + f"    EMA 50:  ₹{tech_data['ema_50']:,.2f} ({'↑ Above' if spot > tech_data['ema_50'] else '↓ Below'})".ljust(98) + "│")
        if tech_data['sma_200']:
            out("│" + f"    SMA 200: ₹{tech_data['sma_200']:,.2f} ({'↑ Above' if spot > tech_data['sma_200'] else '↓ Below'})".ljust(98) + "│")
        
        # EMA trend
        if spot > tech_data['ema_9'] > tech_data['ema_20'] > tech_data['ema_50']:
            ema_trend = "🟢 STRONG UPTREND - All EMAs aligned bullish"
        elif spot < tech_data['ema_9'] < tech_data['ema_20'] < tech_data['ema_50']:
            ema_trend = "🔴 STRONG DOWNTREND - All EMAs aligned bearish"
        elif spot > tech_data['ema_20']:
            ema_trend = "🟡 MILD UPTREND - Price above EMA20"
        elif spot < tech_data['ema_20']:
            ema_trend = "🟡 MILD DOWNTREND - Price below EMA20"
        else:
            ema_trend = "⚪ SIDEWAYS - No clear trend"
        out("│" + f"    Trend: {ema_trend}".ljust(98) + "│")
        
        # Bollinger Bands
        out("│" + " ".ljust(98) + "│")
        out("│" + f"  BOLLINGER BANDS (20, 2):".ljust(98) + "│")
        out("│" + f"    Upper:  ₹{tech_data['bb_upper']:,.2f}".ljust(98) + "│")
        out("│" + f"    Middle: ₹{tech_data['bb_middle']:,.2f}".ljust(98) + "│")
        out("│" + f"    Lower:  ₹{tech_data['bb_lower']:,.2f}".ljust(98) + "│")
        out("│" + f"    Position: {tech_data['bb_position']:.0f}% (0%=lower, 100%=upper)".ljust(98) + "│")
        
        if tech_data['bb_position'] > 80:
            bb_status = "🔴 Near UPPER band - Potentially overextended"
        elif tech_data['bb_position'] < 20:
            bb_status = "🟢 Near LOWER band - Potentially oversold"
        else:
            bb_status = "⚪ Middle of bands - Normal range"
        out("│" + f"    Status: {bb_status}".ljust(98) + "│")
        
        # ATR (Volatility)
        out("│" + " ".ljust(98) + "│")
        out("│" + f"  VOLATILITY (ATR 14):".ljust(98) + "│")
        out("│" + f"    ATR: ₹{tech_data['atr']:.2f} ({tech_data['atr_pct']:.2f}% of price)".ljust(98) + "│")
        out("│" + f"    Expected daily range: ±₹{tech_data['atr']:.0f}".ljust(98) + "│")
        
        # Volume
        out("│" + " ".ljust(98) + "│")
        out("│" + f"  VOLUME:".ljust(98) + "│")
        out("│" + f"    Recent vs Average: {tech_data['volume_ratio']:.2f}x ({tech_data['volume_trend']})".ljust(98) + "│")
        
        if tech_data['volume_trend'] == "HIGH":
            vol_status = "🟢 High volume confirms the move"
        elif tech_data['volume_trend'] == "LOW":
            vol_status = "🔴 Low volume - move may not sustain"
        else:
            vol_status = "⚪ Normal volume"
        out("│" + f"    Status: {vol_status}".ljust(98) + "│")
        
        out("└" + "─" * 98 + "┘")
    
    # ==================== SECTION 3: SUPPORT & RESISTANCE ====================
    if tech_data:
        out("")
        out("┌" + "─" * 98 + "┐")
        out("│" + "  🎯 SECTION 3: SUPPORT & RESISTANCE LEVELS".ljust(98) + "│")
        out("├" + "─" * 98 + "┤")
        
        out("│" + " ".ljust(98) + "│")
        out("│" + f"  Current Price: ₹{spot:,.2f}".ljust(98) + "│")
        out("│" + " ".ljust(98) + "│")
        
        # Resistance levels
        out("│" + "  RESISTANCE LEVELS (Upside Targets):".ljust(98) + "│")
        for i, r in enumerate(tech_data.get('resistances', [])[:3], 1):
            dist = ((r - spot) / spot) * 100
            out("│" + f"    R{i}: ₹{r:,.2f} (+{dist:.1f}%)".ljust(98) + "│")
        
        out("│" + " ".ljust(98) + "│")
        
        # Support levels
        out("│" + "  SUPPORT LEVELS (Downside Targets):".ljust(98) + "│")
        for i, s in enumerate(reversed(tech_data.get('supports', [])[-3:]), 1):
            dist = ((spot - s) / spot) * 100
            out("│" + f"    S{i}: ₹{s:,.2f} (-{dist:.1f}%)".ljust(98) + "│")
        
        out("│" + " ".ljust(98) + "│")
        
        # Strike position relative to S/R
        out("│" + "  YOUR STRIKE POSITION:".ljust(98) + "│")
        out("│" + f"    Strike: ₹{strike:,.2f}".ljust(98) + "│")
        
        if option_type == 'PE':
            # For puts, strike should ideally be near support
            nearest_support = tech_data['nearest_support']
            if strike <= nearest_support * 1.02:
                sr_comment = f"🟢 Strike near support (₹{nearest_support:,.0f}) - Good for puts"
            elif strike <= nearest_support * 1.05:
                sr_comment = f"🟡 Strike slightly above support (₹{nearest_support:,.0f})"
            else:
                sr_comment = f"🔴 Strike far from support - May not reach"
        else:
            # For calls, strike should ideally be near resistance
            nearest_resistance = tech_data['nearest_resistance']
            if strike >= nearest_resistance * 0.98:
                sr_comment = f"🔴 Strike above resistance (₹{nearest_resistance:,.0f}) - May not reach"
            elif strike >= nearest_resistance * 0.95:
                sr_comment = f"🟡 Strike near resistance (₹{nearest_resistance:,.0f})"
            else:
                sr_comment = f"🟢 Strike below resistance - Achievable target"
        
        out("│" + f"    Assessment: {sr_comment}".ljust(98) + "│")
        out("└" + "─" * 98 + "┘")
    
    # ==================== SECTION 4: OVERALL TREND VERDICT ====================
    if tech_data:
        out("")
        out("┌" + "─" * 98 + "┐")
        out("│" + "  📋 SECTION 4: TREND VERDICT & SIGNAL ALIGNMENT".ljust(98) + "│")
        out("├" + "─" * 98 + "┤")
        
        out("│" + " ".ljust(98) + "│")
        out("│" + "  INDIVIDUAL SIGNALS:".ljust(98) + "│")
        
        for indicator, signal, comment in tech_data['trend_signals']:
            if 'BULLISH' in signal or signal in ['OVERSOLD', 'LOWER', 'STRONG']:
                icon = "🟢"
            elif 'BEARISH' in signal or signal in ['OVERBOUGHT', 'UPPER', 'WEAK']:
                icon = "🔴"
            else:
                icon = "⚪"
            out("│" + f"    {icon} {indicator}: {signal} - {comment}".ljust(98) + "│")
        
        out("│" + " ".ljust(98) + "│")
        
        bullish = tech_data['bullish_signals']
        bearish = tech_data['bearish_signals']
        total = bullish + bearish
        
        out("│" + f"  SIGNAL COUNT:".ljust(98) + "│")
        out("│" + f"    Bullish Signals: {bullish}".ljust(98) + "│")
        out("│" + f"    Bearish Signals: {bearish}".ljust(98) + "│")
        
        out("│" + " ".ljust(98) + "│")
        
        overall = tech_data['overall_trend']
        if overall == "BULLISH":
            trend_icon = "🟢"
            trend_text = "BULLISH - Favor CALLS"
        elif overall == "BEARISH":
            trend_icon = "🔴"
            trend_text = "BEARISH - Favor PUTS"
        else:
            trend_icon = "⚪"
            trend_text = "NEUTRAL - No clear direction"
        
        out("│" + f"  OVERALL TREND: {trend_icon} {trend_text}".ljust(98) + "│")
        
        # Check alignment with option type
        out("│" + " ".ljust(98) + "│")
        if option_type == 'PE':
            if overall == "BEARISH":
                alignment = "✅ ALIGNED - You're buying PUTS and trend is BEARISH"
                alignment_score = 2
            elif overall == "NEUTRAL":
                alignment = "⚠️ PARTIAL - Trend is NEUTRAL, PUTS may work on breakdown"
                alignment_score = 1
            else:
                alignment = "❌ CONTRARY - You're buying PUTS but trend is BULLISH!"
                alignment_score = 0
        else:
            if overall == "BULLISH":
                alignment = "✅ ALIGNED - You're buying CALLS and trend is BULLISH"
                alignment_score = 2
            elif overall == "NEUTRAL":
                alignment = "⚠️ PARTIAL - Trend is NEUTRAL, CALLS may work on breakout"
                alignment_score = 1
            else:
                alignment = "❌ CONTRARY - You're buying CALLS but trend is BEARISH!"
                alignment_score = 0
        
        out("│" + f"  ALIGNMENT CHECK: {alignment}".ljust(98) + "│")
        out("└" + "─" * 98 + "┘")
    else:
        alignment_score = 1  # Default to neutral if no data
    
    # ==================== SECTION 5: GREEKS ANALYSIS ====================
    T = dte / 365
    sigma = iv / 100
    greeks = black_scholes_greeks(spot, strike, T, RISK_FREE_RATE, sigma, option_type)
    
    total_cost = premium * lot_size
    breakeven = strike + premium if option_type == 'CE' else strike - premium
    
    pos_delta = greeks['delta'] * lot_size
    pos_theta = greeks['theta'] * lot_size
    pos_vega = greeks['vega'] * lot_size
    
    out("")
    out("┌" + "─" * 98 + "┐")
    out("│" + "  🔢 SECTION 5: OPTIONS GREEKS".ljust(98) + "│")
    out("├" + "─" * 98 + "┤")
    out("│" + " ".ljust(98) + "│")
    out("│" + f"  Premium: ₹{premium:.2f} | Total Cost: ₹{total_cost:,.2f} | Lot Size: {lot_size}".ljust(98) + "│")
    out("│" + f"  Breakeven: ₹{breakeven:,.2f}".ljust(98) + "│")
    out("│" + " ".ljust(98) + "│")
    out("│" + f"  GREEKS (per lot):".ljust(98) + "│")
    out("│" + f"    Delta: {pos_delta:+.2f} (₹{abs(pos_delta):.0f} per 1 point move)".ljust(98) + "│")
    out("│" + f"    Theta: ₹{pos_theta:.2f}/day (loses ₹{abs(pos_theta):.0f} daily)".ljust(98) + "│")
    out("│" + f"    Vega:  ₹{pos_vega:.2f} per 1% IV change".ljust(98) + "│")
    out("│" + f"    Probability ITM: {greeks['prob_itm']:.1f}%".ljust(98) + "│")
    out("└" + "─" * 98 + "┘")
    
    # ==================== SECTION 6: COMPREHENSIVE SCORING ====================
    out("")
    out("┌" + "─" * 98 + "┐")
    out("│" + "  🏆 SECTION 6: COMPREHENSIVE TRADE SCORE".ljust(98) + "│")
    out("├" + "─" * 98 + "┤")
    
    scores = []
    
    # 1. Trend Alignment (0-2 points)
    scores.append(("Trend Alignment", alignment_score, 2, 
                   "Does technical trend support your option direction?"))
    
    # 2. IV Favorability (0-2 points)
    if iv_percentile <= 30:
        iv_score = 2
    elif iv_percentile <= 50:
        iv_score = 1.5
    elif iv_percentile <= 70:
        iv_score = 1
    else:
        iv_score = 0
    scores.append(("IV Percentile", iv_score, 2, 
                   f"IVP={iv_percentile:.0f}% ({'Low/Good' if iv_score >= 1.5 else 'High/Bad'})"))
    
    # 3. Strike Selection (0-2 points)
    distance_pct = abs((strike - spot) / spot * 100)
    if distance_pct <= 3:
        strike_score = 2
    elif distance_pct <= 5:
        strike_score = 1.5
    elif distance_pct <= 8:
        strike_score = 1
    else:
        strike_score = 0.5
    scores.append(("Strike Distance", strike_score, 2, 
                   f"{distance_pct:.1f}% from spot"))
    
    # 4. Time Value (0-2 points)
    if dte >= 30:
        time_score = 2
    elif dte >= 14:
        time_score = 1.5
    elif dte >= 7:
        time_score = 1
    else:
        time_score = 0.5
    scores.append(("Time to Expiry", time_score, 2, 
                   f"{dte} days"))
    
    # 5. Liquidity (0-2 points)
    if volume >= 1000 and oi >= 5000:
        liq_score = 2
    elif volume >= 500 and oi >= 1000:
        liq_score = 1.5
    elif volume >= 100:
        liq_score = 1
    else:
        liq_score = 0.5
    scores.append(("Liquidity", liq_score, 2, 
                   f"Vol={volume:,}, OI={oi:,}"))
    
    # 6. RSI Alignment (0-1 point) - Only if we have tech data
    if tech_data:
        rsi = tech_data['rsi']
        if option_type == 'PE':
            # For puts, want RSI to be high (overbought) or falling
            if rsi > 60:
                rsi_score = 1
            elif rsi > 50:
                rsi_score = 0.5
            else:
                rsi_score = 0
        else:
            # For calls, want RSI to be low (oversold) or rising
            if rsi < 40:
                rsi_score = 1
            elif rsi < 50:
                rsi_score = 0.5
            else:
                rsi_score = 0
        scores.append(("RSI Alignment", rsi_score, 1, 
                       f"RSI={rsi:.0f}"))
    
    # 7. Support/Resistance (0-1 point)
    if tech_data:
        if option_type == 'PE':
            # For puts, check if there's room to fall
            if tech_data['support_distance'] > 3:
                sr_score = 1
            elif tech_data['support_distance'] > 1.5:
                sr_score = 0.5
            else:
                sr_score = 0
        else:
            # For calls, check if there's room to rise
            if tech_data['resistance_distance'] > 3:
                sr_score = 1
            elif tech_data['resistance_distance'] > 1.5:
                sr_score = 0.5
            else:
                sr_score = 0
        scores.append(("S/R Room", sr_score, 1, 
                       f"{'Support' if option_type == 'PE' else 'Resistance'} distance"))
    
    out("│" + " ".ljust(98) + "│")
    out("│" + f"  {'FACTOR':<25} {'SCORE':<12} {'MAX':<8} {'NOTES':<50}".ljust(98) + "│")
    out("│" + "  " + "─" * 94 + "│")
    
    total_score = 0
    max_score = 0
    
    for factor, score, max_s, notes in scores:
        total_score += score
        max_score += max_s
        bar = "█" * int(score / max_s * 5) + "░" * (5 - int(score / max_s * 5))
        out("│" + f"  {factor:<25} [{bar}] {score}/{max_s}".ljust(50) + f"{notes}".ljust(48) + "│")
    
    pct_score = (total_score / max_score) * 100
    
    out("│" + "  " + "─" * 94 + "│")
    out("│" + f"  {'TOTAL':<25} {total_score:.1f}/{max_score:.0f} ({pct_score:.0f}%)".ljust(98) + "│")
    out("│" + " ".ljust(98) + "│")
    
    # Final verdict
    if pct_score >= 80:
        verdict = "🟢 EXCELLENT - Strong setup, consider trading"
        action = "TRADE"
    elif pct_score >= 65:
        verdict = "🟢 GOOD - Favorable conditions, can trade with caution"
        action = "TRADE_CAUTIOUS"
    elif pct_score >= 50:
        verdict = "🟡 MODERATE - Mixed signals, paper trade first"
        action = "PAPER_TRADE"
    elif pct_score >= 35:
        verdict = "🟠 WEAK - Unfavorable conditions, avoid or reduce size"
        action = "AVOID"
    else:
        verdict = "🔴 POOR - Multiple red flags, do not trade"
        action = "NO_TRADE"
    
    out("│" + f"  VERDICT: {verdict}".ljust(98) + "│")
    out("└" + "─" * 98 + "┘")
    
    # ==================== SECTION 7: FINAL RECOMMENDATION ====================
    out("")
    out("┌" + "─" * 98 + "┐")
    out("│" + "  📝 SECTION 7: FINAL RECOMMENDATION".ljust(98) + "│")
    out("├" + "─" * 98 + "┤")
    out("│" + " ".ljust(98) + "│")
    
    if action == "TRADE":
        out("│" + "  ✅ RECOMMENDATION: TRADE".ljust(98) + "│")
        out("│" + " ".ljust(98) + "│")
        out("│" + f"  • Entry: Buy {symbol} {strike} {opt_name} @ ₹{premium:.2f}".ljust(98) + "│")
        out("│" + f"  • Quantity: 1 lot ({lot_size} units)".ljust(98) + "│")
        out("│" + f"  • Investment: ₹{total_cost:,.2f}".ljust(98) + "│")
        out("│" + f"  • Stop Loss: ₹{premium * 0.5:.2f} (-50%)".ljust(98) + "│")
        out("│" + f"  • Target: ₹{premium * 1.5:.2f} (+50%)".ljust(98) + "│")
    elif action == "TRADE_CAUTIOUS":
        out("│" + "  ⚠️ RECOMMENDATION: TRADE WITH CAUTION".ljust(98) + "│")
        out("│" + " ".ljust(98) + "│")
        out("│" + "  • Consider smaller position size".ljust(98) + "│")
        out("│" + "  • Use tighter stop loss (-40%)".ljust(98) + "│")
        out("│" + "  • Watch closely for reversal signals".ljust(98) + "│")
    elif action == "PAPER_TRADE":
        out("│" + "  📋 RECOMMENDATION: PAPER TRADE ONLY".ljust(98) + "│")
        out("│" + " ".ljust(98) + "│")
        out("│" + "  • Track this trade without real money".ljust(98) + "│")
        out("│" + "  • Learn how it behaves".ljust(98) + "│")
        out("│" + "  • Wait for better setup to trade real".ljust(98) + "│")
    else:
        out("│" + "  ❌ RECOMMENDATION: DO NOT TRADE".ljust(98) + "│")
        out("│" + " ".ljust(98) + "│")
        out("│" + "  • Multiple factors against this trade".ljust(98) + "│")
        out("│" + "  • Look for better opportunities".ljust(98) + "│")
    
    out("│" + " ".ljust(98) + "│")
    out("└" + "─" * 98 + "┘")
    
    out("")
    out("█" * 100)
    out("█" + " ANALYSIS COMPLETE ".center(98, "═") + "█")
    out("█" * 100)
    
    # Build result dict
    result = {
        'score': pct_score,
        'action': action,
        'tech_data': tech_data,
        'greeks': greeks,
        'total_cost': total_cost,
        'breakeven': breakeven
    }
    
    # Add verbose output if capturing
    if capture_output:
        result['verbose_output'] = "\n".join(output_lines)
    
    return result


# ================== MAIN ====================

if __name__ == "__main__":
    
    print("\n" + "=" * 100)
    print("  ENHANCED OPTIONS ALERT ANALYZER v2.0")
    print("  Analyzing: NIFTY 25500 PUT (with Technical Analysis)")
    print("=" * 100)
   
    # Analyze Alert #5 from screener
    result = enhanced_alert_analysis(
        symbol="NIFTY",
        strike=25500,
        premium=206.85,
        option_type="PE",
        dte=82,
        iv=11.21,
        iv_percentile=25,
        volume=1371,
        oi=5171,
        capital=50000,
        risk_per_trade_pct=2
    )
    
    print("\n")
    print("=" * 100)
    print("  To analyze another alert, modify the parameters and run again!")
    print("  Or import and call: enhanced_alert_analysis(...)")
    print("=" * 100)