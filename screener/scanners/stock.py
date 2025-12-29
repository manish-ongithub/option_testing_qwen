"""
Stock options scanner.
"""

import time
from datetime import datetime

from screener.config import (
    IST, VOLUME_THRESHOLDS, OI_THRESHOLDS,
    AFTER_HOURS_OI_THRESHOLD_STOCK, AFTER_HOURS_SPREAD_PCT,
    MAX_SPREAD_PCT_STOCK, MAX_PREMIUM_RATIO_STOCK,
    MIN_STOCK_PRICE, MIN_PREMIUM, STRIKE_RANGE_MULTIPLIER,
    RSI_OVERSOLD, RSI_OVERBOUGHT, IV_VERY_HIGH
)
from screener.api.option_chain import fetch_nse_option_chain
from screener.iv.provider import get_iv_data
from screener.utils.helpers import (
    get_lot_size, get_stock_tier, find_atm_strike, get_moneyness,
    calculate_breakeven, calculate_distance_from_spot, calculate_days_to_expiry,
    get_option_price, get_option_spread, get_underlying_price, compute_trend_indicators
)
from screener.utils.logging_setup import logger
from screener.strategies.bull_call_spread import scan_bull_call_spread
from screener.strategies.bear_put_spread import scan_bear_put_spread
from screener.strategies.long_straddle import scan_long_straddle
from screener.strategies.long_strangle import scan_long_strangle


def scan_stock(symbol, market_regime, vix, market_open=True):
    """
    Scan a stock for option trading opportunities.
    
    Args:
        symbol: Stock symbol
        market_regime: Current market volatility regime
        vix: Current India VIX value
        market_open: Whether market is currently open
    
    Returns:
        list: List of alert dictionaries
    """
    alerts = []
    
    try:
        tier = get_stock_tier(symbol)
        lot_size = get_lot_size(symbol)
        
        # Set thresholds based on market status
        if market_open:
            vol_thresh = VOLUME_THRESHOLDS[tier]
            oi_thresh = OI_THRESHOLDS[tier]
            spread_limit = MAX_SPREAD_PCT_STOCK
            min_premium = MIN_PREMIUM
        else:
            # After-hours: require higher OI for liquidity
            vol_thresh = 0  # Don't require volume after hours
            oi_thresh = AFTER_HOURS_OI_THRESHOLD_STOCK
            spread_limit = AFTER_HOURS_SPREAD_PCT
            min_premium = MIN_PREMIUM
        
        spot = get_underlying_price(symbol)
        if not spot:
            return []
        
        if spot < MIN_STOCK_PRICE:
            logger.debug("Stock %s: Spot below minimum (%.2f)", symbol, spot)
            return []
        
        # Get IV data (Opstra or HV fallback)
        iv_data = get_iv_data(symbol)
        
        trend_data = compute_trend_indicators(symbol)
        
        # Log with IV source and mode
        mode_tag = "" if market_open else " [AFTER-HOURS]"
        logger.info("Stock %s: Spot=%.0f | IV=%.1f%% IVP=%d%% [%s] | RSI=%.0f %s%s",
                   symbol, spot, iv_data['iv'], iv_data['iv_percentile'], 
                   iv_data['source'].upper(), trend_data['rsi'], trend_data['bias'], mode_tag)
        
        # IV-based filtering (only if we have reliable IV data)
        if iv_data['source'] == 'opstra' and iv_data['iv_percentile'] > IV_VERY_HIGH:
            logger.info("  Skipping %s: IV Percentile %d%% > %d%% (expensive premiums)",
                       symbol, iv_data['iv_percentile'], IV_VERY_HIGH)
            return []
        
        # Fetch option chain using NSE API v3
        oc = fetch_nse_option_chain(symbol, is_index=False)
        
        if not oc or 'records' not in oc:
            logger.debug("Option chain empty for %s", symbol)
            return []
        
        records = oc['records'].get('data', [])
        if not records:
            logger.debug("No option records for %s", symbol)
            return []
        
        expiry_dates = oc['records'].get('expiryDates', [])
        nearest_expiry = expiry_dates[0] if expiry_dates else "Unknown"
        
        calls, puts = {}, {}
        strikes = set()
        for rec in records:
            strike = rec.get('strikePrice')
            expiry = rec.get('expiryDate', nearest_expiry)
            if strike:
                strikes.add(strike)
                if 'CE' in rec:
                    calls[strike] = rec['CE']
                    calls[strike]['expiryDate'] = expiry
                if 'PE' in rec:
                    puts[strike] = rec['PE']
                    puts[strike]['expiryDate'] = expiry
        
        strikes = sorted(strikes)
        if not strikes:
            return []
        
        atm = find_atm_strike(strikes, spot)
        step = strikes[1] - strikes[0] if len(strikes) > 1 else 50
        max_distance = step * STRIKE_RANGE_MULTIPLIER
        strikes_in_range = [s for s in strikes if abs(s - atm) <= max_distance]
        
        base_alert = {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'instrument_type': 'STOCK',
            'spot': spot,
            'iv': iv_data['iv'],
            'iv_percentile': iv_data['iv_percentile'],
            'iv_rank': iv_data['iv_rank'],
            'iv_source': iv_data['source'],
            'market_regime': market_regime,
            'vix': vix,
            'rsi': trend_data['rsi'],
            'tier': tier,
            'lot_size': lot_size
        }
        
        directional_bias = trend_data['bias']
        rsi = trend_data['rsi']
        
        scan_calls = directional_bias in ["BULLISH", "NEUTRAL"] or rsi < RSI_OVERSOLD
        scan_puts = directional_bias in ["BEARISH", "NEUTRAL"] or rsi > RSI_OVERBOUGHT
        
        # Scan CALLS
        if scan_calls:
            for strike in strikes_in_range:
                if strike not in calls:
                    continue
                
                opt = calls[strike]
                price, price_source = get_option_price(opt, market_open)
                if price <= 0:
                    logger.debug("  [SKIP] %s %d CE: price=0 (no quote)", symbol, strike)
                    continue
                
                # Minimum premium filter (avoid penny options)
                if price < min_premium:
                    logger.debug("  [SKIP] %s %d CE: premium=%.2f < %.2f (too cheap)", 
                               symbol, strike, price, min_premium)
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                expiry = opt.get('expiryDate', nearest_expiry)
                
                # Volume/OI filter - require EITHER good volume OR good OI
                if market_open:
                    if vol < vol_thresh and oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d CE: vol=%d < %d AND oi=%d < %d", 
                                   symbol, strike, vol, vol_thresh, oi, oi_thresh)
                        continue
                else:
                    # After hours: require high OI for liquidity
                    if oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d CE: oi=%d < %d (after-hours)", 
                                   symbol, strike, oi, oi_thresh)
                        continue
                
                spread_pct = get_option_spread(opt, price, market_open)
                if spread_pct > spread_limit:
                    logger.debug("  [SKIP] %s %d CE: spread=%.2f > %.2f", 
                               symbol, strike, spread_pct, spread_limit)
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO_STOCK:
                    logger.debug("  [SKIP] %s %d CE: premium_ratio=%.2f > %.2f", 
                               symbol, strike, price/spot, MAX_PREMIUM_RATIO_STOCK)
                    continue
                
                moneyness = get_moneyness(strike, spot, "CE")
                breakeven = calculate_breakeven(strike, price, "CE")
                distance = calculate_distance_from_spot(strike, spot, "CE")
                total_cost = price * lot_size
                dte = calculate_days_to_expiry(expiry)
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Call', 'strike': strike, 'type': 'CE',
                    'premium': price, 'price_source': price_source,
                    'volume': vol, 'open_interest': oi, 'oi_change': oi_chg,
                    'moneyness': moneyness, 'expiry': expiry, 'days_to_expiry': dte,
                    'total_cost': total_cost, 'breakeven': breakeven, 'distance_from_spot': distance
                })
                alerts.append(alert)
        
        # Scan PUTS
        if scan_puts:
            for strike in strikes_in_range:
                if strike not in puts:
                    continue
                
                opt = puts[strike]
                price, price_source = get_option_price(opt, market_open)
                if price <= 0:
                    logger.debug("  [SKIP] %s %d PE: price=0 (no quote)", symbol, strike)
                    continue
                
                # Minimum premium filter (avoid penny options)
                if price < min_premium:
                    logger.debug("  [SKIP] %s %d PE: premium=%.2f < %.2f (too cheap)", 
                               symbol, strike, price, min_premium)
                    continue
                
                vol = opt.get('totalTradedVolume') or 0
                oi = opt.get('openInterest') or 0
                oi_chg = opt.get('changeinOpenInterest') or 0
                expiry = opt.get('expiryDate', nearest_expiry)
                
                # Volume/OI filter - require EITHER good volume OR good OI
                if market_open:
                    if vol < vol_thresh and oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d PE: vol=%d < %d AND oi=%d < %d", 
                                   symbol, strike, vol, vol_thresh, oi, oi_thresh)
                        continue
                else:
                    # After hours: require high OI for liquidity
                    if oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d PE: oi=%d < %d (after-hours)", 
                                   symbol, strike, oi, oi_thresh)
                        continue
                
                spread_pct = get_option_spread(opt, price, market_open)
                if spread_pct > spread_limit:
                    logger.debug("  [SKIP] %s %d PE: spread=%.2f > %.2f", 
                               symbol, strike, spread_pct, spread_limit)
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO_STOCK:
                    logger.debug("  [SKIP] %s %d PE: premium_ratio=%.2f > %.2f", 
                               symbol, strike, price/spot, MAX_PREMIUM_RATIO_STOCK)
                    continue
                
                moneyness = get_moneyness(strike, spot, "PE")
                breakeven = calculate_breakeven(strike, price, "PE")
                distance = calculate_distance_from_spot(strike, spot, "PE")
                total_cost = price * lot_size
                dte = calculate_days_to_expiry(expiry)
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Put', 'strike': strike, 'type': 'PE',
                    'premium': price, 'price_source': price_source,
                    'volume': vol, 'open_interest': oi, 'oi_change': oi_chg,
                    'moneyness': moneyness, 'expiry': expiry, 'days_to_expiry': dte,
                    'total_cost': total_cost, 'breakeven': breakeven, 'distance_from_spot': distance
                })
                alerts.append(alert)
        
        # ================== SPREAD STRATEGY SCANS ==================
        # Only scan spreads if we have enough data
        if calls and puts and strikes:
            # Bull Call Spread - for bullish stocks
            spread_alerts = scan_bull_call_spread(
                symbol, calls, spot, strikes, atm, nearest_expiry, 
                iv_data, trend_data, lot_size, is_index=False
            )
            alerts.extend(spread_alerts)
            
            # Bear Put Spread - for bearish stocks
            spread_alerts = scan_bear_put_spread(
                symbol, puts, spot, strikes, atm, nearest_expiry,
                iv_data, trend_data, lot_size, is_index=False
            )
            alerts.extend(spread_alerts)
            
            # Long Straddle - for low IV environment
            straddle_alerts = scan_long_straddle(
                symbol, calls, puts, spot, atm, nearest_expiry,
                iv_data, lot_size, is_index=False
            )
            alerts.extend(straddle_alerts)
            
            # Long Strangle - for very low IV environment
            strangle_alerts = scan_long_strangle(
                symbol, calls, puts, spot, strikes, atm, nearest_expiry,
                iv_data, lot_size, is_index=False
            )
            alerts.extend(strangle_alerts)
        
        if alerts:
            logger.info("  -> %d alerts generated", len(alerts))
    
    except Exception as e:
        logger.debug("Stock %s scan error: %s", symbol, e)
    
    return alerts

