from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# --- Data Model ---
class OptionTransaction(BaseModel):
    """
    Represents an option transaction with the relevant details for break-even calculation.
    """
    strike_price: float
    entry_price: float  # Premium paid/received
    lots: int
    option_type: str  # 'CE' for Call, 'PE' for Put.  Important for BE calc.



# --- Models for Strategy API ---
class OptionLeg(BaseModel):
    """
    Represents a single leg in an options strategy
    """
    symbol: str
    expiry: str  # Format: "DD-MMM-YYYY" e.g., "10-Jul-2025"
    strike: float
    option_type: str  # "CE" or "PE"
    action: str  # "BUY" or "SELL"
    quantity: int
    premium: Optional[float] = None  # Add this line to make premium optional
    
    def copy(self):
        """Create a copy of this leg"""
        return OptionLeg(
            symbol=self.symbol,
            expiry=self.expiry,
            strike=self.strike,
            option_type=self.option_type,
            action=self.action,
            premium=self.premium,
            quantity=self.quantity
        )

class StrategyRequest(BaseModel):
    """
    Request model for strategy identification and analysis
    """
    legs: List[OptionLeg]

class StrategyResponse(BaseModel):
    """
    Response model for strategy analysis
    """
    strategy_name: str
    breakeven_points: List[float]
    max_profit: Any  # Can be float or "Unlimited"
    max_loss: Any  # Can be float or "Unlimited"
    profit_zones: List[Dict[str, Any]]  # Changed from float to Any to support "Unlimited"
    risk_reward_ratio: Optional[Any] = None  # Changed to Any to support "Unlimited"
    legs: List[OptionLeg]
    details: Dict[str, Any] = {}