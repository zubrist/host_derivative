from tortoise import fields, models
from tortoise.models import Model
from pydantic import BaseModel, Field
from typing import Optional , List
from tortoise.contrib.pydantic import pydantic_model_creator
from enum import Enum



 

class NIFTY(models.Model):
    id = fields.IntField(pk=True)  # Auto-incrementing ID
    FH_TIMESTAMP = fields.CharField(max_length=20, null=True)
    FH_SYMBOL = fields.CharField(max_length=20, null=True)
    FH_INSTRUMENT = fields.CharField(max_length=20, null=True)
    FH_STRIKE_PRICE = fields.CharField(max_length=20, null=True)
    FH_EXPIRY_DT = fields.CharField(max_length=20, null=True)
    FH_OPTION_TYPE = fields.CharField(max_length=10, null=True)
    FH_CLOSING_PRICE = fields.CharField(max_length=30, null=True)
    FH_LAST_TRADED_PRICE = fields.CharField(max_length=30, null=True)
    FH_MARKET_LOT = fields.CharField(max_length=10, null=True)
    TIMESTAMP = fields.DatetimeField(null=True)
    FH_CHANGE_IN_OI = fields.CharField(max_length=30, null=True)
    FH_MARKET_TYPE = fields.CharField(max_length=5, null=True)
    FH_OPENING_PRICE = fields.CharField(max_length=30, null=True)
    FH_OPEN_INT = fields.CharField(max_length=30, null=True)
    FH_PREV_CLS = fields.CharField(max_length=30, null=True)
    FH_SETTLE_PRICE = fields.CharField(max_length=30, null=True)
    FH_TOT_TRADED_QTY = fields.CharField(max_length=30, null=True)
    FH_TOT_TRADED_VAL = fields.CharField(max_length=40, null=True)
    FH_TRADE_HIGH_PRICE = fields.CharField(max_length=30, null=True)
    FH_TRADE_LOW_PRICE = fields.CharField(max_length=30, null=True)
    FH_UNDERLYING_VALUE = fields.FloatField(null=True)

    class Meta:
        table = "NIFTY"

    def __str__(self):
        return f"{self.FH_TIMESTAMP} - {self.FH_CLOSING_PRICE}"

NIFTY_Pydantic = pydantic_model_creator(NIFTY, name="NIFTY")


class BANKNIFTY(models.Model):
    id = fields.IntField(pk=True)  # Auto-incrementing ID
    symbol = fields.CharField(max_length=20 , null=True)
    date = fields.DateField(null=True)
    expiry = fields.TextField(null=True)
    option_type = fields.CharField(max_length=10, null=True)  # e.g., "CE", "PE"
    strike_price = fields.IntField(null=True)
    open = fields.FloatField(null=True)
    high = fields.FloatField(null=True)
    low = fields.FloatField(null=True)
    close = fields.FloatField(null=True)
    ltp = fields.FloatField(null=True)
    change_in_oi = fields.FloatField(null=True)
    closing_price = fields.FloatField(null=True)
    last_traded_price = fields.FloatField(null=True)
    market_lot = fields.IntField(null=True)
    open_int = fields.FloatField(null=True)
    prev_cls = fields.FloatField(null=True)
    settle_price = fields.FloatField(null=True)
    tot_traded_qty = fields.FloatField(null=True)
    tot_traded_val = fields.FloatField(null=True)
    trade_high_price = fields.FloatField(null=True)
    trade_low_price = fields.FloatField(null=True)
    underlying_value = fields.FloatField(null=True)
    

    class Meta:
        table = "BANKNIFTY"

    def __str__(self):
        return f"{self.date} - {self.close}"
    
BANKNIFTY_Pydantic = pydantic_model_creator(BANKNIFTY, name="BANKNIFTY")


class FINNIFTY(models.Model):
    id = fields.IntField(pk=True)  # Auto-incrementing ID
    symbol = fields.CharField(max_length=20 , null=True)
    date = fields.DateField(null=True)
    expiry = fields.TextField(null=True)
    option_type = fields.CharField(max_length=10, null=True)  # e.g., "CE", "PE"
    strike_price = fields.IntField(null=True)
    open = fields.FloatField(null=True)
    high = fields.FloatField(null=True)
    low = fields.FloatField(null=True)
    close = fields.FloatField(null=True)
    ltp = fields.FloatField(null=True)
    change_in_oi = fields.FloatField(null=True)
    closing_price = fields.FloatField(null=True)
    last_traded_price = fields.FloatField(null=True)
    market_lot = fields.IntField(null=True)
    open_int = fields.FloatField(null=True)
    prev_cls = fields.FloatField(null=True)
    settle_price = fields.FloatField(null=True)
    tot_traded_qty = fields.FloatField(null=True)
    tot_traded_val = fields.FloatField(null=True)
    trade_high_price = fields.FloatField(null=True)
    trade_low_price = fields.FloatField(null=True)
    underlying_value = fields.FloatField(null=True)
    

    class Meta:
        table = "FINNIFTY"

    def __str__(self):
        return f"{self.date} - {self.close}"
    
FINNIFTY_Pydantic = pydantic_model_creator(FINNIFTY, name="FINNIFTY")


# Pydantic model for the API payload
class FetchDataPayload(BaseModel):
    from_date: str
    to_date: str
    instrument_type: str
    symbol: str
    year: Optional[int] = None
    expiry_date: str
    option_type: str
    strike_price: Optional[int] = None



    
class OptionTrade(BaseModel):
    action: str  # BUY or SELL
    expiry_date: str  # Format: DD-MMM-YYYY
    strike_price: float
    option_type: str  # CE or PE
    lots: int
    buy_price: Optional[float] = None  # Optional field
    trade_date: str  # Format: DD-MM-YYYY (New field)

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



class HistoricalDataResponse(BaseModel):
    FH_TIMESTAMP: str = Field(..., example="03-Mar-2025")
    FH_SYMBOL: str = Field(..., example="NIFTY")
    FH_STRIKE_PRICE: str = Field(..., example="22000")
    FH_CLOSING_PRICE: str = Field(..., example="150.25")
    FH_LAST_TRADED_PRICE: str = Field(..., example="150.25")

class SearchDataResponse(BaseModel):
    status: str = Field(..., example="success")
    source: str = Field(..., example="database/nifty")
    data: List[HistoricalDataResponse]

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "source": "database/nifty",
                "data": [{
                    "FH_TIMESTAMP": "03-Mar-2025",
                    "FH_SYMBOL": "NIFTY",
                    "FH_STRIKE_PRICE": "22000",
                    "FH_CLOSING_PRICE": "150.25",
                    "FH_LAST_TRADED_PRICE": "150.25"
                }]
            }
        }


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

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "NIFTY",
                "trades": [
                    {
                        "action": "SELL",
                        "expiry_date": "24-Apr-2024",
                        "strike_price": 24500,
                        "option_type": "CE",
                        "lots": 2,
                        "buy_price": 22.0,
                        "trade_date": "19-03-2025"
                    }
                ]
            }
        }    