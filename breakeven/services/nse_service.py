import aiohttp
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class NSE:
    def __init__(self, timeout=10):
        self.base_url = 'https://www.nseindia.com'
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
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
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }
        self.timeout = timeout

    async def _create_session(self):
        """Create aiohttp session if not exists"""
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers)

    async def get_historical_data(self, symbol: str, from_date: datetime, to_date: datetime, 
                                expiry_date: datetime, option_type: str, strike_price: float) -> List[Dict[str, Any]]:
        """
        Fetch historical options data from NSE
        """
        try:
            # Ensure session is created
            await self._create_session()
            
            # Format dates
            from_date_str = from_date.strftime('%d-%m-%Y')
            to_date_str = to_date.strftime('%d-%m-%Y')
            expiry_date_str = expiry_date.strftime('%d-%b-%Y').upper()  # Make sure it's uppercase
            
            # Step 1: Establish session with NSE homepage
            logger.info("Establishing session with NSE homepage...")
            async with self.session.get(self.base_url, timeout=self.timeout) as r:
                if r.status != 200:
                    logger.error(f"Failed to establish session: {r.status}")
                    raise ValueError(f"Failed to establish session: {r.status}")
                cookies = r.cookies
                logger.info("Session established successfully")
            
            # Step 2: Access option chain page to get additional cookies
            logger.info("Accessing option chain page...")
            async with self.session.get(f"{self.base_url}/option-chain", timeout=self.timeout) as r:
                if r.status != 200:
                    logger.error(f"Failed to access option chain: {r.status}")
                    raise ValueError(f"Failed to access option chain: {r.status}")
                cookies.update(r.cookies)
                logger.info("Option chain accessed successfully")
            
            # Step 3: Fetch historical data - FIXED URL
            # Use historicalOR instead of historical
            url = f"/api/historicalOR/foCPV?from={from_date_str}&to={to_date_str}&instrumentType=OPTIDX&symbol={symbol}&year={expiry_date.year}&expiryDate={expiry_date_str}&optionType={option_type}&strikePrice={strike_price}"
            full_url = self.base_url + url
            logger.info(f"NSE API URL: {full_url}")
            
            async with self.session.get(
                full_url,
                timeout=self.timeout,
                cookies=cookies
            ) as r:
                logger.info(f"Status Code: {r.status}")
                
                if r.status == 401:
                    logger.error("Authentication failed")
                    raise ValueError("Authentication failed: Check your API keys or credentials.")
                
                if r.status != 200:
                    error_text = await r.text()
                    logger.error(f"Failed to fetch data from NSE: {r.status}, Response: {error_text}")
                    raise ValueError(f"Failed to fetch data from NSE: {r.status}")
                
                try:
                    data = await r.json()
                    logger.info(f"Response received, type: {type(data)}")
                    
                    if isinstance(data, dict):
                        logger.info(f"Response keys: {list(data.keys())}")
                        if 'data' in data:
                            result = data.get('data', [])
                            logger.info(f"Number of records: {len(result)}")
                            if result:
                                logger.info(f"Sample record keys: {list(result[0].keys())}")
                                logger.info(f"First record FH_TIMESTAMP: {result[0].get('FH_TIMESTAMP')}")
                                logger.info(f"First record FH_LAST_TRADED_PRICE: {result[0].get('FH_LAST_TRADED_PRICE')}")
                            return result
                        else:
                            logger.warning("No 'data' key found in response")
                            return []
                    else:
                        logger.warning(f"Unexpected response format: {type(data)}")
                        return []
                        
                except Exception as json_error:
                    response_text = await r.text()
                    logger.error(f"Failed to parse JSON response: {str(json_error)}")
                    logger.error(f"Response text: {response_text[:500]}...")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching NSE data: {str(e)}")
            return []

    async def __aenter__(self):
        await self._create_session()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    async def close(self):
        """Close the aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default