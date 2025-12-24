"""
Fee Calculator Module for Indian Options Trading

Calculates transaction costs including brokerage, STT, exchange charges, 
SEBI fees, stamp duty, and GST. Default configuration uses Alice Blue rates.
"""

from dataclasses import dataclass, field
from typing import Literal
from enum import Enum


class TransactionType(Enum):
    BUY = "BUY"
    SELL = "SELL"


class Segment(Enum):
    OPTIONS = "OPTIONS"
    FUTURES = "FUTURES"
    EQUITY = "EQUITY"


@dataclass
class FeeConfig:
    """
    Configurable fee structure for different brokers.
    Default values are for Alice Blue.
    """
    # Brokerage
    brokerage_per_order: float = 15.0  # Rs per executed order (flat fee)
    brokerage_percent: float = 0.0     # Percentage of turnover (if applicable)
    max_brokerage: float = 15.0        # Maximum brokerage cap per order
    
    # STT (Securities Transaction Tax) - Options
    stt_buy_percent: float = 0.0       # STT on options buy (0% for options)
    stt_sell_percent: float = 0.0625   # STT on options sell (0.0625% of premium)
    
    # Exchange Transaction Charges (NSE)
    exchange_txn_charge_percent: float = 0.053  # 0.053% of premium
    
    # SEBI Charges
    sebi_charges_percent: float = 0.0001  # 0.0001% of turnover
    
    # Stamp Duty (only on buy side)
    stamp_duty_percent: float = 0.003  # 0.003% of buy value
    
    # GST (on brokerage + exchange charges)
    gst_percent: float = 18.0  # 18% GST
    
    # Broker name for identification
    broker_name: str = "Alice Blue"


# Pre-configured fee structures for common brokers
ALICE_BLUE_FEES = FeeConfig(
    brokerage_per_order=15.0,
    stt_buy_percent=0.0,
    stt_sell_percent=0.0625,
    exchange_txn_charge_percent=0.053,
    sebi_charges_percent=0.0001,
    stamp_duty_percent=0.003,
    gst_percent=18.0,
    broker_name="Alice Blue"
)

ZERODHA_FEES = FeeConfig(
    brokerage_per_order=20.0,
    stt_buy_percent=0.0,
    stt_sell_percent=0.0625,
    exchange_txn_charge_percent=0.053,
    sebi_charges_percent=0.0001,
    stamp_duty_percent=0.003,
    gst_percent=18.0,
    broker_name="Zerodha"
)

FLAT_FEE_CONFIG = FeeConfig(
    brokerage_per_order=20.0,
    stt_buy_percent=0.0,
    stt_sell_percent=0.05,  # Simplified
    exchange_txn_charge_percent=0.05,
    sebi_charges_percent=0.0001,
    stamp_duty_percent=0.003,
    gst_percent=18.0,
    broker_name="Flat Fee"
)


@dataclass
class FeeBreakdown:
    """Detailed breakdown of all transaction costs."""
    brokerage: float = 0.0
    stt: float = 0.0
    exchange_charges: float = 0.0
    sebi_charges: float = 0.0
    stamp_duty: float = 0.0
    gst: float = 0.0
    
    @property
    def total(self) -> float:
        """Total transaction cost."""
        return round(
            self.brokerage + self.stt + self.exchange_charges + 
            self.sebi_charges + self.stamp_duty + self.gst, 
            2
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging/display."""
        return {
            "brokerage": self.brokerage,
            "stt": self.stt,
            "exchange_charges": self.exchange_charges,
            "sebi_charges": self.sebi_charges,
            "stamp_duty": self.stamp_duty,
            "gst": self.gst,
            "total": self.total
        }


def calculate_fees(
    price: float,
    quantity: int,
    transaction_type: str,
    segment: str = "OPTIONS",
    fee_config: FeeConfig = None
) -> FeeBreakdown:
    """
    Calculate all transaction costs for a trade.
    
    Args:
        price: Execution price per unit
        quantity: Number of units traded
        transaction_type: "BUY" or "SELL"
        segment: "OPTIONS", "FUTURES", or "EQUITY"
        fee_config: Fee configuration (defaults to Alice Blue)
    
    Returns:
        FeeBreakdown with all cost components
    """
    if fee_config is None:
        fee_config = ALICE_BLUE_FEES
    
    turnover = price * quantity
    breakdown = FeeBreakdown()
    
    # 1. Brokerage (flat per order or percentage, whichever is applicable)
    if fee_config.brokerage_percent > 0:
        brokerage = turnover * (fee_config.brokerage_percent / 100)
        breakdown.brokerage = min(brokerage, fee_config.max_brokerage)
    else:
        breakdown.brokerage = fee_config.brokerage_per_order
    
    # 2. STT (Securities Transaction Tax)
    if transaction_type.upper() == "BUY":
        breakdown.stt = turnover * (fee_config.stt_buy_percent / 100)
    else:  # SELL
        breakdown.stt = turnover * (fee_config.stt_sell_percent / 100)
    
    # 3. Exchange Transaction Charges
    breakdown.exchange_charges = turnover * (fee_config.exchange_txn_charge_percent / 100)
    
    # 4. SEBI Charges
    breakdown.sebi_charges = turnover * (fee_config.sebi_charges_percent / 100)
    
    # 5. Stamp Duty (only on buy side)
    if transaction_type.upper() == "BUY":
        breakdown.stamp_duty = turnover * (fee_config.stamp_duty_percent / 100)
    else:
        breakdown.stamp_duty = 0.0
    
    # 6. GST (18% on brokerage + exchange charges)
    gst_base = breakdown.brokerage + breakdown.exchange_charges
    breakdown.gst = gst_base * (fee_config.gst_percent / 100)
    
    # Round all values to 2 decimal places
    breakdown.brokerage = round(breakdown.brokerage, 2)
    breakdown.stt = round(breakdown.stt, 2)
    breakdown.exchange_charges = round(breakdown.exchange_charges, 2)
    breakdown.sebi_charges = round(breakdown.sebi_charges, 2)
    breakdown.stamp_duty = round(breakdown.stamp_duty, 2)
    breakdown.gst = round(breakdown.gst, 2)
    
    return breakdown


def calculate_round_trip_fees(
    entry_price: float,
    exit_price: float,
    quantity: int,
    segment: str = "OPTIONS",
    fee_config: FeeConfig = None
) -> tuple[FeeBreakdown, FeeBreakdown, float]:
    """
    Calculate fees for a complete round-trip trade (entry + exit).
    
    Returns:
        Tuple of (entry_fees, exit_fees, total_fees)
    """
    entry_fees = calculate_fees(entry_price, quantity, "BUY", segment, fee_config)
    exit_fees = calculate_fees(exit_price, quantity, "SELL", segment, fee_config)
    total = entry_fees.total + exit_fees.total
    
    return entry_fees, exit_fees, round(total, 2)


# Convenience function for quick total fee calculation
def get_total_fees(
    price: float,
    quantity: int,
    transaction_type: str,
    fee_config: FeeConfig = None
) -> float:
    """Quick calculation of total fees without breakdown."""
    return calculate_fees(price, quantity, transaction_type, "OPTIONS", fee_config).total
