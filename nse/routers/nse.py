from fastapi import FastAPI,APIRouter, Header , Request, Response, HTTPException , status, Depends, Path
from fastapi.openapi.utils import get_openapi
import requests
import logging
import aiohttp
import asyncio
import os
# from dotenv import load_dotenv # no need to load .env here
#from db.models.nse import NIFTY
from datetime import datetime

from fastapi.responses import JSONResponse, HTMLResponse
from typing import Dict, List
from collections import deque, defaultdict


from conf import settings
from db.models.nse import *
from db.models.users import *
from services.utils import execute_native_query , insert_into_table
#from backend.nse.services import *

app = FastAPI(
    title="NSE Options API",
    description="""
    API for retrieving and analyzing NSE options data.
    
    ## Features
    * Historical data retrieval
    * Options chain analysis
    * Strategy building
    * Performance tracking
    
    ## Authentication
    All endpoints require authentication via request_user_id header.
    """,
    version="0.0.1",
    openapi_tags=[{
        "name": "Options Data",
        "description": "Endpoints for retrieving historical options data"
    }],
    openapi_url="/api/v1_0/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)
router = APIRouter(tags=["nse"])
# load_dotenv() # no need to load .env here

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="NSE Options API",
        version="0.0.1",
        description="API for NSE options data analysis",
        routes=app.routes,
    )
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NSE_POST_API_URL = settings.NSE_SERVICE_URL # using settings to get variable from .env



class NSE:
    def __init__(self, timeout=10):
        # Initialize the base URL and session
        self.base_url = 'https://www.nseindia.com'
        
        self.session = aiohttp.ClientSession() # Create aiohttp session
        # Set the headers for the session
        self.session._default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36 Edg/97.0.1072.55",
            "accept": "application/json, text/html, application/xhtml+xml, application/xml;q=0.9, image/avif, image/webp, image/apng, */*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/option-chain",
            "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="97", "Microsoft Edge";v="97"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "Accept-Encoding": "gzip, deflate"  # Remove brotli from accepted encodings
        }
        self.timeout = timeout

    async def get_historical_data(self, symbol, from_date, to_date, expiry_date, option_type, strike_price):
        try:
            # Format the dates correctly
            from_date_str = from_date.strftime('%d-%m-%Y')  # Format: DD-MM-YYYY
            to_date_str = to_date.strftime('%d-%m-%Y')      # Format: DD-MM-YYYY
            expiry_date_str = expiry_date.strftime('%d-%b-%Y')  # Format: DD-MMM-YYYY (e.g., 20-Mar-2025)

            # First, visit the main page to get necessary cookies
            async with self.session.get(self.base_url, timeout=self.timeout) as r:
                if r.status != 200:
                    raise ValueError(f"Failed to establish session: {r.status}")
                
                # Get cookies from the response
                cookies = r.cookies

            # Visit the option chain page to get additional cookies
            async with self.session.get(f"{self.base_url}/option-chain", timeout=self.timeout) as r:
                if r.status != 200:
                    raise ValueError(f"Failed to access option chain: {r.status}")
                
                # Update cookies
                cookies.update(r.cookies)

            # Construct the URL with the correct parameters
            url = f"/api/historical/foCPV?from={from_date_str}&to={to_date_str}&instrumentType=OPTIDX&symbol={symbol}&year={from_date.year}&expiryDate={expiry_date_str}&optionType={option_type}&strikePrice={strike_price}"
            
            # Log the complete URL
            logger.info(f"NSE API URL: {self.base_url + url}")

            # Make the request to the historical data API with cookies
            async with self.session.get(
                self.base_url + url, 
                timeout=self.timeout,
                cookies=cookies,
                headers={
                    **self.session._default_headers,
                    "Connection": "keep-alive"
                }
            ) as r:
                logger.info(f"Status Code: {r.status}")
                
                if r.status == 401:
                    raise ValueError("Authentication failed: Check your API keys or credentials.")
                if r.status != 200:
                    raise ValueError(f"Failed to fetch data from NSE: {r.status}")
                
                try:
                    data = await r.json()
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {str(e)}")
                    return None
                
                if not data or 'data' not in data:
                    logger.error(f"Invalid response format: {data}")
                    return None
                    
                return data.get('data', [])
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            return None
    

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    async def close(self):
        await self.session.close()

def safe_float(value, default=0.0):
    """Safely convert value to float, returning default if conversion fails."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


@router.get("/api/v1_0/index",status_code=status.HTTP_200_OK,
            summary="To check services is running or not",
            description="This endpoint is used to check if the server is running or not",
            responses={
                200: {"description": "Server is running"},
                500: {"description": "Server is not running"}
                })
async def index(request: Request, response: Response):
    return {"message": "Hello, world!"}



def is_duplicate(db_record, nse_record):
    """
    Checks if an NSE record is a duplicate of a database record based on the primary key.
    """
    try:
        nse_expiry = datetime.strptime(nse_record.get("FH_EXPIRY_DT"), '%d-%b-%Y').strftime('%d-%b-%Y')
        nse_date = datetime.strptime(nse_record.get("TIMESTAMP"), '%Y-%m-%d').strftime('%Y-%m-%d')
        return (
            db_record['expiry'] == nse_expiry and
            db_record['date'] == nse_date and
            db_record['option_type'] == nse_record.get("FH_OPTION_TYPE") and
            db_record['strike_price'] == float(nse_record.get("FH_STRIKE_PRICE", 0))
        )
    except (ValueError, TypeError) as e:
        logger.error(f"Error comparing records: {e}")
        return False
    


@router.get("/api/v1_0/search-data/{from_date}/{to_date}/{instrument_type}/{symbol}/{year}/{expiry_date}/{option_type}/{strike_price}",
             status_code=status.HTTP_200_OK,
             responses={
                200: {
                    "description": "Successfully retrieved options data",
                    "content": {
                        "application/json": {
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
                    }
                }})
async def search_data(
    to_date: str, instrument_type: str, symbol: str, 
    year: int, expiry_date: str, option_type: str, strike_price: int,
    request: Request, response: Response,
    from_date: str = Path(...,
                         description="Start date for data search in DD-MM-YYYY format",
                         example="01-03-2025")):
    
    """
    GET API to search for data dynamically.
    - Checks if data exists in the DB.
    - If not found, fetches from NSE using a POST request, saves, and returns.
    
    Args:
        from_date (str): Start date in DD-MM-YYYY format
        to_date (str): End date in DD-MM-YYYY format
        instrument_type (str): Type of instrument (e.g., OPTIDX)
        symbol (str): Symbol name (NIFTY, BANKNIFTY, FINNIFTY)
        year (int): Year of the data
        expiry_date (str): Expiry date in DD-MMM-YYYY format
        option_type (str): Option type (CE/PE)
        strike_price (int): Strike price of the option
    """
    try:
        # Validate input parameters ( need to other symbol if needed )
        if symbol.upper() not in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
            raise HTTPException(status_code=400, detail="Invalid symbol. Must be NIFTY, BANKNIFTY, or FINNIFTY")
        
        # Check if the option type is valid
        if option_type.upper() not in ["CE", "PE"]:
            raise HTTPException(status_code=400, detail="Invalid option type. Must be CE or PE")
        
        # Check if the strike price is positive
        if strike_price <= 0:
            raise HTTPException(status_code=400, detail="Strike price must be positive")

        # Convert date formats from DD-MM-YYYY to YYYY-MM-DD
        try:
            from_date_dt = datetime.strptime(from_date, '%d-%m-%Y').date()
            to_date_dt = datetime.strptime(to_date, '%d-%m-%Y').date()
            expiry_date_dt = datetime.strptime(expiry_date, '%d-%b-%Y').date()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

        from_date_str = from_date_dt.strftime('%Y-%m-%d')
        to_date_str = to_date_dt.strftime('%Y-%m-%d')
        # Convert the dates to match the database format
        # from_date_str = from_date_dt.strftime('%d-%b-%Y')  # Convert to DD-MMM-YYYY
        # to_date_str = to_date_dt.strftime('%d-%b-%Y')      # Convert to DD-MMM-YYYY

        expiry_date_str = expiry_date_dt.strftime('%Y-%m-%d')

        # Validate date ranges
        if from_date_dt > to_date_dt:
            raise HTTPException(status_code=400, detail="from_date cannot be greater than to_date")
        
        if from_date_dt.year != year:
            raise HTTPException(status_code=400, detail="year parameter must match the from_date year")

        logger.info(f"Searching data for {symbol} from {from_date_str} to {to_date_str}")

        table_name = f"{symbol.lower()}"  
        logger.info(f"Searching in table: {table_name}")

        # First, verify data exists in the table
        verify_query = f"""
            SELECT COUNT(*) as count FROM {table_name}
            WHERE FH_STRIKE_PRICE = %s AND FH_OPTION_TYPE = %s AND FH_SYMBOL = %s
            """
        verify_params = [strike_price, option_type, symbol.upper()]
        verify_result = await execute_native_query(verify_query, verify_params)
        logger.info(f"Records found in table with given strike price and option type: {verify_result[0]['count']}")

        # Construct Query with better error handling
        try:
            # Convert expiry_date to match database format
            expiry_date_obj = datetime.strptime(expiry_date, '%d-%b-%Y')
            formatted_expiry = expiry_date_obj.strftime('%d-%b-%Y')  # This will match your database format

            query = f"""
                SELECT * FROM {table_name}
                WHERE TIMESTAMP >= %s - INTERVAL '18:30' HOUR_MINUTE
                AND TIMESTAMP <= %s + INTERVAL '18:30' HOUR_MINUTE
                AND FH_EXPIRY_DT = %s
                AND FH_OPTION_TYPE = %s
                AND FH_STRIKE_PRICE = %s
                AND FH_SYMBOL = %s
                ORDER BY TIMESTAMP ASC
            """
            #params = [from_date_str, to_date_str, formatted_expiry, option_type, float(strike_price), symbol.upper()]
            
            # Format dates as YYYY-MM-DD for MySQL
            from_date_sql = from_date_dt.strftime('%Y-%m-%d')
            to_date_sql = to_date_dt.strftime('%Y-%m-%d')
            # All parameters as strings
            params = [
                from_date_sql,        # From date YYYY-MM-DD
                to_date_sql,          # To date YYYY-MM-DD
                formatted_expiry,     # Expiry as DD-MMM-YYYY
                option_type,          # CE/PE
                float(strike_price),  # Strike price as float
                symbol.upper()        # Symbol
            ]
            # Add debug logging
            #logger.info(f"Adjusted query dates: {from_date_sql} 18:30 to {to_date_sql} 18:30")
            logger.info(f"Query parameters:")
            logger.info(f"Date range: {from_date_str} to {to_date_str}")
            logger.info(f"Formatted expiry date: {formatted_expiry}")
            logger.info(f"Option type: {option_type}")
            logger.info(f"Strike price: {strike_price}")

            # Execute query
            data = await execute_native_query(query, params)

            # Add debug logging for results
            if data:
                logger.info(f"✅ Found {len(data)} records in database")
                return {
                "status": "success",
                "source": f"database/{table_name}",
                "data": data
                }
            # else:
            #     logger.warning("❌ No records found in database")
            #     # Log a sample record from the database for comparison
            #     sample_query = f"SELECT * FROM {table_name} LIMIT 1"
            #     sample_data = await execute_native_query(sample_query, [])
            #     if sample_data:
            #         logger.info(f"Sample record from database: {sample_data[0]}")

            db_data = data if data else []
            db_source = f"database/{table_name}" if data else None

            logger.warning("❌ No data found in database, fetching from NSE")
            
            # Fetch from NSE
            nse = NSE(timeout=30)
            try:
                records = await nse.get_historical_data(
                    symbol=symbol,
                    from_date=from_date_dt,
                    to_date=to_date_dt,
                    expiry_date=expiry_date_dt,
                    option_type=option_type,
                    strike_price=strike_price,
                )

                if records is None or not records:
                    raise HTTPException(status_code=404, detail="No data retrieved from NSE.")

                logger.info(f"✅ Successfully fetched {len(records)} records from NSE")

                new_records = []
                for nse_record in records:
                    query = f"""
                        SELECT * FROM {table_name}
                        WHERE TIMESTAMP = %s
                        AND FH_EXPIRY_DT = %s
                        AND FH_OPTION_TYPE = %s
                        AND FH_STRIKE_PRICE = %s
                        AND FH_SYMBOL = %s
                        """
                    params = [
                        datetime.strptime(nse_record.get("TIMESTAMP"), '%Y-%m-%dT%H:%M:%S.%fZ'),
                        nse_record.get("FH_EXPIRY_DT"),
                        nse_record.get("FH_OPTION_TYPE"),
                        nse_record.get("FH_STRIKE_PRICE"),
                        nse_record.get("FH_SYMBOL")
                        ]    
                        
                    existing_records = await execute_native_query(query, params)

                    if not existing_records:
                        new_records.append(nse_record)
                    else:
                        logger.info(f"Skipping duplicate record: {nse_record}") # we can show only id instead of whole record

                # Store only the non-duplicate records in database
                for record in new_records:
                    try:
                        symbol_value = record.get("FH_SYMBOL")
                        if not symbol_value:
                            logger.warning("Skipping record: Missing symbol")
                            continue
                        required_fields = {
                        "FH_TIMESTAMP": record.get("FH_TIMESTAMP"),
                        "FH_SYMBOL": record.get("FH_SYMBOL"),
                        "FH_INSTRUMENT": record.get("FH_INSTRUMENT"),
                        "FH_STRIKE_PRICE": record.get("FH_STRIKE_PRICE"),
                        "FH_EXPIRY_DT": record.get("FH_EXPIRY_DT"),
                        "FH_OPTION_TYPE": record.get("FH_OPTION_TYPE"),
                        "FH_CLOSING_PRICE": record.get("FH_CLOSING_PRICE"),
                        "FH_LAST_TRADED_PRICE": record.get("FH_LAST_TRADED_PRICE"),
                        "FH_MARKET_LOT": record.get("FH_MARKET_LOT"),
                        "TIMESTAMP": datetime.strptime(record.get("TIMESTAMP"), '%Y-%m-%dT%H:%M:%S.%fZ'),
                        "FH_CHANGE_IN_OI": record.get("FH_CHANGE_IN_OI"),
                        "FH_MARKET_TYPE": record.get("FH_MARKET_TYPE"),
                        "FH_OPENING_PRICE": record.get("FH_OPENING_PRICE"),
                        "FH_OPEN_INT": record.get("FH_OPEN_INT"),
                        "FH_PREV_CLS": record.get("FH_PREV_CLS"),
                        "FH_SETTLE_PRICE": record.get("FH_SETTLE_PRICE"),
                        "FH_TOT_TRADED_QTY": record.get("FH_TOT_TRADED_QTY"),
                        "FH_TOT_TRADED_VAL": record.get("FH_TOT_TRADED_VAL"),
                        "FH_TRADE_HIGH_PRICE": record.get("FH_TRADE_HIGH_PRICE"),
                        "FH_TRADE_LOW_PRICE": record.get("FH_TRADE_LOW_PRICE"),
                        "FH_UNDERLYING_VALUE": safe_float(record.get("FH_UNDERLYING_VALUE"))
                        }

                                                
                        # Store in appropriate table
                        if symbol_value == "NIFTY":
                            await NIFTY.create(**required_fields)
                        elif symbol_value == "BANKNIFTY":
                            await BANKNIFTY.create(**required_fields)
                        elif symbol_value == "FINNIFTY":
                            await FINNIFTY.create(**required_fields)

                    except (KeyError, ValueError) as e:
                        logger.error(f"Error processing record: {e}")
                        continue

                nse_data = new_records if new_records else []
                nse_source = "nse" if new_records else None

            finally:
                await nse.close()
            
            # Transform NSE records to match the database record format
            transformed_nse_data = []
            for record in nse_data:
                transformed_record = {
                "FH_TIMESTAMP": record.get("FH_TIMESTAMP"),
                "FH_SYMBOL": record.get("FH_SYMBOL"),
                "FH_INSTRUMENT": record.get("FH_INSTRUMENT"),
                "FH_STRIKE_PRICE": record.get("FH_STRIKE_PRICE"),
                "FH_EXPIRY_DT": record.get("FH_EXPIRY_DT"),
                "FH_OPTION_TYPE": record.get("FH_OPTION_TYPE"),
                "FH_CLOSING_PRICE": record.get("FH_CLOSING_PRICE"),
                "FH_LAST_TRADED_PRICE": record.get("FH_LAST_TRADED_PRICE"),
                "FH_MARKET_LOT": record.get("FH_MARKET_LOT"),
                "TIMESTAMP": datetime.strptime(record.get("TIMESTAMP"), '%Y-%m-%dT%H:%M:%S.%fZ'),
                "FH_CHANGE_IN_OI": record.get("FH_CHANGE_IN_OI"),
                "FH_MARKET_TYPE": record.get("FH_MARKET_TYPE"),
                "FH_OPENING_PRICE": record.get("FH_OPENING_PRICE"),
                "FH_OPEN_INT": record.get("FH_OPEN_INT"),
                "FH_PREV_CLS": record.get("FH_PREV_CLS"),
                "FH_SETTLE_PRICE": record.get("FH_SETTLE_PRICE"),
                "FH_TOT_TRADED_QTY": record.get("FH_TOT_TRADED_QTY"),
                "FH_TOT_TRADED_VAL": record.get("FH_TOT_TRADED_VAL"),
                "FH_TRADE_HIGH_PRICE": record.get("FH_TRADE_HIGH_PRICE"),
                "FH_TRADE_LOW_PRICE": record.get("FH_TRADE_LOW_PRICE"),
                "FH_UNDERLYING_VALUE": safe_float(record.get("FH_UNDERLYING_VALUE"))
                }
                transformed_nse_data.append(transformed_record)

            # Combine data from database and NSE
            combined_data = db_data + transformed_nse_data

            source = "combined" if db_data and nse_data else (db_source or nse_source)

            return {
                "status": "success",
                "source": source,
                "data": combined_data
            }

        except Exception as e:
            logger.exception(f"❌ Database error: {e}")
            raise HTTPException(status_code=500, detail="Database operation failed")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"❌ Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


