"""
Alert Normalizer for Paper Trading Application

Converts alerts from the screener format to the trading system format.
Supports both old format (v3.2) and new format (v3.3+).

Old Screener Format Fields (PascalCase):
- Timestamp, Symbol, Type, Strategy, Strike, Premium, PriceSource, Spot,
- Volume, OI, OI_Change, IV, IV_Percentile, IV_Rank, IV_Source,
- Market_Regime, RSI, Tier, Moneyness, Expiry, DaysToExpiry, LotSize,
- TotalCost, Breakeven, DistanceFromSpot

New Screener Format Fields (v3.3+, lowercase_underscore):
- timestamp, symbol, instrument_type, strategy, strike, premium, price_source,
- spot, volume, open_interest, iv, iv_percentile, expiry, days_to_expiry,
- lot_size, total_cost, breakeven, distance_from_spot
- Multi-leg fields: leg1, leg2, max_profit, max_loss, reward_ratio

Trading System Format:
- symbol, expiry, strike, option_type, action, price_limit, quantity,
- stop_loss, target, validity
"""

import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime

logger = logging.getLogger("AlertNormalizer")

# Strategy type constants
SINGLE_LEG_STRATEGIES = ['Long Call', 'Long Put', 'Short Call', 'Short Put']
SPREAD_STRATEGIES = ['Bull Call Spread', 'Bear Put Spread', 'Bull Put Spread', 'Bear Call Spread']
VOLATILITY_STRATEGIES = ['Long Straddle', 'Long Strangle', 'Short Straddle', 'Short Strangle']


def normalize_alert(raw_alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize an alert from screener format to trading system format.
    Supports both old (v3.2) and new (v3.3+) screener formats.
    
    Args:
        raw_alert: Alert dictionary from the screener
    
    Returns:
        Normalized alert dictionary for the trading system
    """
    # Check if it's already normalized (has both 'action' and 'option_type' keys)
    if 'action' in raw_alert and 'option_type' in raw_alert:
        return _ensure_required_fields(raw_alert)
    
    # Detect format based on field naming convention
    is_new_format = _is_new_format(raw_alert)
    
    # Get strategy first - needed for option type inference
    strategy = _get_field(raw_alert, 'Strategy', 'strategy', default='')
    
    # Determine strategy type
    strategy_type = _get_strategy_type(strategy)
    
    # Normalize based on strategy type
    if strategy_type == 'spread':
        return _normalize_spread_alert(raw_alert, strategy, is_new_format)
    elif strategy_type == 'volatility':
        return _normalize_volatility_alert(raw_alert, strategy, is_new_format)
    else:
        return _normalize_single_leg_alert(raw_alert, strategy, is_new_format)


def _is_new_format(raw_alert: Dict[str, Any]) -> bool:
    """Detect if alert is in new v3.3+ format."""
    # New format uses lowercase fields and has specific new fields
    new_format_indicators = ['instrument_type', 'open_interest', 'price_source', 'leg1', 'leg2']
    for indicator in new_format_indicators:
        if indicator in raw_alert:
            return True
    
    # Check if it uses lowercase 'symbol' instead of 'Symbol'
    if 'symbol' in raw_alert and 'Symbol' not in raw_alert:
        return True
    
    return False


def _get_field(alert: Dict[str, Any], old_key: str, new_key: str, default=None) -> Any:
    """Get field value supporting both old and new key names."""
    return alert.get(new_key, alert.get(old_key, default))


def _get_strategy_type(strategy: str) -> str:
    """Determine strategy type: 'single', 'spread', or 'volatility'."""
    if not strategy:
        return 'single'
    
    strategy_lower = strategy.lower().strip()
    
    for s in SPREAD_STRATEGIES:
        if s.lower() in strategy_lower:
            return 'spread'
    
    for s in VOLATILITY_STRATEGIES:
        if s.lower() in strategy_lower:
            return 'volatility'
    
    return 'single'


def _infer_option_type_from_strategy(strategy: str) -> str:
    """
    Infer option type (CE/PE) from strategy name.
    
    Strategies:
    - Long Call, Short Call, Bull Call Spread -> CE
    - Long Put, Short Put, Bear Put Spread -> PE
    - Straddles/Strangles -> Both (handled separately)
    """
    if not strategy:
        return 'CE'
    
    strategy_lower = strategy.lower().strip()
    
    # Call-based strategies
    if 'call' in strategy_lower:
        return 'CE'
    
    # Put-based strategies
    if 'put' in strategy_lower:
        return 'PE'
    
    # Bull strategies typically use calls
    if 'bull' in strategy_lower:
        return 'CE'
    
    # Bear strategies typically use puts
    if 'bear' in strategy_lower:
        return 'PE'
    
    # Default to CE
    return 'CE'


def _parse_strike(strike: Union[str, int, float]) -> float:
    """
    Parse strike price, handling string format for spreads (e.g., "26200/26300").
    Returns the primary (buying) leg strike.
    """
    if strike is None or strike == '':
        return 0.0
    
    if isinstance(strike, (int, float)):
        return float(strike)
    
    if isinstance(strike, str):
        # Handle spread format "26200/26300"
        if '/' in strike:
            parts = strike.split('/')
            try:
                return float(parts[0].strip())
            except ValueError:
                return 0.0
        
        # Standard numeric string
        try:
            return float(strike.replace(',', '').strip())
        except ValueError:
            return 0.0
    
    return 0.0


def _parse_breakeven(breakeven: Union[str, int, float]) -> Union[float, str]:
    """
    Parse breakeven, which can be a number or string range (e.g., "26009/26391").
    Returns float for single value, string for range.
    """
    if breakeven is None or breakeven == '':
        return 0.0
    
    if isinstance(breakeven, (int, float)):
        return float(breakeven)
    
    if isinstance(breakeven, str):
        # Handle range format for straddles/strangles
        if '/' in breakeven:
            return breakeven  # Return as-is for display
        
        try:
            return float(breakeven.replace(',', '').strip())
        except ValueError:
            return breakeven  # Return original string
    
    return 0.0


def _normalize_single_leg_alert(raw_alert: Dict[str, Any], strategy: str, is_new_format: bool) -> Dict[str, Any]:
    """Normalize a single-leg strategy alert (Long Call, Long Put, etc.)."""
    normalized = {}
    
    # === Core Trading Fields ===
    
    # Symbol
    normalized['symbol'] = _get_field(raw_alert, 'Symbol', 'symbol', 'UNKNOWN')
    
    # Option Type - infer from strategy if Type field is missing
    option_type = _get_field(raw_alert, 'Type', 'type', None)
    if option_type:
        normalized['option_type'] = option_type.upper()
    else:
        normalized['option_type'] = _infer_option_type_from_strategy(strategy)
    
    # Strike Price
    strike = _get_field(raw_alert, 'Strike', 'strike', 0)
    normalized['strike'] = _parse_strike(strike)
    
    # Premium -> Price Limit
    premium = _get_field(raw_alert, 'Premium', 'premium', 0)
    normalized['price_limit'] = _parse_number(premium)
    
    # Expiry Date
    expiry = _get_field(raw_alert, 'Expiry', 'expiry', '')
    normalized['expiry'] = _normalize_expiry(expiry)
    
    # Strategy -> Action
    normalized['action'] = _strategy_to_action(strategy)
    
    # Lot Size and Quantity
    lot_size = _get_field(raw_alert, 'LotSize', 'lot_size', 0)
    lot_size = _parse_number(lot_size)
    normalized['lot_size'] = int(lot_size) if lot_size else 0
    
    quantity = _get_field(raw_alert, 'Quantity', 'quantity', 0)
    if quantity:
        normalized['quantity'] = int(_parse_number(quantity))
    elif lot_size > 0:
        normalized['quantity'] = int(lot_size)  # Default to 1 lot
    else:
        normalized['quantity'] = 0
    
    # === Optional Trading Fields ===
    normalized['stop_loss'] = _get_field(raw_alert, 'StopLoss', 'stop_loss', None)
    normalized['target'] = _get_field(raw_alert, 'Target', 'target', None)
    normalized['validity'] = _get_field(raw_alert, 'validity', 'validity', 'DAY')
    
    # === Informational Fields ===
    normalized['timestamp'] = _get_field(raw_alert, 'Timestamp', 'timestamp', '')
    normalized['spot'] = _parse_number(_get_field(raw_alert, 'Spot', 'spot', 0))
    normalized['volume'] = _parse_number(_get_field(raw_alert, 'Volume', 'volume', 0))
    
    # OI field - handle both 'OI' and 'open_interest'
    oi = _get_field(raw_alert, 'OI', 'open_interest', 0)
    normalized['oi'] = _parse_number(oi)
    
    normalized['oi_change'] = _parse_number(_get_field(raw_alert, 'OI_Change', 'oi_change', 0))
    normalized['iv'] = _parse_number(_get_field(raw_alert, 'IV', 'iv', 0))
    normalized['iv_percentile'] = _parse_number(_get_field(raw_alert, 'IV_Percentile', 'iv_percentile', 0))
    normalized['iv_rank'] = _parse_number(_get_field(raw_alert, 'IV_Rank', 'iv_rank', 0))
    normalized['market_regime'] = _get_field(raw_alert, 'Market_Regime', 'market_regime', '')
    normalized['rsi'] = _parse_number(_get_field(raw_alert, 'RSI', 'rsi', 0))
    normalized['tier'] = _get_field(raw_alert, 'Tier', 'tier', '')
    normalized['moneyness'] = _get_field(raw_alert, 'Moneyness', 'moneyness', '')
    normalized['days_to_expiry'] = int(_parse_number(_get_field(raw_alert, 'DaysToExpiry', 'days_to_expiry', 0)))
    normalized['total_cost'] = _parse_number(_get_field(raw_alert, 'TotalCost', 'total_cost', 0))
    normalized['breakeven'] = _parse_breakeven(_get_field(raw_alert, 'Breakeven', 'breakeven', 0))
    normalized['distance_from_spot'] = _get_field(raw_alert, 'DistanceFromSpot', 'distance_from_spot', '')
    normalized['price_source'] = _get_field(raw_alert, 'PriceSource', 'price_source', '')
    normalized['iv_source'] = _get_field(raw_alert, 'IV_Source', 'iv_source', '')
    normalized['strategy'] = strategy
    normalized['strategy_type'] = 'single'
    
    # New format specific fields
    if is_new_format:
        normalized['instrument_type'] = raw_alert.get('instrument_type', '')
    
    return normalized


def _normalize_spread_alert(raw_alert: Dict[str, Any], strategy: str, is_new_format: bool) -> Dict[str, Any]:
    """
    Normalize a spread strategy alert (Bull Call Spread, Bear Put Spread, etc.).
    Uses the buying leg as primary, stores selling leg info separately.
    """
    normalized = _normalize_single_leg_alert(raw_alert, strategy, is_new_format)
    normalized['strategy_type'] = 'spread'
    
    # Parse leg information
    leg1 = raw_alert.get('leg1', {})
    leg2 = raw_alert.get('leg2', {})
    
    if leg1 and leg2:
        # Store leg details
        normalized['leg1'] = {
            'strike': _parse_strike(leg1.get('strike', 0)),
            'premium': _parse_number(leg1.get('premium', 0)),
            'action': leg1.get('action', 'BUY')
        }
        normalized['leg2'] = {
            'strike': _parse_strike(leg2.get('strike', 0)),
            'premium': _parse_number(leg2.get('premium', 0)),
            'action': leg2.get('action', 'SELL')
        }
        
        # Use leg1 strike as primary (buying leg)
        normalized['strike'] = normalized['leg1']['strike']
        normalized['price_limit'] = normalized['leg1']['premium']
        
        # Store spread-specific fields
        normalized['sell_strike'] = normalized['leg2']['strike']
        normalized['sell_premium'] = normalized['leg2']['premium']
    else:
        # Parse from string strike format "26200/26300"
        strike_str = _get_field(raw_alert, 'Strike', 'strike', '')
        if isinstance(strike_str, str) and '/' in strike_str:
            parts = strike_str.split('/')
            normalized['strike'] = float(parts[0].strip())
            normalized['sell_strike'] = float(parts[1].strip())
    
    # Spread-specific fields
    normalized['max_profit'] = _parse_number(raw_alert.get('max_profit', 0))
    normalized['max_loss'] = _parse_number(raw_alert.get('max_loss', 0))
    normalized['reward_ratio'] = _parse_number(raw_alert.get('reward_ratio', 0))
    
    # Display text for spreads
    if normalized.get('leg1') and normalized.get('leg2'):
        opt_type = normalized['option_type']
        normalized['display_text'] = (
            f"{normalized['leg1']['action']} {normalized['leg1']['strike']}{opt_type} / "
            f"{normalized['leg2']['action']} {normalized['leg2']['strike']}{opt_type}"
        )
    
    return normalized


def _normalize_volatility_alert(raw_alert: Dict[str, Any], strategy: str, is_new_format: bool) -> Dict[str, Any]:
    """
    Normalize a volatility strategy alert (Straddle, Strangle).
    Creates a combined alert with both CE and PE legs.
    """
    normalized = {}
    
    # === Core Trading Fields ===
    normalized['symbol'] = _get_field(raw_alert, 'Symbol', 'symbol', 'UNKNOWN')
    
    # For straddles/strangles, option_type indicates the strategy type
    if 'straddle' in strategy.lower():
        normalized['option_type'] = 'STRADDLE'
    else:
        normalized['option_type'] = 'STRANGLE'
    
    # Premium is combined for both legs
    premium = _get_field(raw_alert, 'Premium', 'premium', 0)
    normalized['price_limit'] = _parse_number(premium)
    
    # Expiry
    expiry = _get_field(raw_alert, 'Expiry', 'expiry', '')
    normalized['expiry'] = _normalize_expiry(expiry)
    
    # Action
    normalized['action'] = _strategy_to_action(strategy)
    
    # Lot Size and Quantity
    lot_size = _get_field(raw_alert, 'LotSize', 'lot_size', 0)
    lot_size = _parse_number(lot_size)
    normalized['lot_size'] = int(lot_size) if lot_size else 0
    
    quantity = _get_field(raw_alert, 'Quantity', 'quantity', 0)
    if quantity:
        normalized['quantity'] = int(_parse_number(quantity))
    elif lot_size > 0:
        normalized['quantity'] = int(lot_size)
    else:
        normalized['quantity'] = 0
    
    # Parse leg information
    leg1 = raw_alert.get('leg1', {})
    leg2 = raw_alert.get('leg2', {})
    
    if leg1 and leg2:
        normalized['leg1'] = {
            'strike': _parse_strike(leg1.get('strike', 0)),
            'premium': _parse_number(leg1.get('premium', 0)),
            'action': leg1.get('action', 'BUY CE'),
            'option_type': 'CE' if 'CE' in str(leg1.get('action', '')).upper() else 'PE'
        }
        normalized['leg2'] = {
            'strike': _parse_strike(leg2.get('strike', 0)),
            'premium': _parse_number(leg2.get('premium', 0)),
            'action': leg2.get('action', 'BUY PE'),
            'option_type': 'PE' if 'PE' in str(leg2.get('action', '')).upper() else 'CE'
        }
        
        # For straddles, both legs have same strike
        # For strangles, use CE strike as primary
        if normalized['option_type'] == 'STRADDLE':
            normalized['strike'] = normalized['leg1']['strike']
        else:
            # Strangle: store both strikes
            normalized['strike'] = normalized['leg1']['strike']  # CE strike
            normalized['put_strike'] = normalized['leg2']['strike']  # PE strike
    else:
        # Parse from string strike format "26100/26300" for strangles
        strike_str = _get_field(raw_alert, 'Strike', 'strike', '')
        if isinstance(strike_str, str) and '/' in strike_str:
            parts = strike_str.split('/')
            normalized['strike'] = float(parts[0].strip())  # CE/OTM call strike
            normalized['put_strike'] = float(parts[1].strip())  # PE/OTM put strike
        else:
            # Single strike for straddles
            normalized['strike'] = _parse_strike(strike_str)
    
    # Volatility-specific fields
    normalized['max_loss'] = _parse_number(raw_alert.get('max_loss', 0))
    normalized['breakeven'] = _parse_breakeven(_get_field(raw_alert, 'Breakeven', 'breakeven', ''))
    
    # === Optional Trading Fields ===
    normalized['stop_loss'] = _get_field(raw_alert, 'StopLoss', 'stop_loss', None)
    normalized['target'] = _get_field(raw_alert, 'Target', 'target', None)
    normalized['validity'] = _get_field(raw_alert, 'validity', 'validity', 'DAY')
    
    # === Informational Fields ===
    normalized['timestamp'] = _get_field(raw_alert, 'Timestamp', 'timestamp', '')
    normalized['spot'] = _parse_number(_get_field(raw_alert, 'Spot', 'spot', 0))
    normalized['volume'] = _parse_number(_get_field(raw_alert, 'Volume', 'volume', 0))
    oi = _get_field(raw_alert, 'OI', 'open_interest', 0)
    normalized['oi'] = _parse_number(oi)
    normalized['iv'] = _parse_number(_get_field(raw_alert, 'IV', 'iv', 0))
    normalized['iv_percentile'] = _parse_number(_get_field(raw_alert, 'IV_Percentile', 'iv_percentile', 0))
    normalized['days_to_expiry'] = int(_parse_number(_get_field(raw_alert, 'DaysToExpiry', 'days_to_expiry', 0)))
    normalized['total_cost'] = _parse_number(_get_field(raw_alert, 'TotalCost', 'total_cost', 0))
    normalized['distance_from_spot'] = _get_field(raw_alert, 'DistanceFromSpot', 'distance_from_spot', '')
    normalized['price_source'] = _get_field(raw_alert, 'PriceSource', 'price_source', '')
    normalized['strategy'] = strategy
    normalized['strategy_type'] = 'volatility'
    
    # New format specific fields
    if is_new_format:
        normalized['instrument_type'] = raw_alert.get('instrument_type', '')
    
    # Display text for straddles/strangles
    if normalized.get('leg1') and normalized.get('leg2'):
        normalized['display_text'] = (
            f"{normalized['leg1']['action']} {normalized['leg1']['strike']} / "
            f"{normalized['leg2']['action']} {normalized['leg2']['strike']}"
        )
    
    return normalized


def _parse_number(value) -> float:
    """Parse a value to float, handling various formats."""
    if value is None or value == '':
        return 0.0
    
    if isinstance(value, (int, float)):
        return float(value)
    
    try:
        # Remove commas, percentage signs, ± symbols, etc.
        cleaned = str(value).replace(',', '').replace('%', '').replace('±', '').strip()
        
        # Handle strings like "-0.4% OTM" or "+0.2% ITM"
        if any(x in cleaned.lower() for x in ['otm', 'itm', 'atm']):
            # Extract just the numeric part
            parts = cleaned.split()
            if parts:
                cleaned = parts[0].replace('%', '').replace('+', '')
        
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _normalize_expiry(expiry) -> str:
    """Normalize expiry date to YYYY-MM-DD format."""
    if not expiry:
        return ''
    
    if isinstance(expiry, str):
        # Try common formats (including new v3.3 format)
        formats = [
            '%Y-%m-%d',      # 2025-01-30
            '%d-%b-%Y',      # 30-Dec-2025 (NEW v3.3 format)
            '%d-%m-%Y',      # 30-01-2025
            '%d/%m/%Y',      # 30/01/2025
            '%d%b%Y',        # 30Jan2025
            '%d-%b-%y',      # 30-Jan-25
            '%Y%m%d',        # 20250130
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(expiry.strip(), fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # Return as-is if no format matched
        return expiry
    
    return str(expiry)


def _strategy_to_action(strategy: str) -> str:
    """
    Convert strategy name to action (BUY/SELL).
    
    Strategies:
    - Long Call / Long Put / Long Straddle / Long Strangle -> BUY
    - Short Call / Short Put / Short Straddle / Short Strangle -> SELL
    - Bull Call Spread / Bear Put Spread -> BUY (buying the spread)
    """
    if not strategy:
        return 'BUY'
    
    strategy_lower = str(strategy).lower().strip()
    
    # Check for explicit BUY/SELL
    if strategy_lower in ('buy', 'long'):
        return 'BUY'
    if strategy_lower in ('sell', 'short'):
        return 'SELL'
    
    # Check for compound strategies
    if 'long' in strategy_lower or 'buy' in strategy_lower or 'bull' in strategy_lower or 'bear' in strategy_lower:
        return 'BUY'
    if 'short' in strategy_lower or 'sell' in strategy_lower:
        return 'SELL'
    
    # Default to BUY for safety
    return 'BUY'


def _ensure_required_fields(alert: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all required fields are present with defaults."""
    defaults = {
        'symbol': 'UNKNOWN',
        'option_type': 'CE',
        'strike': 0,
        'price_limit': 0,
        'expiry': '',
        'action': 'BUY',
        'quantity': 0,
        'lot_size': 0,
        'stop_loss': None,
        'target': None,
        'validity': 'DAY',
        'strategy_type': 'single',
    }
    
    for key, default_value in defaults.items():
        if key not in alert or alert[key] is None:
            alert[key] = default_value
    
    return alert


def get_alert_display_info(alert: Dict[str, Any]) -> Dict[str, str]:
    """
    Get formatted display information for an alert.
    Handles single-leg, spread, and volatility strategies.
    
    Returns a dict with formatted strings for UI display.
    """
    strategy_type = alert.get('strategy_type', 'single')
    option_type = alert.get('option_type', 'CE')
    
    if strategy_type == 'spread':
        # Spread display
        if alert.get('display_text'):
            main_line = f"{alert.get('action', 'BUY')} {alert.get('symbol', 'Unknown')} {alert['display_text']}"
        else:
            main_line = (
                f"{alert.get('action', 'BUY')} {alert.get('symbol', 'Unknown')} "
                f"{alert.get('strike', 0)}/{alert.get('sell_strike', 0)}{option_type}"
            )
        details = (
            f"Premium: ₹{alert.get('price_limit', 0):.2f} | "
            f"Max Profit: ₹{alert.get('max_profit', 0):,.0f} | "
            f"Max Loss: ₹{alert.get('max_loss', 0):,.0f}"
        )
    elif strategy_type == 'volatility':
        # Straddle/Strangle display
        if alert.get('display_text'):
            main_line = f"{alert.get('action', 'BUY')} {alert.get('symbol', 'Unknown')} {alert['display_text']}"
        elif option_type == 'STRADDLE':
            main_line = (
                f"{alert.get('action', 'BUY')} {alert.get('symbol', 'Unknown')} "
                f"{alert.get('strike', 0)} STRADDLE"
            )
        else:  # STRANGLE
            main_line = (
                f"{alert.get('action', 'BUY')} {alert.get('symbol', 'Unknown')} "
                f"{alert.get('put_strike', 0)}/{alert.get('strike', 0)} STRANGLE"
            )
        details = (
            f"Premium: ₹{alert.get('price_limit', 0):.2f} | "
            f"Max Loss: ₹{alert.get('max_loss', 0):,.0f} | "
            f"Breakeven: {alert.get('breakeven', 'N/A')}"
        )
    else:
        # Single leg display
        main_line = (
            f"{alert.get('action', 'BUY')} {alert.get('symbol', 'Unknown')} "
            f"{alert.get('strike', 0)}{option_type} "
            f"@ ₹{alert.get('price_limit', 0):.2f}"
        )
        details = (
            f"Qty: {alert.get('quantity', 0)} | "
            f"Spot: ₹{alert.get('spot', 0):,.2f} | "
            f"IV: {alert.get('iv', 0):.1f}%"
        )
    
    return {
        'main_line': main_line,
        'details': details,
        'expiry_info': (
            f"Expiry: {alert.get('expiry', 'N/A')} "
            f"({alert.get('days_to_expiry', 0)} days)"
        ),
        'market_info': (
            f"OI: {alert.get('oi', 0):,.0f} | "
            f"Vol: {alert.get('volume', 0):,.0f} | "
            f"RSI: {alert.get('rsi', 0):.1f}"
        ),
    }


def is_multi_leg_strategy(alert: Dict[str, Any]) -> bool:
    """Check if an alert is for a multi-leg strategy."""
    strategy_type = alert.get('strategy_type', 'single')
    return strategy_type in ('spread', 'volatility')


def get_leg_count(alert: Dict[str, Any]) -> int:
    """Get the number of legs in the strategy."""
    strategy_type = alert.get('strategy_type', 'single')
    if strategy_type == 'single':
        return 1
    elif strategy_type in ('spread', 'volatility'):
        return 2
    return 1
