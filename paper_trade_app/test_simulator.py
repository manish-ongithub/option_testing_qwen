"""
Test Script for Market Tick Simulator

Tests the simulator independently to verify:
1. Price generation (GBM, volatility clustering, jumps)
2. SimulatorWorker integration
3. Pre-defined scenarios
4. Integration with TradeManager
"""

import sys
import signal
from PyQt6.QtCore import QCoreApplication, QTimer
from core.simulator_worker import SimulatorWorker, MockInstrument, create_mock_instruments
from core.trade_manager import TradeManager, OrderValidity
from core.market_simulator import PriceEngine, SimulatorConfig, SIMULATION_SCENARIOS

# Setup App
app = QCoreApplication(sys.argv)

# Enable Ctrl+C
def signal_handler(signum, frame):
    print("\n🛑 Stopping simulation...")
    app.quit()

signal.signal(signal.SIGINT, signal_handler)

# Timer for signal processing
timer = QTimer()
timer.timeout.connect(lambda: None)
timer.start(100)

print("=" * 70)
print("🎮 Market Tick Simulator Test Suite")
print("=" * 70)


def test_price_engine():
    """Test the PriceEngine directly."""
    print("\n" + "=" * 70)
    print("TEST 1: PriceEngine - Basic Price Generation")
    print("=" * 70)
    
    engine = PriceEngine(initial_price=100.0)
    
    print(f"Initial Price: ₹{engine.price:.2f}")
    print("\nGenerating 20 ticks...")
    
    prices = []
    for i in range(20):
        ltp, bid, ask, volume = engine.next_tick()
        prices.append(ltp)
        change = ((ltp - 100) / 100) * 100
        print(f"  Tick {i+1:2d}: LTP=₹{ltp:7.2f} | Bid=₹{bid:7.2f} | Ask=₹{ask:7.2f} | Vol={volume:5d} | Chg={change:+.2f}%")
    
    # Statistics
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    
    print(f"\nStatistics:")
    print(f"  Min: ₹{min_price:.2f}")
    print(f"  Max: ₹{max_price:.2f}")
    print(f"  Avg: ₹{avg_price:.2f}")
    print(f"  Range: {((max_price - min_price) / 100) * 100:.2f}%")


def test_scenarios():
    """Test pre-defined scenarios."""
    print("\n" + "=" * 70)
    print("TEST 2: Pre-defined Scenarios")
    print("=" * 70)
    
    for scenario_name, config in SIMULATION_SCENARIOS.items():
        engine = PriceEngine(initial_price=100.0, config=config)
        
        # Generate 50 ticks
        for _ in range(50):
            engine.next_tick()
        
        final_price = engine.price
        change = ((final_price - 100) / 100) * 100
        
        direction = "📈" if change > 1 else "📉" if change < -1 else "➡️"
        print(f"  {scenario_name:20s}: ₹{final_price:7.2f} ({change:+6.2f}%) {direction}")


def test_simulator_worker():
    """Test SimulatorWorker with TradeManager."""
    print("\n" + "=" * 70)
    print("TEST 3: SimulatorWorker + TradeManager Integration")
    print("=" * 70)
    
    # Create components
    manager = TradeManager()
    worker = SimulatorWorker()
    
    # Tick counter
    tick_count = [0]
    
    # Connect signals
    def on_connected(connected, msg):
        print(f"📡 Connection: {msg}")
        if connected:
            # Subscribe to mock instruments
            instruments = create_mock_instruments(3)
            worker.subscribe_tokens(instruments)
            print(f"   Subscribed to {len(instruments)} instruments")
            
            # Place test orders
            for inst in instruments:
                # Set initial price for the simulator
                worker.set_initial_price(inst.token, 150.0)
                
                # Place order with SL and target
                order_id = manager.place_order(
                    token=inst.token,
                    trading_symbol=inst.name,
                    action="BUY",
                    price_limit=155.0,
                    quantity=inst.lot_size,
                    stop_loss=140.0,
                    target=170.0,
                    validity=OrderValidity.DAY
                )
                print(f"   Order placed: {order_id} for {inst.name}")
    
    def on_tick(tick):
        tick_count[0] += 1
        manager.on_tick(tick)
        
        if tick_count[0] <= 5:
            token = tick.get('token')
            ltp = tick.get('ltp')
            print(f"   Tick #{tick_count[0]}: Token={token} LTP=₹{ltp:.2f}")
        elif tick_count[0] == 6:
            print(f"   ... (continuing to receive ticks)")
    
    def on_pnl_update(data):
        symbol = data.get('symbol', 'Unknown')
        net_pnl = data.get('net_pnl', 0)
        print(f"   💰 MTM Update: {symbol} P&L=₹{net_pnl:.2f}")
    
    def on_sl_hit(data):
        print(f"   🛑 SL HIT: {data.get('symbol')} @ ₹{data.get('exit_price'):.2f}")
    
    def on_target_hit(data):
        print(f"   🎯 TARGET HIT: {data.get('symbol')} @ ₹{data.get('exit_price'):.2f}")
    
    # Connect signals
    worker.connection_signal.connect(on_connected)
    worker.tick_signal.connect(on_tick)
    manager.pnl_update_signal.connect(on_pnl_update)
    manager.sl_hit_signal.connect(on_sl_hit)
    manager.target_hit_signal.connect(on_target_hit)
    manager.log_signal.connect(lambda msg: print(f"   [LOG] {msg}"))
    
    # Start worker
    worker.start()
    
    # Stop after 10 seconds
    def stop_test():
        print(f"\n   Total ticks received: {tick_count[0]}")
        print(f"   Pending orders: {len(manager.get_pending_orders())}")
        print(f"   Open positions: {len(manager.get_open_positions())}")
        
        summary = manager.get_pnl_summary()
        print(f"\n   P&L Summary:")
        print(f"     Realized: ₹{summary['realized_pnl']:.2f}")
        print(f"     Unrealized: ₹{summary['unrealized_pnl']:.2f}")
        print(f"     Total Fees: ₹{summary['total_fees']:.2f}")
        
        worker.stop()
        worker.wait()
        app.quit()
    
    QTimer.singleShot(10000, stop_test)
    print("\n   Running for 10 seconds...")


def test_scenario_application():
    """Test applying scenarios dynamically."""
    print("\n" + "=" * 70)
    print("TEST 4: Dynamic Scenario Application")
    print("=" * 70)
    
    worker = SimulatorWorker()
    
    tick_count = [0]
    scenario_prices = {}
    
    def on_connected(connected, msg):
        if connected:
            # Create a mock instrument
            inst = MockInstrument(99999, "TEST", "TEST_INSTRUMENT", lot_size=1)
            worker.set_initial_price(99999, 100.0)
            worker.subscribe_tokens([inst])
            
            # Apply trending up scenario
            print("   Applying 'trending_up' scenario...")
            worker.set_scenario("trending_up", 99999)
    
    def on_tick(tick):
        tick_count[0] += 1
        ltp = tick.get('ltp', 0)
        
        if tick_count[0] <= 20:
            scenario_prices.setdefault('trending_up', []).append(ltp)
        elif tick_count[0] == 21:
            # Switch to trending down
            print("   Applying 'trending_down' scenario...")
            worker.set_scenario("trending_down", 99999)
        elif tick_count[0] <= 40:
            scenario_prices.setdefault('trending_down', []).append(ltp)
    
    def stop_test():
        print("\n   Results:")
        for scenario, prices in scenario_prices.items():
            if prices:
                start = prices[0]
                end = prices[-1]
                change = ((end - start) / start) * 100
                print(f"     {scenario}: ₹{start:.2f} -> ₹{end:.2f} ({change:+.2f}%)")
        
        worker.stop()
        worker.wait()
        app.quit()
    
    worker.connection_signal.connect(on_connected)
    worker.tick_signal.connect(on_tick)
    worker.start()
    
    QTimer.singleShot(12000, stop_test)
    print("   Running scenario comparison for 12 seconds...")


def run_quick_test():
    """Run a quick test of all components."""
    print("\n" + "=" * 70)
    print("QUICK TEST: Verify All Components")
    print("=" * 70)
    
    # Test 1: Price Engine
    print("\n✓ Testing PriceEngine...")
    engine = PriceEngine(100.0)
    ltp, bid, ask, vol = engine.next_tick()
    assert ltp > 0, "Price should be positive"
    assert bid < ask, "Bid should be less than ask"
    print(f"  Price: ₹{ltp:.2f}, Spread: ₹{ask-bid:.4f}")
    
    # Test 2: Simulator Worker Creation
    print("\n✓ Testing SimulatorWorker...")
    worker = SimulatorWorker()
    assert worker is not None, "Worker should be created"
    print(f"  Worker created, scenarios available: {len(worker.get_available_scenarios())}")
    
    # Test 3: Mock Instruments
    print("\n✓ Testing MockInstruments...")
    instruments = create_mock_instruments(5)
    assert len(instruments) == 5, "Should create 5 instruments"
    print(f"  Created {len(instruments)} mock instruments")
    for inst in instruments:
        print(f"    - {inst.name} (token={inst.token}, lot={inst.lot_size})")
    
    # Test 4: Trade Manager Integration
    print("\n✓ Testing TradeManager...")
    manager = TradeManager()
    order_id = manager.place_order(
        token=12345,
        trading_symbol="TEST_OPTION",
        action="BUY",
        price_limit=100.0,
        quantity=25,  # NIFTY lot
        stop_loss=90.0,
        target=120.0
    )
    assert order_id is not None, "Order should be placed"
    print(f"  Order placed: {order_id}")
    
    print("\n" + "=" * 70)
    print("✅ All Quick Tests Passed!")
    print("=" * 70)


# Main execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Market Simulator Test Suite")
    parser.add_argument("--test", choices=["quick", "engine", "scenarios", "worker", "dynamic", "all"],
                       default="quick", help="Test to run")
    args = parser.parse_args()
    
    if args.test == "quick":
        run_quick_test()
        sys.exit(0)
    elif args.test == "engine":
        test_price_engine()
        sys.exit(0)
    elif args.test == "scenarios":
        test_scenarios()
        sys.exit(0)
    elif args.test == "worker":
        test_simulator_worker()
    elif args.test == "dynamic":
        test_scenario_application()
    elif args.test == "all":
        run_quick_test()
        test_price_engine()
        test_scenarios()
        print("\n⚠️ For interactive tests (worker, dynamic), run separately:")
        print("   python test_simulator.py --test worker")
        print("   python test_simulator.py --test dynamic")
        sys.exit(0)
    
    # Run event loop for interactive tests
    print("\nPress Ctrl+C to stop...")
    sys.exit(app.exec())
