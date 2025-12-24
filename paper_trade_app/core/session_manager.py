"""
Session Manager for Paper Trading Application

Handles:
- Trading session lifecycle (create, resume, close)
- State persistence and restoration
- Integration between TradeManager and Database
"""

import logging
from typing import Optional, List, Dict, Any, Callable
from collections import defaultdict
from datetime import datetime

from core.database import DatabaseManager

logger = logging.getLogger("SessionManager")


class SessionManager:
    """
    Manages trading sessions and coordinates persistence between
    TradeManager and the database.
    
    Responsibilities:
    - Create new sessions
    - Detect and offer resume of previous sessions
    - Persist order state changes to database
    - Restore state from database on resume
    """
    
    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize SessionManager.
        
        Args:
            db_manager: Initialized DatabaseManager instance
        """
        self.db = db_manager
        self.current_session_id: Optional[str] = None
        self._trade_manager = None  # Set via set_trade_manager()
        self._subscribed_tokens: Dict[int, Dict[str, Any]] = {}
    
    def set_trade_manager(self, trade_manager):
        """
        Set reference to TradeManager for state restoration.
        
        Args:
            trade_manager: TradeManager instance
        """
        self._trade_manager = trade_manager
    
    def is_active(self) -> bool:
        """Check if there's an active session."""
        return self.current_session_id is not None
    
    def has_previous_session(self) -> bool:
        """
        Check if there's a previous active session that can be resumed.
        
        Returns:
            True if a resumable session exists
        """
        if not self.db.is_connected():
            return False
        
        session = self.db.get_active_session()
        return session is not None
    
    def get_previous_session_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the previous session for resume prompt.
        
        Returns:
            Session info dict or None
        """
        if not self.db.is_connected():
            return None
        
        session = self.db.get_active_session()
        if not session:
            return None
        
        # Get counts of orders by status
        session_id = str(session['id'])
        pending = self.db.get_orders_by_status(session_id, ['PENDING'])
        open_positions = self.db.get_orders_by_status(session_id, ['OPEN'])
        
        return {
            'session_id': session_id,
            'started_at': session['started_at'],
            'realized_pnl': session.get('realized_pnl', 0.0),
            'unrealized_pnl': session.get('unrealized_pnl', 0.0),
            'total_fees': session.get('total_fees', 0.0),
            'pending_orders_count': len(pending),
            'open_positions_count': len(open_positions),
            'order_counter': session.get('order_counter', 0)
        }
    
    def start_new_session(self) -> Optional[str]:
        """
        Start a new trading session.
        
        Returns:
            Session ID or None if failed
        """
        if not self.db.is_connected():
            logger.warning("Database not connected, running without persistence")
            return None
        
        # Close any existing active session
        existing = self.db.get_active_session()
        if existing:
            self.db.close_session(
                str(existing['id']),
                existing.get('realized_pnl', 0.0),
                existing.get('unrealized_pnl', 0.0),
                existing.get('total_fees', 0.0)
            )
        
        # Create new session
        self.current_session_id = self.db.create_session()
        if self.current_session_id:
            logger.info(f"Started new session: {self.current_session_id}")
        
        return self.current_session_id
    
    def resume_session(self) -> bool:
        """
        Resume the previous active session.
        
        Returns:
            True if resumed successfully
        """
        if not self.db.is_connected():
            return False
        
        session = self.db.get_active_session()
        if not session:
            logger.warning("No active session to resume")
            return False
        
        self.current_session_id = str(session['id'])
        logger.info(f"Resuming session: {self.current_session_id}")
        
        return True
    
    def restore_state(self) -> Dict[str, Any]:
        """
        Restore trading state from the current session.
        
        Must be called after resume_session() and set_trade_manager().
        
        Returns:
            Dict with restored state info:
            {
                'pending_orders': List[dict],
                'open_positions': List[dict],
                'realized_pnl': float,
                'unrealized_pnl': float,
                'total_fees': float,
                'order_counter': int,
                'subscriptions': List[dict]
            }
        """
        if not self.current_session_id or not self.db.is_connected():
            return {
                'pending_orders': [],
                'open_positions': [],
                'realized_pnl': 0.0,
                'unrealized_pnl': 0.0,
                'total_fees': 0.0,
                'order_counter': 0,
                'subscriptions': []
            }
        
        # Get session info
        session = self.db.get_active_session()
        if not session:
            return {
                'pending_orders': [],
                'open_positions': [],
                'realized_pnl': 0.0,
                'unrealized_pnl': 0.0,
                'total_fees': 0.0,
                'order_counter': 0,
                'subscriptions': []
            }
        
        # Get orders
        pending_orders = self.db.get_orders_by_status(self.current_session_id, ['PENDING'])
        open_positions = self.db.get_orders_by_status(self.current_session_id, ['OPEN'])
        
        # Get subscriptions
        subscriptions = self.db.get_subscriptions(self.current_session_id)
        
        state = {
            'pending_orders': self._convert_db_orders(pending_orders),
            'open_positions': self._convert_db_orders(open_positions),
            'realized_pnl': session.get('realized_pnl', 0.0),
            'unrealized_pnl': session.get('unrealized_pnl', 0.0),
            'total_fees': session.get('total_fees', 0.0),
            'order_counter': session.get('order_counter', 0),
            'subscriptions': subscriptions
        }
        
        logger.info(
            f"Restored state: {len(pending_orders)} pending, "
            f"{len(open_positions)} open positions, "
            f"₹{state['realized_pnl']:.2f} realized P&L"
        )
        
        return state
    
    def _convert_db_orders(self, db_orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert database order records to TradeManager format.
        
        Args:
            db_orders: Orders from database
        
        Returns:
            Orders in TradeManager format
        """
        converted = []
        for order in db_orders:
            converted_order = {
                'id': order['id'],
                'token': order['token'],
                'symbol': order['symbol'],
                'action': order['action'],
                'limit_price': order['limit_price'],
                'quantity': order['quantity'],
                'lot_size': order.get('lot_size', 1),
                'lots': order.get('lots', 1),
                'status': order['status'],
                'validity': order.get('validity', 'DAY'),
                'stop_loss': order.get('stop_loss'),
                'target': order.get('target'),
                'sl_order_type': order.get('sl_order_type', 'MARKET'),
                'entry_price': order.get('entry_price', 0.0),
                'exit_price': order.get('exit_price', 0.0),
                'ltp': order.get('ltp', 0.0),
                'placed_at': order.get('placed_at'),
                'entry_time': order.get('entry_time'),
                'exit_time': order.get('exit_time'),
                'exit_reason': order.get('exit_reason'),
                'entry_fees': order.get('entry_fees', 0.0),
                'exit_fees': order.get('exit_fees', 0.0),
                'gross_pnl': order.get('gross_pnl', 0.0),
                'net_pnl': order.get('net_pnl', 0.0),
            }
            converted.append(converted_order)
        
        return converted
    
    def close_current_session(
        self,
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
        total_fees: float = 0.0
    ) -> bool:
        """
        Close the current session.
        
        Args:
            realized_pnl: Final realized P&L
            unrealized_pnl: Final unrealized P&L
            total_fees: Total fees paid
        
        Returns:
            True if closed successfully
        """
        if not self.current_session_id:
            return False
        
        success = self.db.close_session(
            self.current_session_id,
            realized_pnl,
            unrealized_pnl,
            total_fees
        )
        
        if success:
            logger.info(f"Closed session: {self.current_session_id}")
            self.current_session_id = None
        
        return success
    
    # ==================== PERSISTENCE HOOKS ====================
    
    def on_order_placed(self, order: Dict[str, Any]) -> bool:
        """
        Called when a new order is placed.
        
        Args:
            order: Order dictionary
        
        Returns:
            True if persisted successfully
        """
        if not self.current_session_id:
            return False
        
        return self.db.save_order(self.current_session_id, order)
    
    def on_order_updated(self, order_id: str, updates: Dict[str, Any]) -> bool:
        """
        Called when an order is updated (executed, cancelled, etc.).
        
        Args:
            order_id: Order ID
            updates: Dictionary of changed fields
        
        Returns:
            True if persisted successfully
        """
        if not self.current_session_id:
            return False
        
        return self.db.update_order(order_id, updates)
    
    def on_pnl_updated(
        self,
        realized_pnl: float,
        unrealized_pnl: float,
        total_fees: float,
        order_counter: int
    ) -> bool:
        """
        Called when P&L counters are updated.
        
        Args:
            realized_pnl: Current realized P&L
            unrealized_pnl: Current unrealized P&L
            total_fees: Total fees paid
            order_counter: Current order counter
        
        Returns:
            True if persisted successfully
        """
        if not self.current_session_id:
            return False
        
        return self.db.update_session_pnl(
            self.current_session_id,
            realized_pnl,
            unrealized_pnl,
            total_fees,
            order_counter
        )
    
    def on_token_subscribed(
        self,
        token: int,
        symbol: str,
        instrument_data: Dict[str, Any] = None
    ) -> bool:
        """
        Called when a token is subscribed.
        
        Args:
            token: Instrument token
            symbol: Trading symbol
            instrument_data: Optional instrument metadata
        
        Returns:
            True if persisted successfully
        """
        if not self.current_session_id:
            return False
        
        # Track locally
        self._subscribed_tokens[token] = {
            'symbol': symbol,
            'instrument_data': instrument_data
        }
        
        return self.db.save_subscription(
            self.current_session_id,
            token,
            symbol,
            instrument_data
        )
    
    # ==================== CONFIG PROFILES ====================
    
    def save_config_profile(
        self,
        name: str,
        fee_config: Dict[str, Any] = None,
        simulator_config: Dict[str, Any] = None,
        trading_params: Dict[str, Any] = None,
        is_default: bool = False
    ) -> bool:
        """Save a configuration profile."""
        return self.db.save_profile(
            name, fee_config, simulator_config, trading_params, is_default
        )
    
    def load_config_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a configuration profile."""
        return self.db.load_profile(name)
    
    def get_default_profile(self) -> Optional[Dict[str, Any]]:
        """Get the default configuration profile."""
        return self.db.get_default_profile()
    
    def list_config_profiles(self) -> List[str]:
        """List all configuration profile names."""
        return self.db.list_profiles()
    
    def delete_config_profile(self, name: str) -> bool:
        """Delete a configuration profile."""
        return self.db.delete_profile(name)
