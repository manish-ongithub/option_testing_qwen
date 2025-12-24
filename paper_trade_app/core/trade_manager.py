"""
Enhanced Trade Manager for Options Paper Trading

Features:
- Multiple orders per symbol
- Lot size validation
- Market hours enforcement
- Stop-loss and target orders
- Order cancellation/modification
- Slippage simulation
- DAY/IOC order validity
- Position averaging
- Realized/unrealized P&L tracking
- Configurable transaction costs
- PostgreSQL persistence (optional)
- Session resume capability
"""

import datetime
from datetime import time
import logging
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from collections import defaultdict
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from core.fee_calculator import (
    FeeConfig, FeeBreakdown, calculate_fees, 
    ALICE_BLUE_FEES, ZERODHA_FEES, FLAT_FEE_CONFIG
)
from core.lot_sizes import validate_quantity, get_lot_size

# Type hint for SessionManager without circular import
if TYPE_CHECKING:
    from core.session_manager import SessionManager

# Import config with defaults
try:
    from config import (
        SLIPPAGE_PERCENT, ENFORCE_MARKET_HOURS, ALLOW_AMO,
        MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE,
        MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE,
        FEE_CONFIG_NAME, CUSTOM_FEE_CONFIG
    )
except ImportError:
    SLIPPAGE_PERCENT = 0.1
    ENFORCE_MARKET_HOURS = True
    ALLOW_AMO = True
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 15
    MARKET_CLOSE_HOUR = 15
    MARKET_CLOSE_MINUTE = 30
    FEE_CONFIG_NAME = "ALICE_BLUE"
    CUSTOM_FEE_CONFIG = {}

logger = logging.getLogger("TradeManager")


class OrderStatus:
    PENDING = "PENDING"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderValidity:
    DAY = "DAY"
    IOC = "IOC"
    AMO = "AMO"


class TradeManager(QObject):
    """Enhanced Trade Manager with realistic paper trading features."""
    
    # --- Signals to Update UI ---
    log_signal = pyqtSignal(str)                 # Text for the Log Panel
    order_placed_signal = pyqtSignal(dict)       # New order placed
    order_filled_signal = pyqtSignal(dict)       # Order executed, add to positions
    order_rejected_signal = pyqtSignal(dict)     # Order rejected (validation failed)
    order_cancelled_signal = pyqtSignal(dict)    # Order cancelled
    order_modified_signal = pyqtSignal(dict)     # Order modified
    pnl_update_signal = pyqtSignal(dict)         # Update P&L in positions table
    sl_hit_signal = pyqtSignal(dict)             # Stop-loss triggered
    target_hit_signal = pyqtSignal(dict)         # Target triggered
    position_closed_signal = pyqtSignal(dict)    # Position squared off
    total_pnl_signal = pyqtSignal(dict)          # Dashboard summary P&L

    def __init__(self, fee_config: FeeConfig = None, session_manager: "SessionManager" = None):
        super().__init__()
        
        # Fee configuration
        self.fee_config = fee_config or self._get_fee_config()
        
        # Session manager for persistence (optional)
        self._session_manager = session_manager
        
        # Data Stores - Using lists to support multiple orders per token
        # Key: Token ID (int), Value: List of orders
        self.pending_orders: Dict[int, List[dict]] = defaultdict(list)
        self.open_positions: Dict[int, List[dict]] = defaultdict(list)
        
        # Order lookup by ID for quick access
        self._order_index: Dict[str, dict] = {}
        
        # P&L Tracking
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.total_fees_paid = 0.0
        
        # History (for Reporting)
        self.trade_history: List[dict] = []
        
        # Order counter for unique IDs
        self._order_counter = 0
        
        # Market hours
        self.market_open = time(MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)
        self.market_close = time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
        
        # IOC tracking (orders checked but not filled)
        self._ioc_checked: set = set()
        
        # Day order expiry timer
        self._setup_day_order_timer()
        
        # Persistence update throttle (avoid too frequent DB updates)
        self._last_pnl_persist_time = 0
        self._pnl_persist_interval = 5  # seconds
        
        logger.info(f"TradeManager initialized with {self.fee_config.broker_name} fee structure")

    def _get_fee_config(self) -> FeeConfig:
        """Get fee configuration based on config setting."""
        config_map = {
            "ALICE_BLUE": ALICE_BLUE_FEES,
            "ZERODHA": ZERODHA_FEES,
            "FLAT_FEE": FLAT_FEE_CONFIG,
        }
        
        if FEE_CONFIG_NAME == "CUSTOM" and CUSTOM_FEE_CONFIG:
            return FeeConfig(**CUSTOM_FEE_CONFIG)
        
        return config_map.get(FEE_CONFIG_NAME, ALICE_BLUE_FEES)

    def _setup_day_order_timer(self):
        """Setup timer to expire DAY orders at market close."""
        self._day_order_timer = QTimer()
        self._day_order_timer.timeout.connect(self._check_day_order_expiry)
        self._day_order_timer.start(60000)  # Check every minute

    def set_session_manager(self, session_manager: "SessionManager"):
        """
        Set the session manager for persistence.
        
        Args:
            session_manager: SessionManager instance
        """
        self._session_manager = session_manager
        if session_manager:
            session_manager.set_trade_manager(self)
    
    def _persist_order(self, order: dict):
        """Persist order to database via session manager."""
        if self._session_manager:
            self._session_manager.on_order_placed(order)
    
    def _persist_order_update(self, order_id: str, updates: dict):
        """Persist order update to database."""
        if self._session_manager:
            self._session_manager.on_order_updated(order_id, updates)
    
    def _persist_pnl(self):
        """Persist P&L counters to database (throttled)."""
        if not self._session_manager:
            return
        
        import time as time_module
        current_time = time_module.time()
        
        # Throttle updates to avoid excessive DB writes
        if current_time - self._last_pnl_persist_time < self._pnl_persist_interval:
            return
        
        self._last_pnl_persist_time = current_time
        self._session_manager.on_pnl_updated(
            self.realized_pnl,
            self.unrealized_pnl,
            self.total_fees_paid,
            self._order_counter
        )
    
    def restore_state(self, state: Dict[str, Any]):
        """
        Restore trading state from a previous session.
        
        Args:
            state: Dict containing:
                - pending_orders: List of pending order dicts
                - open_positions: List of open position dicts
                - realized_pnl: float
                - unrealized_pnl: float
                - total_fees: float
                - order_counter: int
        """
        # Restore P&L counters
        self.realized_pnl = state.get('realized_pnl', 0.0)
        self.unrealized_pnl = state.get('unrealized_pnl', 0.0)
        self.total_fees_paid = state.get('total_fees', 0.0)
        self._order_counter = state.get('order_counter', 0)
        
        # Restore pending orders
        pending_orders = state.get('pending_orders', [])
        for order in pending_orders:
            token = order['token']
            self.pending_orders[token].append(order)
            self._order_index[order['id']] = order
        
        # Restore open positions
        open_positions = state.get('open_positions', [])
        for position in open_positions:
            token = position['token']
            self.open_positions[token].append(position)
            self._order_index[position['id']] = position
        
        logger.info(
            f"State restored: {len(pending_orders)} pending orders, "
            f"{len(open_positions)} open positions, "
            f"₹{self.realized_pnl:.2f} realized P&L"
        )
        
        # Emit total P&L
        self._emit_total_pnl()
    
    def get_subscribed_tokens(self) -> List[int]:
        """Get list of all tokens that need subscription (pending + open)."""
        tokens = set()
        
        for token in self.pending_orders.keys():
            tokens.add(token)
        
        for token in self.open_positions.keys():
            tokens.add(token)
        
        return list(tokens)

    def _generate_order_id(self) -> str:
        """Generate unique order ID."""
        self._order_counter += 1
        timestamp = datetime.datetime.now().strftime('%H%M%S%f')[:10]
        return f"ORD_{self._order_counter}_{timestamp}"

    # ==================== VALIDATION ====================
    
    def _is_market_open(self) -> bool:
        """Check if market is currently open."""
        if not ENFORCE_MARKET_HOURS:
            return True
        
        now = datetime.datetime.now().time()
        # Check if it's a weekday (Monday = 0, Sunday = 6)
        if datetime.datetime.now().weekday() >= 5:
            return False
        
        return self.market_open <= now <= self.market_close

    def _validate_order(
        self, 
        trading_symbol: str, 
        quantity: int, 
        validity: str,
        instrument: object = None
    ) -> tuple[bool, str]:
        """
        Validate order before placement.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # 1. Quantity validation
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        # 2. Lot size validation
        is_valid_qty, qty_error = validate_quantity(trading_symbol, quantity, instrument)
        if not is_valid_qty:
            return False, qty_error
        
        # 3. Market hours validation
        if validity != OrderValidity.AMO and not self._is_market_open():
            if ALLOW_AMO:
                return False, f"Market is closed. Use AMO (After Market Order) instead."
            else:
                return False, "Market is closed. Orders not allowed."
        
        return True, ""

    # ==================== ORDER PLACEMENT ====================
    
    def place_order(
        self,
        token: int,
        trading_symbol: str,
        action: str,
        price_limit: float,
        quantity: int,
        stop_loss: float = None,
        target: float = None,
        validity: str = OrderValidity.DAY,
        sl_order_type: str = "MARKET",
        instrument: object = None
    ) -> Optional[str]:
        """
        Place a new order with validation.
        
        Args:
            token: Instrument token
            trading_symbol: Trading symbol name
            action: "BUY" or "SELL"
            price_limit: Limit price for entry
            quantity: Order quantity
            stop_loss: Stop-loss price (optional)
            target: Target price (optional)
            validity: "DAY", "IOC", or "AMO"
            sl_order_type: "MARKET" or "LIMIT" for SL exit
            instrument: Instrument object for lot size lookup
        
        Returns:
            Order ID if successful, None if rejected
        """
        token = int(token)
        action = action.upper()
        
        # Validate order
        is_valid, error_msg = self._validate_order(
            trading_symbol, quantity, validity, instrument
        )
        
        if not is_valid:
            rejection = {
                "symbol": trading_symbol,
                "action": action,
                "quantity": quantity,
                "reason": error_msg
            }
            self.order_rejected_signal.emit(rejection)
            self.log_signal.emit(f"❌ Order Rejected: {trading_symbol} - {error_msg}")
            return None
        
        # Create order
        order_id = self._generate_order_id()
        lot_size = get_lot_size(trading_symbol, instrument)
        
        order = {
            "id": order_id,
            "token": token,
            "symbol": trading_symbol,
            "action": action,
            "limit_price": float(price_limit),
            "quantity": int(quantity),
            "lot_size": lot_size,
            "lots": quantity // lot_size,
            "status": OrderStatus.PENDING,
            "validity": validity,
            "stop_loss": float(stop_loss) if stop_loss else None,
            "target": float(target) if target else None,
            "sl_order_type": sl_order_type,
            "placed_at": datetime.datetime.now(),
            "entry_time": None,
            "entry_price": 0.0,
            "exit_time": None,
            "exit_price": 0.0,
            "ltp": 0.0,
            "gross_pnl": 0.0,
            "entry_fees": 0.0,
            "exit_fees": 0.0,
            "net_pnl": 0.0,
            "exit_reason": None,
        }
        
        # Add to pending orders
        self.pending_orders[token].append(order)
        self._order_index[order_id] = order
        
        # Persist to database
        self._persist_order(order)
        
        self.log_signal.emit(
            f"📝 Order Placed: {action} {quantity} {trading_symbol} @ Limit ₹{price_limit}"
            + (f" | SL: ₹{stop_loss}" if stop_loss else "")
            + (f" | Target: ₹{target}" if target else "")
            + f" | Validity: {validity}"
        )
        self.order_placed_signal.emit(order)
        
        return order_id

    # ==================== ORDER MANAGEMENT ====================
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a pending order.
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if cancelled, False if not found or already executed
        """
        order = self._order_index.get(order_id)
        
        if not order:
            self.log_signal.emit(f"❌ Cancel failed: Order {order_id} not found")
            return False
        
        if order['status'] != OrderStatus.PENDING:
            self.log_signal.emit(f"❌ Cancel failed: Order {order_id} is not pending")
            return False
        
        token = order['token']
        
        # Remove from pending orders
        if token in self.pending_orders:
            self.pending_orders[token] = [
                o for o in self.pending_orders[token] if o['id'] != order_id
            ]
            if not self.pending_orders[token]:
                del self.pending_orders[token]
        
        order['status'] = OrderStatus.CANCELLED
        del self._order_index[order_id]
        
        # Persist cancellation to database
        self._persist_order_update(order_id, {'status': OrderStatus.CANCELLED})
        
        self.log_signal.emit(f"🚫 Order Cancelled: {order['symbol']} {order['action']}")
        self.order_cancelled_signal.emit(order)
        
        return True

    def modify_order(
        self,
        order_id: str,
        new_limit_price: float = None,
        new_quantity: int = None,
        new_stop_loss: float = None,
        new_target: float = None
    ) -> bool:
        """
        Modify a pending order.
        
        Args:
            order_id: Order ID to modify
            new_limit_price: New limit price (optional)
            new_quantity: New quantity (optional)
            new_stop_loss: New stop-loss (optional)
            new_target: New target (optional)
        
        Returns:
            True if modified, False if failed
        """
        order = self._order_index.get(order_id)
        
        if not order:
            self.log_signal.emit(f"❌ Modify failed: Order {order_id} not found")
            return False
        
        if order['status'] != OrderStatus.PENDING:
            self.log_signal.emit(f"❌ Modify failed: Order {order_id} is not pending")
            return False
        
        changes = {}
        
        if new_limit_price is not None:
            changes['limit_price'] = (order['limit_price'], new_limit_price)
            order['limit_price'] = float(new_limit_price)
        
        if new_quantity is not None:
            # Validate new quantity
            is_valid, error = validate_quantity(order['symbol'], new_quantity)
            if not is_valid:
                self.log_signal.emit(f"❌ Modify failed: {error}")
                return False
            changes['quantity'] = (order['quantity'], new_quantity)
            order['quantity'] = int(new_quantity)
            order['lots'] = new_quantity // order['lot_size']
        
        if new_stop_loss is not None:
            changes['stop_loss'] = (order['stop_loss'], new_stop_loss)
            order['stop_loss'] = float(new_stop_loss) if new_stop_loss else None
        
        if new_target is not None:
            changes['target'] = (order['target'], new_target)
            order['target'] = float(new_target) if new_target else None
        
        if changes:
            # Persist changes to database
            db_updates = {}
            for key in changes:
                db_updates[key] = order[key]
            self._persist_order_update(order_id, db_updates)
            
            self.log_signal.emit(f"✏️ Order Modified: {order['symbol']} - {changes}")
            self.order_modified_signal.emit({"order_id": order_id, "changes": changes})
        
        return True

    def get_order(self, order_id: str) -> Optional[dict]:
        """Get order by ID."""
        return self._order_index.get(order_id)

    def get_pending_orders(self) -> List[dict]:
        """Get all pending orders."""
        orders = []
        for token_orders in self.pending_orders.values():
            orders.extend(token_orders)
        return orders

    def get_open_positions(self) -> List[dict]:
        """Get all open positions."""
        positions = []
        for token_positions in self.open_positions.values():
            positions.extend(token_positions)
        return positions

    # ==================== TICK PROCESSING ====================
    
    def on_tick(self, tick_data: dict):
        """
        Process incoming tick data.
        
        Args:
            tick_data: {'token': int, 'ltp': float, ...}
        """
        token = int(tick_data.get('token'))
        ltp = float(tick_data.get('ltp'))
        
        # 1. Check pending orders for execution
        if token in self.pending_orders:
            self._check_execution(token, ltp)
        
        # 2. Update open positions MTM and check SL/Target
        if token in self.open_positions:
            self._update_positions(token, ltp)
        
        # 3. Emit total P&L update
        self._emit_total_pnl()

    def _check_execution(self, token: int, ltp: float):
        """Check if any pending orders should be executed."""
        orders_to_execute = []
        orders_to_cancel = []
        
        for order in self.pending_orders[token]:
            limit_price = order['limit_price']
            action = order['action']
            validity = order['validity']
            order_id = order['id']
            
            should_execute = False
            
            # BUY: Fill if price drops to or below limit
            if action == "BUY" and ltp <= limit_price:
                should_execute = True
            
            # SELL: Fill if price rises to or above limit
            elif action == "SELL" and ltp >= limit_price:
                should_execute = True
            
            if should_execute:
                orders_to_execute.append(order)
            elif validity == OrderValidity.IOC and order_id not in self._ioc_checked:
                # IOC order not filled on first check - cancel it
                self._ioc_checked.add(order_id)
                orders_to_cancel.append(order)
        
        # Execute orders
        for order in orders_to_execute:
            self._execute_order(order, ltp)
        
        # Cancel unfilled IOC orders
        for order in orders_to_cancel:
            self.cancel_order(order['id'])
            self.log_signal.emit(f"⏱️ IOC Order expired: {order['symbol']}")

    def _execute_order(self, order: dict, ltp: float):
        """Execute a pending order."""
        token = order['token']
        order_id = order['id']
        
        # Apply slippage
        fill_price = self._apply_slippage(ltp, order['action'])
        
        # Calculate entry fees
        entry_fees = calculate_fees(
            fill_price, order['quantity'], order['action'], 
            fee_config=self.fee_config
        )
        
        # Update order
        order['status'] = OrderStatus.OPEN
        order['entry_price'] = fill_price
        order['entry_time'] = datetime.datetime.now().strftime("%H:%M:%S")
        order['ltp'] = ltp
        order['entry_fees'] = entry_fees.total
        self.total_fees_paid += entry_fees.total
        
        # Check if we should average with existing position
        existing_position = self._find_matching_position(token, order['action'])
        
        if existing_position:
            # Average the positions
            self._average_position(existing_position, order)
        else:
            # Add as new position
            self.open_positions[token].append(order)
        
        # Remove from pending
        self.pending_orders[token] = [
            o for o in self.pending_orders[token] if o['id'] != order_id
        ]
        if not self.pending_orders[token]:
            del self.pending_orders[token]
        
        # Persist order execution to database
        self._persist_order_update(order_id, {
            'status': OrderStatus.OPEN,
            'entry_price': fill_price,
            'entry_time': order['entry_time'],
            'ltp': ltp,
            'entry_fees': entry_fees.total
        })
        
        self.log_signal.emit(
            f"⚡ EXECUTED: {order['action']} {order['symbol']} "
            f"@ ₹{fill_price:.2f} (Fees: ₹{entry_fees.total:.2f})"
        )
        self.order_filled_signal.emit(order)

    def _apply_slippage(self, price: float, action: str) -> float:
        """Apply slippage to execution price."""
        if SLIPPAGE_PERCENT <= 0:
            return price
        
        slippage_factor = SLIPPAGE_PERCENT / 100
        
        if action == "BUY":
            # Buyer pays slightly more
            return round(price * (1 + slippage_factor), 2)
        else:
            # Seller gets slightly less
            return round(price * (1 - slippage_factor), 2)

    def _find_matching_position(self, token: int, action: str) -> Optional[dict]:
        """Find existing position with same token and action for averaging."""
        if token not in self.open_positions:
            return None
        
        for position in self.open_positions[token]:
            if position['action'] == action and position['status'] == OrderStatus.OPEN:
                return position
        
        return None

    def _average_position(self, existing: dict, new_order: dict):
        """Average two positions together."""
        old_qty = existing['quantity']
        old_price = existing['entry_price']
        new_qty = new_order['quantity']
        new_price = new_order['entry_price']
        
        # Calculate weighted average
        total_qty = old_qty + new_qty
        avg_price = ((old_qty * old_price) + (new_qty * new_price)) / total_qty
        
        # Update existing position
        existing['quantity'] = total_qty
        existing['lots'] = total_qty // existing['lot_size']
        existing['entry_price'] = round(avg_price, 2)
        existing['entry_fees'] += new_order['entry_fees']
        
        # Use more favorable SL/Target
        if new_order['stop_loss']:
            if existing['stop_loss']:
                if existing['action'] == "BUY":
                    existing['stop_loss'] = max(existing['stop_loss'], new_order['stop_loss'])
                else:
                    existing['stop_loss'] = min(existing['stop_loss'], new_order['stop_loss'])
            else:
                existing['stop_loss'] = new_order['stop_loss']
        
        if new_order['target']:
            if existing['target']:
                if existing['action'] == "BUY":
                    existing['target'] = max(existing['target'], new_order['target'])
                else:
                    existing['target'] = min(existing['target'], new_order['target'])
            else:
                existing['target'] = new_order['target']
        
        # Remove new order from index (merged into existing)
        if new_order['id'] in self._order_index:
            del self._order_index[new_order['id']]
        
        self.log_signal.emit(
            f"📊 Position Averaged: {existing['symbol']} "
            f"Qty: {total_qty} @ Avg ₹{avg_price:.2f}"
        )

    def _update_positions(self, token: int, ltp: float):
        """Update MTM for all positions and check SL/Target."""
        positions_to_close = []
        
        for position in self.open_positions[token]:
            if position['status'] != OrderStatus.OPEN:
                continue
            
            entry_price = position['entry_price']
            qty = position['quantity']
            action = position['action']
            
            # Calculate gross P&L
            if action == "BUY":
                gross_pnl = (ltp - entry_price) * qty
            else:
                gross_pnl = (entry_price - ltp) * qty
            
            # Net P&L (gross - entry fees - estimated exit fees)
            estimated_exit_fees = calculate_fees(
                ltp, qty, "SELL" if action == "BUY" else "BUY",
                fee_config=self.fee_config
            ).total
            net_pnl = gross_pnl - position['entry_fees'] - estimated_exit_fees
            
            position['ltp'] = ltp
            position['gross_pnl'] = round(gross_pnl, 2)
            position['net_pnl'] = round(net_pnl, 2)
            
            # Emit P&L update
            self.pnl_update_signal.emit({
                "token": token,
                "order_id": position['id'],
                "symbol": position['symbol'],
                "ltp": ltp,
                "gross_pnl": position['gross_pnl'],
                "net_pnl": position['net_pnl'],
            })
            
            # Check SL/Target
            exit_reason = self._check_sl_target(position, ltp)
            if exit_reason:
                positions_to_close.append((position, exit_reason))
        
        # Close triggered positions
        for position, reason in positions_to_close:
            self._close_position(position, position['ltp'], reason)

    def _check_sl_target(self, position: dict, ltp: float) -> Optional[str]:
        """Check if SL or Target is hit."""
        action = position['action']
        stop_loss = position['stop_loss']
        target = position['target']
        
        if action == "BUY":
            # SL hit if price drops below SL
            if stop_loss and ltp <= stop_loss:
                return "SL_HIT"
            # Target hit if price rises above target
            if target and ltp >= target:
                return "TARGET_HIT"
        else:  # SELL
            # SL hit if price rises above SL
            if stop_loss and ltp >= stop_loss:
                return "SL_HIT"
            # Target hit if price drops below target
            if target and ltp <= target:
                return "TARGET_HIT"
        
        return None

    def _close_position(self, position: dict, exit_price: float, reason: str):
        """Close a position and calculate final P&L."""
        token = position['token']
        order_id = position['id']
        action = position['action']
        qty = position['quantity']
        entry_price = position['entry_price']
        
        # Apply slippage to exit
        exit_action = "SELL" if action == "BUY" else "BUY"
        final_exit_price = self._apply_slippage(exit_price, exit_action)
        
        # Calculate exit fees
        exit_fees = calculate_fees(
            final_exit_price, qty, exit_action, fee_config=self.fee_config
        )
        
        # Calculate final P&L
        if action == "BUY":
            gross_pnl = (final_exit_price - entry_price) * qty
        else:
            gross_pnl = (entry_price - final_exit_price) * qty
        
        net_pnl = gross_pnl - position['entry_fees'] - exit_fees.total
        
        # Update position
        position['status'] = OrderStatus.CLOSED
        position['exit_time'] = datetime.datetime.now().strftime("%H:%M:%S")
        position['exit_price'] = final_exit_price
        position['exit_fees'] = exit_fees.total
        position['gross_pnl'] = round(gross_pnl, 2)
        position['net_pnl'] = round(net_pnl, 2)
        position['exit_reason'] = reason
        
        # Update realized P&L
        self.realized_pnl += net_pnl
        self.total_fees_paid += exit_fees.total
        
        # Remove from open positions
        self.open_positions[token] = [
            p for p in self.open_positions[token] if p['id'] != order_id
        ]
        if not self.open_positions[token]:
            del self.open_positions[token]
        
        # Add to history
        self.trade_history.append(position)
        
        # Remove from order index
        if order_id in self._order_index:
            del self._order_index[order_id]
        
        # Persist position closure to database
        self._persist_order_update(order_id, {
            'status': OrderStatus.CLOSED,
            'exit_time': position['exit_time'],
            'exit_price': final_exit_price,
            'exit_fees': exit_fees.total,
            'gross_pnl': position['gross_pnl'],
            'net_pnl': position['net_pnl'],
            'exit_reason': reason
        })
        
        # Emit signals
        if reason == "SL_HIT":
            self.sl_hit_signal.emit({
                "order_id": order_id,
                "symbol": position['symbol'],
                "exit_price": final_exit_price,
                "pnl": position['net_pnl']
            })
            self.log_signal.emit(
                f"🛑 SL HIT: {position['symbol']} exited @ ₹{final_exit_price:.2f} "
                f"| P&L: ₹{position['net_pnl']:.2f}"
            )
        elif reason == "TARGET_HIT":
            self.target_hit_signal.emit({
                "order_id": order_id,
                "symbol": position['symbol'],
                "exit_price": final_exit_price,
                "pnl": position['net_pnl']
            })
            self.log_signal.emit(
                f"🎯 TARGET HIT: {position['symbol']} exited @ ₹{final_exit_price:.2f} "
                f"| P&L: ₹{position['net_pnl']:.2f}"
            )
        else:
            self.log_signal.emit(
                f"🚫 CLOSED: {position['symbol']} @ ₹{final_exit_price:.2f} "
                f"| P&L: ₹{position['net_pnl']:.2f}"
            )
        
        self.position_closed_signal.emit(position)

    def square_off_position(self, order_id: str) -> bool:
        """
        Manually square off an open position.
        
        Args:
            order_id: Order/position ID to close
        
        Returns:
            True if closed, False if not found
        """
        # Find the position
        for token, positions in self.open_positions.items():
            for position in positions:
                if position['id'] == order_id:
                    # Use LTP if available, otherwise use entry price as fallback
                    exit_price = position.get('ltp', 0.0)
                    if exit_price <= 0:
                        exit_price = position.get('entry_price', 0.0)
                        logger.warning(f"⚠️ No LTP for {order_id}, using entry price: {exit_price}")
                    
                    self._close_position(position, exit_price, "MANUAL")
                    return True
        
        self.log_signal.emit(f"❌ Position {order_id} not found")
        return False

    def square_off_all(self) -> int:
        """Square off all open positions. Returns count of closed positions."""
        count = 0
        all_positions = []
        
        for token, positions in list(self.open_positions.items()):
            for position in positions:
                all_positions.append(position)
        
        for position in all_positions:
            if self.square_off_position(position['id']):
                count += 1
        
        self.log_signal.emit(f"🚫 Squared off {count} positions")
        return count

    # ==================== DAY ORDER EXPIRY ====================
    
    def _check_day_order_expiry(self):
        """Check and expire DAY orders after market close."""
        now = datetime.datetime.now().time()
        
        if now <= self.market_close:
            return  # Market still open
        
        orders_to_cancel = []
        
        for token, orders in self.pending_orders.items():
            for order in orders:
                if order['validity'] == OrderValidity.DAY:
                    orders_to_cancel.append(order['id'])
        
        for order_id in orders_to_cancel:
            self.cancel_order(order_id)
            self.log_signal.emit(f"⏱️ DAY order expired: {order_id}")

    # ==================== P&L SUMMARY ====================
    
    def _emit_total_pnl(self):
        """Emit total P&L summary."""
        # Calculate unrealized P&L from open positions
        unrealized = 0.0
        for positions in self.open_positions.values():
            for position in positions:
                unrealized += position.get('net_pnl', 0.0)
        
        self.unrealized_pnl = round(unrealized, 2)
        
        total_pnl = self.realized_pnl + self.unrealized_pnl
        
        self.total_pnl_signal.emit({
            "realized": round(self.realized_pnl, 2),
            "unrealized": self.unrealized_pnl,
            "total": round(total_pnl, 2),
            "fees_paid": round(self.total_fees_paid, 2)
        })
        
        # Persist P&L to database (throttled)
        self._persist_pnl()

    def get_pnl_summary(self) -> dict:
        """Get current P&L summary."""
        self._emit_total_pnl()  # Refresh calculation
        return {
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": round(self.realized_pnl + self.unrealized_pnl, 2),
            "total_fees": round(self.total_fees_paid, 2),
            "open_positions": len(self.get_open_positions()),
            "pending_orders": len(self.get_pending_orders()),
            "closed_trades": len(self.trade_history)
        }

    def get_trade_history(self) -> List[dict]:
        """Get all closed trades."""
        return self.trade_history.copy()
