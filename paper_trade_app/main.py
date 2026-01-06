"""
Indian Options Paper Trading Application - Main Controller

Orchestrates all components:
- UI (Dashboard)
- Data Feed (Alice Blue WebSocket or Simulator)
- Trade Manager (Order matching, P&L)
- Alert Watcher (JSON file monitoring)
- Instrument Mapper (Symbol to token)
- Report Generator (PDF/Excel export)
- Database Persistence (PostgreSQL)
- Session Management (Resume capability)
"""

# ============================================================
# CRITICAL: Qt Plugin Path Fix - MUST be at the very top
# before ANY other imports that might trigger Qt loading
# ============================================================
import sys
import os
import sysconfig

def _setup_qt_plugin_path():
    """Configure Qt plugin path for PyQt6 on macOS."""
    # Find site-packages and construct PyQt6 plugin path
    site_packages = sysconfig.get_path('purelib')
    if site_packages:
        qt_plugins_path = os.path.join(site_packages, 'PyQt6', 'Qt6', 'plugins')
        if os.path.exists(qt_plugins_path):
            os.environ['QT_PLUGIN_PATH'] = qt_plugins_path
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(qt_plugins_path, 'platforms')
            return True
    
    # Fallback: search in sys.path
    for path in sys.path:
        if 'site-packages' in path:
            qt_plugins_path = os.path.join(path, 'PyQt6', 'Qt6', 'plugins')
            if os.path.exists(qt_plugins_path):
                os.environ['QT_PLUGIN_PATH'] = qt_plugins_path
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(qt_plugins_path, 'platforms')
                return True
    return False

# Execute immediately before any other imports
_setup_qt_plugin_path()

import io
import json
import threading
import logging

# IMPORTANT: Import WebEngine BEFORE QApplication is created
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from ui.dashboard import MainWindow
from core.instrument_mapper import InstrumentMapper
from core.trade_manager import TradeManager
from core.alert_watcher import AlertWatcherThread
from core.report_generator import ReportGenerator
from config import USER_ID, API_KEY, USE_SIMULATOR
from core.alert_normalizer import normalize_alert

# Import default ticker symbols
try:
    from config import DEFAULT_TICKER_SYMBOLS
except ImportError:
    DEFAULT_TICKER_SYMBOLS = []

# Import persistence settings
try:
    from config import ENABLE_PERSISTENCE, DB_CONFIG
except ImportError:
    ENABLE_PERSISTENCE = False
    DB_CONFIG = {}

# Import database and session manager
if ENABLE_PERSISTENCE:
    try:
        from core.database import DatabaseManager
        from core.session_manager import SessionManager
        DB_AVAILABLE = True
    except ImportError as e:
        logging.warning(f"Database modules not available: {e}")
        DB_AVAILABLE = False
else:
    DB_AVAILABLE = False

# Conditional import based on mode
if USE_SIMULATOR:
    from core.simulator_worker import SimulatorWorker
else:
    from core.data_feed import AliceBlueWorker


class AppController:
    """Main application controller that wires all components together."""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # Track simulation mode
        self.simulation_mode = USE_SIMULATOR
        
        # Database and session management
        self.db_manager = None
        self.session_manager = None
        self._persistence_enabled = False
        
        # 1. Initialize Database (if enabled)
        self._init_database()
        
        # 2. Initialize Core Services
        self.ui = MainWindow()
        self.manager = TradeManager()
        self.mapper = InstrumentMapper(USER_ID, API_KEY, simulation_mode=self.simulation_mode)
        
        # Link session manager to trade manager
        if self.session_manager:
            self.manager.set_session_manager(self.session_manager)
        
        # Choose worker based on mode
        if self.simulation_mode:
            self.worker = SimulatorWorker()
        else:
            self.worker = AliceBlueWorker(USER_ID, API_KEY)
        
        self.watcher = AlertWatcherThread("./alerts_inbox") 
        self.reporter = ReportGenerator()
        
        # Track order_id -> alert_data mapping for sync between Active Positions and Signal Inbox
        self._order_alert_map = {}  # {order_id: alert_data}
        
        # Track token -> alert_data mapping for LTP updates on alerts
        self._alert_token_map = {}  # {token: [alert_data, ...]}

        # 3. Connect Signals & Slots
        self._connect_signals()
        
        # 4. Startup Tasks
        self.ui.append_log("🚀 System Starting...")
        if self.simulation_mode:
            self.ui.append_log("⚠️ SIMULATION MODE - Using simulated market data")
            self.ui.setWindowTitle("Indian Options Paper Trader (v2.0) - SIMULATION MODE")
        self.ui.append_log(f"📊 Fee Config: {self.manager.fee_config.broker_name}")
        
        if self._persistence_enabled:
            self.ui.append_log("💾 Database persistence: ENABLED")
        else:
            self.ui.append_log("⚠️ Database persistence: DISABLED (in-memory only)")
        
        self.ui.show()
        
        # 5. Handle Session Resume (if applicable)
        self._handle_session_resume()
        
        # 6. Start Background Tasks
        self._start_services()
    
    def _init_database(self):
        """Initialize database connection and session manager."""
        if not ENABLE_PERSISTENCE or not DB_AVAILABLE:
            logging.info("Database persistence disabled or unavailable")
            return
        
        try:
            # Create database manager
            self.db_manager = DatabaseManager(DB_CONFIG)
            
            # Connect to database
            if not self.db_manager.connect():
                logging.error("Failed to connect to database")
                self.db_manager = None
                return
            
            # Initialize schema (create tables if needed)
            if not self.db_manager.init_schema():
                logging.error("Failed to initialize database schema")
                self.db_manager.disconnect()
                self.db_manager = None
                return
            
            # Create session manager
            self.session_manager = SessionManager(self.db_manager)
            self._persistence_enabled = True
            
            logging.info("Database initialized successfully")
            
        except Exception as e:
            logging.error(f"Database initialization error: {e}")
            if self.db_manager:
                self.db_manager.disconnect()
            self.db_manager = None
            self.session_manager = None
    
    def _handle_session_resume(self):
        """Check for previous session and offer resume option."""
        if not self.session_manager:
            return
        
        # Check for previous active session
        if self.session_manager.has_previous_session():
            session_info = self.session_manager.get_previous_session_info()
            
            if session_info:
                # Show resume dialog
                started_at = session_info.get('started_at', 'Unknown')
                pending_count = session_info.get('pending_orders_count', 0)
                open_count = session_info.get('open_positions_count', 0)
                realized_pnl = session_info.get('realized_pnl', 0.0)
                
                msg = (
                    f"A previous trading session was found:\n\n"
                    f"Started: {started_at}\n"
                    f"Pending Orders: {pending_count}\n"
                    f"Open Positions: {open_count}\n"
                    f"Realized P&L: ₹{realized_pnl:.2f}\n\n"
                    f"Would you like to resume this session?"
                )
                
                reply = QMessageBox.question(
                    self.ui,
                    "Resume Previous Session?",
                    msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._resume_session()
                else:
                    self._start_new_session()
        else:
            # No previous session, start new
            self._start_new_session()
    
    def _resume_session(self):
        """Resume the previous trading session."""
        if not self.session_manager:
            return
        
        self.ui.append_log("🔄 Resuming previous session...")
        
        if self.session_manager.resume_session():
            # Restore state to trade manager
            state = self.session_manager.restore_state()
            self.manager.restore_state(state)
            
            # Add restored positions to UI
            for position in state.get('open_positions', []):
                self.ui.add_position_row(position)
            
            # Re-subscribe to tokens
            subscriptions = state.get('subscriptions', [])
            if subscriptions:
                self.ui.append_log(f"📡 Re-subscribing to {len(subscriptions)} tokens...")
                # Note: Actual subscription happens after worker starts
                self._pending_subscriptions = subscriptions
            else:
                self._pending_subscriptions = []
            
            self.ui.append_log(
                f"✅ Session resumed: {len(state.get('pending_orders', []))} pending, "
                f"{len(state.get('open_positions', []))} open positions"
            )
        else:
            self.ui.append_log("❌ Failed to resume session, starting new...")
            self._start_new_session()
    
    def _start_new_session(self):
        """Start a new trading session."""
        self._pending_subscriptions = []
        
        if self.session_manager:
            session_id = self.session_manager.start_new_session()
            if session_id:
                self.ui.append_log(f"📝 New session started: {session_id[:8]}...")
            else:
                self.ui.append_log("⚠️ Could not create session, running without persistence")

    def _connect_signals(self):
        """Wire up all signal connections between components."""
        
        # === A. Connection Status ===
        self.worker.connection_signal.connect(self.ui.update_status)
        self.worker.error_signal.connect(lambda e: self.ui.append_log(f"❌ API Error: {e}"))
        
        # === B. Ticks -> Trade Manager, Live Ticker, AND Alert LTP Updates ===
        self.worker.tick_signal.connect(self.manager.on_tick)
        self.worker.tick_signal.connect(self._handle_ticker_update)
        self.worker.tick_signal.connect(self._handle_alert_ltp_update)
        
        # Track tokens for live ticker display (separate from trading positions)
        self._ticker_tokens = {}  # {token: symbol_name}
        
        # === C. Trade Manager -> UI (Core Signals) ===
        self.manager.log_signal.connect(self.ui.append_log)
        self.manager.order_filled_signal.connect(self.ui.add_position_row)
        self.manager.pnl_update_signal.connect(self.ui.update_pnl_cell)
        self.manager.total_pnl_signal.connect(self.ui.update_total_pnl)
        
        # === D. Trade Manager -> UI (New Tier 1/2 Signals) ===
        self.manager.order_rejected_signal.connect(self._handle_order_rejected)
        self.manager.order_cancelled_signal.connect(self._handle_order_cancelled)
        self.manager.sl_hit_signal.connect(self._handle_sl_hit)
        self.manager.target_hit_signal.connect(self._handle_target_hit)
        self.manager.position_closed_signal.connect(self._handle_position_closed)

        # === E. Alert Watcher -> Controller -> Manager ===
        self.watcher.new_alert_signal.connect(self.handle_alert)
        
        # === F. UI Actions -> Manager ===
        # Exit button now sends order_id (string) instead of token
        self.ui.square_off_signal.connect(self.handle_exit)
        
        # Square off all button
        self.ui.btn_square_off_all.clicked.connect(self.handle_square_off_all)

        # === G. Reporting Buttons ===
        self.ui.btn_pdf.clicked.connect(self.generate_pdf_report)
        self.ui.btn_excel.clicked.connect(self.generate_excel_report)
        
        # === H. Config Profile Signals ===
        self.ui.profile_save_signal.connect(self._handle_save_profile)
        self.ui.profile_load_signal.connect(self._handle_load_profile)
        self.ui.profile_delete_signal.connect(self._handle_delete_profile)
        
        # === I. Alert Action Signals (User-Initiated Trading) ===
        self.ui.enter_trade_signal.connect(self.handle_enter_trade)
        self.ui.square_off_with_alert_signal.connect(self.handle_square_off_with_alert)
        
        # === J. Analysis Report Signals ===
        self.ui.basic_analyze_signal.connect(self.handle_basic_analyze)
        self.ui.enhanced_analyze_signal.connect(self.handle_enhanced_analyze)
        
        # Load available profiles into UI
        self._load_profile_list()
    
    def _handle_ticker_update(self, tick_data):
        """
        Route tick data to live ticker display in UI.
        
        Args:
            tick_data: {'token': int/str, 'ltp': float, 'change': float, 'volume': int}
        """
        token = tick_data.get('token')
        if token is None:
            return
        
        # Convert token to int for consistent lookup
        try:
            token = int(token)
        except (ValueError, TypeError):
            return
        
        if token in self._ticker_tokens:
            ltp = tick_data.get('ltp', 0.0)
            change = tick_data.get('change', 0.0)
            self.ui.update_ticker_price(token, ltp, change)
    
    def _handle_alert_ltp_update(self, tick_data):
        """
        Route tick data to alert widgets for LTP updates.
        
        Args:
            tick_data: {'token': int/str, 'ltp': float, ...}
        """
        token = tick_data.get('token')
        if token is None:
            return
        
        # Convert token to int for consistent lookup
        try:
            token = int(token)
        except (ValueError, TypeError):
            return
        
        ltp = tick_data.get('ltp', 0.0)
        if ltp > 0:
            # Update all alert widgets with this token
            self.ui.update_alert_ltp(token, ltp)

    def _start_services(self):
        """Start all background services."""
        # 1. Start WebSocket/Simulator Worker
        self.worker.start()
        
        # 2. Load Master Contract (Async) - skip in simulation if already cached
        if self.simulation_mode:
            # In simulation mode, we can use mock instruments or cached data
            threading.Thread(target=self._load_data_simulation, daemon=True).start()
        else:
            threading.Thread(target=self._load_data, daemon=True).start()
        
        # 3. Start File Watcher
        self.watcher.start()
        
        # 4. Re-subscribe tokens from resumed session (after worker starts)
        if hasattr(self, '_pending_subscriptions') and self._pending_subscriptions:
            # Use a timer to delay subscription until worker is ready
            QTimer.singleShot(2000, self._resubscribe_tokens)
        
        # 5. Subscribe to default ticker symbols (after worker is ready)
        # Track retry count
        self._ticker_retry_count = 0
        QTimer.singleShot(3000, self._subscribe_default_tickers)
    
    def _resubscribe_tokens(self):
        """Re-subscribe to tokens from resumed session."""
        if not hasattr(self, '_pending_subscriptions'):
            return
        
        for sub in self._pending_subscriptions:
            token = sub.get('token')
            symbol = sub.get('symbol', '')
            
            if token:
                # Create a mock instrument object for subscription
                class MockInstrument:
                    def __init__(self, t, s):
                        self.token = t
                        self.name = s
                
                instrument = MockInstrument(token, symbol)
                self.worker.subscribe_tokens([instrument])
                self.ui.append_log(f"📡 Re-subscribed: {symbol} (Token: {token})")
        
        self._pending_subscriptions = []
    
    def _subscribe_default_tickers(self):
        """
        Subscribe to default ticker symbols for live price display.
        This verifies that the API is responding with ticks.
        Supports INDEX (Nifty 50) and STOCK (RELIANCE) tickers.
        """
        if not DEFAULT_TICKER_SYMBOLS:
            self.ui.append_log("ℹ️ No default ticker symbols configured")
            return
        
        # Check if worker is connected
        if not hasattr(self.worker, 'is_connected') or not self.worker.is_connected:
            self._ticker_retry_count += 1
            if self._ticker_retry_count <= 10:  # Retry up to 10 times (20 seconds total)
                self.ui.set_ticker_status(f"⏳ Connecting... ({self._ticker_retry_count}/10)", "#FFA726")
                self.ui.append_log(f"⏳ Waiting for WebSocket connection... (attempt {self._ticker_retry_count}/10)")
                QTimer.singleShot(2000, self._subscribe_default_tickers)
            else:
                # Get current time info for better diagnostics
                from datetime import datetime
                now = datetime.now()
                current_time = now.strftime("%H:%M")
                weekday = now.strftime("%A")
                
                # Check if within market hours (9:15 AM - 3:30 PM IST)
                market_open = now.replace(hour=9, minute=15, second=0)
                market_close = now.replace(hour=15, minute=30, second=0)
                is_weekend = now.weekday() >= 5  # Saturday = 5, Sunday = 6
                is_market_hours = market_open <= now <= market_close
                
                if is_weekend:
                    status_msg = f"📅 Market Closed (Weekend - {weekday})"
                    log_msg = f"📅 Market is closed - Today is {weekday}"
                elif not is_market_hours:
                    status_msg = f"🕐 Market Closed ({current_time})"
                    log_msg = f"🕐 Market is closed - Current time: {current_time} (Market hours: 9:15 AM - 3:30 PM IST)"
                else:
                    # Market should be open but WebSocket not connecting - might be a holiday
                    status_msg = f"📅 Market Holiday or API Issue"
                    log_msg = f"⚠️ WebSocket not connecting at {current_time} - This may be a market holiday (like Christmas Eve)"
                
                self.ui.set_ticker_status(status_msg, "#FFA726")
                self.ui.append_log("❌ WebSocket not connected - cannot subscribe to tickers")
                self.ui.append_log(log_msg)
                self.ui.append_log("ℹ️ Live tickers will work when market is open on trading days")
            return
        
        self.ui.append_log(f"📊 Subscribing to {len(DEFAULT_TICKER_SYMBOLS)} ticker symbols...")
        
        subscribed_count = 0
        for ticker_config in DEFAULT_TICKER_SYMBOLS:
            symbol = ticker_config.get('symbol', '')
            exchange = ticker_config.get('exchange', 'NSE')
            instrument_type = ticker_config.get('type', 'STOCK')
            
            if not symbol:
                continue
            
            try:
                # Get cash market instrument (index or stock)
                instrument = self.mapper.get_cash_instrument(symbol, exchange, instrument_type)
                
                if instrument:
                    token = int(instrument.token)
                    display_name = symbol
                    
                    # Add to ticker tracking
                    self._ticker_tokens[token] = display_name
                    
                    # Add to UI ticker display
                    self.ui.add_ticker_symbol(token, display_name)
                    
                    # Set initial price for simulator if needed
                    if self.simulation_mode and hasattr(self.worker, 'set_initial_price'):
                        # Use realistic starting prices
                        mock_prices = {
                            'NIFTY 50': 24000,
                            'NIFTY50': 24000,
                            'BANK NIFTY': 51000,
                            'RELIANCE': 2900,
                            'TCS': 4100,
                            'INFY': 1900,
                            'HDFCBANK': 1700,
                        }
                        initial_price = mock_prices.get(symbol.upper(), 1000)
                        self.worker.set_initial_price(token, initial_price)
                    
                    # Subscribe to the instrument
                    self.worker.subscribe_tokens([instrument])
                    subscribed_count += 1
                    
                    self.ui.append_log(f"📡 Ticker: {display_name} ({instrument_type}) Token: {token}")
                else:
                    self.ui.append_log(f"⚠️ Could not map ticker: {symbol}")
                    
            except Exception as e:
                self.ui.append_log(f"⚠️ Error subscribing ticker {symbol}: {e}")
                import traceback
                traceback.print_exc()
        
        if subscribed_count > 0:
            self.ui.append_log(f"✅ Subscribed to {subscribed_count} tickers - watching for ticks...")
        else:
            self.ui.append_log("⚠️ No tickers subscribed - check symbol names")

    def _load_data(self):
        """Load contract master data in background."""
        self.ui.append_log("📥 Downloading Master Contracts... (This may take time)")
        self.mapper.load_master_contract("NFO")
        self.ui.append_log("✅ Master Contract Loaded. Ready for Alerts.")
    
    def _load_data_simulation(self):
        """Load data for simulation mode - uses cached data if available."""
        self.ui.append_log("📥 Loading Master Contracts for Simulation...")
        try:
            # Try to load cached contract data
            self.mapper.load_master_contract("NFO")
            self.ui.append_log("✅ Master Contract Loaded. Ready for Alerts.")
        except Exception as e:
            self.ui.append_log(f"⚠️ Could not load contracts: {e}")
            self.ui.append_log("ℹ️ You can still test with mock instruments in simulation mode.")
        
        # Pre-subscribe to all alerts in example_screener_alert.json
        self._preload_example_alerts()
    
    def _preload_example_alerts(self):
        """Pre-subscribe to all instruments from example_screener_alert.json for simulation."""
        alerts_file = os.path.join("./alerts_inbox", "example_screener_alert.json")
        
        if not os.path.exists(alerts_file):
            self.ui.append_log("ℹ️ No example alerts file found.")
            return
        
        try:
            with open(alerts_file, 'r') as f:
                data = json.load(f)
            
            # Handle both old format (array) and new format (object with top_alerts)
            if isinstance(data, dict) and 'top_alerts' in data:
                alerts = data.get('top_alerts', [])
                self.ui.append_log(f"📊 New format detected: {len(alerts)} alerts")
            elif isinstance(data, list):
                alerts = data
            else:
                alerts = [data] if data else []
            
            if not alerts:
                return
            
            self.ui.append_log(f"📊 Pre-loading {len(alerts)} instruments from example alerts...")
            
            subscribed_count = 0
            for alert in alerts:
                # Support both old (PascalCase) and new (lowercase) field names
                symbol = alert.get('symbol', alert.get('Symbol', ''))
                expiry = alert.get('expiry', alert.get('Expiry', ''))
                strike = alert.get('strike', alert.get('Strike', 0))
                option_type = alert.get('type', alert.get('Type', ''))
                premium = alert.get('premium', alert.get('Premium', 0))
                strategy = alert.get('strategy', alert.get('Strategy', ''))
                
                # For new format, infer option type from strategy if not provided
                if not option_type and strategy:
                    strategy_lower = strategy.lower()
                    if 'call' in strategy_lower or 'bull' in strategy_lower:
                        option_type = 'CE'
                    elif 'put' in strategy_lower or 'bear' in strategy_lower:
                        option_type = 'PE'
                    else:
                        option_type = 'CE'  # Default
                
                # Handle string strikes for spreads (e.g., "26200/26300")
                if isinstance(strike, str) and '/' in strike:
                    strike = float(strike.split('/')[0])
                
                if not all([symbol, expiry, strike]):
                    continue
                
                # Get/create mock instrument
                instrument = self.mapper.get_token(symbol, expiry, strike, option_type or 'CE')
                
                if instrument:
                    token = int(instrument.token)
                    
                    # Set initial price to match the alert premium
                    if premium and premium > 0:
                        self.worker.set_initial_price(token, float(premium))
                    
                    # Subscribe to the instrument
                    self.worker.subscribe_tokens([instrument])
                    subscribed_count += 1
            
            self.ui.append_log(f"✅ Pre-subscribed to {subscribed_count} instruments for simulation")
            self.ui.append_log("🎯 Simulator will generate ticks for all example alerts")
            
        except Exception as e:
            self.ui.append_log(f"⚠️ Error loading example alerts: {e}")

    # === Alert Handling ===
    
    def handle_alert(self, raw_alert_data):
        """
        Process incoming alert from file watcher.
        Normalizes the alert data to handle both old and new (screener) formats.
        Only displays the alert in Signal Inbox - does NOT auto-trade.
        User must select an alert and click "Enter Trade" or "Square Off".
        Also subscribes to live data for LTP updates.
        """
        # Normalize the alert to standard format
        alert_data = normalize_alert(raw_alert_data)
        
        self.ui.add_alert(alert_data)
        
        symbol = alert_data.get('symbol', 'Unknown')
        action = alert_data.get('action', 'BUY')
        strike = alert_data.get('strike', 0)
        option_type = alert_data.get('option_type', 'CE')
        quantity = alert_data.get('quantity', 0)
        price = alert_data.get('price_limit', 0)
        expiry = alert_data.get('expiry', '')
        
        self.ui.append_log(
            f"📥 Alert received: {action} {symbol} {strike}{option_type} "
            f"@ ₹{price:.2f} (Qty: {quantity}) - Click 'Trade' to execute"
        )
        
        # Subscribe to live data for LTP updates
        self._subscribe_alert_for_ltp(alert_data)
    
    def _subscribe_alert_for_ltp(self, alert_data: dict):
        """
        Subscribe an alert to live data feed for LTP updates.
        Maps the alert's instrument and subscribes to tick data.
        """
        symbol = alert_data.get('symbol', '')
        expiry = alert_data.get('expiry', '')
        strike = alert_data.get('strike', 0)
        option_type = alert_data.get('option_type', 'CE')
        strategy_type = alert_data.get('strategy_type', 'single')
        
        # For volatility strategies (straddle/strangle), option_type might be the strategy name
        if option_type in ('STRADDLE', 'STRANGLE'):
            # Subscribe to both CE and PE legs
            self._subscribe_leg_for_ltp(alert_data, symbol, expiry, strike, 'CE')
            put_strike = alert_data.get('put_strike', strike)
            self._subscribe_leg_for_ltp(alert_data, symbol, expiry, put_strike, 'PE')
        elif strategy_type == 'spread':
            # Subscribe to the primary (buying) leg
            self._subscribe_leg_for_ltp(alert_data, symbol, expiry, strike, option_type)
        else:
            # Single leg strategy
            self._subscribe_leg_for_ltp(alert_data, symbol, expiry, strike, option_type)
    
    def _subscribe_leg_for_ltp(self, alert_data: dict, symbol: str, expiry: str, strike: float, option_type: str):
        """Subscribe a single leg to live data."""
        try:
            instrument = self.mapper.get_token(symbol, expiry, strike, option_type)
            
            if instrument:
                token = int(instrument.token)
                
                # Set token on the alert widget
                self.ui.set_alert_token(alert_data, token)
                
                # Track for LTP updates
                if token not in self._alert_token_map:
                    self._alert_token_map[token] = []
                self._alert_token_map[token].append(alert_data)
                
                # Set initial price in simulator if applicable
                premium = alert_data.get('price_limit', 0)
                if self.simulation_mode and hasattr(self.worker, 'set_initial_price'):
                    if premium and premium > 0:
                        self.worker.set_initial_price(token, float(premium))
                
                # Subscribe to tick data
                self.worker.subscribe_tokens([instrument])
                
        except Exception as e:
            # Silently fail - alert will just not have LTP updates
            import traceback
            traceback.print_exc()
    
    def handle_enter_trade(self, alert_data):
        """
        Handle user-initiated trade from selected alert.
        Called when user selects an alert and clicks "Enter Trade".
        Only marks alert as traded if order placement succeeds.
        """
        self.ui.append_log(f"📈 Validating trade from alert...")
        
        # Extract alert fields
        symbol = alert_data.get('symbol', '')
        expiry = alert_data.get('expiry', '')
        strike = alert_data.get('strike', 0)
        option_type = alert_data.get('option_type', 'CE')
        action = alert_data.get('action', 'BUY')
        price_limit = alert_data.get('price_limit', 0)
        quantity = alert_data.get('quantity', 0)
        stop_loss = alert_data.get('stop_loss')
        target = alert_data.get('target')
        validity = alert_data.get('validity', 'DAY')

        # Map Symbol to Token
        instrument = self.mapper.get_token(symbol, expiry, strike, option_type)

        if not instrument:
            self.ui.append_log(f"❌ Mapping Failed: {symbol} {expiry} {strike} {option_type}")
            QMessageBox.warning(
                self.ui,
                "Trade Failed",
                f"Could not map symbol: {symbol} {expiry} {strike} {option_type}\n\n"
                "Check that the symbol and expiry are valid."
            )
            return
        
        token = int(instrument.token)
        symbol_name = instrument.name
        
        self.ui.append_log(f"🎯 Mapped: {symbol} -> Token {token} ({symbol_name})")
        
        # Subscribe to Live Data
        self.worker.subscribe_tokens([instrument])
        
        # Persist subscription for session resume
        if self.session_manager:
            instrument_data = {
                'symbol': symbol,
                'expiry': expiry,
                'strike': strike,
                'option_type': option_type
            }
            self.session_manager.on_token_subscribed(token, symbol_name, instrument_data)
        
        # Place Order with all parameters (returns None if validation fails)
        order_id = self.manager.place_order(
            token=token,
            trading_symbol=symbol_name,
            action=action,
            price_limit=price_limit,
            quantity=quantity,
            stop_loss=stop_loss,
            target=target,
            validity=validity,
            instrument=instrument
        )
        
        if order_id:
            self.ui.append_log(f"📝 Order placed: {order_id}")
            # Store mapping for sync between Active Positions and Signal Inbox
            self._order_alert_map[order_id] = alert_data
            # Mark alert as traded ONLY after successful order placement
            self.ui.mark_alert_as_traded(alert_data)
        else:
            # Order was rejected (validation failed - lot size, market hours, etc.)
            self.ui.append_log(f"⚠️ Order rejected - check lot size and market hours")
    
    def handle_square_off_with_alert(self, alert_data):
        """
        Square off an existing position using the alert's symbol info.
        Finds matching open position and closes it.
        Only marks alert as squared off if operation succeeds.
        """
        symbol = alert_data.get('symbol', '')
        expiry = alert_data.get('expiry', '')
        strike = alert_data.get('strike', 0)
        option_type = alert_data.get('option_type', 'CE')
        
        self.ui.append_log(f"📉 Looking for position to square off: {symbol} {strike}{option_type}")
        
        # Map Symbol to Token
        instrument = self.mapper.get_token(symbol, expiry, strike, option_type)
        
        if not instrument:
            self.ui.append_log(f"❌ Could not map symbol: {symbol} {expiry} {strike} {option_type}")
            QMessageBox.warning(
                self.ui,
                "Square Off Failed",
                f"Could not map symbol: {symbol} {expiry} {strike} {option_type}\n\n"
                "Check that the symbol and expiry are valid."
            )
            return
        
        token = int(instrument.token)
        
        # Find matching open positions
        positions = self.manager.get_open_positions()
        matching_positions = [p for p in positions if p.get('token') == token]
        
        if not matching_positions:
            self.ui.append_log(f"⚠️ No open position found for {symbol} {strike}{option_type}")
            QMessageBox.warning(
                self.ui,
                "No Position Found",
                f"No open position found for:\n\n{symbol} {strike}{option_type}\n\n"
                "You must enter a trade first before you can square off."
            )
            return
        
        # Square off all matching positions
        squared_off = 0
        closed_order_ids = []
        for position in matching_positions:
            order_id = position['id']
            if self.manager.square_off_position(order_id):
                squared_off += 1
                closed_order_ids.append(order_id)
        
        if squared_off > 0:
            self.ui.append_log(f"✅ Squared off {squared_off} position(s)")
            # Clean up order-alert mapping for closed positions
            for order_id in closed_order_ids:
                if order_id in self._order_alert_map:
                    del self._order_alert_map[order_id]
            # Mark alert as squared off ONLY after successful exit
            self.ui.mark_alert_as_squared_off(alert_data)
        else:
            self.ui.append_log(f"⚠️ Failed to square off positions")
            QMessageBox.warning(
                self.ui,
                "Square Off Failed",
                "Failed to square off positions. Please try again."
            )
    
    # === Analysis Reports ===
    
    def handle_basic_analyze(self, alert_data):
        """
        Handle Basic Analyze button click.
        Runs the basic Greeks analysis and shows in popup.
        """
        self.ui.append_log(f"📊 Running basic analysis...")
        
        try:
            # Capture stdout to get the analysis output
            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()
            
            # Import and run basic analyzer
            sys.path.insert(0, '..')
            from alert_analyzer import analyze_alert
            
            # Extract parameters from alert
            symbol = alert_data.get('symbol', 'NIFTY')
            spot = alert_data.get('spot', 0)
            strike = alert_data.get('strike', 0)
            premium = alert_data.get('price_limit', 0)
            option_type = alert_data.get('option_type', 'CE')
            dte = alert_data.get('days_to_expiry', 7)
            iv = alert_data.get('iv', 15)
            iv_pct = alert_data.get('iv_percentile', 50)
            volume = alert_data.get('volume', 0)
            oi = alert_data.get('oi', 0)
            lot_size = alert_data.get('quantity', 50)
            
            # Run analysis
            analyze_alert(
                symbol=symbol,
                spot=spot if spot > 0 else strike * 0.98,
                strike=strike,
                premium=premium,
                option_type=option_type,
                dte=dte if dte > 0 else 7,
                iv=iv if iv > 0 else 15,
                iv_percentile=iv_pct if iv_pct > 0 else 50,
                volume=int(volume) if volume else 1000,
                oi=int(oi) if oi else 10000,
                lot_size=int(lot_size) if lot_size else 50
            )
            
            # Get captured output
            report_text = captured_output.getvalue()
            
            # Restore stdout
            sys.stdout = old_stdout
            
            # Show in dialog
            title = f"Basic Analysis: {symbol} {strike} {option_type}"
            self.ui.show_analysis_report(title, report_text)
            self.ui.append_log(f"✅ Basic analysis complete")
            
        except Exception as e:
            sys.stdout = old_stdout if 'old_stdout' in dir() else sys.stdout
            self.ui.append_log(f"❌ Analysis error: {e}")
            QMessageBox.warning(self.ui, "Analysis Failed", f"Error running analysis:\n\n{e}")
    
    def handle_enhanced_analyze(self, alert_data):
        """
        Handle Enhanced Analyze button click.
        Runs the full technical + Greeks analysis and shows in popup.
        """
        self.ui.append_log(f"📈 Running enhanced analysis (this may take a moment)...")
        
        try:
            # Capture stdout to get the analysis output
            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()
            
            # Import and run enhanced analyzer
            sys.path.insert(0, '..')
            from enhanced_alert_analyzer import enhanced_alert_analysis
            
            # Extract parameters from alert
            symbol = alert_data.get('symbol', 'NIFTY')
            strike = alert_data.get('strike', 0)
            premium = alert_data.get('price_limit', 0)
            option_type = alert_data.get('option_type', 'CE')
            dte = alert_data.get('days_to_expiry', 7)
            iv = alert_data.get('iv', 15)
            iv_pct = alert_data.get('iv_percentile', 50)
            volume = alert_data.get('volume', 0)
            oi = alert_data.get('oi', 0)
            
            # Run enhanced analysis
            enhanced_alert_analysis(
                symbol=symbol,
                strike=strike,
                premium=premium,
                option_type=option_type,
                dte=dte if dte > 0 else 7,
                iv=iv if iv > 0 else 15,
                iv_percentile=iv_pct if iv_pct > 0 else 50,
                volume=int(volume) if volume else 1000,
                oi=int(oi) if oi else 10000
            )
            
            # Get captured output
            report_text = captured_output.getvalue()
            
            # Restore stdout
            sys.stdout = old_stdout
            
            # Show in dialog
            title = f"Enhanced Analysis: {symbol} {strike} {option_type}"
            self.ui.show_analysis_report(title, report_text)
            self.ui.append_log(f"✅ Enhanced analysis complete")
            
        except Exception as e:
            sys.stdout = old_stdout if 'old_stdout' in dir() else sys.stdout
            self.ui.append_log(f"❌ Analysis error: {e}")
            QMessageBox.warning(self.ui, "Analysis Failed", f"Error running analysis:\n\n{e}")

    # === Position Management ===
    
    def handle_exit(self, order_id: str):
        """Handle manual exit button click."""
        self.ui.append_log(f"🔴 Exit clicked for: {order_id}")
        
        # Debug: Show current open positions
        open_count = sum(len(positions) for positions in self.manager.open_positions.values())
        self.ui.append_log(f"   Open positions: {open_count}")
        
        success = self.manager.square_off_position(order_id)
        if success:
            self.ui.append_log(f"✅ Position {order_id} closed successfully")
        else:
            self.ui.append_log(f"⚠️ Could not find position: {order_id}")

    def handle_square_off_all(self):
        """Handle square off all button click."""
        reply = QMessageBox.question(
            self.ui,
            "Confirm Square Off All",
            "Are you sure you want to square off ALL open positions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            count = self.manager.square_off_all()
            self.ui.append_log(f"🚫 Squared off {count} positions")

    # === Signal Handlers for New Tier 1/2 Signals ===
    
    def _handle_order_rejected(self, data):
        """Handle order rejection."""
        symbol = data.get('symbol', 'Unknown')
        reason = data.get('reason', 'Unknown reason')
        self.ui.show_notification(
            "Order Rejected",
            f"{symbol}\n\nReason: {reason}",
            "warning"
        )

    def _handle_order_cancelled(self, order):
        """Handle order cancellation."""
        # No special UI action needed - log is already emitted
        pass

    def _handle_sl_hit(self, data):
        """Handle stop-loss hit notification."""
        symbol = data.get('symbol', 'Unknown')
        pnl = data.get('pnl', 0)
        exit_price = data.get('exit_price', 0)
        
        self.ui.show_notification(
            "Stop-Loss Hit",
            f"{symbol}\n\nExit Price: ₹{exit_price:.2f}\nP&L: ₹{pnl:.2f}",
            "warning"
        )

    def _handle_target_hit(self, data):
        """Handle target hit notification."""
        symbol = data.get('symbol', 'Unknown')
        pnl = data.get('pnl', 0)
        exit_price = data.get('exit_price', 0)
        
        self.ui.show_notification(
            "Target Hit!",
            f"{symbol}\n\nExit Price: ₹{exit_price:.2f}\nP&L: ₹{pnl:.2f}",
            "info"
        )

    def _handle_position_closed(self, position):
        """Handle position closure - remove from UI table and sync Signal Inbox."""
        order_id = position.get('id')
        if order_id:
            self.ui.remove_position_row(order_id)
            
            # Sync with Signal Inbox - mark corresponding alert as squared off
            if order_id in self._order_alert_map:
                alert_data = self._order_alert_map[order_id]
                self.ui.mark_alert_as_squared_off(alert_data)
                # Clean up the mapping
                del self._order_alert_map[order_id]

    # === Reporting ===

    def _get_all_trades_data(self):
        """
        Combine closed history + active open positions for report.
        """
        # Closed trades
        history = self.manager.get_trade_history()
        
        # Open positions (flatten the dict of lists)
        active = self.manager.get_open_positions()
        
        return history + active

    def generate_pdf_report(self):
        """Generate and save PDF report."""
        self.ui.append_log("📄 Generating PDF Report...")
        data = self._get_all_trades_data()
        
        if not data:
            self.ui.append_log("⚠️ No trade data to report.")
            QMessageBox.warning(self.ui, "Report Error", "No trades found to generate report.")
            return

        filepath, msg = self.reporter.export_pdf(data)
        if filepath:
            self.ui.append_log(f"✅ PDF Saved: {filepath}")
            QMessageBox.information(self.ui, "Success", f"PDF Report saved at:\n{filepath}")
        else:
            self.ui.append_log(f"❌ PDF Error: {msg}")
            QMessageBox.critical(self.ui, "Export Error", f"Failed to create PDF:\n{msg}")

    def generate_excel_report(self):
        """Generate and save Excel report."""
        self.ui.append_log("📊 Generating Excel Report...")
        data = self._get_all_trades_data()
        
        if not data:
            self.ui.append_log("⚠️ No trade data to report.")
            QMessageBox.warning(self.ui, "Report Error", "No trades found.")
            return

        filepath, msg = self.reporter.export_excel(data)
        if filepath:
            self.ui.append_log(f"✅ Excel Saved: {filepath}")
            QMessageBox.information(self.ui, "Success", f"Excel Report saved at:\n{filepath}")
        else:
            self.ui.append_log(f"❌ Excel Error: {msg}")
            QMessageBox.critical(self.ui, "Export Error", f"Failed to create Excel:\n{msg}")
    
    # === Config Profile Handlers ===
    
    def _load_profile_list(self):
        """Load available config profiles into UI dropdown."""
        if not self.session_manager:
            return
        
        try:
            profiles = self.session_manager.list_config_profiles()
            self.ui.set_profile_list(profiles)
        except Exception as e:
            logging.error(f"Failed to load profile list: {e}")
    
    def _handle_save_profile(self, name: str):
        """Save current configuration as a profile."""
        if not self.session_manager:
            self.ui.append_log("⚠️ Cannot save profile: persistence not enabled")
            return
        
        try:
            # Import current config values
            from config import (
                FEE_CONFIG_NAME, CUSTOM_FEE_CONFIG,
                SLIPPAGE_PERCENT, ENFORCE_MARKET_HOURS, ALLOW_AMO,
                MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
                MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE,
                SIMULATOR_CONFIG
            )
            
            # Collect fee config
            fee_config = {
                'config_name': FEE_CONFIG_NAME,
                'custom_config': CUSTOM_FEE_CONFIG
            }
            
            # Collect trading params
            trading_params = {
                'slippage_percent': SLIPPAGE_PERCENT,
                'enforce_market_hours': ENFORCE_MARKET_HOURS,
                'allow_amo': ALLOW_AMO,
                'market_open_hour': MARKET_OPEN_HOUR,
                'market_open_minute': MARKET_OPEN_MINUTE,
                'market_close_hour': MARKET_CLOSE_HOUR,
                'market_close_minute': MARKET_CLOSE_MINUTE
            }
            
            # Collect simulator config
            simulator_config = dict(SIMULATOR_CONFIG)
            
            # Save to database
            success = self.session_manager.save_config_profile(
                name,
                fee_config=fee_config,
                simulator_config=simulator_config,
                trading_params=trading_params
            )
            
            if success:
                self.ui.append_log(f"✅ Profile saved: {name}")
            else:
                self.ui.append_log(f"❌ Failed to save profile: {name}")
                
        except Exception as e:
            logging.error(f"Error saving profile: {e}")
            self.ui.append_log(f"❌ Error saving profile: {e}")
    
    def _handle_load_profile(self, name: str):
        """Load a configuration profile."""
        if not self.session_manager:
            self.ui.append_log("⚠️ Cannot load profile: persistence not enabled")
            return
        
        try:
            profile = self.session_manager.load_config_profile(name)
            
            if not profile:
                self.ui.append_log(f"⚠️ Profile not found: {name}")
                return
            
            # Display profile info (actual config application would require app restart)
            fee_config = profile.get('fee_config', {})
            trading_params = profile.get('trading_params', {})
            simulator_config = profile.get('simulator_config', {})
            
            self.ui.append_log(f"📋 Loaded profile: {name}")
            
            if fee_config:
                config_name = fee_config.get('config_name', 'Unknown')
                self.ui.append_log(f"  Fee Config: {config_name}")
            
            if trading_params:
                slippage = trading_params.get('slippage_percent', 0)
                self.ui.append_log(f"  Slippage: {slippage}%")
            
            if simulator_config:
                volatility = simulator_config.get('base_volatility', 0)
                self.ui.append_log(f"  Volatility: {volatility * 100:.1f}%")
            
            self.ui.append_log("ℹ️ Note: Restart app to apply profile settings")
            
        except Exception as e:
            logging.error(f"Error loading profile: {e}")
            self.ui.append_log(f"❌ Error loading profile: {e}")
    
    def _handle_delete_profile(self, name: str):
        """Delete a configuration profile."""
        if not self.session_manager:
            self.ui.append_log("⚠️ Cannot delete profile: persistence not enabled")
            return
        
        try:
            success = self.session_manager.delete_config_profile(name)
            
            if success:
                self.ui.append_log(f"🗑️ Profile deleted: {name}")
            else:
                self.ui.append_log(f"❌ Failed to delete profile: {name}")
                
        except Exception as e:
            logging.error(f"Error deleting profile: {e}")
            self.ui.append_log(f"❌ Error deleting profile: {e}")
        data = self._get_all_trades_data()
        
        if not data:
            self.ui.append_log("⚠️ No trade data to report.")
            QMessageBox.warning(self.ui, "Report Error", "No trades found.")
            return

        filepath, msg = self.reporter.export_excel(data)
        if filepath:
            self.ui.append_log(f"✅ Excel Saved: {filepath}")
            QMessageBox.information(self.ui, "Success", f"Excel Report saved at:\n{filepath}")
        else:
            self.ui.append_log(f"❌ Excel Error: {msg}")
            QMessageBox.critical(self.ui, "Export Error", f"Failed to create Excel:\n{msg}")

    def run(self):
        """Start the application event loop."""
        try:
            result = self.app.exec()
        finally:
            self._cleanup()
        sys.exit(result)
    
    def _cleanup(self):
        """Cleanup resources on application exit."""
        # Get final P&L from trade manager
        pnl_summary = self.manager.get_pnl_summary()
        
        # Close session with final P&L
        if self.session_manager and self.session_manager.is_active():
            self.session_manager.close_current_session(
                realized_pnl=pnl_summary.get('realized_pnl', 0.0),
                unrealized_pnl=pnl_summary.get('unrealized_pnl', 0.0),
                total_fees=pnl_summary.get('total_fees', 0.0)
            )
        
        # Disconnect database
        if self.db_manager:
            self.db_manager.disconnect()
        
        logging.info("Application cleanup completed")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    controller = AppController()
    controller.run()
