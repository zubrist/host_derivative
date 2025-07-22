from fastapi import APIRouter, Depends, HTTPException, Header, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from db.models.users import *
from typing import List
import uuid
from datetime import datetime, timedelta
from services.nse_service import NSE
from db.models.nse import NIFTY

from auth  import generate_access_token
from services.utils import execute_native_query
import traceback

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
    import traceback

    StatusStr = "Success"

    # Check if user ID is provided
    if not request_user_id:
        detail = "request-user-id header is required"
        print(f"create_transection error: {detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

    user_id = int(request_user_id)

    user = await Users.get_or_none(user_id=user_id)
    if not user:
        detail = "User not found"
        print(f"create_transection error: {detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )

    # --- Date Conversion Start ---
    try:
        trade_date_obj = datetime.strptime(trans_payload.trade_date, '%Y-%m-%d').date()
        expiry_date_obj = datetime.strptime(trans_payload.expiry_date, '%Y-%m-%d').date()
    except ValueError:
        detail = "Invalid date format. Please use YYYY-MM-DD."
        print(f"create_transection error: {detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

    # Fetch entry price from NSE
    try:
        async with NSE(timeout=20) as nse:
            nse_data = await nse.get_historical_data(
                symbol=trans_payload.symbol,
                from_date=trade_date_obj,
                to_date=expiry_date_obj,
                expiry_date=expiry_date_obj,
                option_type=trans_payload.option_type,
                strike_price=trans_payload.strike_price
            )
    except Exception as e:
        detail = f"Exception while fetching data from NSE: {str(e)}"
        print(f"create_transection error: {detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )

    if not nse_data or not isinstance(nse_data, list):
        detail = "Could not fetch data from NSE for the given parameters"
        print(f"create_transection error: {detail}")
        #print(f"NSE response: {nse_data}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )

    # Insert NIFTY records
    try:
        for record in nse_data:
            exists = await NIFTY.filter(
                FH_SYMBOL=record.get("FH_SYMBOL"),
                FH_EXPIRY_DT=record.get("FH_EXPIRY_DT"),
                FH_OPTION_TYPE=record.get("FH_OPTION_TYPE"),
                FH_STRIKE_PRICE=record.get("FH_STRIKE_PRICE"),
                FH_TIMESTAMP=record.get("FH_TIMESTAMP")
            ).exists()
            if exists:
                continue  # Skip duplicates

            await NIFTY.create(
                FH_EXPIRY_DT=record.get("FH_EXPIRY_DT"),
                FH_INSTRUMENT=record.get("FH_INSTRUMENT"),
                FH_OPTION_TYPE=record.get("FH_OPTION_TYPE"),
                FH_STRIKE_PRICE=record.get("FH_STRIKE_PRICE"),
                FH_SYMBOL=record.get("FH_SYMBOL"),
                TIMESTAMP=record.get("TIMESTAMP"),
                FH_CHANGE_IN_OI=record.get("FH_CHANGE_IN_OI"),
                FH_CLOSING_PRICE=record.get("FH_CLOSING_PRICE"),
                FH_LAST_TRADED_PRICE=record.get("FH_LAST_TRADED_PRICE"),
                FH_MARKET_LOT=record.get("FH_MARKET_LOT"),
                FH_MARKET_TYPE=record.get("FH_MARKET_TYPE"),
                FH_OPENING_PRICE=record.get("FH_OPENING_PRICE"),
                FH_OPEN_INT=record.get("FH_OPEN_INT"),
                FH_PREV_CLS=record.get("FH_PREV_CLS"),
                FH_SETTLE_PRICE=record.get("FH_SETTLE_PRICE"),
                FH_TIMESTAMP=record.get("FH_TIMESTAMP"),
                FH_TOT_TRADED_QTY=record.get("FH_TOT_TRADED_QTY"),
                FH_TOT_TRADED_VAL=record.get("FH_TOT_TRADED_VAL"),
                FH_TRADE_HIGH_PRICE=record.get("FH_TRADE_HIGH_PRICE"),
                FH_TRADE_LOW_PRICE=record.get("FH_TRADE_LOW_PRICE"),
                FH_UNDERLYING_VALUE=record.get("FH_UNDERLYING_VALUE"),
            )
    except Exception as e:
        detail = f"Exception while inserting NIFTY records: {str(e)}"
        print(f"create_transection error: {detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )

    # Find the record for the trade date
    entry_price = None
    market_lot = None
    try:
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
    except Exception as e:
        detail = f"Exception while searching for entry price: {str(e)}"
        print(f"create_transection error: {detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )

    if entry_price is None or entry_price == 0:
        detail = "No FH_CLOSING_PRICE found for the trade date"
        print(f"create_transection error: {detail}")
        #print(f"NSE data: {nse_data}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )

    # Insert into user_transactions
    try:
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
    except Exception as e:
        detail = f"Exception while creating user transaction: {str(e)}"
        print(f"create_transection error: {detail}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )

    return {
        "status": "success",
        "transaction_id": txn.transaction_id,
        "entry_price": entry_price
    }




@router.delete('/api/v1_0/delete_user_transactions', status_code=status.HTTP_200_OK)
async def delete_user_transactions(
    request: Request, 
    response: Response,
    request_user_id: str = Header(None)
):
    """
    Delete all transactions for a specific user.
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
        request_user_id: User ID from header
        
    Returns:
        Dict: Success message with count of deleted transactions
        
    Raises:
        HTTPException: If user not found or deletion fails
    """
    try:
        # Check if user ID is provided
        if not request_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="request-user-id header is required"
            )

        user_id = int(request_user_id)

        # Check if user exists
        user = await Users.get_or_none(user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Get count of transactions before deletion
        transaction_count = await UserTransactions.filter(user_id=user_id).count()
        
        if transaction_count == 0:
            return {
                "status": "success",
                "message": "No transactions found for this user",
                "deleted_count": 0
            }

        # Delete all transactions for the user
        deleted_count = await UserTransactions.filter(user_id=user_id).delete()

        return {
            "status": "success",
            "message": f"Successfully deleted all transactions for user {user_id}",
            "deleted_count": deleted_count
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    except Exception as e:
        print(f"delete_user_transactions error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting transactions: {str(e)}"
        )
    




@router.delete('/api/v1_0/delete_transaction/{transaction_id}', status_code=status.HTTP_200_OK)
async def delete_specific_transaction(
    transaction_id: int,
    request: Request, 
    response: Response,
    request_user_id: str = Header(None)
):
    """
    Delete a specific transaction by transaction ID for a user.
    
    Args:
        transaction_id: ID of the transaction to delete
        request: FastAPI request object
        response: FastAPI response object
        request_user_id: User ID from header
        
    Returns:
        Dict: Success message
        
    Raises:
        HTTPException: If user/transaction not found or deletion fails
    """
    try:
        # Check if user ID is provided
        if not request_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="request-user-id header is required"
            )

        user_id = int(request_user_id)

        # Check if user exists
        user = await Users.get_or_none(user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Find the specific transaction
        transaction = await UserTransactions.get_or_none(
            transaction_id=transaction_id,
            user_id=user_id
        )
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found or does not belong to this user"
            )

        # Delete the transaction
        await transaction.delete()

        return {
            "status": "success",
            "message": f"Successfully deleted transaction {transaction_id}",
            "transaction_id": transaction_id
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID or transaction ID format"
        )
    except Exception as e:
        print(f"delete_specific_transaction error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting the transaction: {str(e)}"
        )    
    




@router.get('/api/v1_0/get_active_transactions', status_code=status.HTTP_200_OK)
async def get_active_transactions(
    request: Request, 
    response: Response,
    request_user_id: str = Header(None)
):
    """
    Fetch only active transactions for a specific user.
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
        request_user_id: User ID from header
        
    Returns:
        Dict: Success message with list of active transactions
        
    Raises:
        HTTPException: If user not found or fetch fails
    """
    try:
        # Check if user ID is provided
        if not request_user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="request-user-id header is required"
            )

        user_id = int(request_user_id)

        # Check if user exists
        user = await Users.get_or_none(user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Fetch only active transactions
        active_transactions = await UserTransactions.filter(
            user_id=user_id,
            status='active'
        ).order_by('-trade_date', '-transaction_id').all()

        if not active_transactions:
            return {
                "status": "success",
                "message": "No active transactions found for this user",
                "data": [],
                "count": 0
            }

        # Format transaction data with additional calculated fields
        transaction_list = []
        for txn in active_transactions:
            # Calculate days to expiry
            days_to_expiry = (txn.expiry_date - datetime.now().date()).days
            
            # Calculate total investment
            total_investment = float(txn.entry_price) * txn.lots * txn.market_lot if txn.entry_price and txn.market_lot else 0
            
            transaction_data = {
                "transaction_id": txn.transaction_id,
                "symbol": txn.symbol,
                "instrument": txn.instrument,
                "strike_price": float(txn.strike_price),
                "option_type": txn.option_type,
                "lots": txn.lots,
                "trade_date": txn.trade_date.strftime('%Y-%m-%d'),
                "expiry_date": txn.expiry_date.strftime('%Y-%m-%d'),
                "entry_price": float(txn.entry_price) if txn.entry_price else None,
                "market_lot": txn.market_lot,
                "status": txn.status,
                "days_to_expiry": days_to_expiry,
                "total_investment": total_investment,
                "is_expired": days_to_expiry < 0,
            }
            transaction_list.append(transaction_data)

        return {
            "status": "success",
            "message": f"Successfully fetched {len(transaction_list)} active transactions",
            "data": transaction_list,
            "count": len(transaction_list),
            "summary": {
                "total_active_positions": len(transaction_list),
                "total_investment": sum(txn["total_investment"] for txn in transaction_list),
                "expired_positions": len([txn for txn in transaction_list if txn["is_expired"]])
            }
        }

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    except Exception as e:
        print(f"get_active_transactions error: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching active transactions: {str(e)}"
        )

