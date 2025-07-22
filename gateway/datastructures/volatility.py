from pydantic import BaseModel
from typing import List, Optional

class VolatilityRequest(BaseModel):
    symbol: str
    #start_date: str
    end_date: str
    years_of_data: int
    custom_multiplier: bool 
    multipliers: Optional[List[float]]