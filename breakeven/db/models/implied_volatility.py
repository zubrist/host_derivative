from typing import Optional
from datetime import date
from pydantic import BaseModel


class ImpliedVolatilityRequest(BaseModel):
    symbol: str
    strike_price: float
    spot_price: float
    expiry_date: str  # Format: "YYYY-MM-DD"
    risk_free_rate: float = 0.065  # Default 6.5%
    market_data_date: Optional[str] = None  # Optional date for market data (for testing)


class OptionDetails(BaseModel):
    option_type: str  # "CE" or "PE"
    implied_volatility: float
    calculated_premium: float
    market_premium: float
    convergence_achieved: bool



class ImpliedVolatilityResponse(BaseModel):
    """
    Represents the response model for implied volatility calculations.

    Attributes:
        symbol: The stock symbol or identifier.
        strike_price: The strike price of the options.
        expiry_date: The expiry date of the options (YYYY-MM-DD).
        market_data_date: The date for which the market data was fetched (YYYY-MM-DD).
        call_option: Details of the call option.
        put_option: Details of the put option.
        iterations: The number of iterations performed during the calculation.
        spot_price: The spot price of the underlying asset used in calculations.
        underlying_value: The underlying value of the asset as per NSE data.
    """
    symbol: str
    strike_price: float
    expiry_date: str
    market_data_date: str
    call_option: OptionDetails  # CE details
    put_option: OptionDetails   # PE details
    iterations: int
    spot_price: float
    underlying_value: float  # From NSE data