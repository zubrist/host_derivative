from tortoise import fields
from tortoise.models import Model
from datetime import datetime , date
from pydantic import BaseModel, EmailStr, UUID4
from typing import Optional

class Users(Model):
    user_id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50, unique=True)
    password = fields.CharField(max_length=128)  # Will store hashed password
    email = fields.CharField(max_length=100, unique=True)
    full_name = fields.CharField(max_length=100)
    user_profile_pic = fields.CharField(max_length=255 , null= True)
    user_type = fields.CharField(max_length=255 , null= True)
    created_at = fields.DatetimeField(auto_now_add=True)
    last_login = fields.DatetimeField(null=True)
    is_active = fields.BooleanField(default=True)

    class Meta:
        # Specify the table name for the model
        table = "users"

    def __str__(self):
        # This method returns the username of the user when the user object is printed
        return self.username

class UserTransactions(Model):
    transaction_id = fields.IntField(pk=True)
    user = fields.ForeignKeyField('models.Users', related_name='transactions')
    symbol = fields.CharField(max_length=20 , null = True)
    instrument = fields.CharField(max_length=20 , null = True) # Option or Future
    #action = fields.CharField(max_length=4, null = True)  # BUY or SELL
    strike_price = fields.FloatField(null = True)
    option_type = fields.CharField(max_length=2)  # CE or PE
    lots = fields.IntField()
    trade_date = fields.DateField()
    expiry_date = fields.DateField()
    entry_price = fields.FloatField()
    market_lot = fields.IntField(null=True)  # Market lot size for the option
    transaction_time = fields.DatetimeField(auto_now_add=True)
    status = fields.CharField(max_length=20, default='active')  # active, expired, closed
    #PnL = fields.FloatField(null=True)  # To store final P/L when position is closed

    class Meta:
        table = "user_transactions"
        ordering = ['-trade_date', '-transaction_time']  # Order by trade date and time descending

    def __str__(self):
        return f"{self.user.username} - {self.symbol} {self.action} {self.option_type}"
    



class UserCreate(BaseModel):
    username: Optional[str]
    password: Optional[str]
    email: Optional[EmailStr]
    full_name: Optional[str]



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