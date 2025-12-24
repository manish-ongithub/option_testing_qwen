# config_example.py
# COPY this file to config.py and fill in your credentials

# Replace with your actual Alice Blue Credentials
USER_ID = "YOUR_USER_ID"
API_KEY = "YOUR_API_KEY" 

# Directory to save master contracts (CSVs)
DATA_DIR = "./data_cache"

# ============ Trading Configuration ============

# Slippage simulation (0.0 = disabled, 0.1 = 0.1%)
SLIPPAGE_PERCENT = 0.1

# ============ Live Ticker Configuration ============

# Default symbols to subscribe for live ticker display (verifies API connection)
# These are informational only - shows market is open and ticks are flowing
# Supported types:
#   - "INDEX": Index like NIFTY 50, BANK NIFTY (exchange: "NSE")
#   - "STOCK": Stocks like RELIANCE, TCS (exchange: "NSE")
# Use empty list [] to disable default ticker
DEFAULT_TICKER_SYMBOLS = [
    {"symbol": "Nifty 50", "exchange": "NSE", "type": "INDEX"},
    {"symbol": "RELIANCE", "exchange": "NSE", "type": "STOCK"},
]

# ============ Simulator Configuration ============

# Enable simulation mode (True = use simulator, False = use real Alice Blue API)
USE_SIMULATOR = False

# Market hours (IST)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

# Enable/disable market hours validation
# Automatically disabled in simulation mode for unrestricted testing
ENFORCE_MARKET_HOURS = False if USE_SIMULATOR else True

# Allow After Market Orders (queue for next day)
ALLOW_AMO = True

# Fee configuration: "ALICE_BLUE", "ZERODHA", "FLAT_FEE", or "CUSTOM"
FEE_CONFIG_NAME = "ALICE_BLUE"

# Custom fee config (used when FEE_CONFIG_NAME = "CUSTOM")
CUSTOM_FEE_CONFIG = {
    "brokerage_per_order": 20.0,
    "stt_buy_percent": 0.0,
    "stt_sell_percent": 0.0625,
    "exchange_txn_charge_percent": 0.053,
    "sebi_charges_percent": 0.0001,
    "stamp_duty_percent": 0.003,
    "gst_percent": 18.0,
    "broker_name": "Custom Broker"
}

# Simulation parameters
SIMULATOR_CONFIG = {
    # Tick timing
    "tick_interval_ms": 500,      # Generate tick every 500ms (2 ticks/second)
    
    # Volatility settings
    "base_volatility": 0.015,     # 1.5% daily volatility (typical for NIFTY options)
    "volatility_clustering": 0.7, # GARCH alpha: 0-1, higher = more clustering
    
    # Mean reversion
    "mean_reversion_speed": 0.05, # Speed of reversion to moving average
    
    # Jump diffusion (sudden large moves)
    "jump_probability": 0.001,    # 0.1% chance of jump per tick
    "jump_magnitude": 0.02,       # 2% jump size when it occurs
    
    # Trend/Drift
    "trend": 0.0,                 # 0 = sideways, positive = bullish, negative = bearish
}

# Pre-defined simulation scenarios
# Use: simulator.set_scenario("trending_up") to apply
SIMULATION_SCENARIOS = {
    "sideways": {
        "trend": 0.0,
        "base_volatility": 0.01,
        "jump_probability": 0.0005
    },
    "trending_up": {
        "trend": 0.002,
        "base_volatility": 0.01,
        "mean_reversion_speed": 0.02
    },
    "trending_down": {
        "trend": -0.002,
        "base_volatility": 0.01,
        "mean_reversion_speed": 0.02
    },
    "high_volatility": {
        "trend": 0.0,
        "base_volatility": 0.03,
        "volatility_clustering": 0.8,
        "jump_probability": 0.002
    },
    "sl_test": {
        "trend": -0.003,
        "base_volatility": 0.015,
        "mean_reversion_speed": 0.01
    },
    "target_test": {
        "trend": 0.003,
        "base_volatility": 0.015,
        "mean_reversion_speed": 0.01
    },
}

# ============ Database Configuration ============

# Enable/disable persistence (False = in-memory only, True = PostgreSQL)
ENABLE_PERSISTENCE = True

# PostgreSQL connection settings
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "paper_trade",
    "user": "your_username",
    "password": ""  # Empty password for local peer authentication
}

