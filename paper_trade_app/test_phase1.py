import sys
import signal
from PyQt6.QtCore import QCoreApplication, QTimer
from config import USER_ID, API_KEY
from core.data_feed import AliceBlueWorker
from core.instrument_mapper import InstrumentMapper

# 1. Setup minimal PyQt App (Required for QThread)
app = QCoreApplication(sys.argv)

# Enable Ctrl+C to work with PyQt event loop
def signal_handler(signum, frame):
    print("\n🛑 Ctrl+C received, shutting down...")
    app.quit()

signal.signal(signal.SIGINT, signal_handler)

# Timer to allow Python to process signals (PyQt blocks Python's signal handling)
timer = QTimer()
timer.timeout.connect(lambda: None)  # Empty callback to let Python handle signals
timer.start(100)  # Check every 100ms

print("--- 🚀 Starting Phase 1 Verification ---")

# 2. Initialize Mapper & Load Data
mapper = InstrumentMapper(USER_ID, API_KEY)
# Note: Ensure you have internet access. This downloads ~50MB CSV.
mapper.load_master_contract("NFO") 

# 3. Define Multiple Tokens to Subscribe
# ADJUST THESE VALUES TO VALID UPCOMING EXPIRY DATES
TEST_INSTRUMENTS = [
    {"symbol": "TCS",       "expiry": "2025-12-30", "strike": 3200,  "type": "PE"},
    {"symbol": "TCS",       "expiry": "2025-12-30", "strike": 3200,  "type": "CE"},
    {"symbol": "NIFTY",     "expiry": "2025-12-23", "strike": 24000, "type": "CE"},
    {"symbol": "NIFTY",     "expiry": "2025-12-23", "strike": 24000, "type": "PE"},
    {"symbol": "BANKNIFTY", "expiry": "2025-12-30", "strike": 48000, "type": "CE"},
    # Add more instruments as needed...
]

# Resolve all instruments
instruments_to_subscribe = []
print("\n🔍 Resolving instruments...")

for item in TEST_INSTRUMENTS:
    print(f"  Looking for: {item['symbol']} {item['expiry']} {item['strike']} {item['type']}", end=" ")
    instrument = mapper.get_token(
        symbol=item["symbol"],
        expiry_str=item["expiry"],
        strike=item["strike"],
        option_type=item["type"]
    )
    
    if instrument:
        instruments_to_subscribe.append(instrument)
        print(f"✅ Token: {instrument.token}")
    else:
        print("❌ Not found")

if not instruments_to_subscribe:
    print("\n❌ No instruments found. Check expiry/strike values.")
    sys.exit()

print(f"\n✅ Found {len(instruments_to_subscribe)} instruments to subscribe")

# 4. Start WebSocket Worker
worker = AliceBlueWorker(USER_ID, API_KEY)

# Track if we've already subscribed (connection callback may fire multiple times)
subscribed = False

def handle_connect(connected, msg):
    global subscribed
    print(f"📡 Connection Status: {msg}")
    if connected and not subscribed:
        print(f"Subscribing to {len(instruments_to_subscribe)} tokens...")
        worker.subscribe_tokens(instruments_to_subscribe)
        subscribed = True

# Create a token-to-name mapping for better display
token_name_map = {str(inst.token): inst.name for inst in instruments_to_subscribe}

def handle_tick(tick_data):
    # This proves we are getting live data!
    token = tick_data['token']
    name = token_name_map.get(str(token), token)
    print(f"⚡ TICK: {name} | LTP={tick_data['ltp']} | Change={tick_data.get('change', 0):.2f}%")

# Connect Signals
worker.connection_signal.connect(handle_connect)
worker.tick_signal.connect(handle_tick)
worker.error_signal.connect(lambda e: print(f"Error: {e}"))

# Run Worker
worker.start()

# Keep script running
print("\nListening for ticks... (Press Ctrl+C to stop)")

# Run the event loop
exit_code = app.exec()

# Cleanup after event loop exits
print("🛑 Stopping worker...")
worker.stop()
worker.wait()  # Wait for thread to finish
print("✅ Exited cleanly.")
sys.exit(exit_code)