"""
Simulator Worker - Drop-in replacement for AliceBlueWorker

Provides the same interface as AliceBlueWorker but generates
simulated market ticks instead of connecting to real exchange.

Use for testing outside market hours.
"""

import logging
import datetime
from typing import List, Dict, Optional
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QMutex, QMutexLocker

from core.market_simulator import (
    MarketSimulator, 
    InstrumentSimulator, 
    SimulatorConfig,
    SIMULATION_SCENARIOS
)

# Import config with defaults
try:
    from config import SIMULATOR_CONFIG
except ImportError:
    SIMULATOR_CONFIG = {}

logger = logging.getLogger("SimulatorWorker")

# Default prices for example alert instruments (matching premiums from example_screener_alert.json)
# These are used in _get_initial_price() for instruments matching the example alerts
EXAMPLE_ALERT_PRICES = {
    100001: 150.50,  # NIFTY 24000 CE premium
    100002: 250.75,  # BANKNIFTY 51000 PE premium
}


class SimulatorWorker(QThread):
    """
    QThread worker that emits simulated market ticks.
    
    Same interface as AliceBlueWorker for drop-in replacement.
    
    Signals:
        connection_signal: (bool, str) - Connection status
        tick_signal: (dict) - Price tick data
        error_signal: (str) - Error messages
    """
    
    # Same signals as AliceBlueWorker
    connection_signal = pyqtSignal(bool, str)
    tick_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, config: dict = None):
        super().__init__()
        
        # Merge provided config with defaults
        self.config = {**SIMULATOR_CONFIG, **(config or {})}
        
        # Create simulator config
        sim_config = SimulatorConfig(
            tick_interval_ms=self.config.get('tick_interval_ms', 500),
            base_volatility=self.config.get('base_volatility', 0.015),
            volatility_clustering=self.config.get('volatility_clustering', 0.7),
            mean_reversion_speed=self.config.get('mean_reversion_speed', 0.05),
            jump_probability=self.config.get('jump_probability', 0.001),
            jump_magnitude=self.config.get('jump_magnitude', 0.02),
            trend=self.config.get('trend', 0.0),
        )
        
        # Initialize simulator
        self.simulator = MarketSimulator(sim_config)
        
        # State
        self.is_connected = False
        self._stop_requested = False
        self._mutex = QMutex()
        
        # Pending subscriptions (instruments waiting to be added)
        self._pending_subscriptions: List[object] = []
        
        # Token to initial price mapping (for instruments without price)
        self._default_prices: Dict[int, float] = {}
        
        logger.info("SimulatorWorker initialized")
    
    def run(self):
        """
        Main thread loop - generates ticks at configured interval.
        """
        logger.info("SimulatorWorker starting...")
        
        # Simulate connection delay
        self.msleep(500)
        
        # Emit connected signal
        self.is_connected = True
        self.connection_signal.emit(True, "Simulator Connected")
        logger.info("Simulator connected")
        
        # Process any pending subscriptions
        self._process_pending_subscriptions()
        
        # Tick interval
        tick_interval = self.config.get('tick_interval_ms', 500)
        
        # Main tick loop
        while not self._stop_requested:
            try:
                # Generate ticks for all subscribed instruments
                self._emit_ticks()
                
                # Wait for next tick interval
                self.msleep(tick_interval)
                
            except Exception as e:
                logger.error(f"Error in tick loop: {e}")
                self.error_signal.emit(str(e))
        
        # Cleanup
        self.is_connected = False
        self.connection_signal.emit(False, "Simulator Disconnected")
        logger.info("SimulatorWorker stopped")
    
    def _emit_ticks(self):
        """Generate and emit ticks for all instruments."""
        with QMutexLocker(self._mutex):
            ticks = self.simulator.get_all_ticks()
        
        for token, tick in ticks.items():
            if tick:
                self.tick_signal.emit(tick)
    
    def _process_pending_subscriptions(self):
        """Process any instruments that were subscribed before connection."""
        with QMutexLocker(self._mutex):
            for instrument in self._pending_subscriptions:
                self._add_instrument(instrument)
            self._pending_subscriptions.clear()
    
    def _add_instrument(self, instrument):
        """Add an instrument to the simulator."""
        try:
            token = int(instrument.token)
            symbol = instrument.name
            
            # Get initial price (from lot_size field which sometimes has price info,
            # or use a default based on token)
            initial_price = self._get_initial_price(token, symbol)
            
            self.simulator.add_instrument(token, symbol, initial_price)
            logger.info(f"Subscribed: {symbol} (token={token}) @ ₹{initial_price}")
            
        except Exception as e:
            logger.error(f"Failed to add instrument: {e}")
    
    def _get_initial_price(self, token: int, symbol: str) -> float:
        """
        Determine initial price for an instrument.
        
        Priority:
        1. Stored default prices (from set_initial_price)
        2. Example alert prices (from EXAMPLE_ALERT_PRICES)
        3. Heuristics based on symbol name
        """
        # Check if we have a stored default
        if token in self._default_prices:
            return self._default_prices[token]
        
        # Check example alert prices
        if token in EXAMPLE_ALERT_PRICES:
            return EXAMPLE_ALERT_PRICES[token]
        
        # Heuristic based on symbol
        symbol_upper = symbol.upper()
        
        if 'BANKNIFTY' in symbol_upper:
            # BANKNIFTY options typically trade in 100-500 range
            import random
            price = random.uniform(100, 400)
        elif 'NIFTY' in symbol_upper:
            # NIFTY options typically trade in 50-300 range
            import random
            price = random.uniform(80, 300)
        elif 'FINNIFTY' in symbol_upper or 'MIDCPNIFTY' in symbol_upper:
            import random
            price = random.uniform(50, 200)
        else:
            # Stock options
            import random
            price = random.uniform(20, 150)
        
        return round(price, 2)
    
    def subscribe_tokens(self, instruments: list):
        """
        Subscribe to instruments for tick simulation.
        
        Same interface as AliceBlueWorker.subscribe().
        
        Args:
            instruments: List of Instrument namedtuples
        """
        with QMutexLocker(self._mutex):
            if self.is_connected:
                for instrument in instruments:
                    self._add_instrument(instrument)
            else:
                # Queue for later
                self._pending_subscriptions.extend(instruments)
                logger.info(f"Queued {len(instruments)} instruments for subscription")
        
        # Log subscriptions
        for inst in instruments:
            logger.info(f"📡 Subscribed to {inst.token} ({inst.name})")
    
    def unsubscribe_tokens(self, instruments: list):
        """
        Unsubscribe from instruments.
        
        Same interface as AliceBlueWorker.unsubscribe().
        
        Args:
            instruments: List of Instrument namedtuples
        """
        with QMutexLocker(self._mutex):
            for instrument in instruments:
                token = int(instrument.token)
                self.simulator.remove_instrument(token)
                logger.info(f"📴 Unsubscribed from {token}")
    
    def set_initial_price(self, token: int, price: float):
        """
        Set the initial price for an instrument before subscribing.
        
        Useful for testing specific price scenarios.
        
        Args:
            token: Instrument token
            price: Initial price
        """
        self._default_prices[token] = price
    
    def set_scenario(self, scenario_name: str, token: int = None):
        """
        Apply a pre-defined price scenario.
        
        Args:
            scenario_name: One of 'trending_up', 'trending_down', 
                          'high_volatility', 'sl_test', 'target_test', etc.
            token: Specific token, or None for all instruments
        """
        with QMutexLocker(self._mutex):
            self.simulator.set_scenario(scenario_name, token)
        logger.info(f"Applied scenario '{scenario_name}' to {'all' if token is None else token}")
    
    def get_available_scenarios(self) -> list:
        """Get list of available scenario names."""
        return self.simulator.get_available_scenarios()
    
    def stop(self):
        """
        Stop the simulator worker.
        
        Same interface as AliceBlueWorker.stop().
        """
        logger.info("🛑 Stopping SimulatorWorker...")
        self._stop_requested = True
        self.is_connected = False
    
    def is_simulation_mode(self) -> bool:
        """Check if running in simulation mode (always True for this worker)."""
        return True


class MockInstrument:
    """
    Mock Instrument for testing without real contract data.
    
    Mimics the Instrument namedtuple from alice_utils.
    """
    
    def __init__(
        self,
        token: int,
        symbol: str,
        name: str = None,
        exchange: str = "NFO",
        expiry: str = "",
        lot_size: int = 1
    ):
        self.token = token
        self.symbol = symbol
        self.name = name or symbol
        self.exchange = exchange
        self.expiry = expiry
        self.lot_size = lot_size
    
    def __repr__(self):
        return f"MockInstrument(token={self.token}, name={self.name})"


def create_mock_instruments(count: int = 5) -> List[MockInstrument]:
    """
    Create mock instruments for testing.
    
    Args:
        count: Number of instruments to create
    
    Returns:
        List of MockInstrument objects
    """
    instruments = [
        MockInstrument(12345, "NIFTY", "NIFTY26DEC25C24000", lot_size=25),
        MockInstrument(12346, "NIFTY", "NIFTY26DEC25P24000", lot_size=25),
        MockInstrument(23456, "BANKNIFTY", "BANKNIFTY26DEC25C52000", lot_size=15),
        MockInstrument(23457, "BANKNIFTY", "BANKNIFTY26DEC25P52000", lot_size=15),
        MockInstrument(34567, "TCS", "TCS30DEC25C4000", lot_size=150),
        MockInstrument(34568, "RELIANCE", "RELIANCE30DEC25C1300", lot_size=250),
        MockInstrument(45678, "INFY", "INFY30DEC25P1800", lot_size=300),
    ]
    
    return instruments[:count]


# Pre-defined instruments matching example_screener_alert.json
# These map directly to the alerts in paper_trade_app/alerts_inbox/example_screener_alert.json
EXAMPLE_ALERT_INSTRUMENTS = {
    # NIFTY 24000 CE - from example_screener_alert.json
    "NIFTY_24000_CE": MockInstrument(
        token=100001,
        symbol="NIFTY",
        name="NIFTY30JAN25C24000",
        exchange="NFO",
        expiry="2025-01-30",
        lot_size=50
    ),
    # BANKNIFTY 51000 PE - from example_screener_alert.json
    "BANKNIFTY_51000_PE": MockInstrument(
        token=100002,
        symbol="BANKNIFTY",
        name="BANKNIFTY30JAN25P51000",
        exchange="NFO",
        expiry="2025-01-30",
        lot_size=15
    ),
}


def get_example_alert_instruments() -> List[MockInstrument]:
    """
    Get mock instruments that match the alerts in example_screener_alert.json.
    
    These instruments have:
    - Matching strike prices
    - Matching expiry dates
    - Matching lot sizes
    - Pre-configured initial prices matching the alert premiums
    
    Returns:
        List of MockInstrument objects matching example alerts
    """
    return list(EXAMPLE_ALERT_INSTRUMENTS.values())


def create_simulator_for_alerts(config: dict = None) -> SimulatorWorker:
    """
    Create a SimulatorWorker pre-configured for testing with example alerts.
    
    The simulator will have:
    - Instruments matching example_screener_alert.json
    - Initial prices set to match the alert premiums
    
    Args:
        config: Optional simulator configuration
    
    Returns:
        SimulatorWorker ready for alert testing
    
    Usage:
        worker = create_simulator_for_alerts()
        worker.start()
        
        # Instruments are auto-subscribed with correct prices
        instruments = get_example_alert_instruments()
        worker.subscribe_tokens(instruments)
    """
    worker = SimulatorWorker(config)
    
    # Pre-configure prices for alert instruments
    for token, price in EXAMPLE_ALERT_PRICES.items():
        worker.set_initial_price(token, price)
    
    return worker
