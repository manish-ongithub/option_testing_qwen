"""
Enhanced Options Probability of Profit Calculator
==================================================
Combines the best features from both implementations:
- Multi-strategy support (6 strategies)
- STT (Securities Transaction Tax) adjustment for Indian markets
- Configurable drift/market view parameter
- Precise timestamp-based time calculation
- Both Delta-based (Method 1) and Black-Scholes d2 (Method 2) approaches
- scipy fallback for environments without scipy

Supports: Long Call, Long Put, Bull Call Spread, Bear Put Spread, Long Straddle, Long Strangle

For Indian Stock Market (NSE/BSE)
"""

import json
import math
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any, Union
from enum import Enum
from datetime import datetime

# Try to import numpy/scipy, fall back to manual implementations if not available
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Note: scipy not installed. Using manual normal distribution approximation.")


# =============================================================================
# Constants and Enums
# =============================================================================

class Strategy(Enum):
    LONG_CALL = "Long Call"
    LONG_PUT = "Long Put"
    BULL_CALL_SPREAD = "Bull Call Spread"
    BEAR_PUT_SPREAD = "Bear Put Spread"
    LONG_STRADDLE = "Long Straddle"
    LONG_STRANGLE = "Long Strangle"


@dataclass
class IndianMarketConfig:
    """Configuration for Indian derivatives market"""
    risk_free_rate: float = 0.066       # India 10Y bond rate ~6.6%
    stt_rate: float = 0.00125           # STT on exercise: 0.125%
    market_close_hour: int = 15         # IST 15:30
    market_close_minute: int = 30
    trading_days_per_year: int = 252    # For annualization


@dataclass
class ProbabilityResult:
    """Result container for probability calculations"""
    pop_raw: float                      # Raw probability of profit
    pop_stt_adjusted: float             # STT-adjusted probability
    breakeven_raw: float
    breakeven_stt_adjusted: float
    probability_itm: Optional[float]
    probability_max_profit: Optional[float]
    delta: Optional[float]
    expected_value: Optional[float]
    tax_risk: float                     # Probability lost due to STT
    method: str
    details: Dict[str, Any]


# =============================================================================
# Mathematical Functions
# =============================================================================

def manual_norm_cdf(x: float) -> float:
    """
    Manual implementation of cumulative normal distribution.
    Uses Abramowitz and Stegun approximation (error < 7.5e-8)
    """
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911
    
    sign = 1 if x >= 0 else -1
    x = abs(x)
    
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x / 2)
    
    return 0.5 * (1.0 + sign * y)


def norm_cdf(x: float) -> float:
    """Cumulative normal distribution function"""
    if SCIPY_AVAILABLE:
        return float(norm.cdf(x))
    return manual_norm_cdf(x)


def norm_pdf(x: float) -> float:
    """Probability density function of standard normal distribution"""
    return (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x ** 2)


def calculate_d1_d2(spot: float, target_price: float, time_years: float, 
                    volatility: float, drift: float) -> Tuple[float, float]:
    """
    Calculate d1 and d2 for Black-Scholes formula
    
    Args:
        spot: Current spot price
        target_price: Strike or breakeven price
        time_years: Time to expiry in years
        volatility: Implied volatility as decimal
        drift: Expected return (risk-free rate or custom view)
    
    Returns:
        Tuple of (d1, d2)
    """
    if time_years <= 0:
        time_years = 1/365  # Minimum 1 day
    
    sqrt_t = math.sqrt(time_years)
    
    d1 = (math.log(spot / target_price) + (drift + 0.5 * volatility ** 2) * time_years) / (volatility * sqrt_t)
    d2 = d1 - volatility * sqrt_t
    
    return d1, d2


def calculate_delta(spot: float, strike: float, time_years: float,
                    volatility: float, drift: float, 
                    option_type: str = 'call') -> float:
    """Calculate option delta"""
    d1, _ = calculate_d1_d2(spot, strike, time_years, volatility, drift)
    
    if option_type.lower() == 'call':
        return norm_cdf(d1)
    else:
        return norm_cdf(d1) - 1


# =============================================================================
# Time Calculation
# =============================================================================

def calculate_time_to_expiry(expiry: Union[str, datetime], 
                              current_time: Union[str, datetime] = None,
                              config: IndianMarketConfig = None) -> float:
    """
    Calculate time to expiry in years with high precision.
    Accounts for IST market close time (15:30).
    
    Args:
        expiry: Expiry date as string (YYYY-MM-DD or ISO 8601) or datetime
        current_time: Current time (optional, defaults to now)
        config: Market configuration
    
    Returns:
        Time to expiry in years
    """
    if config is None:
        config = IndianMarketConfig()
    
    # Parse expiry
    if isinstance(expiry, str):
        # Handle various date formats
        try:
            if 'T' in expiry:
                exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            elif '-' in expiry:
                # Try different formats
                for fmt in ['%Y-%m-%d', '%d-%b-%Y', '%d-%B-%Y']:
                    try:
                        exp_dt = datetime.strptime(expiry, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    exp_dt = datetime.strptime(expiry, '%Y-%m-%d')
            else:
                exp_dt = datetime.strptime(expiry, '%d-%b-%Y')
        except Exception:
            # Fallback: assume it's days to expiry as integer
            if expiry.isdigit():
                return int(expiry) / 365.0
            raise ValueError(f"Cannot parse expiry date: {expiry}")
    else:
        exp_dt = expiry
    
    # Set expiry to market close time (15:30 IST)
    exp_dt = exp_dt.replace(hour=config.market_close_hour, 
                            minute=config.market_close_minute, 
                            second=0, microsecond=0)
    
    # Parse current time
    if current_time is None:
        now = datetime.now()
    elif isinstance(current_time, str):
        now = datetime.fromisoformat(current_time.replace("Z", "+00:00"))
    else:
        now = current_time
    
    # Calculate difference
    diff = exp_dt - now
    days = diff.total_seconds() / (24 * 3600)
    
    # Return years, minimum of ~1 minute to avoid division by zero
    return max(days / 365.0, 0.00002)


def days_to_years(days: int) -> float:
    """Simple conversion for integer days"""
    return max(days / 365.0, 1/365)


# =============================================================================
# STT Calculation
# =============================================================================

def calculate_stt_cost(spot: float, config: IndianMarketConfig = None) -> float:
    """Calculate STT cost on exercise"""
    if config is None:
        config = IndianMarketConfig()
    return spot * config.stt_rate


def adjust_breakeven_for_stt(breakeven: float, spot: float, 
                              option_type: str,
                              config: IndianMarketConfig = None) -> float:
    """
    Adjust breakeven for STT on exercise.
    
    For Calls: BEP_adj = BEP + STT_cost
    For Puts: BEP_adj = BEP - STT_cost
    """
    stt_cost = calculate_stt_cost(spot, config)
    
    if option_type.lower() in ['call', 'ce', 'bullish']:
        return breakeven + stt_cost
    else:  # put, pe, bearish
        return breakeven - stt_cost


# =============================================================================
# Enhanced Probability Calculators
# =============================================================================

class EnhancedProbabilityCalculator:
    """
    Enhanced probability calculator combining:
    - Multi-strategy support
    - STT adjustment
    - Configurable drift
    - Precise time calculation
    """
    
    def __init__(self, config: IndianMarketConfig = None):
        self.config = config or IndianMarketConfig()
    
    def calculate_pop_single_option(self, 
                                     spot: float,
                                     strike: float,
                                     premium: float,
                                     iv: float,
                                     time_to_expiry: float,
                                     option_type: str,
                                     drift: float = None,
                                     include_stt: bool = True) -> ProbabilityResult:
        """
        Calculate PoP for a single option (Long Call or Long Put).
        
        Args:
            spot: Current spot price
            strike: Strike price
            premium: Premium paid
            iv: Implied volatility (as percentage, e.g., 14.5 for 14.5%)
            time_to_expiry: Time in years (or use calculate_time_to_expiry)
            option_type: 'call'/'CE' or 'put'/'PE'
            drift: Expected return (None = use risk-free rate)
            include_stt: Whether to calculate STT-adjusted probability
        
        Returns:
            ProbabilityResult with raw and adjusted probabilities
        """
        # Normalize inputs
        volatility = iv / 100 if iv > 1 else iv
        mu = drift if drift is not None else self.config.risk_free_rate
        is_call = option_type.lower() in ['call', 'ce']
        
        # Calculate breakevens
        if is_call:
            breakeven_raw = strike + premium
            breakeven_stt = breakeven_raw + calculate_stt_cost(spot, self.config) if include_stt else breakeven_raw
        else:
            breakeven_raw = strike - premium
            breakeven_stt = breakeven_raw - calculate_stt_cost(spot, self.config) if include_stt else breakeven_raw
        
        # Calculate d1, d2 for various targets
        d1_strike, d2_strike = calculate_d1_d2(spot, strike, time_to_expiry, volatility, mu)
        d1_be_raw, d2_be_raw = calculate_d1_d2(spot, breakeven_raw, time_to_expiry, volatility, mu)
        d1_be_stt, d2_be_stt = calculate_d1_d2(spot, breakeven_stt, time_to_expiry, volatility, mu)
        
        # Calculate probabilities
        if is_call:
            prob_itm = norm_cdf(d2_strike) * 100
            pop_raw = norm_cdf(d2_be_raw) * 100
            pop_stt = norm_cdf(d2_be_stt) * 100
            delta = norm_cdf(d1_strike)
        else:
            prob_itm = norm_cdf(-d2_strike) * 100
            pop_raw = norm_cdf(-d2_be_raw) * 100
            pop_stt = norm_cdf(-d2_be_stt) * 100
            delta = norm_cdf(d1_strike) - 1
        
        # Tax risk
        tax_risk = pop_raw - pop_stt
        
        return ProbabilityResult(
            pop_raw=round(pop_raw, 2),
            pop_stt_adjusted=round(pop_stt, 2),
            breakeven_raw=round(breakeven_raw, 2),
            breakeven_stt_adjusted=round(breakeven_stt, 2),
            probability_itm=round(prob_itm, 2),
            probability_max_profit=None,  # Unlimited for single options
            delta=round(delta, 4),
            expected_value=None,  # Calculate separately if needed
            tax_risk=round(tax_risk, 2),
            method='Black-Scholes d2',
            details={
                'd2_strike': round(d2_strike, 4),
                'd2_breakeven_raw': round(d2_be_raw, 4),
                'd2_breakeven_stt': round(d2_be_stt, 4),
                'drift_used': mu,
                'time_years': round(time_to_expiry, 5),
                'volatility': volatility,
                'stt_cost': round(calculate_stt_cost(spot, self.config), 2)
            }
        )
    
    def calculate_pop_spread(self,
                              spot: float,
                              long_strike: float,
                              short_strike: float,
                              net_premium: float,
                              iv: float,
                              time_to_expiry: float,
                              spread_type: str,
                              max_profit: float = None,
                              max_loss: float = None,
                              drift: float = None,
                              include_stt: bool = True) -> ProbabilityResult:
        """
        Calculate PoP for spread strategies.
        
        Args:
            spot: Current spot price
            long_strike: Long leg strike
            short_strike: Short leg strike
            net_premium: Net premium paid
            iv: Implied volatility (as percentage)
            time_to_expiry: Time in years
            spread_type: 'bull_call' or 'bear_put'
            max_profit: Maximum profit (optional)
            max_loss: Maximum loss (optional)
            drift: Expected return (None = use risk-free rate)
            include_stt: Whether to calculate STT-adjusted probability
        
        Returns:
            ProbabilityResult
        """
        volatility = iv / 100 if iv > 1 else iv
        mu = drift if drift is not None else self.config.risk_free_rate
        is_bull = spread_type.lower() in ['bull_call', 'bull', 'bullish']
        
        # Calculate breakevens
        if is_bull:
            breakeven_raw = long_strike + net_premium
            # For spreads, STT impact is more complex (depends on which leg is exercised)
            stt_adjustment = calculate_stt_cost(spot, self.config) if include_stt else 0
            breakeven_stt = breakeven_raw + stt_adjustment
        else:  # bear put
            breakeven_raw = long_strike - net_premium
            stt_adjustment = calculate_stt_cost(spot, self.config) if include_stt else 0
            breakeven_stt = breakeven_raw - stt_adjustment
        
        # Calculate d2 values
        _, d2_be_raw = calculate_d1_d2(spot, breakeven_raw, time_to_expiry, volatility, mu)
        _, d2_be_stt = calculate_d1_d2(spot, breakeven_stt, time_to_expiry, volatility, mu)
        _, d2_short = calculate_d1_d2(spot, short_strike, time_to_expiry, volatility, mu)
        
        # Calculate probabilities
        if is_bull:
            pop_raw = norm_cdf(d2_be_raw) * 100
            pop_stt = norm_cdf(d2_be_stt) * 100
            prob_max_profit = norm_cdf(d2_short) * 100
        else:
            pop_raw = norm_cdf(-d2_be_raw) * 100
            pop_stt = norm_cdf(-d2_be_stt) * 100
            prob_max_profit = norm_cdf(-d2_short) * 100
        
        # Expected value calculation
        ev = None
        if max_profit is not None and max_loss is not None:
            ev = (max_profit * pop_raw / 100) - (max_loss * (1 - pop_raw / 100))
        
        tax_risk = pop_raw - pop_stt
        
        return ProbabilityResult(
            pop_raw=round(pop_raw, 2),
            pop_stt_adjusted=round(pop_stt, 2),
            breakeven_raw=round(breakeven_raw, 2),
            breakeven_stt_adjusted=round(breakeven_stt, 2),
            probability_itm=None,
            probability_max_profit=round(prob_max_profit, 2),
            delta=None,
            expected_value=round(ev, 2) if ev else None,
            tax_risk=round(tax_risk, 2),
            method='Black-Scholes d2',
            details={
                'd2_breakeven_raw': round(d2_be_raw, 4),
                'drift_used': mu,
                'time_years': round(time_to_expiry, 5),
                'volatility': volatility
            }
        )
    
    def calculate_pop_straddle_strangle(self,
                                         spot: float,
                                         call_strike: float,
                                         put_strike: float,
                                         total_premium: float,
                                         iv: float,
                                         time_to_expiry: float,
                                         drift: float = None,
                                         include_stt: bool = True) -> ProbabilityResult:
        """
        Calculate PoP for straddle or strangle.
        
        Args:
            spot: Current spot price
            call_strike: Call strike (same as put for straddle)
            put_strike: Put strike
            total_premium: Total premium paid for both legs
            iv: Implied volatility (as percentage)
            time_to_expiry: Time in years
            drift: Expected return
            include_stt: Whether to calculate STT-adjusted probability
        
        Returns:
            ProbabilityResult
        """
        volatility = iv / 100 if iv > 1 else iv
        mu = drift if drift is not None else self.config.risk_free_rate
        
        # Calculate breakevens
        upper_be_raw = call_strike + total_premium
        lower_be_raw = put_strike - total_premium
        
        stt_cost = calculate_stt_cost(spot, self.config) if include_stt else 0
        upper_be_stt = upper_be_raw + stt_cost
        lower_be_stt = lower_be_raw - stt_cost
        
        # Calculate d2 values
        _, d2_upper_raw = calculate_d1_d2(spot, upper_be_raw, time_to_expiry, volatility, mu)
        _, d2_lower_raw = calculate_d1_d2(spot, lower_be_raw, time_to_expiry, volatility, mu)
        _, d2_upper_stt = calculate_d1_d2(spot, upper_be_stt, time_to_expiry, volatility, mu)
        _, d2_lower_stt = calculate_d1_d2(spot, lower_be_stt, time_to_expiry, volatility, mu)
        
        # P(Profit) = P(S < Lower BE) + P(S > Upper BE)
        pop_raw = (norm_cdf(-d2_lower_raw) + norm_cdf(d2_upper_raw)) * 100
        pop_stt = (norm_cdf(-d2_lower_stt) + norm_cdf(d2_upper_stt)) * 100
        
        tax_risk = pop_raw - pop_stt
        
        return ProbabilityResult(
            pop_raw=round(pop_raw, 2),
            pop_stt_adjusted=round(pop_stt, 2),
            breakeven_raw=f"{round(lower_be_raw, 2)}/{round(upper_be_raw, 2)}",
            breakeven_stt_adjusted=f"{round(lower_be_stt, 2)}/{round(upper_be_stt, 2)}",
            probability_itm=None,
            probability_max_profit=None,
            delta=None,
            expected_value=None,
            tax_risk=round(tax_risk, 2),
            method='Black-Scholes d2',
            details={
                'd2_upper_raw': round(d2_upper_raw, 4),
                'd2_lower_raw': round(d2_lower_raw, 4),
                'prob_above_upper': round(norm_cdf(d2_upper_raw) * 100, 2),
                'prob_below_lower': round(norm_cdf(-d2_lower_raw) * 100, 2),
                'drift_used': mu,
                'time_years': round(time_to_expiry, 5),
                'volatility': volatility,
                'stt_cost': round(stt_cost, 2)
            }
        )


# =============================================================================
# JSON Alert Processor
# =============================================================================

def process_alert_enhanced(alert: Dict[str, Any], 
                           config: IndianMarketConfig = None,
                           drift: float = None,
                           include_stt: bool = True) -> Dict[str, Any]:
    """
    Process a single alert from JSON and calculate probabilities.
    
    Compatible with the original JSON format from the screener.
    """
    if config is None:
        config = IndianMarketConfig()
    
    calculator = EnhancedProbabilityCalculator(config)
    
    strategy = alert.get('strategy', '')
    spot = float(alert.get('spot', 0))
    iv = float(alert.get('iv', 0))
    
    # Get time to expiry
    if 'days_to_expiry' in alert:
        time_years = days_to_years(alert['days_to_expiry'])
    elif 'expiry' in alert:
        time_years = calculate_time_to_expiry(alert['expiry'], config=config)
    else:
        time_years = 1/365  # Default to 1 day
    
    result = {
        'symbol': alert.get('symbol'),
        'strategy': strategy,
        'strike': alert.get('strike'),
        'spot': spot,
        'iv': iv,
        'time_to_expiry_years': round(time_years, 5),
        'probability_analysis': None,
        'error': None
    }
    
    try:
        if strategy == Strategy.LONG_CALL.value:
            strike = float(alert.get('strike', 0))
            premium = float(alert.get('premium', 0))
            
            prob_result = calculator.calculate_pop_single_option(
                spot=spot, strike=strike, premium=premium,
                iv=iv, time_to_expiry=time_years,
                option_type='call', drift=drift, include_stt=include_stt
            )
            result['probability_analysis'] = prob_result.__dict__
            
        elif strategy == Strategy.LONG_PUT.value:
            strike = float(alert.get('strike', 0))
            premium = float(alert.get('premium', 0))
            
            prob_result = calculator.calculate_pop_single_option(
                spot=spot, strike=strike, premium=premium,
                iv=iv, time_to_expiry=time_years,
                option_type='put', drift=drift, include_stt=include_stt
            )
            result['probability_analysis'] = prob_result.__dict__
            
        elif strategy == Strategy.BULL_CALL_SPREAD.value:
            strikes = parse_strikes(alert.get('strike', ''))
            long_strike = strikes[0]
            short_strike = strikes[1] if strikes[1] else long_strike + 100
            net_premium = float(alert.get('premium', 0))
            max_profit = alert.get('max_profit')
            max_loss = alert.get('max_loss')
            
            prob_result = calculator.calculate_pop_spread(
                spot=spot, long_strike=long_strike, short_strike=short_strike,
                net_premium=net_premium, iv=iv, time_to_expiry=time_years,
                spread_type='bull_call', max_profit=max_profit, max_loss=max_loss,
                drift=drift, include_stt=include_stt
            )
            result['probability_analysis'] = prob_result.__dict__
            
        elif strategy == Strategy.BEAR_PUT_SPREAD.value:
            strikes = parse_strikes(alert.get('strike', ''))
            long_strike = strikes[0]
            short_strike = strikes[1] if strikes[1] else long_strike - 100
            net_premium = float(alert.get('premium', 0))
            max_profit = alert.get('max_profit')
            max_loss = alert.get('max_loss')
            
            prob_result = calculator.calculate_pop_spread(
                spot=spot, long_strike=long_strike, short_strike=short_strike,
                net_premium=net_premium, iv=iv, time_to_expiry=time_years,
                spread_type='bear_put', max_profit=max_profit, max_loss=max_loss,
                drift=drift, include_stt=include_stt
            )
            result['probability_analysis'] = prob_result.__dict__
            
        elif strategy in [Strategy.LONG_STRADDLE.value, Strategy.LONG_STRANGLE.value]:
            strike_info = alert.get('strike', '')
            
            if strategy == Strategy.LONG_STRADDLE.value:
                call_strike = put_strike = float(strike_info)
            else:
                strikes = parse_strikes(strike_info)
                # For strangle: first is put strike, second is call strike (or vice versa)
                put_strike = min(strikes[0], strikes[1]) if strikes[1] else strikes[0] - 10
                call_strike = max(strikes[0], strikes[1]) if strikes[1] else strikes[0] + 10
            
            total_premium = float(alert.get('premium', 0))
            
            prob_result = calculator.calculate_pop_straddle_strangle(
                spot=spot, call_strike=call_strike, put_strike=put_strike,
                total_premium=total_premium, iv=iv, time_to_expiry=time_years,
                drift=drift, include_stt=include_stt
            )
            result['probability_analysis'] = prob_result.__dict__
        else:
            result['error'] = f'Unknown strategy: {strategy}'
            
    except Exception as e:
        result['error'] = str(e)
    
    return result


def parse_strikes(strike_str) -> Tuple[float, Optional[float]]:
    """Parse strike string which could be single value or spread like '25700/25600'"""
    if isinstance(strike_str, (int, float)):
        return float(strike_str), None
    
    if isinstance(strike_str, str):
        if '/' in strike_str:
            parts = strike_str.split('/')
            return float(parts[0]), float(parts[1])
        else:
            return float(strike_str), None
    
    return 0, None


def process_alerts_file_enhanced(input_file: str, 
                                  output_file: str = None,
                                  drift: float = None,
                                  include_stt: bool = True):
    """
    Process alerts from JSON file with enhanced probability calculations.
    """
    config = IndianMarketConfig()
    
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    alerts = data.get('top_alerts', [])
    processed_results = []
    
    print("\n" + "=" * 110)
    print("ENHANCED OPTIONS PROBABILITY CALCULATOR (with STT Adjustment)")
    print("=" * 110)
    print(f"\nProcessing {len(alerts)} alerts from {input_file}")
    print(f"Risk-free rate: {config.risk_free_rate * 100:.2f}%")
    print(f"STT Rate: {config.stt_rate * 100:.3f}%")
    print(f"Drift override: {drift if drift is not None else 'None (using risk-free rate)'}")
    print("-" * 110)
    
    for i, alert in enumerate(alerts):
        result = process_alert_enhanced(alert, config, drift, include_stt)
        processed_results.append(result)
        
        # Print results
        print(f"\n[{i+1}] {result['symbol']} - {result['strategy']}")
        print(f"    Strike: {result['strike']} | Spot: {result['spot']} | IV: {result['iv']}%")
        
        if result.get('probability_analysis'):
            pa = result['probability_analysis']
            print(f"\n    PROBABILITY OF PROFIT:")
            print(f"      Raw PoP:          {pa['pop_raw']}%")
            print(f"      STT-Adjusted PoP: {pa['pop_stt_adjusted']}%")
            print(f"      Tax Risk:         {pa['tax_risk']}% (probability lost to STT)")
            print(f"\n    BREAKEVENS:")
            print(f"      Raw:         {pa['breakeven_raw']}")
            print(f"      STT-Adjusted: {pa['breakeven_stt_adjusted']}")
            
            if pa.get('probability_itm') is not None:
                print(f"\n    Probability ITM: {pa['probability_itm']}%")
            if pa.get('probability_max_profit') is not None:
                print(f"    Probability Max Profit: {pa['probability_max_profit']}%")
            if pa.get('delta') is not None:
                print(f"    Delta: {pa['delta']}")
            if pa.get('expected_value') is not None:
                print(f"    Expected Value: ₹{pa['expected_value']}")
        
        if result.get('error'):
            print(f"    ERROR: {result['error']}")
        
        print("-" * 110)
    
    # Save output
    output_data = data.copy()
    for i, alert in enumerate(output_data.get('top_alerts', [])):
        if i < len(processed_results):
            alert['enhanced_probability'] = processed_results[i].get('probability_analysis')
    
    if output_file is None:
        output_file = input_file.replace('.json', '_enhanced_probabilities.json')
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    # Summary table
    print("\n" + "=" * 110)
    print("SUMMARY TABLE (with Tax Risk)")
    print("=" * 110)
    print(f"{'Symbol':<12} {'Strategy':<20} {'Strike':<15} {'Raw PoP':<10} {'Adj PoP':<10} {'Tax Risk':<10} {'STT Cost':<10}")
    print("-" * 110)
    
    for result in processed_results:
        if result.get('probability_analysis'):
            pa = result['probability_analysis']
            stt_cost = pa.get('details', {}).get('stt_cost', 0)
            print(f"{result['symbol']:<12} {result['strategy']:<20} {str(result['strike']):<15} "
                  f"{pa['pop_raw']:>7.1f}%  {pa['pop_stt_adjusted']:>7.1f}%  {pa['tax_risk']:>7.1f}%  ₹{stt_cost:>7.2f}")
    
    print("=" * 110)
    
    return processed_results


# =============================================================================
# Quick Functions for Direct Use
# =============================================================================

def quick_pop(spot: float, breakeven: float, iv: float, days_to_expiry: int,
              direction: str = 'bullish', drift: float = 0.066,
              include_stt: bool = True, stt_rate: float = 0.00125) -> Dict[str, float]:
    """
    Quick probability of profit calculation with STT adjustment.
    
    Args:
        spot: Current spot price
        breakeven: Breakeven price
        iv: IV as percentage (e.g., 14.5)
        days_to_expiry: Days to expiry
        direction: 'bullish' or 'bearish'
        drift: Expected return (default 6.6%)
        include_stt: Include STT adjustment
        stt_rate: STT rate (default 0.125%)
    
    Returns:
        Dict with raw and adjusted PoP
    """
    time_years = days_to_expiry / 365
    volatility = iv / 100 if iv > 1 else iv
    
    stt_cost = spot * stt_rate if include_stt else 0
    
    if direction.lower() == 'bullish':
        be_adj = breakeven + stt_cost
        _, d2_raw = calculate_d1_d2(spot, breakeven, time_years, volatility, drift)
        _, d2_adj = calculate_d1_d2(spot, be_adj, time_years, volatility, drift)
        pop_raw = norm_cdf(d2_raw) * 100
        pop_adj = norm_cdf(d2_adj) * 100
    else:
        be_adj = breakeven - stt_cost
        _, d2_raw = calculate_d1_d2(spot, breakeven, time_years, volatility, drift)
        _, d2_adj = calculate_d1_d2(spot, be_adj, time_years, volatility, drift)
        pop_raw = norm_cdf(-d2_raw) * 100
        pop_adj = norm_cdf(-d2_adj) * 100
    
    return {
        'pop_raw': round(pop_raw, 2),
        'pop_stt_adjusted': round(pop_adj, 2),
        'tax_risk': round(pop_raw - pop_adj, 2),
        'breakeven_raw': breakeven,
        'breakeven_adjusted': round(be_adj, 2)
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Demo with sample data
    print("\n" + "=" * 80)
    print("DEMO: Enhanced Options Probability Calculator")
    print("=" * 80)
    
    # Example 1: Single option with STT
    print("\n--- Example 1: Long Call with STT Adjustment ---")
    result = quick_pop(
        spot=24480,
        breakeven=24650.50,
        iv=14.5,
        days_to_expiry=6,
        direction='bullish',
        drift=0.0  # Zero drift view
    )
    print(f"Spot: 24480, Breakeven: 24650.50, IV: 14.5%, DTE: 6")
    print(f"Raw PoP: {result['pop_raw']}%")
    print(f"STT-Adjusted PoP: {result['pop_stt_adjusted']}%")
    print(f"Tax Risk: {result['tax_risk']}%")
    
    # Example 2: Process file if provided
    input_file = "new_screener_alerts_v3_3.json"
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    
    try:
        with open(input_file, 'r') as f:
            pass
        print(f"\n--- Processing {input_file} ---")
        process_alerts_file_enhanced(input_file, drift=None, include_stt=True)
    except FileNotFoundError:
        print(f"\nNote: {input_file} not found. Run with a JSON file path as argument.")
        print("Usage: python options_probability_calculator_enhanced.py [alerts.json]")
