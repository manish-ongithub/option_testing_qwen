"""
Smart Options Screener v3.3 - Main Entry Point

Run the screener:
    python -m screener.main
"""

import time
import schedule

from screener.config import (
    INDEX_SYMBOLS, STOCK_SYMBOLS, ALLOW_AFTER_HOURS_SCAN,
    AFTER_HOURS_OI_THRESHOLD_STOCK, AFTER_HOURS_OI_THRESHOLD_INDEX
)
from screener.api.market_status import is_market_hours, get_india_vix, determine_market_regime
from screener.iv.opstra import is_opstra_configured, set_opstra_cookies
from screener.scanners.stock import scan_stock
from screener.scanners.index import scan_index
from screener.output.csv_logger import log_to_csv
from screener.output.json_logger import log_alerts_batch_to_json
from screener.utils.logging_setup import logger


def job():
    """
    Main scanning job. Scans all configured indices and stocks.
    """
    logger.info("=" * 100)
    logger.info("Starting scan...")
    
    market_open = is_market_hours()
    opstra_status = "CONFIGURED" if is_opstra_configured() else "NOT SET (using HV fallback)"
    
    # Check if we should skip scanning when market is closed
    if not market_open and not ALLOW_AFTER_HOURS_SCAN:
        logger.info("Market: CLOSED | Scanning disabled outside market hours")
        logger.info("Set ALLOW_AFTER_HOURS_SCAN=True to enable after-hours scanning")
        logger.info("=" * 100)
        return
    
    mode_str = "LIVE" if market_open else "AFTER-HOURS (relaxed filters)"
    logger.info("Market: %s | Mode: %s | Opstra: %s", 
               "OPEN" if market_open else "CLOSED", mode_str, opstra_status)
    
    if not market_open:
        logger.info("After-Hours Mode: Using OI-only filters (OI >= %d for stocks, >= %d for indices)",
                   AFTER_HOURS_OI_THRESHOLD_STOCK, AFTER_HOURS_OI_THRESHOLD_INDEX)
    
    vix = get_india_vix()
    regime = determine_market_regime(vix)
    
    logger.info("VIX=%.1f | Regime=%s", vix, regime)
    logger.info("=" * 100)
    
    all_alerts = []
    
    # Scan indices
    logger.info("\n--- Scanning Indices ---")
    for sym in INDEX_SYMBOLS:
        alerts = scan_index(sym, 60, regime, vix, market_open)
        all_alerts.extend(alerts)
    
    # Scan stocks
    logger.info("\n--- Scanning Stocks (%d) ---", len(STOCK_SYMBOLS))
    for i, sym in enumerate(STOCK_SYMBOLS):
        if (i + 1) % 20 == 0:
            logger.info("Progress: %d/%d...", i + 1, len(STOCK_SYMBOLS))
        alerts = scan_stock(sym, regime, vix, market_open)
        all_alerts.extend(alerts)
        time.sleep(0.3)
    
    # Deduplicate
    seen = set()
    unique_alerts = []
    for a in all_alerts:
        key = (a['strategy'], a['symbol'], a['strike'])
        if key not in seen:
            seen.add(key)
            unique_alerts.append(a)
    
    unique_alerts.sort(key=lambda x: x.get('volume', 0), reverse=True)
    
    logger.info("=" * 100)
    logger.info("SCAN COMPLETE: %d unique alerts", len(unique_alerts))
    logger.info("=" * 100)
    
    if unique_alerts:
        _print_top_alerts(unique_alerts)
        _save_alerts(unique_alerts)
    else:
        logger.info("\nNo alerts generated.")


def _print_top_alerts(unique_alerts):
    """Print top 15 alerts by volume."""
    logger.info("\n" + "=" * 120)
    logger.info("TOP 15 ALERTS BY VOLUME")
    logger.info("=" * 120)
    logger.info("")
    logger.info("%-3s %-10s %-6s %-4s %-10s %-10s %-7s %-11s %-10s %-4s %-12s %-8s",
               "#", "SYMBOL", "TYPE", "MON", "STRIKE", "PREMIUM", "VOL", 
               "COST", "BREAKEVEN", "DTE", "DISTANCE", "IV_SRC")
    logger.info("-" * 120)
    
    for i, alert in enumerate(unique_alerts[:15]):
        iv_src = alert.get('iv_source', '?')[:3].upper()
        # Handle breakeven - can be number or string for multi-leg strategies
        breakeven = alert.get('breakeven', 0)
        if isinstance(breakeven, (int, float)):
            breakeven_str = f"{breakeven:.0f}"
        else:
            breakeven_str = str(breakeven)[:10]  # Truncate if too long
        
        logger.info("%-3d %-10s %-6s %-4s %-10s ₹%-9.2f %-7d ₹%-10.0f %-10s %-4d %-12s %-8s",
                   i+1, alert['symbol'],
                   alert['strategy'].replace('Long ', ''),
                   alert.get('moneyness', '')[:3],
                   str(alert['strike'])[:10], alert['premium'], alert['volume'],
                   alert.get('total_cost', 0), breakeven_str,
                   alert.get('days_to_expiry', -1),
                   str(alert.get('distance_from_spot', ''))[:12],
                   iv_src)
    
    logger.info("-" * 120)
    
    # IV source summary
    opstra_count = sum(1 for a in unique_alerts if a.get('iv_source') == 'opstra')
    hv_count = sum(1 for a in unique_alerts if a.get('iv_source') == 'hv_calculated')
    default_count = sum(1 for a in unique_alerts if a.get('iv_source') == 'default')
    
    logger.info("\nIV Data Sources: Opstra=%d | HV Calculated=%d | Default=%d",
               opstra_count, hv_count, default_count)
    
    if default_count > 0:
        logger.info("WARNING: %d alerts have no reliable IV data", default_count)
    
    if not is_opstra_configured():
        logger.info("\nTIP: Configure Opstra cookies for accurate IV data:")
        logger.info("   set_opstra_cookies('your_jsessionid', 'your_dsessionid')")


def _save_alerts(unique_alerts):
    """Save alerts to CSV and JSON files."""
    from screener.config import CSV_FILE, JSON_FILE
    
    # Save to CSV
    for alert in unique_alerts:
        log_to_csv(alert)
    
    # Save to JSON (batch for efficiency)
    log_alerts_batch_to_json(unique_alerts)
    
    logger.info("\nResults saved to:")
    logger.info("  CSV: %s", CSV_FILE)
    logger.info("  JSON: %s", JSON_FILE)


def run_scheduler(interval_seconds=300):
    """
    Run the screener on a schedule.
    
    Args:
        interval_seconds: Time between scans (default: 300 = 5 minutes)
    """
    logger.info("Smart Options Screener v3.3")
    logger.info("Features: Opstra IV + HV Fallback + Enhanced Alerts")
    logger.info("Stocks: %d | Indices: %d", len(STOCK_SYMBOLS), len(INDEX_SYMBOLS))
    
    if not is_opstra_configured():
        logger.info("")
        logger.info("Opstra cookies not configured - using Historical Volatility fallback")
        logger.info("   For accurate IV data, set cookies after logging into Opstra:")
        logger.info("   set_opstra_cookies('JSESSIONID_value', 'DSESSIONID_value')")
        logger.info("")
    
    # Run once immediately
    job()
    
    # Schedule recurring runs
    schedule.every(interval_seconds).seconds.do(job)
    logger.info("\nScheduler started. Press Ctrl+C to stop.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_scheduler()

