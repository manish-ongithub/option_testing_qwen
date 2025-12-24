import sys
import os
import json
import logging
from PyQt6.QtCore import QThread, pyqtSignal
from core.alice_utils import Aliceblue  # Importing your code

# Configure Logging - ensure handler flushes immediately
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("AliceWorker")

# Force stdout to be unbuffered for print statements from alice_utils
os.environ['PYTHONUNBUFFERED'] = '1'

class AliceBlueWorker(QThread):
    # Signals to communicate with the Main App
    connection_signal = pyqtSignal(bool, str) # (Connected?, Message)
    tick_signal = pyqtSignal(dict)            # Sends live price updates
    error_signal = pyqtSignal(str)

    def __init__(self, user_id, api_key):
        super().__init__()
        self.user_id = user_id
        self.api_key = api_key
        self.alice = None
        self.is_connected = False
        self._stop_requested = False

    def run(self):
        """
        Main execution method for the thread.
        1. Login
        2. Start WebSocket
        """
        try:
            # 1. Initialize API
            logger.info("🔄 Initializing Alice Blue API...")
            sys.stdout.flush()
            self.alice = Aliceblue(user_id=self.user_id, api_key=self.api_key)
            
            # 2. Get Session ID (Login)
            logger.info("🔑 Getting Session ID...")
            sys.stdout.flush()
            session_data = self.alice.get_session_id()
            logger.info(f"📋 Session Response: stat={session_data.get('stat')}")
            sys.stdout.flush()
            
            if session_data.get('stat') == 'Ok':
                self.connection_signal.emit(True, "Session Created Successfully")
                logger.info("✅ Session ID Generated")
                sys.stdout.flush()
                
                # 3. Start WebSocket (Blocking Call handled by this Thread)
                logger.info("🔌 Starting WebSocket connection...")
                logger.info("   (Note: WebSocket only works during market hours 9:15 AM - 3:30 PM IST on trading days)")
                sys.stdout.flush()
                
                # Debug: Check if session_id is set
                if hasattr(self.alice, 'session_id') and self.alice.session_id:
                    logger.info(f"✓ session_id is set (length: {len(self.alice.session_id)})")
                else:
                    logger.error("❌ session_id is NOT set - WebSocket will not connect!")
                    self.error_signal.emit("Session ID not available")
                    return
                
                # Debug: Test invalidate session endpoint
                try:
                    logger.info("🔹 Testing invalidateSocketSess...")
                    sys.stdout.flush()
                    invalid_resp = self.alice.invalid_sess(self.alice.session_id)
                    logger.info(f"   Response: {invalid_resp}")
                    sys.stdout.flush()
                    
                    if invalid_resp.get('stat') != 'Ok':
                        logger.warning(f"⚠️ invalid_sess returned: {invalid_resp}")
                except Exception as e:
                    logger.error(f"❌ invalid_sess failed: {e}")
                
                # Debug: Test create session endpoint  
                try:
                    logger.info("🔹 Testing createSocketSess...")
                    sys.stdout.flush()
                    create_resp = self.alice.createSession(self.alice.session_id)
                    logger.info(f"   Response: {create_resp}")
                    sys.stdout.flush()
                    
                    if create_resp.get('stat') != 'Ok':
                        logger.warning(f"⚠️ createSession returned: {create_resp}")
                        # Check for specific error messages
                        if 'emsg' in create_resp:
                            self.error_signal.emit(f"Socket session error: {create_resp['emsg']}")
                except Exception as e:
                    logger.error(f"❌ createSession failed: {e}")
                
                try:
                    self.alice.start_websocket(
                        socket_open_callback=self.on_open,
                        socket_close_callback=self.on_close,
                        socket_error_callback=self.on_error,
                        subscription_callback=self.on_message,
                        run_in_background=False  # We run in this QThread, so false is fine
                    )
                except Exception as ws_error:
                    logger.error(f"❌ WebSocket failed to start: {ws_error}")
                    import traceback
                    logger.error(traceback.format_exc())
                    self.error_signal.emit(f"WebSocket Error: {ws_error}")
                    
                # If we reach here, WebSocket has closed
                if not self.is_connected:
                    logger.warning("⚠️ WebSocket closed without ever connecting")
                    self.connection_signal.emit(False, "WebSocket could not connect (Market may be closed)")
            else:
                error_msg = session_data.get('emsg', 'Unknown error')
                logger.error(f"❌ Login Failed: {error_msg}")
                self.connection_signal.emit(False, f"Login Failed: {error_msg}")
        
        except Exception as e:
            import traceback
            logger.error(f"❌ API Error: {e}")
            logger.error(traceback.format_exc())
            self.error_signal.emit(str(e))

    # --- Callbacks ---
    def on_open(self):
        self.is_connected = True
        self.connection_signal.emit(True, "WebSocket Connected")
        logger.info("✅ WebSocket Opened")

    def on_close(self):
        self.is_connected = False
        self.connection_signal.emit(False, "WebSocket Disconnected")
        logger.info("❌ WebSocket Closed")

    def on_error(self, error):
        logger.error(f"🔴 WebSocket Error: {error}")
        self.error_signal.emit(str(error))

    def on_message(self, message):
        """
        Triggered when a price tick arrives.
        Parses JSON and emits it to the UI.
        """
        try:
            data = json.loads(message)
            # data structure depends on Alice Blue response. 
            # Usually contains 'tk' (token), 'lp' (ltp), or similar keys.
            
            # Standardization for our App
            if 'tk' in data and 'lp' in data:
                clean_tick = {
                    'token': int(data['tk']),  # Convert to int for consistent lookup
                    'ltp': float(data['lp']),
                    'change': float(data['pc']) if 'pc' in data else 0.0,
                    'volume': int(data['v']) if 'v' in data else 0
                }
                self.tick_signal.emit(clean_tick)
                # Log first few ticks to verify connection
                if not hasattr(self, '_tick_count'):
                    self._tick_count = 0
                self._tick_count += 1
                if self._tick_count <= 5:
                    logger.info(f"📈 Tick #{self._tick_count}: Token {data['tk']} LTP {data['lp']}")
                
        except json.JSONDecodeError:
            # Heartbeat messages may not be valid JSON, ignore them
            pass
        except Exception as e:
            logger.warning(f"Error processing tick message: {e}")

    # --- Helper Methods ---
    def subscribe_tokens(self, instruments):
        """
        Subscribes to a list of instruments.
        
        Args:
            instruments: List of 'Instrument' namedtuples required by the library.
        """
        if self.alice and self.is_connected:
            self.alice.subscribe(instruments)
            for inst in instruments:
                logger.info(f"📡 Subscribed to {inst.token} ({getattr(inst, 'name', getattr(inst, 'symbol', 'Unknown'))})")
        else:
            logger.warning(f"⚠️ Cannot subscribe - WebSocket not connected (is_connected={self.is_connected})")

    def unsubscribe_tokens(self, instruments):
        """
        Unsubscribes from a list of instruments.
        
        Args:
            instruments: List of 'Instrument' namedtuples to unsubscribe from.
        """
        if self.alice and self.is_connected:
            self.alice.unsubscribe(instruments)
            for inst in instruments:
                logger.info(f"📴 Unsubscribed from {inst.token}")

    def stop(self):
        """
        Gracefully stops the WebSocket connection and the worker thread.
        """
        logger.info("🛑 Stopping AliceBlueWorker...")
        self._stop_requested = True
        if self.alice and self.is_connected:
            try:
                self.alice.stop_websocket()
            except Exception as e:
                logger.warning(f"Error stopping websocket: {e}")
        self.is_connected = False