"""
Lot Size Module for Indian Options Trading

Contains lot size mappings for Index and Stock options.
Lot sizes are updated periodically by exchanges, so this serves as a 
reference that can be updated or overridden from contract master data.
"""

from typing import Optional
import logging

logger = logging.getLogger("LotSizes")


# Index Options Lot Sizes (as of Dec 2024)
INDEX_LOT_SIZES = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "NIFTYIT": 15,
    "SENSEX": 10,
    "BANKEX": 15,
}

# Stock Options Lot Sizes (commonly traded, as of Dec 2024)
# This is a subset - full list should be loaded from contract master
STOCK_LOT_SIZES = {
    "RELIANCE": 250,
    "TCS": 150,
    "HDFCBANK": 550,
    "INFY": 300,
    "ICICIBANK": 700,
    "SBIN": 750,
    "BHARTIARTL": 475,
    "ITC": 1600,
    "KOTAKBANK": 400,
    "LT": 150,
    "AXISBANK": 600,
    "HINDUNILVR": 300,
    "BAJFINANCE": 125,
    "MARUTI": 100,
    "ASIANPAINT": 200,
    "TITAN": 175,
    "TATAMOTORS": 575,
    "TATASTEEL": 425,
    "SUNPHARMA": 350,
    "WIPRO": 1000,
    "TECHM": 400,
    "HCLTECH": 350,
    "POWERGRID": 2700,
    "NTPC": 2000,
    "ONGC": 3850,
    "COALINDIA": 1500,
    "JSWSTEEL": 650,
    "ADANIENT": 250,
    "ADANIPORTS": 625,
    "BAJAJFINSV": 500,
    "ULTRACEMCO": 100,
    "HINDALCO": 1300,
    "GRASIM": 275,
    "DIVISLAB": 175,
    "DRREDDY": 125,
    "CIPLA": 650,
    "APOLLOHOSP": 125,
    "EICHERMOT": 175,
    "M&M": 350,
    "HEROMOTOCO": 150,
    "BAJAJ-AUTO": 250,
    "TATACONSUM": 450,
    "BRITANNIA": 100,
    "NESTLEIND": 50,
    "INDUSINDBK": 450,
    "PNB": 6000,
    "BANKBARODA": 2900,
    "CANBK": 5400,
    "IDFCFIRSTB": 7500,
    "FEDERALBNK": 5000,
    "HDFC": 300,  # Merged but may still have some contracts
}

# Combined lookup
ALL_LOT_SIZES = {**INDEX_LOT_SIZES, **STOCK_LOT_SIZES}

# Default lot size for unknown symbols
DEFAULT_LOT_SIZE = 1


def get_lot_size(symbol: str, from_instrument: Optional[object] = None) -> int:
    """
    Get lot size for a given symbol.
    
    Priority order:
    1. Hardcoded INDEX lot sizes (most reliable, updated with NSE changes)
    2. Hardcoded STOCK lot sizes 
    3. Instrument's lot_size (from NFO.csv - may be outdated)
    4. Default lot size
    
    Args:
        symbol: Trading symbol (e.g., "NIFTY", "RELIANCE")
        from_instrument: Optional Instrument namedtuple with lot_size field
    
    Returns:
        Lot size as integer
    """
    # Clean the symbol (remove expiry/strike info if present)
    base_symbol = _extract_base_symbol(symbol)
    
    # Priority 1: Hardcoded INDEX lot sizes (most reliable - updated Dec 2024)
    # NSE changed NIFTY from 75->25, BANKNIFTY from 25->15 in late 2024
    if base_symbol in INDEX_LOT_SIZES:
        return INDEX_LOT_SIZES[base_symbol]
    
    # Priority 2: Hardcoded STOCK lot sizes
    if base_symbol in STOCK_LOT_SIZES:
        return STOCK_LOT_SIZES[base_symbol]
    
    # Priority 3: Use lot size from instrument if available (for unknown symbols)
    if from_instrument is not None:
        try:
            lot_size = int(from_instrument.lot_size)
            if lot_size > 0:
                return lot_size
        except (AttributeError, ValueError, TypeError):
            pass
    
    # Priority 4: Return default
    logger.warning(f"Lot size not found for {symbol}, using default: {DEFAULT_LOT_SIZE}")
    return DEFAULT_LOT_SIZE


def _extract_base_symbol(symbol: str) -> str:
    """
    Extract base symbol from trading symbol.
    E.g., "NIFTY23DEC25C24000" -> "NIFTY"
    """
    symbol = symbol.upper().strip()
    
    # Check if it matches any known symbol as prefix
    for known_symbol in sorted(ALL_LOT_SIZES.keys(), key=len, reverse=True):
        if symbol.startswith(known_symbol):
            return known_symbol
    
    # Fallback: return as-is
    return symbol


def validate_quantity(symbol: str, quantity: int, from_instrument: Optional[object] = None) -> tuple[bool, str]:
    """
    Validate if quantity is a valid multiple of lot size.
    
    Args:
        symbol: Trading symbol
        quantity: Order quantity
        from_instrument: Optional Instrument with lot_size
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if quantity <= 0:
        return False, "Quantity must be positive"
    
    lot_size = get_lot_size(symbol, from_instrument)
    
    if quantity % lot_size != 0:
        return False, f"Quantity {quantity} is not a multiple of lot size {lot_size} for {symbol}"
    
    return True, ""


def get_lots_count(symbol: str, quantity: int, from_instrument: Optional[object] = None) -> int:
    """
    Calculate number of lots for a given quantity.
    
    Args:
        symbol: Trading symbol
        quantity: Total quantity
        from_instrument: Optional Instrument with lot_size
    
    Returns:
        Number of lots
    """
    lot_size = get_lot_size(symbol, from_instrument)
    return quantity // lot_size


def quantity_to_lots(quantity: int, lot_size: int) -> int:
    """Convert quantity to number of lots."""
    return quantity // lot_size


def lots_to_quantity(lots: int, lot_size: int) -> int:
    """Convert number of lots to quantity."""
    return lots * lot_size


def round_to_lot_size(symbol: str, quantity: int, from_instrument: Optional[object] = None) -> int:
    """
    Round quantity down to nearest valid lot size multiple.
    
    Args:
        symbol: Trading symbol
        quantity: Desired quantity
        from_instrument: Optional Instrument with lot_size
    
    Returns:
        Valid quantity (rounded down)
    """
    lot_size = get_lot_size(symbol, from_instrument)
    return (quantity // lot_size) * lot_size


# Function to update lot sizes at runtime (from contract master)
def update_lot_size(symbol: str, lot_size: int) -> None:
    """
    Update lot size for a symbol at runtime.
    Useful when loading from contract master CSV.
    """
    if lot_size > 0:
        ALL_LOT_SIZES[symbol.upper()] = lot_size


def bulk_update_lot_sizes(lot_size_map: dict) -> None:
    """
    Bulk update lot sizes from a dictionary.
    
    Args:
        lot_size_map: Dict of {symbol: lot_size}
    """
    for symbol, lot_size in lot_size_map.items():
        if lot_size > 0:
            ALL_LOT_SIZES[symbol.upper()] = int(lot_size)
