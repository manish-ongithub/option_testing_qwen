"""
Index options scanner.
"""

from datetime import datetime

from screener.config import (
    IST, VOLUME_THRESHOLD_INDEX, OI_THRESHOLD_INDEX,
    AFTER_HOURS_OI_THRESHOLD_INDEX, AFTER_HOURS_SPREAD_PCT,
    MAX_SPREAD_PCT, MAX_PREMIUM_RATIO,
    MIN_PREMIUM_INDEX, STRIKE_RANGE_MULTIPLIER
)
from screener.api.option_chain import fetch_nse_option_chain
from screener.iv.provider import get_iv_data
from screener.utils.helpers import (
    get_lot_size, find_atm_strike, get_moneyness,
    calculate_breakeven, calculate_distance_from_spot, calculate_days_to_expiry,
    get_option_price, get_option_spread, get_underlying_price
)
from screener.utils.logging_setup import logger
from screener.strategies.bull_call_spread import scan_bull_call_spread
from screener.strategies.bear_put_spread import scan_bear_put_spread
from screener.strategies.long_straddle import scan_long_straddle
from screener.strategies.long_strangle import scan_long_strangle


def scan_index(symbol, iv_threshold, market_regime, vix, market_open=True):
    """
    Scan an index for option trading opportunities.
    
    Args:
        symbol: Index symbol (e.g., 'NIFTY', 'BANKNIFTY')
        iv_threshold: IV threshold for filtering
        market_regime: Current market volatility regime
        vix: Current India VIX value
        market_open: Whether market is currently open
    
    Returns:
        list: List of alert dictionaries
    """
    alerts = []
    
    try:
        lot_size = get_lot_size(symbol)
        
        # Set thresholds based on market status
        if market_open:
            vol_thresh = VOLUME_THRESHOLD_INDEX
            oi_thresh = OI_THRESHOLD_INDEX
            spread_limit = MAX_SPREAD_PCT
            min_premium = MIN_PREMIUM_INDEX
        else:
            vol_thresh = 0  # No volume requirement after hours
            oi_thresh = AFTER_HOURS_OI_THRESHOLD_INDEX
            spread_limit = AFTER_HOURS_SPREAD_PCT
            min_premium = MIN_PREMIUM_INDEX
        
        spot = get_underlying_price(symbol)
        if not spot:
            return []
        
        # Get IV data for index
        iv_data = get_iv_data(symbol)
        
        logger.info("Index %s: Spot=%.0f | IV=%.1f%% IVP=%d%% [%s] | Mode=%s",
                   symbol, spot, iv_data['iv'], iv_data['iv_percentile'], 
                   iv_data['source'].upper(), "LIVE" if market_open else "AFTER-HOURS")
        
        # Fetch option chain using NSE API v3
        oc = fetch_nse_option_chain(symbol, is_index=True)
        
        if not oc or 'records' not in oc:
            logger.warning("Index %s: Option chain data unavailable", symbol)
            return []
        
        records = oc['records'].get('data', [])
        if not records:
            logger.warning("Index %s: No option records found", symbol)
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
        step = strikes[1] - strikes[0] if len(strikes) > 1 else (100 if symbol == "BANKNIFTY" else 50)
        max_distance = step * STRIKE_RANGE_MULTIPLIER
        strikes_in_range = [s for s in strikes if abs(s - atm) <= max_distance]
        
        base_alert = {
            'timestamp': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol, 'instrument_type': 'INDEX', 'spot': spot,
            'iv': iv_data['iv'], 'iv_percentile': iv_data['iv_percentile'],
            'iv_rank': iv_data['iv_rank'], 'iv_source': iv_data['source'],
            'market_regime': market_regime, 'vix': vix, 'rsi': 0,
            'tier': 'INDEX', 'lot_size': lot_size
        }
        
        for strike in strikes_in_range:
            # CALLS
            if strike in calls:
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
                    if not (vol >= vol_thresh or oi >= oi_thresh):
                        logger.debug("  [SKIP] %s %d CE: vol=%d < %d and oi=%d < %d", 
                                   symbol, strike, vol, vol_thresh, oi, oi_thresh)
                        continue
                else:
                    # After hours: require very high OI for liquidity
                    if oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d CE: oi=%d < %d (after-hours)", 
                                   symbol, strike, oi, oi_thresh)
                        continue
                
                spread_pct = get_option_spread(opt, price, market_open)
                if spread_pct > spread_limit:
                    logger.debug("  [SKIP] %s %d CE: spread=%.2f > %.2f", 
                               symbol, strike, spread_pct, spread_limit)
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO:
                    logger.debug("  [SKIP] %s %d CE: premium_ratio=%.2f > %.2f", 
                               symbol, strike, price/spot, MAX_PREMIUM_RATIO)
                    continue
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Call', 'strike': strike, 'type': 'CE',
                    'premium': price, 'price_source': price_source,
                    'volume': vol, 'open_interest': oi, 'oi_change': oi_chg,
                    'moneyness': get_moneyness(strike, spot, "CE"),
                    'expiry': expiry, 'days_to_expiry': calculate_days_to_expiry(expiry),
                    'total_cost': price * lot_size,
                    'breakeven': calculate_breakeven(strike, price, "CE"),
                    'distance_from_spot': calculate_distance_from_spot(strike, spot, "CE")
                })
                alerts.append(alert)
            
            # PUTS
            if strike in puts:
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
                    if not (vol >= vol_thresh or oi >= oi_thresh):
                        logger.debug("  [SKIP] %s %d PE: vol=%d < %d and oi=%d < %d", 
                                   symbol, strike, vol, vol_thresh, oi, oi_thresh)
                        continue
                else:
                    # After hours: require very high OI for liquidity
                    if oi < oi_thresh:
                        logger.debug("  [SKIP] %s %d PE: oi=%d < %d (after-hours)", 
                                   symbol, strike, oi, oi_thresh)
                        continue
                
                spread_pct = get_option_spread(opt, price, market_open)
                if spread_pct > spread_limit:
                    logger.debug("  [SKIP] %s %d PE: spread=%.2f > %.2f", 
                               symbol, strike, spread_pct, spread_limit)
                    continue
                
                if price / spot > MAX_PREMIUM_RATIO:
                    logger.debug("  [SKIP] %s %d PE: premium_ratio=%.2f > %.2f", 
                               symbol, strike, price/spot, MAX_PREMIUM_RATIO)
                    continue
                
                alert = base_alert.copy()
                alert.update({
                    'strategy': 'Long Put', 'strike': strike, 'type': 'PE',
                    'premium': price, 'price_source': price_source,
                    'volume': vol, 'open_interest': oi, 'oi_change': oi_chg,
                    'moneyness': get_moneyness(strike, spot, "PE"),
                    'expiry': expiry, 'days_to_expiry': calculate_days_to_expiry(expiry),
                    'total_cost': price * lot_size,
                    'breakeven': calculate_breakeven(strike, price, "PE"),
                    'distance_from_spot': calculate_distance_from_spot(strike, spot, "PE")
                })
                alerts.append(alert)
        
        # ================== SPREAD STRATEGY SCANS FOR INDEX ==================
        # Create trend_data for index (neutral bias for spread strategies)
        index_trend = {'bias': 'NEUTRAL', 'rsi': 50}
        
        if calls and puts and strikes:
            # Bull Call Spread - for moderately bullish view
            spread_alerts = scan_bull_call_spread(
                symbol, calls, spot, strikes, atm, nearest_expiry,
                iv_data, index_trend, lot_size, is_index=True
            )
            alerts.extend(spread_alerts)
            
            # Bear Put Spread - for moderately bearish view
            spread_alerts = scan_bear_put_spread(
                symbol, puts, spot, strikes, atm, nearest_expiry,
                iv_data, index_trend, lot_size, is_index=True
            )
            alerts.extend(spread_alerts)
            
            # Long Straddle - for low IV environment (event play)
            straddle_alerts = scan_long_straddle(
                symbol, calls, puts, spot, atm, nearest_expiry,
                iv_data, lot_size, is_index=True
            )
            alerts.extend(straddle_alerts)
            
            # Long Strangle - for very low IV environment
            strangle_alerts = scan_long_strangle(
                symbol, calls, puts, spot, strikes, atm, nearest_expiry,
                iv_data, lot_size, is_index=True
            )
            alerts.extend(strangle_alerts)
        
        logger.info("  -> %d alerts generated", len(alerts))
    
    except Exception as e:
        logger.exception("Index %s scan error: %s", symbol, e)
    
    return alerts

