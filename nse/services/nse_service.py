import aiohttp
import logging
from datetime import datetime
from db.models.nse import NIFTY
from services.utils import execute_native_query

logger = logging.getLogger(__name__)

class NSE:
    def __init__(self, timeout=60):  # Increased timeout
        self.base_url = 'https://www.nseindia.com'
        self.session = aiohttp.ClientSession()
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
            "Accept-Encoding": "gzip, deflate"
        }
        self.timeout = timeout

    async def get_historical_data(self, symbol, from_date, to_date, expiry_date, option_type, strike_price):
        try:
            from_date_str = from_date.strftime('%d-%m-%Y')
            to_date_str = to_date.strftime('%d-%m-%Y')
            expiry_date_str = expiry_date.strftime('%d-%b-%Y')
            async with self.session.get(self.base_url, timeout=self.timeout) as r:
                if r.status != 200:
                    raise ValueError(f"Failed to establish session: {r.status}")
                cookies = r.cookies
            async with self.session.get(f"{self.base_url}/option-chain", timeout=self.timeout) as r:
                if r.status != 200:
                    raise ValueError(f"Failed to access option chain: {r.status}")
                cookies.update(r.cookies)
            url = f"/api/historical/foCPV?from={from_date_str}&to={to_date_str}&instrumentType=OPTIDX&symbol={symbol}&year={from_date.year}&expiryDate={expiry_date_str}&optionType={option_type}&strikePrice={strike_price}"
            logger.info(f"NSE API URL: {self.base_url + url}")
            async with self.session.get(
                self.base_url + url,
                timeout=self.timeout,
                cookies=cookies,
                headers={**self.session._default_headers, "Connection": "keep-alive"}
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

async def get_option_data_with_cache(symbol, from_date, to_date, expiry_date, option_type, strike_price):
    """
    Get option data from cache (NIFTY table) first, then fetch from NSE if not found
    """
    try:
        # Convert dates to string format for query
        from_date_str = from_date.strftime('%d-%b-%Y')
        to_date_str = to_date.strftime('%d-%b-%Y') 
        expiry_date_str = expiry_date.strftime('%d-%b-%Y')
        
        # Check cache first using native query for better performance
        cache_query = """
        SELECT 
            id, FH_TIMESTAMP, FH_SYMBOL, FH_INSTRUMENT, FH_STRIKE_PRICE, FH_EXPIRY_DT, 
            FH_OPTION_TYPE, FH_CLOSING_PRICE, FH_LAST_TRADED_PRICE, FH_MARKET_LOT, 
            TIMESTAMP, FH_CHANGE_IN_OI, FH_MARKET_TYPE, FH_OPENING_PRICE, FH_OPEN_INT, 
            FH_PREV_CLS, FH_SETTLE_PRICE, FH_TOT_TRADED_QTY, FH_TOT_TRADED_VAL, 
            FH_TRADE_HIGH_PRICE, FH_TRADE_LOW_PRICE, FH_UNDERLYING_VALUE
        FROM nifty 
        WHERE FH_SYMBOL = %s 
        AND FH_STRIKE_PRICE = %s 
        AND FH_EXPIRY_DT = %s 
        AND FH_OPTION_TYPE = %s 
        AND STR_TO_DATE(FH_TIMESTAMP, '%%d-%%b-%%Y') BETWEEN STR_TO_DATE(%s, '%%d-%%b-%%Y') AND STR_TO_DATE(%s, '%%d-%%b-%%Y')
        ORDER BY FH_TIMESTAMP
        """
        
        cached_data = await execute_native_query(
            cache_query, 
            [symbol, float(strike_price), expiry_date_str, option_type, from_date_str, to_date_str]
        )
        
        if cached_data and len(cached_data) > 0:
            logger.info(f"Found {len(cached_data)} cached records for {symbol} {strike_price} {option_type}")
            # Convert to NSE API format
            return convert_db_to_nse_format(cached_data)
        
        # If not in cache, fetch from NSE
        logger.info(f"Cache miss - fetching from NSE: {symbol} {strike_price} {option_type}")
        async with NSE(timeout=60) as nse:  # Increased timeout
            nse_data = await nse.get_historical_data(
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                expiry_date=expiry_date,
                option_type=option_type,
                strike_price=strike_price
            )
        
        if nse_data:
            # Store in cache for future use
            await store_nse_data_to_cache(nse_data)
            logger.info(f"Stored {len(nse_data)} records to cache")
            
        return nse_data
        
    except Exception as e:
        logger.error(f"Error in get_option_data_with_cache: {str(e)}")
        return None

def convert_db_to_nse_format(db_records):
    """Convert database records to NSE API format"""
    nse_format = []
    try:
        for record in db_records:
            # Fix the logging statement - handle the record properly
            try:
                record_preview = str(record[:5]) if len(record) > 5 else str(record)
                logger.info(f"Processing record with {len(record)} columns: {record_preview}")
            except Exception as log_error:
                logger.info(f"Processing record with unknown structure: {type(record)}")
            
            # Ensure record has enough elements
            if len(record) < 22:
                logger.warning(f"Record has insufficient columns: {len(record)}, skipping")
                continue
                
            # Map database record to NSE format
            nse_record = {
                'FH_SYMBOL': safe_get_value(record, 2, 'NIFTY'),
                'FH_EXPIRY_DT': safe_get_value(record, 5),
                'FH_OPTION_TYPE': safe_get_value(record, 6),
                'FH_STRIKE_PRICE': safe_float(safe_get_value(record, 4)),
                'FH_TIMESTAMP': safe_get_value(record, 1),
                'FH_INSTRUMENT': safe_get_value(record, 3, 'OPTIDX'),
                'FH_CLOSING_PRICE': safe_float(safe_get_value(record, 7)),
                'FH_LAST_TRADED_PRICE': safe_float(safe_get_value(record, 8)),
                'FH_MARKET_LOT': safe_get_value(record, 9, 75),
                'TIMESTAMP': safe_get_value(record, 10),
                'FH_CHANGE_IN_OI': safe_float(safe_get_value(record, 11)),
                'FH_MARKET_TYPE': safe_get_value(record, 12, 'N'),
                'FH_OPENING_PRICE': safe_float(safe_get_value(record, 13)),
                'FH_OPEN_INT': safe_float(safe_get_value(record, 14)),
                'FH_PREV_CLS': safe_float(safe_get_value(record, 15)),
                'FH_SETTLE_PRICE': safe_float(safe_get_value(record, 16)),
                'FH_TOT_TRADED_QTY': safe_float(safe_get_value(record, 17)),
                'FH_TOT_TRADED_VAL': safe_float(safe_get_value(record, 18)),
                'FH_TRADE_HIGH_PRICE': safe_float(safe_get_value(record, 19)),
                'FH_TRADE_LOW_PRICE': safe_float(safe_get_value(record, 20)),
                'FH_UNDERLYING_VALUE': safe_float(safe_get_value(record, 21)),
            }
            
            # Validate essential fields
            if nse_record['FH_CLOSING_PRICE'] is not None and nse_record['FH_CLOSING_PRICE'] > 0:
                nse_format.append(nse_record)
                logger.debug(f"Added record: {nse_record['FH_SYMBOL']} {nse_record['FH_STRIKE_PRICE']} {nse_record['FH_OPTION_TYPE']} - Price: {nse_record['FH_CLOSING_PRICE']}")
            else:
                logger.warning(f"Skipping record with invalid closing price: {nse_record['FH_CLOSING_PRICE']}")
                
        logger.info(f"Successfully converted {len(nse_format)} records from {len(db_records)} database records")
        return nse_format
        
    except Exception as e:
        logger.error(f"Error in convert_db_to_nse_format: {str(e)}", exc_info=True)
        return []

def safe_get_value(record, index, default=None):
    """Safely get value from record by index"""
    try:
        if isinstance(record, (list, tuple)) and len(record) > index:
            value = record[index]
            return value if value is not None else default
        elif hasattr(record, '__getitem__'):  # Handle other sequence types
            value = record[index]
            return value if value is not None else default
        return default
    except (IndexError, TypeError, KeyError) as e:
        logger.warning(f"Error accessing index {index} from record type {type(record)}: {e}")
        return default

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        # Handle string values
        if isinstance(value, str):
            # Remove any non-numeric characters except decimal point and minus
            cleaned = ''.join(c for c in value if c.isdigit() or c in '.-')
            if cleaned and cleaned != '-' and cleaned != '.':
                return float(cleaned)
        return default
    except (ValueError, TypeError) as e:
        logger.debug(f"Error converting {value} to float: {e}")
        return default

async def store_nse_data_to_cache(nse_data):
    """Store NSE data to NIFTY table cache"""
    try:
        for record in nse_data:
            # Check if record already exists
            exists = await NIFTY.filter(
                FH_SYMBOL=record.get("FH_SYMBOL"),
                FH_EXPIRY_DT=record.get("FH_EXPIRY_DT"),
                FH_OPTION_TYPE=record.get("FH_OPTION_TYPE"),
                FH_STRIKE_PRICE=record.get("FH_STRIKE_PRICE"),
                FH_TIMESTAMP=record.get("FH_TIMESTAMP")
            ).exists()
            
            if not exists:
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
        logger.error(f"Error storing NSE data to cache: {str(e)}")

def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default