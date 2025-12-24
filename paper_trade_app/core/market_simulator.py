"""
Market Tick Simulator - Price Engine

Generates realistic price movements using:
- Geometric Brownian Motion (GBM) base model
- Volatility clustering (GARCH-like behavior)
- Mean reversion
- Jump diffusion (occasional large moves)
- Bid-ask spread simulation

For testing the paper trading application outside market hours.
"""

import random
import math
import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger("MarketSimulator")


@dataclass
class SimulatorConfig:
    """Configuration for the market simulator."""
    
    # Timing
    tick_interval_ms: int = 500  # Tick every 500ms
    
    # Base volatility (daily, annualized would be ~sqrt(252) * this)
    base_volatility: float = 0.015  # 1.5% daily volatility
    
    # Volatility clustering (GARCH alpha parameter)
    # Higher = more clustering, range 0-1
    volatility_clustering: float = 0.7
    
    # Mean reversion
    mean_reversion_speed: float = 0.05  # Speed of reversion to mean
    mean_reversion_window: int = 50  # Number of ticks for moving average
    
    # Jump parameters (Poisson jump diffusion)
    jump_probability: float = 0.001  # 0.1% chance per tick
    jump_magnitude: float = 0.02  # 2% jump size
    
    # Trend (drift)
    trend: float = 0.0  # 0 = sideways, positive = up, negative = down
    
    # Bid-ask spread
    base_spread_percent: float = 0.05  # 0.05% base spread
    spread_volatility_factor: float = 2.0  # Spread widens with volatility
    
    # Volume simulation
    base_volume: int = 1000
    volume_volatility: float = 0.5


# Pre-defined scenarios for testing
SIMULATION_SCENARIOS = {
    "sideways": SimulatorConfig(
        trend=0.0,
        base_volatility=0.01,
        jump_probability=0.0005
    ),
    "trending_up": SimulatorConfig(
        trend=0.002,  # Strong upward bias
        base_volatility=0.01,
        mean_reversion_speed=0.02
    ),
    "trending_down": SimulatorConfig(
        trend=-0.002,  # Strong downward bias
        base_volatility=0.01,
        mean_reversion_speed=0.02
    ),
    "high_volatility": SimulatorConfig(
        trend=0.0,
        base_volatility=0.03,  # 3% daily volatility
        volatility_clustering=0.8,
        jump_probability=0.002
    ),
    "sl_test": SimulatorConfig(
        trend=-0.003,  # Price drops to hit stop-loss
        base_volatility=0.015,
        mean_reversion_speed=0.01
    ),
    "target_test": SimulatorConfig(
        trend=0.003,  # Price rises to hit target
        base_volatility=0.015,
        mean_reversion_speed=0.01
    ),
    "flash_crash": SimulatorConfig(
        trend=-0.001,
        base_volatility=0.02,
        jump_probability=0.01,  # High jump probability
        jump_magnitude=0.05  # 5% jumps
    ),
    "recovery_rally": SimulatorConfig(
        trend=0.004,
        base_volatility=0.02,
        jump_probability=0.005,
        jump_magnitude=0.03
    ),
}


class PriceEngine:
    """
    Generates realistic price movements using GBM with enhancements.
    
    The model combines:
    1. Geometric Brownian Motion for base movement
    2. GARCH-like volatility clustering
    3. Ornstein-Uhlenbeck mean reversion
    4. Merton jump diffusion for sudden moves
    """
    
    def __init__(
        self,
        initial_price: float,
        config: SimulatorConfig = None
    ):
        self.config = config or SimulatorConfig()
        
        # Current state
        self.price = initial_price
        self.initial_price = initial_price
        self.open_price = initial_price
        
        # Volatility state (for clustering)
        self.current_volatility = self.config.base_volatility
        self.last_shock = 0.0
        
        # Price history for mean reversion
        self.price_history: list = [initial_price]
        self.max_history = self.config.mean_reversion_window
        
        # Volume state
        self.current_volume = self.config.base_volume
        
        # Tick counter
        self.tick_count = 0
        
        # Scale factor: convert daily volatility to per-tick
        # Assuming ~7200 ticks per day (6 hours * 60 min * 2 ticks/min at 500ms)
        self.ticks_per_day = 7200
        self.tick_volatility_scale = 1.0 / math.sqrt(self.ticks_per_day)
    
    def next_tick(self) -> Tuple[float, float, float, int]:
        """
        Generate the next price tick.
        
        Returns:
            Tuple of (ltp, bid_price, ask_price, volume)
        """
        self.tick_count += 1
        
        # 1. Update volatility (clustering effect)
        self._update_volatility()
        
        # 2. Calculate price change components
        drift = self._calculate_drift()
        diffusion = self._calculate_diffusion()
        jump = self._calculate_jump()
        mean_reversion = self._calculate_mean_reversion()
        
        # 3. Combine components
        total_return = drift + diffusion + jump + mean_reversion
        
        # 4. Update price (multiplicative model)
        self.price = self.price * (1 + total_return)
        
        # Ensure price stays positive
        self.price = max(self.price, 0.05)
        
        # 5. Update history
        self.price_history.append(self.price)
        if len(self.price_history) > self.max_history:
            self.price_history.pop(0)
        
        # 6. Calculate bid-ask spread
        bid, ask = self._calculate_spread()
        
        # 7. Simulate volume
        volume = self._simulate_volume()
        
        return round(self.price, 2), round(bid, 2), round(ask, 2), volume
    
    def _update_volatility(self):
        """
        Update volatility with GARCH-like clustering.
        High volatility tends to persist, then mean-revert.
        """
        alpha = self.config.volatility_clustering
        base_vol = self.config.base_volatility
        
        # GARCH(1,1) inspired update
        # current_vol = alpha * |last_shock| + (1-alpha) * base_vol
        shock_contribution = alpha * abs(self.last_shock)
        base_contribution = (1 - alpha) * base_vol
        
        self.current_volatility = shock_contribution + base_contribution
        
        # Clamp volatility to reasonable range
        self.current_volatility = max(
            base_vol * 0.5,
            min(self.current_volatility, base_vol * 3.0)
        )
    
    def _calculate_drift(self) -> float:
        """Calculate the trend/drift component."""
        # Scale daily trend to per-tick
        return self.config.trend * self.tick_volatility_scale
    
    def _calculate_diffusion(self) -> float:
        """Calculate the random diffusion component (GBM)."""
        # Standard normal shock
        shock = random.gauss(0, 1)
        self.last_shock = shock
        
        # Scale volatility to per-tick
        tick_vol = self.current_volatility * self.tick_volatility_scale
        
        return tick_vol * shock
    
    def _calculate_jump(self) -> float:
        """Calculate jump component (Poisson process)."""
        if random.random() < self.config.jump_probability:
            # Jump occurred
            direction = random.choice([-1, 1])
            magnitude = self.config.jump_magnitude * random.uniform(0.5, 1.5)
            
            logger.debug(f"Price jump: {direction * magnitude:.2%}")
            return direction * magnitude
        
        return 0.0
    
    def _calculate_mean_reversion(self) -> float:
        """Calculate mean reversion component (Ornstein-Uhlenbeck)."""
        if len(self.price_history) < 2:
            return 0.0
        
        # Calculate moving average
        mean_price = sum(self.price_history) / len(self.price_history)
        
        # Reversion force: pull price towards mean
        deviation = (self.price - mean_price) / mean_price
        reversion = -self.config.mean_reversion_speed * deviation * self.tick_volatility_scale
        
        return reversion
    
    def _calculate_spread(self) -> Tuple[float, float]:
        """Calculate bid and ask prices based on volatility."""
        # Spread widens with volatility
        vol_ratio = self.current_volatility / self.config.base_volatility
        spread_percent = self.config.base_spread_percent * (
            1 + (vol_ratio - 1) * self.config.spread_volatility_factor
        )
        
        half_spread = self.price * (spread_percent / 100) / 2
        
        bid = self.price - half_spread
        ask = self.price + half_spread
        
        return bid, ask
    
    def _simulate_volume(self) -> int:
        """Simulate trading volume."""
        # Volume varies with volatility
        vol_factor = self.current_volatility / self.config.base_volatility
        
        # Random variation
        variation = random.gauss(1.0, self.config.volume_volatility)
        variation = max(0.1, variation)  # Ensure positive
        
        volume = int(self.config.base_volume * vol_factor * variation)
        return max(1, volume)
    
    def get_percent_change(self) -> float:
        """Get percent change from open price."""
        if self.open_price == 0:
            return 0.0
        return ((self.price - self.open_price) / self.open_price) * 100
    
    def reset_day(self):
        """Reset for a new trading day."""
        self.open_price = self.price
        self.price_history = [self.price]
        self.tick_count = 0
    
    def set_scenario(self, scenario_name: str):
        """Apply a pre-defined scenario."""
        if scenario_name in SIMULATION_SCENARIOS:
            self.config = SIMULATION_SCENARIOS[scenario_name]
            logger.info(f"Applied scenario: {scenario_name}")
        else:
            logger.warning(f"Unknown scenario: {scenario_name}")


class InstrumentSimulator:
    """
    Manages price simulation for a single instrument.
    Wraps PriceEngine and provides tick data in exchange format.
    """
    
    def __init__(
        self,
        token: int,
        symbol: str,
        initial_price: float,
        config: SimulatorConfig = None
    ):
        self.token = token
        self.symbol = symbol
        self.engine = PriceEngine(initial_price, config)
        self.is_active = True
    
    def get_tick(self) -> dict:
        """
        Generate a tick in the same format as Alice Blue WebSocket.
        
        Returns:
            dict with tick data matching Alice Blue format
        """
        if not self.is_active:
            return None
        
        ltp, bid, ask, volume = self.engine.next_tick()
        pc = self.engine.get_percent_change()
        
        tick = {
            'tk': str(self.token),  # Token as string (Alice Blue format)
            'token': self.token,    # Token as int (our format)
            'lp': str(ltp),         # LTP as string (Alice Blue format)
            'ltp': ltp,             # LTP as float (our format)
            'pc': round(pc, 2),     # Percent change
            'v': str(volume),       # Volume as string
            'volume': volume,       # Volume as int
            'bp': str(bid),         # Best bid
            'sp': str(ask),         # Best ask (sell price)
            'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        return tick
    
    def set_scenario(self, scenario_name: str):
        """Apply a scenario to this instrument."""
        self.engine.set_scenario(scenario_name)
    
    def pause(self):
        """Pause tick generation."""
        self.is_active = False
    
    def resume(self):
        """Resume tick generation."""
        self.is_active = True


class MarketSimulator:
    """
    Manages simulation for multiple instruments.
    Central controller for the simulation engine.
    """
    
    def __init__(self, default_config: SimulatorConfig = None):
        self.default_config = default_config or SimulatorConfig()
        self.instruments: Dict[int, InstrumentSimulator] = {}
        self.is_running = False
    
    def add_instrument(
        self,
        token: int,
        symbol: str,
        initial_price: float,
        config: SimulatorConfig = None
    ) -> InstrumentSimulator:
        """Add an instrument to simulate."""
        config = config or self.default_config
        simulator = InstrumentSimulator(token, symbol, initial_price, config)
        self.instruments[token] = simulator
        logger.info(f"Added instrument: {symbol} (token={token}) @ {initial_price}")
        return simulator
    
    def remove_instrument(self, token: int):
        """Remove an instrument from simulation."""
        if token in self.instruments:
            del self.instruments[token]
            logger.info(f"Removed instrument: token={token}")
    
    def get_tick(self, token: int) -> Optional[dict]:
        """Get tick for a specific instrument."""
        if token in self.instruments:
            return self.instruments[token].get_tick()
        return None
    
    def get_all_ticks(self) -> Dict[int, dict]:
        """Get ticks for all instruments."""
        ticks = {}
        for token, simulator in self.instruments.items():
            tick = simulator.get_tick()
            if tick:
                ticks[token] = tick
        return ticks
    
    def set_scenario(self, scenario_name: str, token: int = None):
        """
        Apply a scenario to one or all instruments.
        
        Args:
            scenario_name: Name of the scenario
            token: Specific token, or None for all
        """
        if token is not None:
            if token in self.instruments:
                self.instruments[token].set_scenario(scenario_name)
        else:
            for simulator in self.instruments.values():
                simulator.set_scenario(scenario_name)
    
    def get_available_scenarios(self) -> list:
        """Get list of available scenario names."""
        return list(SIMULATION_SCENARIOS.keys())
    
    def reset_all(self):
        """Reset all instruments for a new day."""
        for simulator in self.instruments.values():
            simulator.engine.reset_day()
