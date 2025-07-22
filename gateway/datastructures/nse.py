from pydantic import BaseModel , Field
from typing import Optional, List
from datetime import datetime
from enum import Enum



class FetchDataPayload(BaseModel):
    from_date: str
    to_date: str
    instrument_type: str
    symbol: str
    year: int
    expiry_date: str
    option_type: str
    strike_price: int 




    
class OptionTrade(BaseModel):
    action: str  # BUY or SELL
    expiry_date: str  # Format: DD-MMM-YYYY
    strike_price: float
    option_type: str  # CE or PE
    lots: int
    buy_price: Optional[float] = None  # Optional field
    trade_date = str

class OptionStrategyPayload(BaseModel):
    trades: List[OptionTrade]
    symbol: str  # NIFTY, BANKNIFTY, or FINNIFTY    



class ActionType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"

class IndexSymbol(str, Enum):
    NIFTY = "NIFTY"
    BANKNIFTY = "BANKNIFTY"
    FINNIFTY = "FINNIFTY"

class OptionStrategy(BaseModel):
    symbol: IndexSymbol
    trades: List[dict] = Field(..., example=[{
        "action": "SELL",
        "expiry_date": "24-Apr-2024",
        "strike_price": 24500,
        "option_type": "CE",
        "lots": 2,
        "buy_price": 22.0,
        "trade_date": "19-03-2025"
    }])    