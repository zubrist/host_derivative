from fastapi import APIRouter, Depends, HTTPException, Header, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from db.models.users import *
from typing import List
import uuid
from datetime import datetime, timedelta
from services.nse_service import NSE, get_option_data_with_cache
from db.models.nse import NIFTY

from auth  import generate_access_token
from services.utils import execute_native_query

router = APIRouter()
#oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.post("/api/v1_0/register_user", status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, request:Request, response: Response):
    # Check if username already exists
    if await Users.filter(username=user.username).exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Create new user
    user_dict = user.dict()
    
    
    user_obj = await Users.create(**user_dict)

    return {"Status":"success","data":user_obj}



@router.post('/api/v1_0/user_login', status_code=status.HTTP_202_ACCEPTED)
async def user_login(login_payload: UserLogin, request: Request, response: Response):
    print("[Debug] login started")

    statusStr = "Success"
    user_in_db =  await Users.filter(username=login_payload.username).first()
    if not user_in_db:
        statusStr = "Fail"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='user not found with this username',

        )
    
    # verify password
    if not user_in_db.password == login_payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password is wrong",
        )
    
    # Generate access token
    token_data = {
        "user_id": user_in_db.user_id,
        "user_type": "default"  # or fetch from user_in_db if it's stored
    }
    access_token = generate_access_token(token_data)

    return {
        "Status": statusStr, 
        "access_token": access_token,
        "data":{
            "user_id": user_in_db.user_id,
            "username": user_in_db.username,
            "user_type": "default",
        }
    }

@router.post('/api/v1_0/create_transection', status_code=status.HTTP_201_CREATED)
async def create_transection(trans_payload: TransactionCreate, 
                             request: Request, response: Response,
                             request_user_id: str = Header(None)):
    
    StatusStr = "Success"
    
    # Check if user ID is provided
    if not request_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request-user-id header is required"
        )

    user_id = int(request_user_id)
    user = await Users.get_or_none(user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Date Conversion
    try:
        trade_date_obj = datetime.strptime(trans_payload.trade_date, '%Y-%m-%d').date()
        expiry_date_obj = datetime.strptime(trans_payload.expiry_date, '%Y-%m-%d').date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Please use YYYY-MM-DD."
        )
    
    # Use cache-first approach to fetch entry price
    nse_data = await get_option_data_with_cache(
        symbol=trans_payload.symbol,
        from_date=trade_date_obj,
        to_date=expiry_date_obj,
        expiry_date=expiry_date_obj,
        option_type=trans_payload.option_type,
        strike_price=trans_payload.strike_price
    )
    
    if not nse_data or not isinstance(nse_data, list):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not fetch data from cache or NSE for the given parameters"
        )

    # Find the record for the trade date
    entry_price = None
    market_lot = None
    for record in nse_data:
        if 'FH_TIMESTAMP' in record:
            try:
                record_date = datetime.strptime(record['FH_TIMESTAMP'], '%d-%b-%Y').date()
            except Exception:
                continue
            if record_date == trade_date_obj:
                entry_price = float(record.get('FH_CLOSING_PRICE', 0))
                market_lot = record.get('FH_MARKET_LOT', None)
                break
                
    if entry_price is None or entry_price == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No FH_CLOSING_PRICE found for the trade date"
        )

    # Insert into user_transactions
    txn = await UserTransactions.create(
        user=user,
        symbol=trans_payload.symbol,
        instrument=trans_payload.instrument,
        strike_price=trans_payload.strike_price,
        option_type=trans_payload.option_type,
        lots=trans_payload.lots,
        trade_date=trade_date_obj,
        expiry_date=expiry_date_obj,
        entry_price=entry_price,
        market_lot=market_lot,
        status='active'
    )

    return {
        "status": "success",
        "transaction_id": txn.transaction_id,
        "entry_price": entry_price
    }
