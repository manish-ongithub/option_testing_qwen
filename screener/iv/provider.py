"""
Unified IV data provider.

Provides a single interface that tries multiple data sources.
"""

from screener.iv.opstra import get_iv_from_opstra, is_opstra_configured
from screener.iv.historical import calculate_historical_volatility
from screener.utils.logging_setup import logger


# Global flag to skip Opstra (can be set by UI or CLI)
_SKIP_OPSTRA = False


def set_skip_opstra(skip: bool):
    """Set whether to skip Opstra and use HV only."""
    global _SKIP_OPSTRA
    _SKIP_OPSTRA = skip
    logger.debug("Skip Opstra set to: %s", skip)


def is_skip_opstra_enabled() -> bool:
    """Check if Opstra is being skipped."""
    return _SKIP_OPSTRA


def get_iv_data(symbol):
    """
    Get IV data with fallback chain:
    1. Try Opstra API (if cookies configured and not skipped)
    2. Fall back to Historical Volatility calculation
    3. Return defaults with warning
    
    Args:
        symbol: Stock or index symbol
    
    Returns:
        dict: {'iv': float, 'iv_percentile': int, 'iv_rank': int, 'source': str}
    """
    # Try Opstra first (unless skipped)
    if not _SKIP_OPSTRA and is_opstra_configured():
        opstra_data = get_iv_from_opstra(symbol)
        if opstra_data:
            return opstra_data
    
    # Fallback to Historical Volatility
    hv_data = calculate_historical_volatility(symbol)
    if hv_data:
        return hv_data
    
    # Last resort: return defaults with warning
    logger.debug("%s: Using default IV values (no data available)", symbol)
    return {
        'iv': 0,
        'iv_percentile': 50,  # Assume middle of the range
        'iv_rank': 50,
        'source': 'default'  # Clearly marked as unreliable
    }

