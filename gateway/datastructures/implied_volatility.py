from datetime import date
from pydantic import BaseModel
from typing import Optional

class ImpliedVolatilityRequest(BaseModel):
    symbol: str
    strike_price: float
    spot_price: float
    expiry_date: str  # Format: "YYYY-MM-DD"
    #risk_free_rate: float = 0.05  # Default 5%
    risk_free_rate: float = 0.065  # Default 6.5%
    market_data_date: Optional[str] = None  # Optional date for market data (for testing)