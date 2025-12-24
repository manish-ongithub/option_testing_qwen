"""
PostgreSQL Database Manager for Paper Trading Application

Handles:
- Database connection and schema creation
- Order/Position persistence
- Session management
- Configuration profile storage
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

logger = logging.getLogger("DatabaseManager")


class DatabaseManager:
    """
    Manages PostgreSQL database operations for the paper trading app.
    
    Features:
    - Auto-creates tables on first run
    - Persists orders, positions, and trade history
    - Manages trading sessions for resume capability
    - Stores configuration profiles
    """
    
    # SQL for creating tables
    SCHEMA_SQL = """
    -- Sessions table: tracks trading sessions for resume capability
    CREATE TABLE IF NOT EXISTS sessions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        started_at TIMESTAMP NOT NULL DEFAULT NOW(),
        ended_at TIMESTAMP,
        realized_pnl FLOAT DEFAULT 0.0,
        unrealized_pnl FLOAT DEFAULT 0.0,
        total_fees FLOAT DEFAULT 0.0,
        is_active BOOLEAN DEFAULT TRUE,
        order_counter INTEGER DEFAULT 0
    );
    
    -- Orders table: stores all orders (pending, open, closed, cancelled)
    CREATE TABLE IF NOT EXISTS orders (
        id VARCHAR(50) PRIMARY KEY,
        session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
        token INTEGER NOT NULL,
        symbol VARCHAR(100) NOT NULL,
        action VARCHAR(10) NOT NULL,
        limit_price FLOAT NOT NULL,
        quantity INTEGER NOT NULL,
        lot_size INTEGER DEFAULT 1,
        lots INTEGER DEFAULT 1,
        status VARCHAR(20) NOT NULL,
        validity VARCHAR(10) DEFAULT 'DAY',
        stop_loss FLOAT,
        target FLOAT,
        sl_order_type VARCHAR(10) DEFAULT 'MARKET',
        entry_price FLOAT DEFAULT 0.0,
        exit_price FLOAT DEFAULT 0.0,
        ltp FLOAT DEFAULT 0.0,
        placed_at TIMESTAMP,
        entry_time TIMESTAMP,
        exit_time TIMESTAMP,
        exit_reason VARCHAR(50),
        entry_fees FLOAT DEFAULT 0.0,
        exit_fees FLOAT DEFAULT 0.0,
        gross_pnl FLOAT DEFAULT 0.0,
        net_pnl FLOAT DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Index for faster session-based queries
    CREATE INDEX IF NOT EXISTS idx_orders_session ON orders(session_id);
    CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
    CREATE INDEX IF NOT EXISTS idx_orders_token ON orders(token);
    
    -- Configuration profiles table
    CREATE TABLE IF NOT EXISTS config_profiles (
        name VARCHAR(100) PRIMARY KEY,
        fee_config JSONB,
        simulator_config JSONB,
        trading_params JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        is_default BOOLEAN DEFAULT FALSE
    );
    
    -- Subscriptions table: tracks subscribed tokens for session resume
    CREATE TABLE IF NOT EXISTS subscriptions (
        id SERIAL PRIMARY KEY,
        session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
        token INTEGER NOT NULL,
        symbol VARCHAR(100),
        instrument_data JSONB,
        subscribed_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(session_id, token)
    );
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize DatabaseManager with connection configuration.
        
        Args:
            config: Dictionary with keys: host, port, database, user, password
        """
        if not PSYCOPG2_AVAILABLE:
            raise ImportError(
                "psycopg2 is not installed. Install it with: pip install psycopg2-binary"
            )
        
        self.config = config
        self._connection = None
        self._connected = False
        
    def connect(self) -> bool:
        """
        Establish database connection.
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            self._connection = psycopg2.connect(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 5432),
                database=self.config.get("database", "paper_trade"),
                user=self.config.get("user", "postgres"),
                password=self.config.get("password", ""),
                connect_timeout=5
            )
            self._connection.autocommit = False
            self._connected = True
            logger.info(f"Connected to PostgreSQL database: {self.config.get('database')}")
            return True
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Close database connection."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None
            self._connected = False
            logger.info("Disconnected from database")
    
    def is_connected(self) -> bool:
        """Check if database is connected."""
        if not self._connected or not self._connection:
            return False
        try:
            # Test connection with a simple query
            with self._connection.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            self._connected = False
            return False
    
    def init_schema(self) -> bool:
        """
        Initialize database schema (create tables if they don't exist).
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            logger.error("Cannot init schema: not connected")
            return False
        
        try:
            with self._connection.cursor() as cur:
                cur.execute(self.SCHEMA_SQL)
            self._connection.commit()
            logger.info("Database schema initialized successfully")
            return True
        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Failed to initialize schema: {e}")
            return False
    
    # ==================== SESSION MANAGEMENT ====================
    
    def create_session(self) -> Optional[str]:
        """
        Create a new trading session.
        
        Returns:
            Session ID (UUID string) or None if failed
        """
        if not self.is_connected():
            return None
        
        try:
            with self._connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sessions (started_at, is_active)
                    VALUES (NOW(), TRUE)
                    RETURNING id
                    """
                )
                session_id = cur.fetchone()[0]
            self._connection.commit()
            logger.info(f"Created new session: {session_id}")
            return str(session_id)
        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Failed to create session: {e}")
            return None
    
    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently active session if one exists.
        
        Returns:
            Session dict or None
        """
        if not self.is_connected():
            return None
        
        try:
            with self._connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, started_at, realized_pnl, unrealized_pnl, 
                           total_fees, order_counter
                    FROM sessions 
                    WHERE is_active = TRUE 
                    ORDER BY started_at DESC 
                    LIMIT 1
                    """
                )
                result = cur.fetchone()
                if result:
                    return dict(result)
            return None
        except psycopg2.Error as e:
            logger.error(f"Failed to get active session: {e}")
            return None
    
    def close_session(
        self, 
        session_id: str, 
        realized_pnl: float = 0.0,
        unrealized_pnl: float = 0.0,
        total_fees: float = 0.0
    ) -> bool:
        """
        Close a trading session.
        
        Args:
            session_id: Session UUID
            realized_pnl: Final realized P&L
            unrealized_pnl: Final unrealized P&L
            total_fees: Total fees paid
        
        Returns:
            True if successful
        """
        if not self.is_connected():
            return False
        
        try:
            with self._connection.cursor() as cur:
                cur.execute(
                    """
                    UPDATE sessions 
                    SET is_active = FALSE,
                        ended_at = NOW(),
                        realized_pnl = %s,
                        unrealized_pnl = %s,
                        total_fees = %s
                    WHERE id = %s
                    """,
                    (realized_pnl, unrealized_pnl, total_fees, session_id)
                )
            self._connection.commit()
            logger.info(f"Closed session: {session_id}")
            return True
        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Failed to close session: {e}")
            return False
    
    def update_session_pnl(
        self,
        session_id: str,
        realized_pnl: float,
        unrealized_pnl: float,
        total_fees: float,
        order_counter: int
    ) -> bool:
        """Update session P&L counters."""
        if not self.is_connected():
            return False
        
        try:
            with self._connection.cursor() as cur:
                cur.execute(
                    """
                    UPDATE sessions 
                    SET realized_pnl = %s,
                        unrealized_pnl = %s,
                        total_fees = %s,
                        order_counter = %s
                    WHERE id = %s
                    """,
                    (realized_pnl, unrealized_pnl, total_fees, order_counter, session_id)
                )
            self._connection.commit()
            return True
        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Failed to update session P&L: {e}")
            return False
    
    # ==================== ORDER MANAGEMENT ====================
    
    def save_order(self, session_id: str, order: Dict[str, Any]) -> bool:
        """
        Save a new order to the database.
        
        Args:
            session_id: Session UUID
            order: Order dictionary from TradeManager
        
        Returns:
            True if successful
        """
        if not self.is_connected():
            return False
        
        try:
            # Convert datetime objects to strings if present
            placed_at = order.get('placed_at')
            if isinstance(placed_at, datetime):
                placed_at = placed_at
            
            with self._connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (
                        id, session_id, token, symbol, action, limit_price,
                        quantity, lot_size, lots, status, validity,
                        stop_loss, target, sl_order_type, placed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    """,
                    (
                        order['id'],
                        session_id,
                        order['token'],
                        order['symbol'],
                        order['action'],
                        order['limit_price'],
                        order['quantity'],
                        order.get('lot_size', 1),
                        order.get('lots', 1),
                        order['status'],
                        order.get('validity', 'DAY'),
                        order.get('stop_loss'),
                        order.get('target'),
                        order.get('sl_order_type', 'MARKET'),
                        placed_at
                    )
                )
            self._connection.commit()
            return True
        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Failed to save order {order.get('id')}: {e}")
            return False
    
    def update_order(self, order_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing order.
        
        Args:
            order_id: Order ID
            updates: Dictionary of fields to update
        
        Returns:
            True if successful
        """
        if not self.is_connected() or not updates:
            return False
        
        # Build dynamic UPDATE query
        set_clauses = []
        values = []
        
        field_mapping = {
            'status': 'status',
            'entry_price': 'entry_price',
            'exit_price': 'exit_price',
            'ltp': 'ltp',
            'entry_time': 'entry_time',
            'exit_time': 'exit_time',
            'exit_reason': 'exit_reason',
            'entry_fees': 'entry_fees',
            'exit_fees': 'exit_fees',
            'gross_pnl': 'gross_pnl',
            'net_pnl': 'net_pnl',
            'stop_loss': 'stop_loss',
            'target': 'target',
            'quantity': 'quantity',
            'lots': 'lots',
            'limit_price': 'limit_price',
        }
        
        for key, value in updates.items():
            if key in field_mapping:
                set_clauses.append(f"{field_mapping[key]} = %s")
                values.append(value)
        
        if not set_clauses:
            return True  # Nothing to update
        
        set_clauses.append("updated_at = NOW()")
        values.append(order_id)
        
        try:
            with self._connection.cursor() as cur:
                query = f"UPDATE orders SET {', '.join(set_clauses)} WHERE id = %s"
                cur.execute(query, values)
            self._connection.commit()
            return True
        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Failed to update order {order_id}: {e}")
            return False
    
    def get_orders_by_status(
        self, 
        session_id: str, 
        statuses: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Get orders by status for a session.
        
        Args:
            session_id: Session UUID
            statuses: List of status strings (e.g., ['PENDING', 'OPEN'])
        
        Returns:
            List of order dictionaries
        """
        if not self.is_connected():
            return []
        
        try:
            with self._connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT * FROM orders 
                    WHERE session_id = %s AND status = ANY(%s)
                    ORDER BY placed_at
                    """,
                    (session_id, statuses)
                )
                results = cur.fetchall()
                return [dict(row) for row in results]
        except psycopg2.Error as e:
            logger.error(f"Failed to get orders: {e}")
            return []
    
    def get_trade_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get closed orders (trade history) for a session."""
        return self.get_orders_by_status(session_id, ['CLOSED'])
    
    # ==================== SUBSCRIPTION MANAGEMENT ====================
    
    def save_subscription(
        self, 
        session_id: str, 
        token: int, 
        symbol: str,
        instrument_data: Dict[str, Any] = None
    ) -> bool:
        """Save a token subscription for session resume."""
        if not self.is_connected():
            return False
        
        try:
            with self._connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO subscriptions (session_id, token, symbol, instrument_data)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (session_id, token) DO UPDATE SET
                        symbol = EXCLUDED.symbol,
                        instrument_data = EXCLUDED.instrument_data
                    """,
                    (session_id, token, symbol, Json(instrument_data) if instrument_data else None)
                )
            self._connection.commit()
            return True
        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Failed to save subscription: {e}")
            return False
    
    def get_subscriptions(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all subscriptions for a session."""
        if not self.is_connected():
            return []
        
        try:
            with self._connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT token, symbol, instrument_data FROM subscriptions WHERE session_id = %s",
                    (session_id,)
                )
                return [dict(row) for row in cur.fetchall()]
        except psycopg2.Error as e:
            logger.error(f"Failed to get subscriptions: {e}")
            return []
    
    # ==================== CONFIGURATION PROFILES ====================
    
    def save_profile(
        self,
        name: str,
        fee_config: Dict[str, Any] = None,
        simulator_config: Dict[str, Any] = None,
        trading_params: Dict[str, Any] = None,
        is_default: bool = False
    ) -> bool:
        """
        Save a configuration profile.
        
        Args:
            name: Profile name
            fee_config: Fee configuration dict
            simulator_config: Simulator configuration dict
            trading_params: Trading parameters dict
            is_default: Whether this is the default profile
        
        Returns:
            True if successful
        """
        if not self.is_connected():
            return False
        
        try:
            # If setting as default, unset other defaults
            if is_default:
                with self._connection.cursor() as cur:
                    cur.execute("UPDATE config_profiles SET is_default = FALSE")
            
            with self._connection.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO config_profiles (
                        name, fee_config, simulator_config, trading_params, is_default
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        fee_config = EXCLUDED.fee_config,
                        simulator_config = EXCLUDED.simulator_config,
                        trading_params = EXCLUDED.trading_params,
                        is_default = EXCLUDED.is_default,
                        updated_at = NOW()
                    """,
                    (
                        name,
                        Json(fee_config) if fee_config else None,
                        Json(simulator_config) if simulator_config else None,
                        Json(trading_params) if trading_params else None,
                        is_default
                    )
                )
            self._connection.commit()
            logger.info(f"Saved config profile: {name}")
            return True
        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Failed to save profile {name}: {e}")
            return False
    
    def load_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Load a configuration profile.
        
        Args:
            name: Profile name
        
        Returns:
            Profile dict or None
        """
        if not self.is_connected():
            return None
        
        try:
            with self._connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM config_profiles WHERE name = %s",
                    (name,)
                )
                result = cur.fetchone()
                if result:
                    return dict(result)
            return None
        except psycopg2.Error as e:
            logger.error(f"Failed to load profile {name}: {e}")
            return None
    
    def get_default_profile(self) -> Optional[Dict[str, Any]]:
        """Get the default configuration profile."""
        if not self.is_connected():
            return None
        
        try:
            with self._connection.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM config_profiles WHERE is_default = TRUE LIMIT 1"
                )
                result = cur.fetchone()
                if result:
                    return dict(result)
            return None
        except psycopg2.Error as e:
            logger.error(f"Failed to get default profile: {e}")
            return None
    
    def list_profiles(self) -> List[str]:
        """
        List all configuration profile names.
        
        Returns:
            List of profile names
        """
        if not self.is_connected():
            return []
        
        try:
            with self._connection.cursor() as cur:
                cur.execute("SELECT name FROM config_profiles ORDER BY name")
                return [row[0] for row in cur.fetchall()]
        except psycopg2.Error as e:
            logger.error(f"Failed to list profiles: {e}")
            return []
    
    def delete_profile(self, name: str) -> bool:
        """
        Delete a configuration profile.
        
        Args:
            name: Profile name
        
        Returns:
            True if successful
        """
        if not self.is_connected():
            return False
        
        try:
            with self._connection.cursor() as cur:
                cur.execute("DELETE FROM config_profiles WHERE name = %s", (name,))
            self._connection.commit()
            logger.info(f"Deleted config profile: {name}")
            return True
        except psycopg2.Error as e:
            self._connection.rollback()
            logger.error(f"Failed to delete profile {name}: {e}")
            return False
    
    # ==================== UTILITY ====================
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
