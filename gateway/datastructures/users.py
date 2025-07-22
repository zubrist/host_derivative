from datetime import datetime, date
from pydantic import BaseModel, EmailStr, UUID4
from typing import Optional


class UserCreate(BaseModel):
    username: Optional[str]
    password: Optional[str]
    email: Optional[EmailStr]
    full_name: Optional[str]

class UserResponse(BaseModel):
    user_id: UUID4
    username: str
    email: EmailStr
    full_name: str
    created_at: datetime
    last_login: Optional[datetime]

class UserLogin(BaseModel):
    username: Optional[str]
    password: Optional[str]

class TransactionCreate(BaseModel):
    symbol: str
    strike_price: float
    option_type: str
    lots: int
    trade_date: str
    expiry_date: str
    instrument: str