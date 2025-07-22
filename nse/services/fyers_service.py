import base64
import hmac
import os
import struct
import time
import requests
import math
import logging
import datetime
from datetime import datetime, timedelta
import pandas as pd
from fyers_apiv3 import fyersModel
import numpy as np
from urllib.parse import urlparse, parse_qs
import json
import math
import calendar
from db.models.volatility import IndexHistoricalData



logging.basicConfig(level=logging.DEBUG) # Set logging level to DEBUG for detailed output
logger = logging.getLogger(__name__)

# --- Fyers Access Token Functionality ---
totp_key = "UXBTESMDAORW67VOEYTH7ZZ3P7OTZLGZ"  # totp_key (ex., "OMKRABCDCDVDFGECLWXK6OVB7T4DTKU5")
username = "YA47373"  # Fyers Client ID (ex., "TK01248")
pin = 7872  # four-digit PIN
client_id = "FYZT8L00T9-100"  # App ID of the created app (ex., "L9NY305RTW-100")
secret_key = "QQN6HP1VZD"  # Secret ID of the created app
redirect_uri = "https://127.0.0.1:5000/"  # Redircet URL you entered while creating the app (ex., "https://trade.fyers.in/api-login/redirect-uri/index.html")

# Initialize the Fyers API client
access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIiwieDoyIl0sImF0X2hhc2giOiJnQUFBQUFCb1hCMnYzeFRUbXB0LVJVaU9nNjFlbldRZVE1cHBDQWlkRWdfQURfR0hMYzlSYkZaQ3lkM1M0M3QtVnIwU29WQVp6U0R6a2ozb1NQdmVXamdSanF3X18xSUZXcW56aGF5NzNoVDQwa1REelF1N05ROD0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiIzNzJmNjg5NTlmYWQ2NDBkOGEyMmQ3NTEzMWU3ODk0ZjE3MDViYWU5MzNkNjYzMzE3MjY5NjNmZiIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWUE0NzM3MyIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzUwODk3ODAwLCJpYXQiOjE3NTA4NjczNzUsImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc1MDg2NzM3NSwic3ViIjoiYWNjZXNzX3Rva2VuIn0.lbnlWdEO4sWt6LZl9Bv4LgmO6ueYduWGLBZqAYwCHLw"  # or your existing token
client_id = "FYZT8L00T9-100"
fyers = fyersModel.FyersModel(client_id=client_id, token=access_token)



def totp(key, time_step=30, digits=6, digest="sha1"):
    key = base64.b32decode(key.upper() + "=" * ((8 - len(key)) % 8))
    counter = struct.pack(">Q", int(time.time() / time_step))
    mac = hmac.new(key, counter, digest).digest()
    offset = mac[-1] & 0x0F
    binary = struct.unpack(">L", mac[offset: offset + 4])[0] & 0x7FFFFFFF
    return str(binary)[-digits:].zfill(digits)




def get_token():
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
    }

    s = requests.Session()
    s.headers.update(headers)

    data1 = f'{{"fy_id":"{base64.b64encode(f"{username}".encode()).decode()}","app_id":"2"}}'
    r1 = s.post("https://api-t2.fyers.in/vagator/v2/send_login_otp_v2", data=data1)

    request_key = r1.json()["request_key"]
    data2 = f'{{"request_key":"{request_key}","otp":{totp(totp_key)}}}'
    r2 = s.post("https://api-t2.fyers.in/vagator/v2/verify_otp", data=data2)
    assert r2.status_code == 200, f"Error in r2:\n {r2.text}"

    request_key = r2.json()["request_key"]
    data3 = f'{{"request_key":"{request_key}","identity_type":"pin","identifier":"{base64.b64encode(f"{pin}".encode()).decode()}"}}'
    r3 = s.post("https://api-t2.fyers.in/vagator/v2/verify_pin_v2", data=data3)
    assert r3.status_code == 200, f"Error in r3:\n {r3.json()}"

    headers = {"authorization": f"Bearer {r3.json()['data']['access_token']}", "content-type": "application/json; charset=UTF-8"}
    data4 = f'{{"fyers_id":"{username}","app_id":"{client_id[:-4]}","redirect_uri":"{redirect_uri}","appType":"100","code_challenge":"","state":"abcdefg","scope":"","nonce":"","response_type":"code","create_cookie":true}}'
    #r4 = s.post("https://api.fyers.in/api/v2/token", headers=headers, data=data4)
    #r4 = s.post("https://api-t1.fyers.in/api/v3/token", headers=headers, data=data4)
    r4 = s.post("https://api-t1.fyers.in/api/v3/token", headers=headers, data=data4)
    assert r4.status_code == 308, f"Error in r4:\n {r4.json()}"

    parsed = urlparse(r4.json()["Url"])
    auth_code = parse_qs(parsed.query)["auth_code"][0]

    session = fyersModel.SessionModel(client_id=client_id, secret_key=secret_key, redirect_uri=redirect_uri, response_type="code", grant_type="authorization_code")
    session.set_token(auth_code)
    response = session.generate_token()
    if response and 'access_token' in response:
        return response["access_token"]
    else:
        raise Exception(f"Failed to generate access token: {response}")



## fetch_historical_data from Fyers
'''
def fetch_historical_data(symbol, start_date, end_date, interval="D"):
    access_token = get_token()
    fyers = fyersModel.FyersModel(client_id=client_id, token=access_token)

    all_candles = []

    # Convert string dates to datetime objects
    current_end_date = datetime.strptime(end_date, "%Y-%m-%d")
    overall_start_date = datetime.strptime(start_date, "%Y-%m-%d")

    data = {
        "symbol": symbol,
        "resolution": interval,
        "date_format": "1",  # Use "1" for string dates
        "range_from": start_date,
        "range_to": end_date,
        "cont_flag": "1"
    }
    response = fyers.history(data)
    if response['s'] == 'ok':
        df = pd.DataFrame(response['candles'], columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['date'], unit='s')
        df.set_index('date', inplace=True)
        return df
    else:
        print("Error fetching data:", response)
        return None
    '''

# NEW FETCH HISTORICAL DATA

def fetch_historical_data(symbol: str, end_date_str: str, years_of_data: int, interval: str = "D"):
    """
    Fetches historical data for a symbol for a specified number of years ending on end_date_str.
    Data is fetched year by year.

    Args:
        symbol (str): The trading symbol (e.g., "NSE:NIFTY50-INDEX").
        end_date_str (str): The end date for the data in "YYYY-MM-DD" format.
        years_of_data (int): The number of past full years of data to fetch, plus the current year up to end_date.
                              Example: end_date_str="2025-04-30", years_of_data=4 means data from
                              2021-01-01 to 2021-12-31, ..., 2024-01-01 to 2024-12-31,
                              and 2025-01-01 to 2025-04-30.
        interval (str): The data interval (e.g., "D" for daily).

    Returns:
        pandas.DataFrame: A DataFrame containing the historical data, or None if an error occurs.
    """
    try: 
        print("Debug: Starting fetch_historical_data")
        access_token = get_token()

        print(f"Debug: Got access token: {access_token[:20]}...")

        # The fyersModel should be imported. It might be fyersModel.FyersModel or similar
        # depending on the library version.
        try:
            fyers = fyersModel.FyersModel(
                client_id=client_id,
                token=access_token,
                is_async=False
            )
            print("Debug: FyersModel initialized successfully")
        except Exception as e:
            print(f"Debug: Error initializing FyersModel: {str(e)}")
            raise

        all_candles = []

        try:
            target_end_date_obj = datetime.strptime(end_date_str, "%Y-%m-%d")
        except ValueError:
            print(f"Error: Invalid end_date_str format. Please use YYYY-MM-DD. Got: {end_date_str}")
            return None

        if not isinstance(years_of_data, int) or years_of_data < 0: # Allow 0 for current year only
            print("Error: years_of_data must be a non-negative integer.")
            return None

        # Calculate the range of years to fetch
        # If years_of_data = 4 and end_date is 2025-04-30, we fetch for 2021, 2022, 2023, 2024, and part of 2025.
        # The first year in the iteration will be target_end_date_obj.year - years_of_data.
        first_year_to_fetch = target_end_date_obj.year - years_of_data
        last_year_to_fetch = target_end_date_obj.year # This is the year of the end_date_str

        print(f"Preparing to fetch data for '{symbol}' from year {first_year_to_fetch} up to {end_date_str} (covering {years_of_data} prior full year(s) plus current year portion).")

        for year_iter in range(first_year_to_fetch, last_year_to_fetch + 1):
            current_chunk_start_date_str = f"{year_iter}-01-01"
            
            if year_iter < last_year_to_fetch:
                # For full years before the target_end_date_obj's year
                current_chunk_end_date_str = f"{year_iter}-12-31"
            else:
                # For the final year (which is target_end_date_obj.year), fetch up to target_end_date_obj
                current_chunk_end_date_str = target_end_date_obj.strftime("%Y-%m-%d")
            
            # Ensure the chunk_start_date is not later than chunk_end_date.
            if datetime.strptime(current_chunk_start_date_str, "%Y-%m-%d") > datetime.strptime(current_chunk_end_date_str, "%Y-%m-%d"):
                print(f"    Skipping data fetch for year {year_iter}: chunk start date {current_chunk_start_date_str} is after chunk end date {current_chunk_end_date_str}.")
                continue

            payload = {
                "symbol": symbol,
                "resolution": interval,
                "date_format": "1",   # "1" for epoch timestamp in response
                "range_from": current_chunk_start_date_str,
                "range_to": current_chunk_end_date_str,
                "cont_flag": "1"      # For continuous data for expired futures
            }
            
            print(f"Fetching data for '{symbol}' from {payload['range_from']} to {payload['range_to']}")
            #response = fyers.history(data=payload) # Pass payload with keyword 'data='
            try:
                response = fyers.history(data=payload)
                print(f"Debug: API response status: {response.get('s', 'no status')}")
            except Exception as e:
                print(f"Debug: Error calling fyers.history: {str(e)}")
                raise
            if response and response.get('s') == 'ok':
                if response.get('candles'):
                    all_candles.extend(response['candles'])
                    print(f"    Successfully fetched {len(response['candles'])} candles for {payload['range_from']} to {payload['range_to']}.")
                else:
                    print(f"    No data in 'candles' (s='ok') for range: {payload['range_from']} to {payload['range_to']}.")
            elif response and response.get('s') == 'no_data':
                print(f"    API reported no data (s='no_data') for range: {payload['range_from']} to {payload['range_to']}. Message: {response.get('message')}")
            else:
                error_message = response.get('message', 'Unknown error') if response else "No response or malformed response from API"
                print(f"    Error fetching data for range {payload['range_from']} to {payload['range_to']}: {error_message}")
                # print(f"    Full response for error: {response}") # Uncomment for detailed debugging
                return None # Fail fast if any chunk results in an error
            
        if not all_candles:
            print(f"No historical data was fetched for '{symbol}' after all attempts for the period ending {end_date_str} covering {years_of_data} prior year(s).")
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume']).set_index(pd.to_datetime([]))


        # Convert all collected candles to a DataFrame
        df = pd.DataFrame(all_candles, columns=['date', 'open', 'high', 'low', 'close', 'volume'])
        
        # Convert 'date' from epoch timestamp to datetime objects
        df['date'] = pd.to_datetime(df['date'], unit='s')
        df.set_index('date', inplace=True)
        
        # Sort by date as data from chunks might not be perfectly ordered
        df = df.sort_index()

        # Remove duplicate dates if any
        df = df[~df.index.duplicated(keep='first')]
        
        # Filter to ensure data is within the *overall* requested date range.
        # The overall_start_date is January 1st of the first_year_to_fetch.
        # The overall_end_date is the target_end_date_obj.
        overall_start_date_for_filter = datetime(first_year_to_fetch, 1, 1)
        
        # Apply the precise range filtering. Pandas slicing with datetime index includes both start and end.
        df = df.loc[overall_start_date_for_filter : target_end_date_obj]

        if df.empty:
            print(f"Dataframe is empty after processing for '{symbol}' ending {end_date_str} (requested {years_of_data} prior years).")
        else:
            print(f"Successfully processed data for '{symbol}'. Total records: {len(df)}. Date range in DataFrame: {df.index.min()} to {df.index.max()}")
        
        return df

    except Exception as e:
        print(f"Debug: Top-level error in fetch_historical_data: {str(e)}")
        raise

def get_yearly_breakdown(df):
    # Get the stats first
    yearly_stats = df.groupby(df.index.year).agg({
        'close': ['count', 'first', 'last', 'min', 'max']
    }).round(2)
    
    # Convert to a more JSON-friendly format
    result = {}
    for year in yearly_stats.index:
        result[str(year)] = {
            "trading_days": int(yearly_stats.loc[year, ('close', 'count')]),
            "first_close": float(yearly_stats.loc[year, ('close', 'first')]),
            "last_close": float(yearly_stats.loc[year, ('close', 'last')]),
            "min_close": float(yearly_stats.loc[year, ('close', 'min')]),
            "max_close": float(yearly_stats.loc[year, ('close', 'max')])
        }
    
    return result

# calculate_volatility
def calculate_volatility(dates,closing_prices):
    if len(closing_prices) < 2:
        raise ValueError("At least two closing prices are required.")

    percentage_returns = []

    #print(f" Calculations of month {dates[0].month} and year {dates[0].year} \n")
    # # Calculate daily percentage returns
    # percentage_returns = [
    #     ((closing_prices[i] - closing_prices[i - 1]) / closing_prices[i - 1]) * 100
    #     for i in range(1, len(closing_prices))
    # ]
    for i in range(1, len(closing_prices)):
        today_price = closing_prices[i]
        yesterday_price = closing_prices[i - 1]
        pct_return = ((today_price - yesterday_price) / yesterday_price) * 100
        percentage_returns.append(pct_return)

        # Print date, formula and result
        #print(f"{dates[i].date()}:\t(({today_price:.2f} - {yesterday_price:.2f}) / {yesterday_price:.2f}) * 100 = {pct_return:.4f}%")

    # print("LN")
    # for r in percentage_returns:
    #     print(r)

    # Calculate mean
    mean = np.mean(percentage_returns)
    print(f"Mean:  {mean:.6f}")

    # Calculate variance (sample variance)
    variance = np.var(percentage_returns, ddof=1)
    print(f"variance:  {variance:.6f}")

    # Daily standard deviation (volatility)
    daily_volatility = np.sqrt(variance)
    print(f"dailyVolatility:  {daily_volatility:.6f}")

    # Annualized volatility
    # annualized_volatility = daily_volatility * np.sqrt(252)
    # print(f"annualizedVolatility:  {annualized_volatility:.6f}")

    monthly_volatility = daily_volatility * np.sqrt(23)
    print(f"monthlyVolatility:  {monthly_volatility:.6f}")

    # closing price of last trade date ,i.e spot of symbol
    spot = closing_prices[-1]
    print(f"spot:  {spot:.2f}")

    #return annualized_volatility , mean ,monthly_volatility
    return {
       # "annualized_volatility": annualized_volatility,
        "mean": mean,
        "daily_volatility": daily_volatility,
        "monthly_volatility": monthly_volatility,
        "spot": spot
    }






def get_nearest_strike(price: float, interval: int = 100, method: str = "ceil") -> int:
    """
    Rounds the given price to the nearest strike according to NSE interval.
    method: 'ceil' or 'floor' based on expected direction
    """
    if method == "ceil":
        return int(math.ceil(price / interval) * interval)
    else:
        return int(math.floor(price / interval) * interval)
    '''
    If method == "ceil":

        price / interval: 15234.50 / 100 = 152.345
        math.ceil(152.345): This rounds up to the nearest whole number, which is 153.0.
        153.0 * interval: 153.0 * 100 = 15300.0
        int(15300.0): Returns 15300.

    If method == "floor" (or anything else):

        price / interval: 15234.50 / 100 = 152.345
        math.floor(152.345): This rounds down to the nearest whole number, which is 152.0.
        152.0 * interval: 152.0 * 100 = 15200.0
        int(15200.0): Returns 15200.
    
    '''


def get_next_trading_day(last_date: datetime) -> datetime:
    """
    Calculates the next trading day after a given date.
    A "trading day" is defined here simply as a weekday (Monday to Friday).
    It does not account for public holidays.
    """
    next_day = last_date + timedelta(days=1)
    while next_day.weekday() >= 5:  # Skip Saturday/Sunday
        next_day += timedelta(days=1)

    print("Next trading day: ", next_day)    
    return next_day
    '''
    next_day.weekday(): This is a method of datetime objects. 
    It returns an integer representing the day of the week, where:
            Monday is 0
            Tuesday is 1
            Wednesday is 2
            Thursday is 3
            Friday is 4
            Saturday is 5
            Sunday is 6
    `>= 5:` The condition checks if the next_day is either a Saturday (5) 
    or a Sunday (6).

    `while` ...: This loop will continue to execute as long as next_day 
    falls on a weekend.
    '''


def get_monthly_expiry(date: datetime) -> datetime:
    # 1. Extract year and month from the input date
    year = date.year
    month = date.month
    # 2. Determine the last calendar day of that month
    # calendar.monthrange(year, month) returns a tuple:
    # (weekday of first day of the month, number of days in month)
    # We need the second element [1], which is the number of days.
    last_day = calendar.monthrange(year, month)[1]
    # 3. Create a datetime object for the last calendar day of the month
    last_date = datetime(year, month, last_day)

    # Backtrack to last Thursday
    while last_date.weekday() != 3:  # Thursday = 3
        last_date -= timedelta(days=1) # Go back one day as we already at end of the month
    return last_date



def calculate_rolling_volatility(df: pd.DataFrame, calc_date: datetime) -> dict:
    """
    Calculate volatility for a 12-month window ending on calc_date
    """
    # Define the 12-month window
    window_end = calc_date - timedelta(days=1)
    window_start =  calc_date - pd.DateOffset(years=1)
    
    # Debug: Print the timeline of data being used
    print(f"Debug: Calculating rolling volatility for {calc_date.strftime('%Y-%m-%d')}")
    print(f"Debug: Using data from {window_start.strftime('%Y-%m-%d')} to {window_end.strftime('%Y-%m-%d')}")

    # Get data for this window
    window_data = df[window_start:window_end]
    
    if window_data.empty:
        raise ValueError(f"No data found for window {window_start} to {window_end}")

    # Debug: Print the number of trading days in the window
    print(f"Debug: Found {len(window_data)} trading days in the window")

    # Calculate returns and volatility using existing function
    closing_prices = window_data['close'].tolist()
    dates = window_data.index.tolist()
    
    result = calculate_volatility(dates, closing_prices)
    
    return {
        "calculation_date": calc_date.strftime("%Y-%m-%d"),
        "window_start": window_start.strftime("%Y-%m-%d"),
        "window_end": window_end.strftime("%Y-%m-%d"),
        "trading_days": len(window_data),
        "volatility_stats": result
    }

def calculate_month_specific_volatility(df: pd.DataFrame, calc_date: datetime, simulation_enabled: bool = False) -> dict:
    """
    Calculate volatility for a specific month using historical data.
    Also returns the actual data for the target month if available.
    
    Args:
        df: Historical price DataFrame
        calc_date: Target date (first day of the month)
        simulation_enabled: Whether to simulate spot prices (False by default)
        
    Returns:
        Dictionary with volatility metrics and month data
    """
    # Define the 12-month window for volatility calculation
    window_end = calc_date - timedelta(days=1)
    window_start = calc_date - pd.DateOffset(years=1)
    
    # Debug: Print the timeline of data being used
    print(f"Debug: Calculating month-specific volatility for {calc_date.strftime('%Y-%m-%d')}")
    print(f"Debug: Using data from {window_start.strftime('%Y-%m-%d')} to {window_end.strftime('%Y-%m-%d')}")

    # Get data for this window
    window_data = df[window_start:window_end]
    
    if window_data.empty:
        raise ValueError(f"No data found for window {window_start} to {window_end}")

    # Check if we have actual data for the target month
    target_month_start = calc_date
    target_month_end = target_month_start + pd.DateOffset(months=1) - pd.DateOffset(days=1)
    
    # Extract data for the target month if it exists in our dataset
    target_month_data = df[target_month_start:target_month_end]
    
    # Debug: Print info about the requested month's data
    if not target_month_data.empty:
        print(f"\n--- ACTUAL DATA FOR {calc_date.strftime('%B %Y')} ---")
        print(f"Found {len(target_month_data)} trading days for {calc_date.strftime('%B %Y')}")
        print("First 5 rows of the month's data:")
        print(target_month_data.head().to_string())
        print("\nLast 5 rows of the month's data:")
        print(target_month_data.tail().to_string())
        print(f"--- END OF {calc_date.strftime('%B %Y')} DATA ---\n")
    else:
        print(f"\nNo actual data available for {calc_date.strftime('%B %Y')} in the dataset.\n")

    # Debug: Print the number of trading days in the window
    print(f"Debug: Found {len(window_data)} trading days in the historical window")

    # Calculate returns and volatility 
    closing_prices = window_data['close'].tolist()
    dates = window_data.index.tolist()
    
    # Use the original calculate_volatility logic (no simulation)
    # Calculate percentage returns
    percentage_returns = []
    for i in range(1, len(closing_prices)):
        today_price = closing_prices[i]
        yesterday_price = closing_prices[i - 1]
        pct_return = ((today_price - yesterday_price) / yesterday_price) * 100
        percentage_returns.append(pct_return)

    # Calculate mean
    mean = np.mean(percentage_returns)
    print(f"Mean: {mean:.8f}")

    # Calculate variance (sample variance)
    variance = np.var(percentage_returns, ddof=1)
    print(f"variance: {variance:.6f}")

    # Daily standard deviation (volatility)
    daily_volatility = np.sqrt(variance)
    print(f"dailyVolatility: {daily_volatility:.6f}")

    # Monthly volatility
    monthly_volatility = daily_volatility * np.sqrt(23)
    print(f"monthlyVolatility: {monthly_volatility:.6f}")

    # Base spot price from the last closing price of historical window
    spot = closing_prices[-1]
    print(f"spot: {spot:.2f} (based on last closing price from historical data)")

    # Return in same format as calculate_volatility with additional month data
    result = {
        "mean": mean,
        "variance": variance,
        "daily_volatility": daily_volatility,
        "monthly_volatility": monthly_volatility,
        "spot": spot
    }
    
    response_data = {
        "calculation_date": calc_date.strftime("%Y-%m-%d"),
        "window_start": window_start.strftime("%Y-%m-%d"),
        "window_end": window_end.strftime("%Y-%m-%d"),
        "trading_days": len(window_data),
        "volatility_stats": result
    }
    
    # Add the month's data if available
    if not target_month_data.empty:
        month_data_dict = target_month_data.reset_index().to_dict('records')
        response_data["target_month_data"] = {
            "available": True,
            "trading_days": len(target_month_data),
            "date_range": {
                "first": target_month_data.index.min().strftime("%Y-%m-%d"),
                "last": target_month_data.index.max().strftime("%Y-%m-%d")
            },
            "first_close": float(target_month_data['close'].iloc[0]),
            "last_close": float(target_month_data['close'].iloc[-1])
            # We don't include the full dataframe in the response as it could be large,
            # but we do print it to the console for analysis
        }
    else:
        response_data["target_month_data"] = {
            "available": False,
            "message": f"No data available for {calc_date.strftime('%B %Y')}"
        }
    
    return response_data
