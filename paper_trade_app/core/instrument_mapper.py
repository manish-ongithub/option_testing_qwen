import datetime
import hashlib
from collections import namedtuple
from core.alice_utils import Aliceblue, Instrument

# Mock Instrument for simulation mode
MockInstrument = namedtuple('MockInstrument', ['token', 'symbol', 'name', 'exchange', 'expiry', 'lot_size'])


class InstrumentMapper:
    def __init__(self, user_id, api_key, simulation_mode=False):
        # We need an Alice instance just to download contracts/search
        self.alice = Aliceblue(user_id=user_id, api_key=api_key)
        self.downloaded_exchanges = set()  # Use set to avoid duplicates
        self.simulation_mode = simulation_mode
        
        # Cache for mock instruments created in simulation mode
        self._mock_instrument_cache = {}

    def load_master_contract(self, exchange="NFO"):
        """
        Downloads the master CSV for the specified exchange (e.g., NFO for Derivatives).
        Skips download if already downloaded in this session.
        """
        if exchange in self.downloaded_exchanges:
            print(f"ℹ️ Master Contract for {exchange} already loaded.")
            return
        
        print(f"📥 Downloading Master Contract for {exchange}...")
        self.alice.get_contract_master(exchange)
        self.downloaded_exchanges.add(exchange)
        print("✅ Master Contract Downloaded.")

    def get_token(self, symbol, expiry_str, strike, option_type, exchange="NFO"):
        """
        Finds the Instrument object for specific options parameters.
        
        Args:
            symbol: "NIFTY" or "BANKNIFTY"
            expiry_str: Date in "YYYY-MM-DD" format (e.g., "2025-12-25")
            strike: Strike price (int or float)
            option_type: "CE" or "PE"
            exchange: Exchange code (default: "NFO")
        
        Returns:
            Instrument object or None if not found.
        """
        try:
            # Validate strike price
            if strike is None:
                print(f"❌ Strike price cannot be None for options")
                return None
            
            # Determine Option Type boolean
            is_ce = option_type.upper() == "CE"
            
            # Use the library's search function
            instrument = self.alice.get_instrument_for_fno(
                exch=exchange,
                symbol=symbol.upper(),
                expiry_date=expiry_str, 
                is_fut=False,
                strike=float(strike),
                is_CE=is_ce
            )

            # Error Handling (Library returns {'stat': 'Not_ok'} on failure)
            if isinstance(instrument, dict) and instrument.get('stat') == 'Not_ok':
                # In simulation mode, create a mock instrument instead of failing
                if self.simulation_mode:
                    print(f"🔧 Simulation Mode: Creating mock instrument for {symbol} {strike} {option_type}")
                    return self._create_mock_instrument(symbol, expiry_str, strike, option_type, exchange)
                print(f"❌ Instrument Not Found: {symbol} {strike} {option_type}")
                return None
            
            return instrument

        except Exception as e:
            # In simulation mode, create a mock instrument on any error
            if self.simulation_mode:
                print(f"🔧 Simulation Mode: Creating mock instrument for {symbol} {strike} {option_type} (error: {e})")
                return self._create_mock_instrument(symbol, expiry_str, strike, option_type, exchange)
            print(f"❌ Mapping Error: {e}")
            return None
    
    def _create_mock_instrument(self, symbol, expiry_str, strike, option_type, exchange="NFO"):
        """
        Create a mock instrument for simulation mode.
        
        Uses a deterministic token generation based on symbol/strike/expiry/type
        so the same alert always gets the same token.
        """
        # Create a unique key for caching
        cache_key = f"{symbol}_{expiry_str}_{strike}_{option_type}"
        
        if cache_key in self._mock_instrument_cache:
            return self._mock_instrument_cache[cache_key]
        
        # Generate deterministic token from hash
        hash_input = f"{symbol}{expiry_str}{strike}{option_type}"
        token = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16) % 1000000 + 100000
        
        # Format expiry for name (convert YYYY-MM-DD to DDMMMYY)
        try:
            expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d")
            expiry_fmt = expiry_date.strftime("%d%b%y").upper()
        except:
            expiry_fmt = expiry_str.replace("-", "")
        
        # Create instrument name (e.g., NIFTY30JAN25C24000)
        name = f"{symbol.upper()}{expiry_fmt}{option_type.upper()}{int(strike)}"
        
        # Determine lot size based on symbol
        lot_sizes = {
            'NIFTY': 50,
            'BANKNIFTY': 15,
            'FINNIFTY': 25,
            'MIDCPNIFTY': 50,
        }
        lot_size = lot_sizes.get(symbol.upper(), 1)
        
        mock_instrument = MockInstrument(
            token=token,
            symbol=symbol.upper(),
            name=name,
            exchange=exchange,
            expiry=expiry_str,
            lot_size=lot_size
        )
        
        # Cache for future lookups
        self._mock_instrument_cache[cache_key] = mock_instrument
        print(f"✅ Mock Instrument Created: {name} (token={token}, lot_size={lot_size})")
        
        return mock_instrument
            
    def get_future_token(self, symbol, expiry_str, exchange="NFO"):
        """
        Finds the Instrument object for futures.
        
        Args:
            symbol: "NIFTY" or "BANKNIFTY"
            expiry_str: Date in "YYYY-MM-DD" format (e.g., "2025-12-25")
            exchange: Exchange code (default: "NFO")
        
        Returns:
            Instrument object or None if not found.
        """
        try:
            instrument = self.alice.get_instrument_for_fno(
                exch=exchange,
                symbol=symbol.upper(),
                expiry_date=expiry_str,
                is_fut=True,
                strike=None
            )
            
            # Error Handling
            if isinstance(instrument, dict) and instrument.get('stat') == 'Not_ok':
                print(f"❌ Future Not Found: {symbol} {expiry_str}")
                return None
            
            return instrument
            
        except Exception as e:
            print(f"❌ Future Mapping Error: {e}")
            return None
    
    def get_cash_instrument(self, symbol, exchange="NSE", instrument_type="STOCK"):
        """
        Get instrument for cash market (stocks or indices).
        Used for live ticker display to verify API connection.
        
        Args:
            symbol: Symbol name (e.g., "RELIANCE", "Nifty 50")
            exchange: Exchange code - "NSE" for stocks, "INDICES" for indices
            instrument_type: "STOCK" or "INDEX"
        
        Returns:
            Instrument object or None if not found.
        """
        try:
            # For indices, use INDICES exchange
            if instrument_type.upper() == "INDEX":
                actual_exchange = "INDICES"
            else:
                actual_exchange = exchange
            
            # Make sure contract master is loaded
            if actual_exchange not in self.downloaded_exchanges:
                print(f"📥 Downloading Master Contract for {actual_exchange}...")
                self.alice.get_contract_master(actual_exchange)
                self.downloaded_exchanges.add(actual_exchange)
            
            # Get instrument by symbol
            instrument = self.alice.get_instrument_by_symbol(actual_exchange, symbol)
            
            # Error Handling
            if isinstance(instrument, dict) and instrument.get('stat') == 'Not_ok':
                # In simulation mode, create a mock instrument
                if self.simulation_mode:
                    print(f"🔧 Simulation Mode: Creating mock ticker for {symbol}")
                    return self._create_mock_cash_instrument(symbol, exchange, instrument_type)
                print(f"❌ Cash Instrument Not Found: {symbol} on {actual_exchange}")
                return None
            
            return instrument
            
        except Exception as e:
            # In simulation mode, create a mock instrument on any error
            if self.simulation_mode:
                print(f"🔧 Simulation Mode: Creating mock ticker for {symbol} (error: {e})")
                return self._create_mock_cash_instrument(symbol, exchange, instrument_type)
            print(f"❌ Cash Instrument Error: {e}")
            return None
    
    def _create_mock_cash_instrument(self, symbol, exchange="NSE", instrument_type="STOCK"):
        """
        Create a mock cash instrument for simulation mode.
        """
        import hashlib
        
        cache_key = f"CASH_{symbol}_{exchange}_{instrument_type}"
        
        if cache_key in self._mock_instrument_cache:
            return self._mock_instrument_cache[cache_key]
        
        # Generate deterministic token from hash
        hash_input = f"{symbol}{exchange}{instrument_type}"
        token = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16) % 100000 + 200000
        
        # Mock starting prices for common symbols
        mock_prices = {
            'NIFTY 50': 24000,
            'NIFTY50': 24000,
            'BANK NIFTY': 51000,
            'BANKNIFTY': 51000,
            'RELIANCE': 2900,
            'TCS': 4100,
            'INFY': 1900,
            'HDFCBANK': 1700,
        }
        
        mock_instrument = MockInstrument(
            token=token,
            symbol=symbol.upper(),
            name=symbol,
            exchange=exchange,
            expiry='',
            lot_size=1  # Cash market has lot size 1
        )
        
        self._mock_instrument_cache[cache_key] = mock_instrument
        print(f"✅ Mock Ticker Created: {symbol} (token={token})")
        
        return mock_instrument