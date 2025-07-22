from pydantic import BaseModel
from typing import List, Dict, Any, Optional


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
    # premium: float
    quantity: int = 75  # Default is 1 lot of NIFTY (75 shares)

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
    profit_zones: List[Dict[str, float]]
    risk_reward_ratio: Optional[float] = None
    legs: List[OptionLeg]
    details: Dict[str, Any] = {}