"""
Alert Connector v1.2
=====================
Connects the Options Screener v3.3 with the Enhanced Alert Analyzer.
Provides batch analysis, comparison, and ranking of multiple alerts.

Features:
1. Read alerts from screener CSV output
2. Batch analyze multiple alerts
3. Score and rank alerts
4. Compare alerts side-by-side
5. Generate summary reports (TXT, HTML, PDF)
6. Generate verbose analysis reports (TXT, HTML, PDF)
7. Filter and sort by various criteria
8. Export detailed technical analysis with all indicators

Author: Options Screener Project
"""

import pandas as pd
import numpy as np
from datetime import datetime
import os
import sys
from typing import List, Dict, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# For PDF generation using fpdf2
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

# Import the enhanced analyzer
from enhanced_alert_analyzer import (
    enhanced_alert_analysis,
    analyze_price_history,
    black_scholes_greeks,
    LOT_SIZES,
    RISK_FREE_RATE
)

# ================== CONFIGURATION ==================

# Default CSV file from screener
DEFAULT_CSV_FILE = "new_screener_options_scan_log_v3_3.csv"

# Analysis settings
DEFAULT_CAPITAL = 100000  # ₹1 Lakh default capital
DEFAULT_RISK_PCT = 2      # 2% risk per trade

# Ranking weights (customizable)
RANKING_WEIGHTS = {
    'score': 0.35,           # Overall analysis score
    'iv_percentile': 0.20,   # Lower IV = better (inverted)
    'volume': 0.15,          # Higher volume = better
    'oi': 0.10,              # Higher OI = better
    'dte': 0.10,             # Prefer 14-45 DTE sweet spot
    'distance': 0.10,        # Closer to ATM = better
}

# ================== ALERT READER ==================

# Expected CSV columns from the screener
CSV_COLUMNS = [
    "timestamp", "symbol", "type", "strategy", "strike", "premium", "price_source",
    "spot", "volume", "oi", "oi_change", "iv", "iv_percentile", "iv_rank", "iv_source",
    "market_regime", "rsi", "tier", "moneyness", "expiry", "days_to_expiry",
    "lot_size", "total_cost", "breakeven", "distance_from_spot"
]

def read_alerts_from_csv(
    csv_file: str = DEFAULT_CSV_FILE,
    filter_symbol: str = None,
    filter_type: str = None,  # 'CE' or 'PE'
    filter_strategy: str = None,  # 'Long Call' or 'Long Put'
    min_volume: int = 0,
    max_iv_percentile: float = 100,
    limit: int = None
) -> pd.DataFrame:
    """
    Read alerts from screener CSV output with optional filters.
    
    Args:
        csv_file: Path to CSV file
        filter_symbol: Filter by specific symbol
        filter_type: Filter by option type ('CE' or 'PE')
        filter_strategy: Filter by strategy ('Long Call' or 'Long Put')
        min_volume: Minimum volume threshold
        max_iv_percentile: Maximum IV percentile
        limit: Limit number of alerts returned
    
    Returns:
        DataFrame with filtered alerts
    """
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        return pd.DataFrame()
    
    try:
        # First, check if CSV has headers by reading first line
        with open(csv_file, 'r') as f:
            first_line = f.readline().strip()
        
        # Check if first line looks like a header (contains 'Timestamp' or 'timestamp')
        has_header = 'timestamp' in first_line.lower() or 'symbol' in first_line.lower()
        
        if has_header:
            # Read with headers
            df = pd.read_csv(csv_file)
            
            # Standardize column names (handle variations)
            column_mapping = {
                'Type': 'type',
                'TYPE': 'type',
                'Symbol': 'symbol',
                'SYMBOL': 'symbol',
                'Strike': 'strike',
                'STRIKE': 'strike',
                'Premium': 'premium',
                'PREMIUM': 'premium',
                'Volume': 'volume',
                'VOLUME': 'volume',
                'OI': 'oi',
                'OI_Change': 'oi_change',
                'IV': 'iv',
                'IV_Percentile': 'iv_percentile',
                'IV_Rank': 'iv_rank',
                'DaysToExpiry': 'days_to_expiry',
                'Strategy': 'strategy',
                'Moneyness': 'moneyness',
                'TotalCost': 'total_cost',
                'Breakeven': 'breakeven',
                'DistanceFromSpot': 'distance_from_spot',
                'Spot': 'spot',
                'LotSize': 'lot_size',
                'Expiry': 'expiry',
                'Timestamp': 'timestamp',
                'PriceSource': 'price_source',
                'IV_Source': 'iv_source',
                'Market_Regime': 'market_regime',
                'RSI': 'rsi',
                'Tier': 'tier',
            }
            df = df.rename(columns=column_mapping)
        else:
            # No headers - use predefined column names
            df = pd.read_csv(csv_file, header=None, names=CSV_COLUMNS)
        
        if df.empty:
            print("⚠️ CSV file is empty")
            return df
        
        # Convert numeric columns
        numeric_cols = ['strike', 'premium', 'spot', 'volume', 'oi', 'oi_change', 
                       'iv', 'iv_percentile', 'iv_rank', 'rsi', 'days_to_expiry',
                       'lot_size', 'total_cost', 'breakeven']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Apply filters
        if filter_symbol:
            df = df[df['symbol'].str.upper() == filter_symbol.upper()]
        
        if filter_type:
            # Handle both 'type' column (CE/PE) and 'strategy' column (Long Call/Long Put)
            if 'type' in df.columns and df['type'].dtype == 'object':
                df = df[df['type'].str.upper() == filter_type.upper()]
            elif 'strategy' in df.columns:
                if filter_type.upper() in ['CE', 'CALL']:
                    df = df[df['strategy'].str.contains('Call', case=False, na=False)]
                else:
                    df = df[df['strategy'].str.contains('Put', case=False, na=False)]
        
        if filter_strategy:
            df = df[df['strategy'].str.contains(filter_strategy, case=False, na=False)]
        
        if min_volume > 0 and 'volume' in df.columns:
            df = df[df['volume'] >= min_volume]
        
        if max_iv_percentile < 100 and 'iv_percentile' in df.columns:
            df = df[df['iv_percentile'] <= max_iv_percentile]
        
        if limit:
            df = df.head(limit)
        
        print(f"✓ Loaded {len(df)} alerts from {csv_file}")
        return df
    
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def get_latest_alerts(
    csv_file: str = DEFAULT_CSV_FILE,
    hours: int = 24
) -> pd.DataFrame:
    """Get alerts from the last N hours."""
    df = read_alerts_from_csv(csv_file)
    
    if df.empty or 'timestamp' not in df.columns:
        return df
    
    try:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        cutoff = datetime.now() - pd.Timedelta(hours=hours)
        df = df[df['timestamp'] >= cutoff]
        print(f"✓ Found {len(df)} alerts from last {hours} hours")
    except:
        pass
    
    return df


# ================== BATCH ANALYZER ==================

def analyze_single_alert(
    alert: dict, 
    verbose: bool = True,
    capture_output: bool = False,
    export_format: str = None,
    export_filename: str = None
) -> dict:
    """
    Analyze a single alert using the enhanced analyzer.
    
    Args:
        alert: Dictionary with alert data
        verbose: Print detailed analysis (True) or silent mode (False)
        capture_output: If True, captures verbose output for export
        export_format: 'txt', 'html', 'pdf', or 'all' to auto-export
        export_filename: Base filename for export (auto-generated if None)
    
    Returns:
        Dictionary with analysis results (includes 'verbose_output' if capture_output=True)
    """
    # Extract required fields
    symbol = alert.get('symbol', '')
    strike = float(alert.get('strike', 0))
    premium = float(alert.get('premium', 0))
    option_type = alert.get('type', 'CE')
    dte = int(alert.get('days_to_expiry', 0))
    iv = float(alert.get('iv', 20))
    iv_percentile = float(alert.get('iv_percentile', 50))
    volume = int(alert.get('volume', 0))
    oi = int(alert.get('oi', alert.get('open_interest', 0)))
    
    # Map strategy to option type if needed
    strategy = alert.get('strategy', '')
    if 'Call' in strategy:
        option_type = 'CE'
    elif 'Put' in strategy:
        option_type = 'PE'
    
    # Determine if we need to capture output
    should_capture = capture_output or export_format is not None
    
    if verbose:
        result = enhanced_alert_analysis(
            symbol=symbol,
            strike=strike,
            premium=premium,
            option_type=option_type,
            dte=dte,
            iv=iv,
            iv_percentile=iv_percentile,
            volume=volume,
            oi=oi,
            capital=DEFAULT_CAPITAL,
            risk_per_trade_pct=DEFAULT_RISK_PCT,
            capture_output=should_capture
        )
    else:
        # Silent mode - calculate score without printing
        result = analyze_alert_silent(
            symbol=symbol,
            strike=strike,
            premium=premium,
            option_type=option_type,
            dte=dte,
            iv=iv,
            iv_percentile=iv_percentile,
            volume=volume,
            oi=oi
        )
    
    # Add original alert data to result
    result['alert'] = alert
    result['symbol'] = symbol
    result['strike'] = strike
    result['option_type'] = option_type
    result['premium'] = premium
    result['dte'] = dte
    result['iv'] = iv
    result['iv_percentile'] = iv_percentile
    result['volume'] = volume
    result['oi'] = oi
    
    # Auto-export if format specified
    if export_format and result.get('verbose_output'):
        exported = export_verbose_analysis(
            verbose_output=result['verbose_output'],
            symbol=symbol,
            strike=strike,
            option_type=option_type,
            format=export_format,
            base_filename=export_filename
        )
        result['exported_files'] = exported
    
    return result


def analyze_alert_silent(
    symbol: str,
    strike: float,
    premium: float,
    option_type: str,
    dte: int,
    iv: float,
    iv_percentile: float,
    volume: int,
    oi: int
) -> dict:
    """
    Analyze an alert without verbose output.
    Returns only the score and key metrics.
    """
    lot_size = LOT_SIZES.get(symbol, 500)
    total_cost = premium * lot_size
    breakeven = strike + premium if option_type == 'CE' else strike - premium
    
    # Get technical data
    tech_data = analyze_price_history(symbol)
    
    if tech_data:
        spot = tech_data['current_price']
        overall_trend = tech_data['overall_trend']
    else:
        spot = strike * (0.97 if option_type == 'CE' else 1.03)
        overall_trend = 'NEUTRAL'
    
    # Calculate Greeks
    T = dte / 365
    sigma = iv / 100 if iv > 0 else 0.20
    greeks = black_scholes_greeks(spot, strike, T, RISK_FREE_RATE, sigma, option_type)
    
    # Calculate scores (same logic as enhanced_alert_analysis)
    scores = []
    
    # 1. Trend Alignment
    if option_type == 'PE':
        if overall_trend == "BEARISH":
            alignment_score = 2
        elif overall_trend == "NEUTRAL":
            alignment_score = 1
        else:
            alignment_score = 0
    else:
        if overall_trend == "BULLISH":
            alignment_score = 2
        elif overall_trend == "NEUTRAL":
            alignment_score = 1
        else:
            alignment_score = 0
    scores.append(alignment_score)
    
    # 2. IV Favorability
    if iv_percentile <= 30:
        iv_score = 2
    elif iv_percentile <= 50:
        iv_score = 1.5
    elif iv_percentile <= 70:
        iv_score = 1
    else:
        iv_score = 0
    scores.append(iv_score)
    
    # 3. Strike Selection
    distance_pct = abs((strike - spot) / spot * 100) if spot > 0 else 5
    if distance_pct <= 3:
        strike_score = 2
    elif distance_pct <= 5:
        strike_score = 1.5
    elif distance_pct <= 8:
        strike_score = 1
    else:
        strike_score = 0.5
    scores.append(strike_score)
    
    # 4. Time Value
    if dte >= 30:
        time_score = 2
    elif dte >= 14:
        time_score = 1.5
    elif dte >= 7:
        time_score = 1
    else:
        time_score = 0.5
    scores.append(time_score)
    
    # 5. Liquidity
    if volume >= 1000 and oi >= 5000:
        liq_score = 2
    elif volume >= 500 and oi >= 1000:
        liq_score = 1.5
    elif volume >= 100:
        liq_score = 1
    else:
        liq_score = 0.5
    scores.append(liq_score)
    
    # Total score
    total_score = sum(scores)
    max_score = 10  # 5 factors × 2 max each
    pct_score = (total_score / max_score) * 100
    
    # Determine action
    if pct_score >= 80:
        action = "TRADE"
    elif pct_score >= 65:
        action = "TRADE_CAUTIOUS"
    elif pct_score >= 50:
        action = "PAPER_TRADE"
    elif pct_score >= 35:
        action = "AVOID"
    else:
        action = "NO_TRADE"
    
    return {
        'score': pct_score,
        'action': action,
        'tech_data': tech_data,
        'greeks': greeks,
        'total_cost': total_cost,
        'breakeven': breakeven,
        'spot': spot,
        'overall_trend': overall_trend,
        'distance_pct': distance_pct,
        'alignment_score': alignment_score,
        'iv_score': iv_score,
        'strike_score': strike_score,
        'time_score': time_score,
        'liq_score': liq_score,
    }


def batch_analyze_alerts(
    alerts: pd.DataFrame,
    verbose: bool = False,
    max_alerts: int = 20
) -> List[dict]:
    """
    Analyze multiple alerts in batch.
    
    Args:
        alerts: DataFrame with alerts
        verbose: Print detailed analysis for each alert
        max_alerts: Maximum number of alerts to analyze
    
    Returns:
        List of analysis results sorted by score
    """
    if alerts.empty:
        print("❌ No alerts to analyze")
        return []
    
    results = []
    total = min(len(alerts), max_alerts)
    
    print(f"\n{'='*80}")
    print(f"  BATCH ANALYSIS: Analyzing {total} alerts")
    print(f"{'='*80}\n")
    
    for i, (idx, row) in enumerate(alerts.head(max_alerts).iterrows()):
        alert = row.to_dict()
        
        if not verbose:
            print(f"[{i+1}/{total}] Analyzing {alert.get('symbol', '?')} {alert.get('strike', '?')} {alert.get('strategy', '?')}...", end=" ")
        
        try:
            result = analyze_single_alert(alert, verbose=verbose)
            results.append(result)
            
            if not verbose:
                score = result.get('score', 0)
                action = result.get('action', 'UNKNOWN')
                print(f"Score: {score:.0f}% → {action}")
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    # Sort by score descending
    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    return results


# ================== COMPARISON & RANKING ==================

def calculate_composite_rank(result: dict) -> float:
    """
    Calculate a composite ranking score using weighted factors.
    """
    score = result.get('score', 0)
    iv_pct = result.get('iv_percentile', 50)
    volume = result.get('volume', 0)
    oi = result.get('oi', 0)
    dte = result.get('dte', 0)
    distance = result.get('distance_pct', 5)
    
    # Normalize factors to 0-100 scale
    score_norm = score  # Already 0-100
    
    # IV: Lower is better, invert
    iv_norm = 100 - iv_pct
    
    # Volume: Log scale, cap at 100
    volume_norm = min(100, np.log10(max(1, volume)) * 25)
    
    # OI: Log scale, cap at 100
    oi_norm = min(100, np.log10(max(1, oi)) * 20)
    
    # DTE: Sweet spot is 14-45 days
    if 14 <= dte <= 45:
        dte_norm = 100
    elif 7 <= dte < 14 or 45 < dte <= 60:
        dte_norm = 70
    elif 3 <= dte < 7 or 60 < dte <= 90:
        dte_norm = 40
    else:
        dte_norm = 20
    
    # Distance: Closer to ATM is better
    if distance <= 2:
        distance_norm = 100
    elif distance <= 4:
        distance_norm = 80
    elif distance <= 6:
        distance_norm = 60
    else:
        distance_norm = 40
    
    # Weighted composite
    composite = (
        RANKING_WEIGHTS['score'] * score_norm +
        RANKING_WEIGHTS['iv_percentile'] * iv_norm +
        RANKING_WEIGHTS['volume'] * volume_norm +
        RANKING_WEIGHTS['oi'] * oi_norm +
        RANKING_WEIGHTS['dte'] * dte_norm +
        RANKING_WEIGHTS['distance'] * distance_norm
    )
    
    return composite


def rank_alerts(results: List[dict]) -> List[dict]:
    """
    Rank analyzed alerts by composite score.
    """
    for result in results:
        result['composite_rank'] = calculate_composite_rank(result)
    
    # Sort by composite rank descending
    results.sort(key=lambda x: x.get('composite_rank', 0), reverse=True)
    
    # Add rank numbers
    for i, result in enumerate(results, 1):
        result['rank'] = i
    
    return results


def compare_alerts(results: List[dict], top_n: int = 10) -> None:
    """
    Display a comparison table of top alerts.
    """
    if not results:
        print("❌ No results to compare")
        return
    
    print("\n")
    print("█" * 120)
    print("█" + " ALERT COMPARISON & RANKING ".center(118) + "█")
    print("█" * 120)
    print()
    
    # Header
    print("┌" + "─" * 118 + "┐")
    print("│" + f"{'#':^4}│{'SYMBOL':^12}│{'STRIKE':^10}│{'TYPE':^6}│{'PREMIUM':^10}│{'SCORE':^8}│{'IV%':^6}│{'VOL':^8}│{'DTE':^5}│{'ACTION':^15}│{'COMPOSITE':^10}│".ljust(118) + "│")
    print("├" + "─" * 118 + "┤")
    
    # Data rows
    for result in results[:top_n]:
        rank = result.get('rank', '-')
        symbol = result.get('symbol', '?')[:10]
        strike = result.get('strike', 0)
        opt_type = 'CALL' if result.get('option_type', 'CE') == 'CE' else 'PUT'
        premium = result.get('premium', 0)
        score = result.get('score', 0)
        iv_pct = result.get('iv_percentile', 0)
        volume = result.get('volume', 0)
        dte = result.get('dte', 0)
        action = result.get('action', '?')
        composite = result.get('composite_rank', 0)
        
        # Action with emoji
        action_display = {
            'TRADE': '✅ TRADE',
            'TRADE_CAUTIOUS': '⚠️ CAUTIOUS',
            'PAPER_TRADE': '📋 PAPER',
            'AVOID': '🟠 AVOID',
            'NO_TRADE': '❌ NO',
        }.get(action, action)
        
        row = f"│{rank:^4}│{symbol:^12}│{strike:^10.0f}│{opt_type:^6}│₹{premium:^8.2f}│{score:^7.0f}%│{iv_pct:^6.0f}│{volume:^8,}│{dte:^5}│{action_display:^15}│{composite:^9.1f}│"
        print(row.ljust(119) + "│")
    
    print("└" + "─" * 118 + "┘")
    
    # Summary statistics
    if len(results) > 0:
        scores = [r.get('score', 0) for r in results]
        tradeable = sum(1 for r in results if r.get('action') in ['TRADE', 'TRADE_CAUTIOUS'])
        
        print()
        print(f"  📊 SUMMARY:")
        print(f"     Total Alerts Analyzed: {len(results)}")
        print(f"     Tradeable (Score ≥65%): {tradeable}")
        print(f"     Average Score: {np.mean(scores):.1f}%")
        print(f"     Best Score: {max(scores):.1f}%")
        print(f"     Worst Score: {min(scores):.1f}%")
    
    print()


def detailed_comparison(results: List[dict], indices: List[int] = None) -> None:
    """
    Show detailed side-by-side comparison of specific alerts.
    
    Args:
        results: List of analyzed results
        indices: List of indices (ranks) to compare (default: top 3)
    """
    if not results:
        print("❌ No results to compare")
        return
    
    if indices is None:
        indices = [0, 1, 2] if len(results) >= 3 else list(range(len(results)))
    
    # Filter to valid indices
    indices = [i for i in indices if i < len(results)]
    
    if not indices:
        print("❌ No valid indices")
        return
    
    selected = [results[i] for i in indices]
    
    print("\n")
    print("█" * 120)
    print("█" + " DETAILED COMPARISON ".center(118) + "█")
    print("█" * 120)
    print()
    
    # Create comparison rows
    fields = [
        ('Symbol', lambda r: r.get('symbol', '?')),
        ('Strike', lambda r: f"₹{r.get('strike', 0):,.0f}"),
        ('Type', lambda r: 'CALL' if r.get('option_type') == 'CE' else 'PUT'),
        ('Premium', lambda r: f"₹{r.get('premium', 0):.2f}"),
        ('Total Cost', lambda r: f"₹{r.get('total_cost', 0):,.0f}"),
        ('Spot Price', lambda r: f"₹{r.get('spot', 0):,.2f}"),
        ('Breakeven', lambda r: f"₹{r.get('breakeven', 0):,.2f}"),
        ('─' * 20, lambda r: '─' * 15),
        ('Days to Expiry', lambda r: f"{r.get('dte', 0)} days"),
        ('IV', lambda r: f"{r.get('iv', 0):.1f}%"),
        ('IV Percentile', lambda r: f"{r.get('iv_percentile', 0):.0f}%"),
        ('Volume', lambda r: f"{r.get('volume', 0):,}"),
        ('Open Interest', lambda r: f"{r.get('oi', 0):,}"),
        ('─' * 20, lambda r: '─' * 15),
        ('Overall Trend', lambda r: r.get('overall_trend', '?')),
        ('Distance from ATM', lambda r: f"{r.get('distance_pct', 0):.1f}%"),
        ('Prob. ITM', lambda r: f"{r.get('greeks', {}).get('prob_itm', 0):.1f}%"),
        ('Delta', lambda r: f"{r.get('greeks', {}).get('delta', 0):.3f}"),
        ('Theta/day', lambda r: f"₹{r.get('greeks', {}).get('theta', 0) * LOT_SIZES.get(r.get('symbol', ''), 500):.2f}"),
        ('─' * 20, lambda r: '─' * 15),
        ('ANALYSIS SCORE', lambda r: f"{r.get('score', 0):.0f}%"),
        ('COMPOSITE RANK', lambda r: f"{r.get('composite_rank', 0):.1f}"),
        ('ACTION', lambda r: r.get('action', '?')),
    ]
    
    # Calculate column width
    n_cols = len(selected)
    col_width = 20
    
    # Header with ranks
    header = f"{'METRIC':<25}"
    for i, res in enumerate(selected):
        header += f"│ #{res.get('rank', i+1):<{col_width-2}}"
    print(header)
    print("─" * 25 + ("┼" + "─" * col_width) * n_cols)
    
    # Data rows
    for field_name, getter in fields:
        row = f"{field_name:<25}"
        for res in selected:
            value = getter(res)
            row += f"│ {str(value):<{col_width-2}}"
        print(row)
    
    print()
    
    # Winner announcement
    best = selected[0]
    print(f"  🏆 RECOMMENDED: #{best.get('rank')} - {best.get('symbol')} {best.get('strike')} "
          f"{'CALL' if best.get('option_type') == 'CE' else 'PUT'}")
    print(f"     Score: {best.get('score', 0):.0f}% | Action: {best.get('action', '?')}")
    print()


# ================== FILTERING UTILITIES ==================

def filter_by_action(results: List[dict], actions: List[str]) -> List[dict]:
    """Filter results by action type."""
    return [r for r in results if r.get('action') in actions]


def filter_tradeable(results: List[dict]) -> List[dict]:
    """Get only tradeable alerts (TRADE or TRADE_CAUTIOUS)."""
    return filter_by_action(results, ['TRADE', 'TRADE_CAUTIOUS'])


def filter_by_symbol(results: List[dict], symbol: str) -> List[dict]:
    """Filter results by symbol."""
    return [r for r in results if r.get('symbol', '').upper() == symbol.upper()]


def filter_by_type(results: List[dict], option_type: str) -> List[dict]:
    """Filter results by option type (CE/PE or CALL/PUT)."""
    opt = option_type.upper()
    if opt in ['CALL', 'CE']:
        return [r for r in results if r.get('option_type') == 'CE']
    elif opt in ['PUT', 'PE']:
        return [r for r in results if r.get('option_type') == 'PE']
    return results


def filter_by_score(results: List[dict], min_score: float) -> List[dict]:
    """Filter results by minimum score."""
    return [r for r in results if r.get('score', 0) >= min_score]


# ================== VERBOSE ANALYSIS EXPORT ==================

def save_verbose_analysis_txt(verbose_output: str, output_file: str = "verbose_analysis.txt") -> bool:
    """
    Save verbose analysis output to a text file.
    
    Args:
        verbose_output: The captured verbose output string
        output_file: Output file path
    
    Returns:
        True if successful
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(verbose_output)
        print(f"✓ Verbose analysis saved to: {output_file}")
        return True
    except Exception as e:
        print(f"❌ Error saving verbose analysis: {e}")
        return False


def generate_verbose_html(verbose_output: str, symbol: str, strike: float, 
                          option_type: str, output_file: str = "verbose_analysis.html") -> str:
    """
    Generate an HTML file from verbose analysis output.
    
    Args:
        verbose_output: The captured verbose output string
        symbol: Symbol name
        strike: Strike price
        option_type: CE or PE
        output_file: Output HTML file path
    
    Returns:
        HTML content string
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    opt_name = "CALL" if option_type == 'CE' else "PUT"
    
    # Convert terminal output to HTML with styling
    # Replace box-drawing characters and format for HTML
    html_content = verbose_output
    
    # Escape HTML special characters first
    html_content = html_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Convert emojis to spans with color
    emoji_map = {
        '🟢': '<span class="emoji green">🟢</span>',
        '🔴': '<span class="emoji red">🔴</span>',
        '🟡': '<span class="emoji yellow">🟡</span>',
        '🟠': '<span class="emoji orange">🟠</span>',
        '⚪': '<span class="emoji white">⚪</span>',
        '✅': '<span class="emoji green">✅</span>',
        '❌': '<span class="emoji red">❌</span>',
        '⚠️': '<span class="emoji yellow">⚠️</span>',
        '📊': '<span class="emoji blue">📊</span>',
        '📈': '<span class="emoji blue">📈</span>',
        '🎯': '<span class="emoji blue">🎯</span>',
        '📋': '<span class="emoji blue">📋</span>',
        '🔢': '<span class="emoji blue">🔢</span>',
        '🏆': '<span class="emoji gold">🏆</span>',
        '📝': '<span class="emoji blue">📝</span>',
        '█': '<span class="block">█</span>',
        '░': '<span class="block-light">░</span>',
    }
    
    for emoji, replacement in emoji_map.items():
        html_content = html_content.replace(emoji, replacement)
    
    # Wrap in pre tag for monospace formatting
    html_content = f'<pre class="analysis-output">{html_content}</pre>'
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verbose Analysis - {symbol} {strike} {opt_name}</title>
    <style>
        :root {{
            --bg-dark: #1a1a2e;
            --bg-medium: #16213e;
            --accent: #e94560;
            --text-light: #eaeaea;
            --text-muted: #a0a0a0;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            background: linear-gradient(135deg, var(--bg-dark) 0%, var(--bg-medium) 100%);
            min-height: 100vh;
            padding: 20px;
            color: var(--text-light);
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, var(--accent) 0%, #ff6b6b 100%);
            color: white;
            padding: 30px 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 1.8em;
            margin-bottom: 10px;
            font-weight: 400;
        }}
        
        .header .subtitle {{
            opacity: 0.9;
            font-size: 1em;
        }}
        
        .header .timestamp {{
            margin-top: 10px;
            font-size: 0.85em;
            opacity: 0.7;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .analysis-output {{
            background: #0d1117;
            border-radius: 8px;
            padding: 20px;
            overflow-x: auto;
            font-size: 13px;
            line-height: 1.5;
            color: #c9d1d9;
            border: 1px solid #30363d;
        }}
        
        .emoji {{
            font-style: normal;
        }}
        
        .emoji.green {{ color: #3fb950; }}
        .emoji.red {{ color: #f85149; }}
        .emoji.yellow {{ color: #d29922; }}
        .emoji.orange {{ color: #db6d28; }}
        .emoji.white {{ color: #8b949e; }}
        .emoji.blue {{ color: #58a6ff; }}
        .emoji.gold {{ color: #f0c000; }}
        
        .block {{
            color: #58a6ff;
        }}
        
        .block-light {{
            color: #30363d;
        }}
        
        .footer {{
            text-align: center;
            padding: 20px;
            background: rgba(0, 0, 0, 0.2);
            color: var(--text-muted);
            font-size: 0.85em;
        }}
        
        .actions {{
            padding: 20px 30px;
            background: rgba(0, 0, 0, 0.2);
            display: flex;
            gap: 15px;
            justify-content: center;
        }}
        
        .btn {{
            padding: 12px 25px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.95em;
            font-weight: 500;
            transition: all 0.2s;
        }}
        
        .btn-primary {{
            background: var(--accent);
            color: white;
        }}
        
        .btn-primary:hover {{
            background: #ff6b6b;
            transform: translateY(-2px);
        }}
        
        .btn-secondary {{
            background: #30363d;
            color: var(--text-light);
        }}
        
        .btn-secondary:hover {{
            background: #484f58;
        }}
        
        @media print {{
            body {{
                background: white;
                color: black;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                background: white;
            }}
            .header {{
                background: #333 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            .analysis-output {{
                background: #f6f8fa;
                color: #24292f;
                border-color: #d0d7de;
            }}
            .actions {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Verbose Analysis Report</h1>
            <div class="subtitle">{symbol} {strike} {opt_name} - Enhanced Alert Analysis</div>
            <div class="timestamp">Generated: {timestamp}</div>
        </div>
        
        <div class="actions">
            <button class="btn btn-primary" onclick="window.print()">🖨️ Print / Save PDF</button>
            <button class="btn btn-secondary" onclick="copyToClipboard()">📋 Copy Text</button>
        </div>
        
        <div class="content">
            {html_content}
        </div>
        
        <div class="footer">
            <p>Generated by Smart Options Screener v3.3 - Enhanced Alert Analyzer</p>
            <p>For educational purposes only. Not financial advice.</p>
        </div>
    </div>
    
    <script>
        function copyToClipboard() {{
            const text = document.querySelector('.analysis-output').innerText;
            navigator.clipboard.writeText(text).then(() => {{
                alert('Analysis copied to clipboard!');
            }});
        }}
    </script>
</body>
</html>'''
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✓ Verbose HTML report saved to: {output_file}")
    return html


def generate_verbose_pdf(verbose_output: str, symbol: str, strike: float, 
                         option_type: str, output_file: str = "verbose_analysis.pdf") -> bool:
    """
    Generate a PDF from verbose analysis output using fpdf2.
    
    Args:
        verbose_output: The captured verbose output string
        symbol: Symbol name
        strike: Strike price
        option_type: CE or PE
        output_file: Output PDF file path
    
    Returns:
        True if successful
    """
    if not FPDF_AVAILABLE:
        print("❌ PDF generation requires 'fpdf2' library.")
        print("   Install with: pip install fpdf2")
        return False
    
    try:
        opt_name = "CALL" if option_type == 'CE' else "PUT"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create PDF
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # Header
        pdf.set_fill_color(233, 69, 96)  # Accent color
        pdf.rect(0, 0, 210, 30, 'F')
        
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_y(8)
        pdf.cell(0, 10, f'Verbose Analysis: {symbol} {strike} {opt_name}', align='C')
        pdf.ln(8)
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 5, f'Generated: {timestamp}', align='C')
        pdf.ln(20)
        
        # Content - Clean the output for PDF
        # Remove emojis and special characters that might cause issues
        clean_output = verbose_output
        
        # Replace emojis and Unicode characters with text equivalents
        emoji_text_map = {
            # Emojis
            '🟢': '[OK]',
            '🔴': '[X]',
            '🟡': '[!]',
            '🟠': '[!]',
            '⚪': '[-]',
            '✅': '[YES]',
            '❌': '[NO]',
            '⚠️': '[WARN]',
            '⚠': '[WARN]',
            '📊': '[CHART]',
            '📈': '[UP]',
            '🎯': '[TARGET]',
            '📋': '[LIST]',
            '🔢': '[NUM]',
            '🏆': '[BEST]',
            '📝': '[NOTE]',
            # Box drawing characters
            '█': '#',
            '░': '.',
            '─': '-',
            '│': '|',
            '┌': '+',
            '┐': '+',
            '└': '+',
            '┘': '+',
            '├': '+',
            '┤': '+',
            '┼': '+',
            '═': '=',
            '║': '|',
            '╔': '+',
            '╗': '+',
            '╚': '+',
            '╝': '+',
            '╠': '+',
            '╣': '+',
            '╬': '+',
            # Arrows
            '↑': '^',
            '↓': 'v',
            '→': '->',
            '←': '<-',
            # Checkmarks and symbols
            '✓': '[OK]',
            '✗': '[X]',
            '•': '*',
            '●': '*',
            '○': 'o',
            '◆': '*',
            '◇': 'o',
            '★': '*',
            '☆': '*',
            # Currency symbols (keep rupee as Rs)
            '₹': 'Rs',
            '€': 'EUR',
            '£': 'GBP',
            '¥': 'JPY',
            # Math symbols
            '±': '+/-',
            '×': 'x',
            '÷': '/',
            '≥': '>=',
            '≤': '<=',
            '≠': '!=',
            '≈': '~',
            '∞': 'inf',
            # Other common Unicode
            '…': '...',
            '–': '-',
            '—': '--',
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
        }
        
        for emoji, text in emoji_text_map.items():
            clean_output = clean_output.replace(emoji, text)
        
        # Remove any remaining non-ASCII characters
        clean_output = ''.join(char if ord(char) < 128 else '?' for char in clean_output)
        
        # Set monospace font for content
        pdf.set_font('Courier', '', 8)
        pdf.set_text_color(0, 0, 0)
        
        # Split into lines and add to PDF
        lines = clean_output.split('\n')
        for line in lines:
            # Truncate long lines
            if len(line) > 110:
                line = line[:107] + '...'
            pdf.cell(0, 4, line, ln=True)
        
        # Footer
        pdf.ln(10)
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(128, 128, 128)
        pdf.multi_cell(0, 4, 
            'Generated by Smart Options Screener v3.3 - Enhanced Alert Analyzer\n'
            'For educational purposes only. Not financial advice.',
            align='C'
        )
        
        # Save PDF
        pdf.output(output_file)
        print(f"✓ Verbose PDF report saved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating verbose PDF: {e}")
        import traceback
        traceback.print_exc()
        return False


def export_verbose_analysis(
    verbose_output: str,
    symbol: str,
    strike: float,
    option_type: str,
    format: str = 'all',
    base_filename: str = None
) -> dict:
    """
    Export verbose analysis in multiple formats.
    
    Args:
        verbose_output: The captured verbose output string
        symbol: Symbol name
        strike: Strike price
        option_type: CE or PE
        format: 'txt', 'html', 'pdf', or 'all'
        base_filename: Base filename (default: auto-generated)
    
    Returns:
        Dictionary with paths to generated files
    """
    if not base_filename:
        opt_name = "call" if option_type == 'CE' else "put"
        base_filename = f"verbose_{symbol}_{int(strike)}_{opt_name}"
    
    generated = {}
    
    if format in ['txt', 'all']:
        txt_file = f"{base_filename}.txt"
        if save_verbose_analysis_txt(verbose_output, txt_file):
            generated['txt'] = txt_file
    
    if format in ['html', 'all']:
        html_file = f"{base_filename}.html"
        generate_verbose_html(verbose_output, symbol, strike, option_type, html_file)
        generated['html'] = html_file
    
    if format in ['pdf', 'all']:
        pdf_file = f"{base_filename}.pdf"
        if generate_verbose_pdf(verbose_output, symbol, strike, option_type, pdf_file):
            generated['pdf'] = pdf_file
    
    return generated


# ================== REPORT GENERATOR ==================

def generate_report(results: List[dict], output_file: str = None) -> str:
    """
    Generate a comprehensive text report of all analyzed alerts.
    """
    report_lines = []
    
    report_lines.append("=" * 100)
    report_lines.append("  OPTIONS ALERT ANALYSIS REPORT")
    report_lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("=" * 100)
    report_lines.append("")
    
    # Summary
    total = len(results)
    if total == 0:
        report_lines.append("No alerts analyzed.")
        report = "\n".join(report_lines)
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
        return report
    
    tradeable = len(filter_tradeable(results))
    calls = len(filter_by_type(results, 'CE'))
    puts = len(filter_by_type(results, 'PE'))
    scores = [r.get('score', 0) for r in results]
    
    report_lines.append("SUMMARY")
    report_lines.append("-" * 50)
    report_lines.append(f"Total Alerts Analyzed:    {total}")
    report_lines.append(f"Tradeable Alerts:         {tradeable} ({tradeable/total*100:.0f}%)")
    report_lines.append(f"Call Options:             {calls}")
    report_lines.append(f"Put Options:              {puts}")
    report_lines.append(f"Average Score:            {np.mean(scores):.1f}%")
    report_lines.append(f"Score Range:              {min(scores):.0f}% - {max(scores):.0f}%")
    report_lines.append("")
    
    # Action breakdown
    report_lines.append("ACTION BREAKDOWN")
    report_lines.append("-" * 50)
    action_counts = {}
    for r in results:
        action = r.get('action', 'UNKNOWN')
        action_counts[action] = action_counts.get(action, 0) + 1
    
    for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
        report_lines.append(f"  {action:<20} {count:>5} ({count/total*100:>5.1f}%)")
    report_lines.append("")
    
    # Top alerts
    report_lines.append("TOP 10 ALERTS BY COMPOSITE RANK")
    report_lines.append("-" * 100)
    report_lines.append(f"{'#':<4} {'Symbol':<12} {'Strike':<10} {'Type':<6} {'Score':<8} {'IV%':<6} {'DTE':<5} {'Action':<15}")
    report_lines.append("-" * 100)
    
    for r in results[:10]:
        report_lines.append(
            f"{r.get('rank', '-'):<4} "
            f"{r.get('symbol', '?'):<12} "
            f"{r.get('strike', 0):<10.0f} "
            f"{'CALL' if r.get('option_type') == 'CE' else 'PUT':<6} "
            f"{r.get('score', 0):<7.0f}% "
            f"{r.get('iv_percentile', 0):<6.0f} "
            f"{r.get('dte', 0):<5} "
            f"{r.get('action', '?'):<15}"
        )
    
    report_lines.append("")
    report_lines.append("=" * 100)
    report_lines.append("  END OF REPORT")
    report_lines.append("=" * 100)
    
    report = "\n".join(report_lines)
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(report)
        print(f"✓ Report saved to: {output_file}")
    
    return report


def generate_html_report(results: List[dict], output_file: str = "alert_report.html") -> str:
    """
    Generate a comprehensive HTML report with styling.
    
    Args:
        results: List of analyzed results
        output_file: Output HTML file path
    
    Returns:
        HTML content string
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Calculate summary stats
    total = len(results)
    if total == 0:
        html = "<html><body><h1>No alerts analyzed</h1></body></html>"
        with open(output_file, 'w') as f:
            f.write(html)
        return html
    
    tradeable = len(filter_tradeable(results))
    calls = len(filter_by_type(results, 'CE'))
    puts = len(filter_by_type(results, 'PE'))
    scores = [r.get('score', 0) for r in results]
    
    # Action counts
    action_counts = {}
    for r in results:
        action = r.get('action', 'UNKNOWN')
        action_counts[action] = action_counts.get(action, 0) + 1
    
    # Build HTML
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Options Alert Analysis Report</title>
    <style>
        :root {{
            --primary: #1a73e8;
            --success: #34a853;
            --warning: #fbbc04;
            --danger: #ea4335;
            --dark: #202124;
            --light: #f8f9fa;
            --border: #dadce0;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: var(--dark);
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            font-weight: 300;
        }}
        
        .header .subtitle {{
            opacity: 0.8;
            font-size: 1.1em;
        }}
        
        .header .timestamp {{
            margin-top: 15px;
            font-size: 0.9em;
            opacity: 0.6;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .section {{
            margin-bottom: 40px;
        }}
        
        .section-title {{
            font-size: 1.5em;
            color: var(--dark);
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid var(--primary);
            display: inline-block;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }}
        
        .stat-card .value {{
            font-size: 2.5em;
            font-weight: bold;
            color: var(--primary);
        }}
        
        .stat-card .label {{
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }}
        
        .stat-card.success .value {{ color: var(--success); }}
        .stat-card.warning .value {{ color: var(--warning); }}
        .stat-card.danger .value {{ color: var(--danger); }}
        
        .action-breakdown {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 20px 0;
        }}
        
        .action-badge {{
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: 500;
            font-size: 0.9em;
        }}
        
        .action-badge.trade {{ background: #d4edda; color: #155724; }}
        .action-badge.cautious {{ background: #fff3cd; color: #856404; }}
        .action-badge.paper {{ background: #d1ecf1; color: #0c5460; }}
        .action-badge.avoid {{ background: #ffe5d0; color: #833a0a; }}
        .action-badge.no-trade {{ background: #f8d7da; color: #721c24; }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 0.95em;
        }}
        
        th {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: white;
            padding: 15px 12px;
            text-align: left;
            font-weight: 500;
            position: sticky;
            top: 0;
        }}
        
        td {{
            padding: 12px;
            border-bottom: 1px solid var(--border);
        }}
        
        tr:hover {{
            background: #f8f9fa;
        }}
        
        tr:nth-child(even) {{
            background: #fafbfc;
        }}
        
        tr:nth-child(even):hover {{
            background: #f0f1f2;
        }}
        
        .rank {{
            font-weight: bold;
            color: var(--primary);
        }}
        
        .score {{
            font-weight: bold;
        }}
        
        .score.high {{ color: var(--success); }}
        .score.medium {{ color: var(--warning); }}
        .score.low {{ color: var(--danger); }}
        
        .action {{
            padding: 5px 12px;
            border-radius: 15px;
            font-size: 0.85em;
            font-weight: 500;
            display: inline-block;
        }}
        
        .action.trade {{ background: #d4edda; color: #155724; }}
        .action.cautious {{ background: #fff3cd; color: #856404; }}
        .action.paper {{ background: #d1ecf1; color: #0c5460; }}
        .action.avoid {{ background: #ffe5d0; color: #833a0a; }}
        .action.no-trade {{ background: #f8d7da; color: #721c24; }}
        
        .type-call {{ color: var(--success); font-weight: bold; }}
        .type-put {{ color: var(--danger); font-weight: bold; }}
        
        .footer {{
            text-align: center;
            padding: 30px;
            background: #f8f9fa;
            color: #666;
            font-size: 0.9em;
        }}
        
        .legend {{
            margin-top: 20px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        
        .legend h4 {{
            margin-bottom: 10px;
            color: var(--dark);
        }}
        
        .legend-items {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
        }}
        
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
            }}
            .header {{
                background: var(--dark) !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Options Alert Analysis Report</h1>
            <div class="subtitle">Smart Options Screener v3.3 - Enhanced Analysis</div>
            <div class="timestamp">Generated: {timestamp}</div>
        </div>
        
        <div class="content">
            <div class="section">
                <h2 class="section-title">📈 Summary Statistics</h2>
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="value">{total}</div>
                        <div class="label">Total Alerts Analyzed</div>
                    </div>
                    <div class="stat-card success">
                        <div class="value">{tradeable}</div>
                        <div class="label">Tradeable Alerts</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{calls}</div>
                        <div class="label">Call Options</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{puts}</div>
                        <div class="label">Put Options</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{np.mean(scores):.1f}%</div>
                        <div class="label">Average Score</div>
                    </div>
                    <div class="stat-card">
                        <div class="value">{max(scores):.0f}%</div>
                        <div class="label">Best Score</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">🎯 Action Breakdown</h2>
                <div class="action-breakdown">
'''
    
    # Add action badges
    action_classes = {
        'TRADE': 'trade',
        'TRADE_CAUTIOUS': 'cautious',
        'PAPER_TRADE': 'paper',
        'AVOID': 'avoid',
        'NO_TRADE': 'no-trade'
    }
    
    for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
        css_class = action_classes.get(action, 'paper')
        pct = count / total * 100
        html += f'                    <div class="action-badge {css_class}">{action}: {count} ({pct:.1f}%)</div>\n'
    
    html += '''                </div>
            </div>
            
            <div class="section">
                <h2 class="section-title">🏆 Top Alerts by Composite Rank</h2>
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Symbol</th>
                            <th>Strike</th>
                            <th>Type</th>
                            <th>Premium</th>
                            <th>Score</th>
                            <th>IV%</th>
                            <th>Volume</th>
                            <th>DTE</th>
                            <th>Composite</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
'''
    
    # Add table rows
    for r in results[:20]:
        rank = r.get('rank', '-')
        symbol = r.get('symbol', '?')
        strike = r.get('strike', 0)
        opt_type = 'CALL' if r.get('option_type') == 'CE' else 'PUT'
        type_class = 'type-call' if opt_type == 'CALL' else 'type-put'
        premium = r.get('premium', 0)
        score = r.get('score', 0)
        score_class = 'high' if score >= 65 else 'medium' if score >= 50 else 'low'
        iv_pct = r.get('iv_percentile', 0)
        volume = r.get('volume', 0)
        dte = r.get('dte', 0)
        composite = r.get('composite_rank', 0)
        action = r.get('action', '?')
        action_class = action_classes.get(action, 'paper')
        
        html += f'''                        <tr>
                            <td class="rank">{rank}</td>
                            <td><strong>{symbol}</strong></td>
                            <td>₹{strike:,.0f}</td>
                            <td class="{type_class}">{opt_type}</td>
                            <td>₹{premium:.2f}</td>
                            <td class="score {score_class}">{score:.0f}%</td>
                            <td>{iv_pct:.0f}%</td>
                            <td>{volume:,}</td>
                            <td>{dte}</td>
                            <td>{composite:.1f}</td>
                            <td><span class="action {action_class}">{action.replace('_', ' ')}</span></td>
                        </tr>
'''
    
    html += '''                    </tbody>
                </table>
                
                <div class="legend">
                    <h4>Score Legend</h4>
                    <div class="legend-items">
                        <span class="action trade">TRADE: Score ≥ 80%</span>
                        <span class="action cautious">CAUTIOUS: Score 65-79%</span>
                        <span class="action paper">PAPER: Score 50-64%</span>
                        <span class="action avoid">AVOID: Score 35-49%</span>
                        <span class="action no-trade">NO TRADE: Score < 35%</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>Generated by Smart Options Screener v3.3 - Alert Connector</p>
            <p>For educational purposes only. Not financial advice.</p>
        </div>
    </div>
</body>
</html>'''
    
    # Save to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✓ HTML Report saved to: {output_file}")
    return html


class AlertPDF(FPDF):
    """Custom PDF class for alert reports using fpdf2."""
    
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
    
    def header(self):
        # Header background
        self.set_fill_color(26, 26, 46)  # Dark blue
        self.rect(0, 0, 210, 25, 'F')
        
        # Title
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 16)
        self.set_y(8)
        self.cell(0, 10, 'Options Alert Analysis Report', align='C')
        self.ln(20)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} | Smart Options Screener v3.3', align='C')
    
    def section_title(self, title):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(26, 115, 232)  # Blue
        self.cell(0, 10, title, ln=True)
        self.ln(2)
    
    def add_summary_table(self, data):
        """Add a summary table with alternating row colors."""
        self.set_font('Helvetica', 'B', 10)
        
        # Header row
        self.set_fill_color(26, 26, 46)
        self.set_text_color(255, 255, 255)
        self.cell(95, 8, 'Metric', border=1, fill=True, align='C')
        self.cell(95, 8, 'Value', border=1, fill=True, align='C')
        self.ln()
        
        # Data rows
        self.set_font('Helvetica', '', 10)
        self.set_text_color(0, 0, 0)
        
        for i, (metric, value) in enumerate(data):
            if i % 2 == 0:
                self.set_fill_color(248, 249, 250)
            else:
                self.set_fill_color(255, 255, 255)
            
            self.cell(95, 7, str(metric), border=1, fill=True)
            self.cell(95, 7, str(value), border=1, fill=True, align='C')
            self.ln()
    
    def add_action_table(self, action_counts, total):
        """Add action breakdown table."""
        self.set_font('Helvetica', 'B', 10)
        
        # Header row
        self.set_fill_color(26, 26, 46)
        self.set_text_color(255, 255, 255)
        self.cell(70, 8, 'Action', border=1, fill=True, align='C')
        self.cell(50, 8, 'Count', border=1, fill=True, align='C')
        self.cell(70, 8, 'Percentage', border=1, fill=True, align='C')
        self.ln()
        
        # Data rows with color coding
        self.set_font('Helvetica', '', 10)
        
        action_colors = {
            'TRADE': (212, 237, 218),
            'TRADE_CAUTIOUS': (255, 243, 205),
            'PAPER_TRADE': (209, 236, 241),
            'AVOID': (255, 229, 208),
            'NO_TRADE': (248, 215, 218),
        }
        
        for action, count in sorted(action_counts.items(), key=lambda x: -x[1]):
            color = action_colors.get(action, (255, 255, 255))
            self.set_fill_color(*color)
            self.set_text_color(0, 0, 0)
            
            pct = count / total * 100
            self.cell(70, 7, action.replace('_', ' '), border=1, fill=True, align='C')
            self.cell(50, 7, str(count), border=1, fill=True, align='C')
            self.cell(70, 7, f'{pct:.1f}%', border=1, fill=True, align='C')
            self.ln()
    
    def add_alerts_table(self, results):
        """Add main alerts table."""
        # Column widths
        col_widths = [12, 25, 22, 18, 22, 18, 16, 14, 43]
        headers = ['#', 'Symbol', 'Strike', 'Type', 'Premium', 'Score', 'IV%', 'DTE', 'Action']
        
        # Header row
        self.set_font('Helvetica', 'B', 8)
        self.set_fill_color(26, 26, 46)
        self.set_text_color(255, 255, 255)
        
        for i, (header, width) in enumerate(zip(headers, col_widths)):
            self.cell(width, 7, header, border=1, fill=True, align='C')
        self.ln()
        
        # Data rows
        self.set_font('Helvetica', '', 8)
        
        action_colors = {
            'TRADE': (212, 237, 218),
            'TRADE_CAUTIOUS': (255, 243, 205),
            'PAPER_TRADE': (209, 236, 241),
            'AVOID': (255, 229, 208),
            'NO_TRADE': (248, 215, 218),
        }
        
        for i, r in enumerate(results[:15]):
            # Alternating row background
            if i % 2 == 0:
                row_color = (248, 249, 250)
            else:
                row_color = (255, 255, 255)
            
            rank = str(r.get('rank', '-'))
            symbol = r.get('symbol', '?')[:8]
            strike = f"Rs{r.get('strike', 0):,.0f}"
            opt_type = 'CALL' if r.get('option_type') == 'CE' else 'PUT'
            premium = f"Rs{r.get('premium', 0):.1f}"
            score = f"{r.get('score', 0):.0f}%"
            iv_pct = f"{r.get('iv_percentile', 0):.0f}%"
            dte = str(r.get('dte', 0))
            action = r.get('action', '?').replace('_', ' ')
            
            row_data = [rank, symbol, strike, opt_type, premium, score, iv_pct, dte, action]
            
            self.set_text_color(0, 0, 0)
            
            for j, (value, width) in enumerate(zip(row_data, col_widths)):
                # Special coloring for action column
                if j == len(row_data) - 1:
                    action_key = r.get('action', '')
                    color = action_colors.get(action_key, row_color)
                    self.set_fill_color(*color)
                # Special coloring for type column
                elif j == 3:
                    if value == 'CALL':
                        self.set_text_color(52, 168, 83)  # Green
                    else:
                        self.set_text_color(234, 67, 53)  # Red
                    self.set_fill_color(*row_color)
                else:
                    self.set_fill_color(*row_color)
                    self.set_text_color(0, 0, 0)
                
                self.cell(width, 6, value, border=1, fill=True, align='C')
            
            self.ln()


def generate_pdf_report(results: List[dict], output_file: str = "alert_report.pdf") -> bool:
    """
    Generate a PDF report using fpdf2.
    
    Args:
        results: List of analyzed results
        output_file: Output PDF file path
    
    Returns:
        True if successful, False otherwise
    """
    if not FPDF_AVAILABLE:
        print("❌ PDF generation requires 'fpdf2' library.")
        print("   Install with: pip install fpdf2")
        return False
    
    if not results:
        print("❌ No results to generate PDF report")
        return False
    
    try:
        # Create PDF
        pdf = AlertPDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Timestamp
        pdf.set_font('Helvetica', 'I', 10)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 10, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', align='C', ln=True)
        pdf.ln(5)
        
        # Summary Statistics
        total = len(results)
        tradeable = len(filter_tradeable(results))
        calls = len(filter_by_type(results, 'CE'))
        puts = len(filter_by_type(results, 'PE'))
        scores = [r.get('score', 0) for r in results]
        
        pdf.section_title('Summary Statistics')
        
        summary_data = [
            ('Total Alerts Analyzed', str(total)),
            ('Tradeable Alerts', f"{tradeable} ({tradeable/total*100:.0f}%)"),
            ('Call Options', str(calls)),
            ('Put Options', str(puts)),
            ('Average Score', f"{np.mean(scores):.1f}%"),
            ('Best Score', f"{max(scores):.0f}%"),
            ('Worst Score', f"{min(scores):.0f}%"),
        ]
        
        pdf.add_summary_table(summary_data)
        pdf.ln(10)
        
        # Action Breakdown
        pdf.section_title('Action Breakdown')
        
        action_counts = {}
        for r in results:
            action = r.get('action', 'UNKNOWN')
            action_counts[action] = action_counts.get(action, 0) + 1
        
        pdf.add_action_table(action_counts, total)
        pdf.ln(10)
        
        # Top Alerts Table
        pdf.section_title('Top 15 Alerts by Composite Rank')
        pdf.add_alerts_table(results)
        
        # Legend
        pdf.ln(10)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, 'Score Legend:', ln=True)
        
        pdf.set_font('Helvetica', '', 9)
        legends = [
            ('TRADE', 'Score >= 80%', (212, 237, 218)),
            ('CAUTIOUS', 'Score 65-79%', (255, 243, 205)),
            ('PAPER', 'Score 50-64%', (209, 236, 241)),
            ('AVOID', 'Score 35-49%', (255, 229, 208)),
            ('NO TRADE', 'Score < 35%', (248, 215, 218)),
        ]
        
        for action, desc, color in legends:
            pdf.set_fill_color(*color)
            pdf.cell(30, 6, action, border=1, fill=True, align='C')
            pdf.cell(50, 6, desc, border=1, align='C')
            pdf.ln()
        
        # Footer note
        pdf.ln(15)
        pdf.set_font('Helvetica', 'I', 9)
        pdf.set_text_color(128, 128, 128)
        pdf.multi_cell(0, 5, 
            'Disclaimer: This report is for educational purposes only. '
            'Not financial advice. Always do your own research before trading.',
            align='C'
        )
        
        # Save PDF
        pdf.output(output_file)
        print(f"✓ PDF Report saved to: {output_file}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
        return False


def export_report(
    results: List[dict],
    format: str = 'all',
    base_filename: str = 'alert_report'
) -> dict:
    """
    Export report in multiple formats.
    
    Args:
        results: List of analyzed results
        format: 'txt', 'html', 'pdf', or 'all'
        base_filename: Base filename without extension
    
    Returns:
        Dictionary with paths to generated files
    """
    generated = {}
    
    if format in ['txt', 'all']:
        txt_file = f"{base_filename}.txt"
        generate_report(results, output_file=txt_file)
        generated['txt'] = txt_file
    
    if format in ['html', 'all']:
        html_file = f"{base_filename}.html"
        generate_html_report(results, output_file=html_file)
        generated['html'] = html_file
    
    if format in ['pdf', 'all']:
        pdf_file = f"{base_filename}.pdf"
        if generate_pdf_report(results, output_file=pdf_file):
            generated['pdf'] = pdf_file
    
    return generated


# ================== MAIN FUNCTIONS ==================

def analyze_csv_alerts(
    csv_file: str = DEFAULT_CSV_FILE,
    top_n: int = 15,
    verbose: bool = False,
    filter_symbol: str = None,
    filter_type: str = None,
    min_volume: int = 0,
    max_iv_percentile: float = 85
) -> List[dict]:
    """
    Main function to analyze alerts from CSV file.
    
    Args:
        csv_file: Path to screener CSV output
        top_n: Number of top alerts to display
        verbose: Show detailed analysis for each alert
        filter_symbol: Filter by symbol
        filter_type: Filter by type ('CE' or 'PE')
        min_volume: Minimum volume filter
        max_iv_percentile: Maximum IV percentile filter
    
    Returns:
        List of ranked analysis results
    """
    # Read alerts
    alerts = read_alerts_from_csv(
        csv_file=csv_file,
        filter_symbol=filter_symbol,
        filter_type=filter_type,
        min_volume=min_volume,
        max_iv_percentile=max_iv_percentile
    )
    
    if alerts.empty:
        return []
    
    # Batch analyze
    results = batch_analyze_alerts(alerts, verbose=verbose, max_alerts=top_n * 2)
    
    # Rank alerts
    results = rank_alerts(results)
    
    # Display comparison
    compare_alerts(results, top_n=top_n)
    
    return results


def analyze_alert_list(
    alerts: List[dict],
    verbose: bool = False
) -> List[dict]:
    """
    Analyze a list of alert dictionaries directly.
    
    Args:
        alerts: List of alert dictionaries
        verbose: Show detailed analysis
    
    Returns:
        List of ranked analysis results
    """
    df = pd.DataFrame(alerts)
    results = batch_analyze_alerts(df, verbose=verbose, max_alerts=len(alerts))
    results = rank_alerts(results)
    return results


def quick_compare(csv_file: str = DEFAULT_CSV_FILE, top_n: int = 5) -> None:
    """
    Quick comparison of top alerts from CSV.
    """
    results = analyze_csv_alerts(csv_file=csv_file, top_n=top_n, verbose=True)
    if results:
        detailed_comparison(results, indices=[0, 1, 2])


# ================== INTERACTIVE CLI ==================

def interactive_menu():
    """Interactive menu for alert analysis."""
    print("\n")
    print("█" * 80)
    print("█" + " ALERT CONNECTOR - Interactive Mode ".center(78) + "█")
    print("█" * 80)
    print()
    
    # Store last analyzed results for export
    last_results = []
    last_verbose_result = None  # Store last verbose analysis result
    
    while True:
        print("\n" + "─" * 60)
        print("MENU:")
        print("  1. Analyze all alerts from CSV")
        print("  2. Analyze top N alerts")
        print("  3. Filter by symbol")
        print("  4. Filter by type (CALL/PUT)")
        print("  5. Show only tradeable alerts")
        print("  6. Quick comparison (top 5)")
        print("  ─" * 30)
        print("  SUMMARY REPORTS:")
        print("  7. Generate TXT summary report")
        print("  8. Generate HTML summary report")
        print("  9. Generate PDF summary report")
        print("  10. Export ALL summary formats")
        print("  ─" * 30)
        print("  VERBOSE ANALYSIS:")
        print("  11. Analyze specific alert (verbose)")
        print("  12. Analyze & Export verbose to TXT")
        print("  13. Analyze & Export verbose to HTML")
        print("  14. Analyze & Export verbose to PDF")
        print("  15. Analyze & Export verbose to ALL formats")
        print("  ─" * 30)
        print("  0. Exit")
        print("─" * 60)
        
        choice = input("Select option: ").strip()
        
        if choice == '0':
            print("Goodbye!")
            break
        
        elif choice == '1':
            last_results = analyze_csv_alerts(top_n=20, verbose=True)
        
        elif choice == '2':
            n = int(input("Enter number of alerts to analyze: ") or "10")
            last_results = analyze_csv_alerts(top_n=n, verbose=True)
        
        elif choice == '3':
            symbol = input("Enter symbol (e.g., RELIANCE, NIFTY): ").strip().upper()
            last_results = analyze_csv_alerts(top_n=20, filter_symbol=symbol, verbose=True)
        
        elif choice == '4':
            opt_type = input("Enter type (CALL/PUT or CE/PE): ").strip().upper()
            if opt_type in ['CALL', 'CE']:
                last_results = analyze_csv_alerts(top_n=20, filter_type='CE', verbose=True)
            else:
                last_results = analyze_csv_alerts(top_n=20, filter_type='PE', verbose=True)
        
        elif choice == '5':
            all_results = analyze_csv_alerts(top_n=50, verbose=True)
            last_results = filter_tradeable(all_results)
            print(f"\n✓ Found {len(last_results)} tradeable alerts")
            compare_alerts(last_results, top_n=15)
        
        elif choice == '6':
            quick_compare()
        
        elif choice == '7':
            # Generate TXT summary report
            if not last_results:
                print("\n⚠️ No results available. Running analysis first...")
                last_results = analyze_csv_alerts(top_n=30, verbose=True)
            
            if last_results:
                filename = input("Enter filename (default: alert_report.txt): ").strip()
                if not filename:
                    filename = "alert_report.txt"
                if not filename.endswith('.txt'):
                    filename += '.txt'
                report = generate_report(last_results, output_file=filename)
                print("\n--- REPORT PREVIEW (first 50 lines) ---")
                print('\n'.join(report.split('\n')[:50]))
                print("...\n")
        
        elif choice == '8':
            # Generate HTML summary report
            if not last_results:
                print("\n⚠️ No results available. Running analysis first...")
                last_results = analyze_csv_alerts(top_n=30, verbose=False)
            
            if last_results:
                filename = input("Enter filename (default: alert_report.html): ").strip()
                if not filename:
                    filename = "alert_report.html"
                if not filename.endswith('.html'):
                    filename += '.html'
                generate_html_report(last_results, output_file=filename)
                
                # Ask to open in browser
                open_browser = input("Open in browser? (y/n): ").strip().lower()
                if open_browser == 'y':
                    import webbrowser
                    webbrowser.open(f'file://{os.path.abspath(filename)}')
        
        elif choice == '9':
            # Generate PDF summary report
            if not FPDF_AVAILABLE:
                print("\n❌ PDF generation requires 'fpdf2' library.")
                print("   Install with: pip install fpdf2")
                continue
            
            if not last_results:
                print("\n⚠️ No results available. Running analysis first...")
                last_results = analyze_csv_alerts(top_n=30, verbose=True)
            
            if last_results:
                filename = input("Enter filename (default: alert_report.pdf): ").strip()
                if not filename:
                    filename = "alert_report.pdf"
                if not filename.endswith('.pdf'):
                    filename += '.pdf'
                generate_pdf_report(last_results, output_file=filename)
        
        elif choice == '10':
            # Export all summary formats
            if not last_results:
                print("\n⚠️ No results available. Running analysis first...")
                last_results = analyze_csv_alerts(top_n=30, verbose=False)
            
            if last_results:
                base_name = input("Enter base filename (default: alert_report): ").strip()
                if not base_name:
                    base_name = "alert_report"
                
                print("\n📄 Generating summary reports...")
                generated = export_report(last_results, format='all', base_filename=base_name)
                
                print("\n✓ Summary reports generated:")
                for fmt, path in generated.items():
                    print(f"   • {fmt.upper()}: {path}")
        
        elif choice == '11':
            # Analyze specific alert (verbose, no export)
            alerts = read_alerts_from_csv(limit=20)
            if not alerts.empty:
                print("\nAvailable alerts:")
                for i, (_, row) in enumerate(alerts.iterrows()):
                    print(f"  {i+1}. {row.get('symbol', '?')} {row.get('strike', '?')} {row.get('strategy', '?')}")
                
                idx = int(input("Select alert number: ") or "1") - 1
                if 0 <= idx < len(alerts):
                    alert = alerts.iloc[idx].to_dict()
                    last_verbose_result = analyze_single_alert(alert, verbose=True, capture_output=True)
        
        elif choice in ['12', '13', '14', '15']:
            # Verbose export options
            alerts = read_alerts_from_csv(limit=20)
            if alerts.empty:
                print("\n❌ No alerts found in CSV")
                continue
            
            print("\nAvailable alerts:")
            for i, (_, row) in enumerate(alerts.iterrows()):
                print(f"  {i+1}. {row.get('symbol', '?')} {row.get('strike', '?')} {row.get('strategy', '?')}")
            
            idx = int(input("Select alert number: ") or "1") - 1
            if not (0 <= idx < len(alerts)):
                print("Invalid selection")
                continue
            
            alert = alerts.iloc[idx].to_dict()
            
            # Determine export format
            if choice == '12':
                export_fmt = 'txt'
            elif choice == '13':
                export_fmt = 'html'
            elif choice == '14':
                export_fmt = 'pdf'
            else:
                export_fmt = 'all'
            
            # Get filename
            default_name = f"verbose_{alert.get('symbol', 'alert')}_{int(alert.get('strike', 0))}"
            filename = input(f"Enter base filename (default: {default_name}): ").strip()
            if not filename:
                filename = default_name
            
            # Analyze and export
            print(f"\n📊 Analyzing and exporting to {export_fmt.upper()}...")
            result = analyze_single_alert(
                alert, 
                verbose=True, 
                capture_output=True,
                export_format=export_fmt,
                export_filename=filename
            )
            
            last_verbose_result = result
            
            if result.get('exported_files'):
                print("\n✓ Verbose analysis exported:")
                for fmt, path in result['exported_files'].items():
                    print(f"   • {fmt.upper()}: {path}")
                
                # Ask to open HTML in browser
                if 'html' in result['exported_files']:
                    open_browser = input("\nOpen HTML in browser? (y/n): ").strip().lower()
                    if open_browser == 'y':
                        import webbrowser
                        webbrowser.open(f'file://{os.path.abspath(result["exported_files"]["html"])}')
        
        else:
            print("Invalid option")


# ================== MAIN ====================

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("  ALERT CONNECTOR v1.2")
    print("  Connecting Screener Alerts with Enhanced Analysis")
    print("  Report Formats: Summary (TXT, HTML, PDF) + Verbose Analysis (TXT, HTML, PDF)")
    print("=" * 80)
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg == '--interactive':
            interactive_menu()
            sys.exit(0)
        
        elif arg == '--export-html':
            results = analyze_csv_alerts(top_n=30, verbose=False)
            if results:
                generate_html_report(results)
            sys.exit(0)
        
        elif arg == '--export-pdf':
            results = analyze_csv_alerts(top_n=30, verbose=False)
            if results:
                generate_pdf_report(results)
            sys.exit(0)
        
        elif arg == '--export-all':
            results = analyze_csv_alerts(top_n=30, verbose=False)
            if results:
                export_report(results, format='all')
            sys.exit(0)
        
        elif arg == '--verbose-export':
            # Export verbose analysis for first alert
            alerts = read_alerts_from_csv(limit=1)
            if not alerts.empty:
                alert = alerts.iloc[0].to_dict()
                print(f"\n📊 Analyzing: {alert.get('symbol')} {alert.get('strike')} {alert.get('strategy')}")
                result = analyze_single_alert(
                    alert, 
                    verbose=True, 
                    capture_output=True,
                    export_format='all'
                )
                if result.get('exported_files'):
                    print("\n✓ Verbose analysis exported:")
                    for fmt, path in result['exported_files'].items():
                        print(f"   • {fmt.upper()}: {path}")
            sys.exit(0)
        
        elif arg == '--help':
            print("\nUsage: python alert_connector.py [OPTIONS]")
            print("\nSummary Report Options:")
            print("  --interactive    Run in interactive mode with menu")
            print("  --export-html    Analyze alerts and export HTML summary report")
            print("  --export-pdf     Analyze alerts and export PDF summary report")
            print("  --export-all     Export summary reports in all formats")
            print("\nVerbose Analysis Options:")
            print("  --verbose-export Export detailed verbose analysis (first alert)")
            print("\nOther:")
            print("  --help           Show this help message")
            print("\nExamples:")
            print("  python alert_connector.py                 # Quick analysis")
            print("  python alert_connector.py --interactive   # Interactive menu")
            print("  python alert_connector.py --export-all    # Export all summary reports")
            print("  python alert_connector.py --verbose-export # Export verbose analysis")
            sys.exit(0)
    
    # Check if CSV exists
    if os.path.exists(DEFAULT_CSV_FILE):
        print(f"\n✓ Found CSV file: {DEFAULT_CSV_FILE}")
        
        # Check PDF availability
        if FPDF_AVAILABLE:
            print("✓ PDF generation available (fpdf2 installed)")
        else:
            print("⚠️ PDF generation unavailable (install: pip install fpdf2)")
        
        # Quick analysis
        print("\nRunning quick analysis of top 15 alerts...\n")
        results = analyze_csv_alerts(top_n=15, verbose=True, max_iv_percentile=85)
        
        if results:
            # Show detailed comparison of top 3
            print("\n" + "─" * 80)
            print("DETAILED COMPARISON OF TOP 3 ALERTS")
            print("─" * 80)
            detailed_comparison(results, indices=[0, 1, 2])
            
            # Generate all reports
            print("\n" + "─" * 80)
            print("GENERATING REPORTS")
            print("─" * 80)
            
            generated = export_report(results, format='all', base_filename='alert_analysis_report')
            
            print("\n📄 Reports generated:")
            for fmt, path in generated.items():
                print(f"   • {fmt.upper()}: {path}")
        
        print("\n" + "─" * 80)
        print("COMMAND OPTIONS:")
        print("  python alert_connector.py --interactive  # Interactive menu")
        print("  python alert_connector.py --export-all   # Export all formats")
        print("  python alert_connector.py --help         # Show all options")
        print("─" * 80)
    else:
        print(f"\n⚠️ CSV file not found: {DEFAULT_CSV_FILE}")
        print("Run the screener first to generate alerts.")
        print("\nYou can also use this module programmatically:")
        print("  from alert_connector import analyze_alert_list, export_report")
        print("  results = analyze_alert_list([alert1, alert2, ...])")
        print("  export_report(results, format='all')")

