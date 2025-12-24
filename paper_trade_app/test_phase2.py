"""
Phase 2 Test: Enhanced Trade Manager Features

Tests:
1. Lot size validation
2. Stop-loss and target orders
3. Order cancellation and modification
4. Multiple orders per symbol
5. Position averaging
6. Transaction costs
7. Slippage simulation
8. P&L tracking (realized/unrealized)
"""

import sys
import signal
import time
import os
import json
from PyQt6.QtCore import QCoreApplication, QTimer
from core.trade_manager import TradeManager, OrderValidity
from core.alert_watcher import AlertWatcherThread
from core.fee_calculator import ALICE_BLUE_FEES

# Setup App
app = QCoreApplication(sys.argv)

# Enable Ctrl+C to work with PyQt event loop
def signal_handler(signum, frame):
    print("\n🛑 Ctrl+C received, shutting down...")
    app.quit()

signal.signal(signal.SIGINT, signal_handler)

# Timer to allow Python to process signals
timer = QTimer()
timer.timeout.connect(lambda: None)
timer.start(100)

print("=" * 60)
print("🧠 Phase 2: Enhanced Trade Manager Test")
print("=" * 60)

# Initialize Trade Manager
manager = TradeManager()

# Connect all signals for logging
manager.log_signal.connect(lambda msg: print(f"[LOG] {msg}"))
manager.order_placed_signal.connect(lambda o: print(f"[ORDER PLACED] {o['id']}: {o['action']} {o['quantity']} {o['symbol']}"))
manager.order_filled_signal.connect(lambda o: print(f"[FILLED] {o['id']}: {o['symbol']} @ ₹{o['entry_price']}"))
manager.order_rejected_signal.connect(lambda r: print(f"[REJECTED] {r['symbol']}: {r['reason']}"))
manager.order_cancelled_signal.connect(lambda o: print(f"[CANCELLED] {o['id']}"))
manager.order_modified_signal.connect(lambda m: print(f"[MODIFIED] {m['order_id']}: {m['changes']}"))
manager.sl_hit_signal.connect(lambda s: print(f"[SL HIT] {s['symbol']} @ ₹{s['exit_price']} | P&L: ₹{s['pnl']}"))
manager.target_hit_signal.connect(lambda t: print(f"[TARGET HIT] {t['symbol']} @ ₹{t['exit_price']} | P&L: ₹{t['pnl']}"))
manager.pnl_update_signal.connect(lambda p: print(f"[MTM] {p['symbol']}: LTP=₹{p['ltp']} | Net P&L=₹{p['net_pnl']}"))
manager.total_pnl_signal.connect(lambda t: print(f"[TOTAL P&L] Realized=₹{t['realized']} | Unrealized=₹{t['unrealized']} | Fees=₹{t['fees_paid']}"))


def run_tests():
    """Run all tests sequentially."""
    
    print("\n" + "=" * 60)
    print("TEST 1: Lot Size Validation")
    print("=" * 60)
    
    # NIFTY lot size is 25, so 50 should be valid, 40 should be invalid
    token1 = 12345
    
    # Valid quantity (50 = 2 lots of 25)
    order_id = manager.place_order(
        token=token1,
        trading_symbol="NIFTY23DEC25C24000",
        action="BUY",
        price_limit=100.0,
        quantity=50,  # 2 lots
        validity=OrderValidity.DAY
    )
    print(f"  Valid order (50 qty): {'✅ Accepted' if order_id else '❌ Rejected'}")
    
    # Invalid quantity (40 is not a multiple of 25)
    order_id_invalid = manager.place_order(
        token=token1,
        trading_symbol="NIFTY23DEC25C24000",
        action="BUY",
        price_limit=100.0,
        quantity=40,  # Not a valid lot
        validity=OrderValidity.DAY
    )
    print(f"  Invalid order (40 qty): {'❌ Should be rejected' if order_id_invalid else '✅ Correctly Rejected'}")
    
    time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("TEST 2: Stop-Loss and Target Orders")
    print("=" * 60)
    
    token2 = 23456
    
    # Place order with SL and Target
    order_id_sl = manager.place_order(
        token=token2,
        trading_symbol="BANKNIFTY30DEC25C52000",
        action="BUY",
        price_limit=200.0,
        quantity=15,  # 1 lot of BANKNIFTY
        stop_loss=180.0,  # SL at 180
        target=250.0,     # Target at 250
        validity=OrderValidity.DAY
    )
    print(f"  Order with SL/Target placed: {order_id_sl}")
    
    # Execute the order
    print("\n  Simulating price hitting limit...")
    manager.on_tick({'token': token2, 'ltp': 199.0})  # Below limit, should execute
    time.sleep(0.5)
    
    # Price moves up (profitable)
    print("  Price moving up to 220...")
    manager.on_tick({'token': token2, 'ltp': 220.0})
    time.sleep(0.5)
    
    # Price hits target
    print("  Price hitting target at 250...")
    manager.on_tick({'token': token2, 'ltp': 251.0})  # Above target
    time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("TEST 3: Order Cancellation")
    print("=" * 60)
    
    token3 = 34567
    
    # Place an order
    order_id_cancel = manager.place_order(
        token=token3,
        trading_symbol="TCS30DEC25P3200",
        action="SELL",
        price_limit=50.0,
        quantity=150,  # TCS lot size is 150
        validity=OrderValidity.DAY
    )
    print(f"  Order placed: {order_id_cancel}")
    
    # Cancel it before execution
    print(f"  Cancelling order...")
    result = manager.cancel_order(order_id_cancel)
    print(f"  Cancel result: {'✅ Success' if result else '❌ Failed'}")
    
    time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("TEST 4: Order Modification")
    print("=" * 60)
    
    token4 = 45678
    
    # Place an order
    order_id_mod = manager.place_order(
        token=token4,
        trading_symbol="RELIANCE30DEC25C1300",
        action="BUY",
        price_limit=30.0,
        quantity=250,  # RELIANCE lot size is 250
        stop_loss=25.0,
        validity=OrderValidity.DAY
    )
    print(f"  Original order: Limit=30, SL=25")
    
    # Modify limit price and SL
    result = manager.modify_order(
        order_id_mod,
        new_limit_price=32.0,
        new_stop_loss=28.0
    )
    print(f"  Modified to: Limit=32, SL=28 - {'✅ Success' if result else '❌ Failed'}")
    
    # Check modified order
    order = manager.get_order(order_id_mod)
    if order:
        print(f"  Verified: Limit={order['limit_price']}, SL={order['stop_loss']}")
    
    time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("TEST 5: Multiple Orders & Position Averaging")
    print("=" * 60)
    
    token5 = 56789
    
    # Place first order
    order1 = manager.place_order(
        token=token5,
        trading_symbol="NIFTY23DEC25P23500",
        action="BUY",
        price_limit=150.0,
        quantity=25,  # 1 lot
        validity=OrderValidity.DAY
    )
    
    # Place second order (same symbol, same action - should average)
    order2 = manager.place_order(
        token=token5,
        trading_symbol="NIFTY23DEC25P23500",
        action="BUY",
        price_limit=160.0,
        quantity=50,  # 2 lots
        validity=OrderValidity.DAY
    )
    
    print(f"  Order 1: 25 qty @ limit 150")
    print(f"  Order 2: 50 qty @ limit 160")
    
    # Execute first order at 148
    print("\n  Executing first order at 148...")
    manager.on_tick({'token': token5, 'ltp': 148.0})
    time.sleep(0.5)
    
    # Execute second order at 158 (should average)
    print("  Executing second order at 158...")
    manager.on_tick({'token': token5, 'ltp': 158.0})
    time.sleep(0.5)
    
    # Check averaged position
    positions = manager.get_open_positions()
    for pos in positions:
        if pos['token'] == token5:
            print(f"  Averaged Position: Qty={pos['quantity']}, Avg Price=₹{pos['entry_price']:.2f}")
    
    print("\n" + "=" * 60)
    print("TEST 6: Stop-Loss Hit Scenario")
    print("=" * 60)
    
    token6 = 67890
    
    # Place order with tight SL
    order_sl = manager.place_order(
        token=token6,
        trading_symbol="INFY30DEC25C1800",
        action="BUY",
        price_limit=40.0,
        quantity=300,  # INFY lot size is 300
        stop_loss=35.0,
        validity=OrderValidity.DAY
    )
    
    # Execute
    print("  Executing order...")
    manager.on_tick({'token': token6, 'ltp': 39.0})
    time.sleep(0.5)
    
    # Price drops, hits SL
    print("  Price dropping to 34 (below SL)...")
    manager.on_tick({'token': token6, 'ltp': 34.0})
    time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("TEST 7: P&L Summary")
    print("=" * 60)
    
    summary = manager.get_pnl_summary()
    print(f"  Realized P&L: ₹{summary['realized_pnl']}")
    print(f"  Unrealized P&L: ₹{summary['unrealized_pnl']}")
    print(f"  Total P&L: ₹{summary['total_pnl']}")
    print(f"  Total Fees Paid: ₹{summary['total_fees']}")
    print(f"  Open Positions: {summary['open_positions']}")
    print(f"  Pending Orders: {summary['pending_orders']}")
    print(f"  Closed Trades: {summary['closed_trades']}")
    
    print("\n" + "=" * 60)
    print("TEST 8: Square Off All Remaining Positions")
    print("=" * 60)
    
    count = manager.square_off_all()
    print(f"  Squared off {count} positions")
    
    # Final summary
    final_summary = manager.get_pnl_summary()
    print(f"\n  Final Realized P&L: ₹{final_summary['realized_pnl']}")
    print(f"  Final Total Fees: ₹{final_summary['total_fees']}")
    
    print("\n" + "=" * 60)
    print("✅ All Tests Completed!")
    print("=" * 60)
    
    # Quit after tests
    app.quit()


# Run tests after a short delay
QTimer.singleShot(500, run_tests)

# Start event loop
print("\nStarting tests...")
exit_code = app.exec()

print("✅ Test suite finished.")
sys.exit(exit_code)
