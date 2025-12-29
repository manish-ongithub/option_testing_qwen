"""
Helper functions for spread strategy calculations.
"""


def find_spread_strikes(spot, strikes, atm_strike, direction, width=1):
    """
    Find appropriate strikes for spread strategies.
    
    Args:
        spot: Current spot price
        strikes: List of available strikes (sorted)
        atm_strike: ATM strike price
        direction: 'bull' or 'bear'
        width: Number of strikes away for the short leg
    
    Returns:
        tuple: (buy_strike, sell_strike) or (None, None) if not found
    """
    try:
        atm_idx = strikes.index(atm_strike)
        
        if direction == 'bull':
            # Bull Call Spread: Buy lower strike, Sell higher strike
            buy_strike = atm_strike
            sell_idx = atm_idx + width
            if sell_idx < len(strikes):
                sell_strike = strikes[sell_idx]
                return (buy_strike, sell_strike)
        
        elif direction == 'bear':
            # Bear Put Spread: Buy higher strike, Sell lower strike
            buy_strike = atm_strike
            sell_idx = atm_idx - width
            if sell_idx >= 0:
                sell_strike = strikes[sell_idx]
                return (buy_strike, sell_strike)
    except (ValueError, IndexError):
        pass
    
    return (None, None)


def find_strangle_strikes(spot, strikes, atm_strike, width=1):
    """
    Find OTM call and put strikes for strangle.
    
    Args:
        spot: Current spot price
        strikes: List of available strikes (sorted)
        atm_strike: ATM strike price
        width: Number of strikes away from ATM
    
    Returns:
        tuple: (call_strike, put_strike) or (None, None) if not found
    """
    try:
        atm_idx = strikes.index(atm_strike)
        
        call_idx = atm_idx + width  # OTM call (higher strike)
        put_idx = atm_idx - width   # OTM put (lower strike)
        
        if call_idx < len(strikes) and put_idx >= 0:
            return (strikes[call_idx], strikes[put_idx])
    except (ValueError, IndexError):
        pass
    
    return (None, None)


def calculate_spread_metrics(buy_price, sell_price, strike_diff, opt_type, buy_strike):
    """
    Calculate spread strategy metrics.
    
    Args:
        buy_price: Premium paid for long leg
        sell_price: Premium received for short leg
        strike_diff: Absolute difference between strikes
        opt_type: 'CE' for call spread, 'PE' for put spread
        buy_strike: Strike of the long leg
    
    Returns:
        dict with net_debit, max_profit, max_loss, breakeven, reward_ratio
    """
    net_debit = buy_price - sell_price
    max_loss = net_debit
    max_profit = strike_diff - net_debit
    
    if max_loss > 0:
        reward_ratio = max_profit / max_loss
    else:
        reward_ratio = 0
    
    # Breakeven calculation
    if opt_type == 'CE':
        # Bull Call Spread: breakeven = buy_strike + net_debit
        breakeven = buy_strike + net_debit
    else:
        # Bear Put Spread: breakeven = buy_strike - net_debit
        breakeven = buy_strike - net_debit
    
    return {
        'net_debit': net_debit,
        'max_profit': max_profit,
        'max_loss': max_loss,
        'breakeven': breakeven,
        'reward_ratio': reward_ratio
    }


def calculate_straddle_metrics(call_price, put_price, strike, spot):
    """
    Calculate straddle metrics.
    
    Args:
        call_price: Premium for call
        put_price: Premium for put  
        strike: Strike price (same for both legs in straddle)
        spot: Current spot price
    
    Returns:
        dict with total_cost, upper_breakeven, lower_breakeven, move_required_pct
    """
    total_cost = call_price + put_price
    
    upper_breakeven = strike + total_cost
    lower_breakeven = strike - total_cost
    
    # Percentage move required to breakeven
    move_required = (total_cost / spot) * 100
    
    return {
        'total_cost': total_cost,
        'upper_breakeven': upper_breakeven,
        'lower_breakeven': lower_breakeven,
        'move_required_pct': move_required
    }


def calculate_strangle_metrics(call_price, put_price, call_strike, put_strike, spot):
    """
    Calculate strangle metrics (different strikes).
    
    Args:
        call_price: Premium for OTM call
        put_price: Premium for OTM put
        call_strike: Strike of the call (higher)
        put_strike: Strike of the put (lower)
        spot: Current spot price
    
    Returns:
        dict with total_cost, upper_breakeven, lower_breakeven, move_required_pct
    """
    total_cost = call_price + put_price
    
    upper_breakeven = call_strike + total_cost
    lower_breakeven = put_strike - total_cost
    
    # Percentage move required (use the closer breakeven)
    up_move = ((upper_breakeven - spot) / spot) * 100
    down_move = ((spot - lower_breakeven) / spot) * 100
    move_required = min(up_move, down_move)
    
    return {
        'total_cost': total_cost,
        'upper_breakeven': upper_breakeven,
        'lower_breakeven': lower_breakeven,
        'move_required_pct': move_required
    }


def is_spread_liquid(leg1_oi, leg2_oi, threshold):
    """Check if both legs of a spread have sufficient liquidity."""
    return leg1_oi >= threshold and leg2_oi >= threshold

