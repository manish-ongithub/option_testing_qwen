"""
Smart Options Screener v3.3

A modular options screener for NSE stocks and indices with support for:
- Single-leg strategies (Long Call, Long Put)
- Multi-leg strategies (Bull Call Spread, Bear Put Spread, Straddle, Strangle)
- IV data from Opstra with Historical Volatility fallback
- Real-time and after-hours scanning modes

Usage:
    # Run the screener
    python -m screener.main
    
    # Or import and use programmatically
    from screener import job, scan_stock, scan_index
    from screener.config import STOCK_SYMBOLS, INDEX_SYMBOLS
    from screener.iv import set_opstra_cookies
"""

from screener.main import job, run_scheduler
from screener.config import STOCK_SYMBOLS, INDEX_SYMBOLS
from screener.scanners import scan_stock, scan_index
from screener.iv import set_opstra_cookies, is_opstra_configured, get_iv_data
from screener.api import is_market_hours, get_india_vix, determine_market_regime

__version__ = "3.3.0"

__all__ = [
    # Main functions
    "job",
    "run_scheduler",
    # Scanners
    "scan_stock",
    "scan_index",
    # Configuration
    "STOCK_SYMBOLS",
    "INDEX_SYMBOLS",
    # IV functions
    "set_opstra_cookies",
    "is_opstra_configured",
    "get_iv_data",
    # Market status
    "is_market_hours",
    "get_india_vix",
    "determine_market_regime",
]
