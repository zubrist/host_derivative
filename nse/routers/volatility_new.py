from fastapi import APIRouter , HTTPException, status, Request ,Response, Depends, Header
from pydantic import BaseModel, Field
from services.fyers_service import get_token, fetch_historical_data,calculate_volatility, get_nearest_strike, get_next_trading_day, get_monthly_expiry , get_yearly_breakdown,calculate_rolling_volatility
from fastapi import Query
import pandas as pd
from typing import Optional, List
from services.utils import execute_native_query
from routers.users import create_transection  # Add this import if not already present
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
#from services.nse_service import get_option_data_with_cache
from services.transaction_service import create_single_transaction_with_cache, create_transactions_batch_concurrent
import logging
from datetime import datetime


logger = logging.getLogger(__name__)


router = APIRouter()


# @router.get("/api/v1_0/fyres/access_token", status_code=status.HTTP_200_OK)
# async def access_token(response: Response, request: Request):
#     try:
#         token = get_token()
#         print("Token: ", token)
#         return {"access_token": token}
#     except Exception as e:
#         print("Error in getting access token")
#         response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
#         return {"error": "Error in getting access token"}
    

# class TransactionCreate(BaseModel):
#     symbol: str
#     strike_price: float
#     option_type: str
#     lots: int
#     trade_date: str
#     expiry_date: str
#     instrument: str

# class VolatilityRequest(BaseModel):
#     symbol: str
#     #start_date: str
#     end_date: str
#     years_of_data: int
#     custom_multiplier: bool = Field(False, description="Flag to enable custom multipliers.")
#     multipliers: Optional[List[float]] = Field(
#         None,
#         description="List of custom standard deviation multipliers (e.g., [0.5, 2.0]). "
#                     "Only used if custom_multiplier is True."
#     )




'''
@router.post("/api/v1_0/fyres/volatility_old", status_code=status.HTTP_200_OK)
async def calculate_volatility_api(payload:VolatilityRequest,
                                   response: Response,
                                   request: Request,
                                #    background_tasks = BackgroundTasks,
                                   request_user_id: str = Header(None) ):
    try:
        # Step 1: Get the access token
        #access_token = get_token()

        
        # Step 2: Fetch historical data for the given symbol and date range
        #df = fetch_historical_data(payload.symbol,payload.start_date,payload.end_date)
        df = fetch_historical_data(payload.symbol, payload.end_date, payload.years_of_data)
        if df is None or df.empty:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"error": "No data found for the given symbol and date range"}
        
        # Get yearly breakdown
        yearly_data = get_yearly_breakdown(df)

        data_info = {
            "data_summary": {
                "start_date": df.index.min().strftime("%Y-%m-%d"),
                "end_date": df.index.max().strftime("%Y-%m-%d"),
                "total_trading_days": len(df),
                "total_years": (df.index.max() - df.index.min()).days / 365.25,
                "years_requested": payload.years_of_data,
                "yearly_breakdown": yearly_data
            }
        }

        # Extract the closing prices and dates from the historical data
        closing_prices = df['close'].tolist()
        dates = df.index.tolist()



        # Step 3: Calculate the volatility using the historical data
        result = calculate_volatility(dates, closing_prices)

        # Extract returned values
        annul_volatility = result["annualized_volatility"]
        mean = result["mean"]
        daily_volatility = result["daily_volatility"]
        monthly_volatility = result["monthly_volatility"]
        spot = result["spot"]

        # Initialize dictionaries to store volatility ranges and strike prices
        volatility_ranges= {} # Renamed for clarity
        strike_prices_from_spot = {} # Renamed for clarity

        # Define multipliers to iterate over
        multipliers_to_calculate = []
        if payload.custom_multiplier and payload.multipliers:
            multipliers_to_calculate.extend(payload.multipliers)
        else:
            # Default multipliers if custom_multiplier is false or multipliers are not provided
            multipliers_to_calculate.extend([1.0, 1.5]) # Add 1 SD and 1.5 SD

        # Step 4 : calculate ±1 SD and ±1.5 SD


        monthly_volatility_decimal = monthly_volatility / 100 # Convert monthly_volatility to a decimal

        for multiplier in multipliers_to_calculate:
        # Calculate range based on mean
            lower_sd =  (monthly_volatility * multiplier)
            upper_sd =  (monthly_volatility * multiplier)
            volatility_ranges[f"range_{multiplier:.1f}sd"] = {
                "lower": f"{lower_sd:.4f}%",
                "upper": f"{upper_sd:.4f}%"
            }
        

            # step 5 : calculating strike from Spot at both directions

        
            lower_spot_price  = spot * (1 - monthly_volatility_decimal  * multiplier)
            upper_spot_price  = spot * (1 + monthly_volatility_decimal  * multiplier)

            
            # lower_1sd_price = spot * (1 + lower_1sd / 100)

            # lower_1sd / 100: Converts the negative percentage lower_1sd to a decimal.
            # 1 + lower_1sd / 100: Creates a multiplier. 
            # For example, if lower_1sd is -2.0,
            # this becomes 1 + (-2.0 / 100) = 1 - 0.02 = 0.98.
            # spot * 0.98: Calculates the price that is 2% below the spot price.
            # So, lower_1sd_price is the price level one standard deviation
            # below the spot price
            
            

            # NSE formatted strikes 
            strike_interval = 100  # or 100 based on symbol; can later be dynamic


         # Find nearest strikes using get_nearest_strike
            lower_strike = get_nearest_strike(lower_spot_price, interval=strike_interval, method="floor")
            upper_strike = get_nearest_strike(upper_spot_price, interval=strike_interval, method="ceil")

        
            strike_prices_from_spot[f"range_{multiplier:.1f}sd"] = {
                    "lower": lower_strike,
                    "upper": upper_strike
                }
        #--- End of For -----    
        
        # Step 6: Create option transaction payloads
        last_date = dates[-1]
        print("last_date", last_date)
        if isinstance(last_date, pd.Timestamp):
            last_date = last_date.to_pydatetime()
        trade_date = get_next_trading_day(last_date)

        next_month = last_date + pd.DateOffset(months=1)
        expiry_date = get_monthly_expiry(next_month)

        option_type_map = {
            "lower_1sd_strike": "PE",
            "upper_1sd_strike": "CE",
            "lower_1_5sd_strike": "PE",
            "upper_1_5sd_strike": "CE"
        }
        

        option_payloads = []
        # Add payloads for calculated SD strikes
        symbol_for_option = "NIFTY" if payload.symbol == "NSE:NIFTY50-INDEX" else payload.symbol

        for multiplier_str, strike_range in strike_prices_from_spot.items():
            # For lower strike (PE)
            option_payloads.append({
                "symbol": symbol_for_option,
                "strike_price": strike_range["lower"],
                "option_type": "PE",
                "lots": 1,
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                "instrument": "OPTIDX"
            })
            option_payloads.append({
                "symbol": symbol_for_option,
                "strike_price": strike_range["lower"],
                "option_type": "PE",
                "lots": -10,
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                "instrument": "OPTIDX"
            })

            # For upper strike (CE)
            option_payloads.append({
                "symbol": symbol_for_option,
                "strike_price": strike_range["upper"],
                "option_type": "CE",
                "lots": 1,
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                "instrument": "OPTIDX"
            })
            option_payloads.append({
                "symbol": symbol_for_option,
                "strike_price": strike_range["upper"],
                "option_type": "CE",
                "lots": -10,
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                "instrument": "OPTIDX"
            })
    
        # #  Additional BUYs: PE at floor(spot) and CE at ceil(spot)
        floor_spot_strike = get_nearest_strike(spot, interval=strike_interval, method="floor")
        ceil_spot_strike = get_nearest_strike(spot, interval=strike_interval, method="ceil")

        # if payload.symbol == "NSE:NIFTY50-INDEX":
        #         symbol = "NIFTY"
        option_payloads.append({
            "symbol": symbol_for_option,
            "strike_price": floor_spot_strike,
            "option_type": "PE",
            "lots": 1,
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "expiry_date": expiry_date.strftime("%Y-%m-%d"),
            "instrument": "OPTIDX"
        })

        option_payloads.append({
            "symbol": symbol_for_option,
            "strike_price": ceil_spot_strike,
            "option_type": "CE",
            "lots": 1,
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "expiry_date": expiry_date.strftime("%Y-%m-%d"),
            "instrument": "OPTIDX"
        })
        
        
        transactions_created = []
        for option_payload in option_payloads:
            # Create transaction payload
            trans_payload = TransactionCreate(
                symbol=option_payload["symbol"],
                strike_price=option_payload["strike_price"],
                option_type=option_payload["option_type"],
                lots=option_payload["lots"],
                trade_date=option_payload["trade_date"],
                expiry_date=option_payload["expiry_date"],
                instrument=option_payload["instrument"]
            )
            # Call transaction creation method
            try:
                result = await create_transection(
                    trans_payload=trans_payload,
                    request=request,
                    response=response,
                    request_user_id=request_user_id
                )
                transactions_created.append(result)
            except HTTPException as e:
                print(f"Failed to create transaction: {e.detail}")
                continue

        

        return {
        "data_verification": data_info,
        "annualized_volatility": f"{annul_volatility:.4f}%",
        "mean_daily": f"{mean:.4f}%",
        "daily_volatility": f"{daily_volatility:.4f}%",
        "monthly_volatility": f"{monthly_volatility:.4f}%",
        "symbol_spot": spot,
        "volatility_ranges": volatility_ranges,
        "strike_prices_from_spot": strike_prices_from_spot,
        "option_transactions": option_payloads,
        #"transactions_inserted": transactions_created
        
    }
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            "error": str(e)
        }
'''


# '''
# The NEW one

# '''


@router.post("/api/v1_0/fyres/volatility", status_code=status.HTTP_200_OK)
async def calculate_volatility_api(payload: VolatilityRequest,
                                 response: Response,
                                 request: Request,
                                 request_user_id: str = Header(None)):
    try:
        print("Debug: Starting volatility calculation")
        print(f"Debug: Request payload: {payload}")
        
        # First get all required historical data
        end_date = pd.to_datetime(payload.end_date)
        # Need 2 years of data: 1 for first calculation + 1 for rolling
        
        #df = fetch_historical_data(payload.symbol, payload.end_date, payload.years_of_data)
        try:
            df = fetch_historical_data(
                symbol=payload.symbol,
                end_date_str=payload.end_date,
                years_of_data=payload.years_of_data
            )
            print(f"Debug: Historical data fetch result: {'Success' if df is not None else 'Failed'}")
        except Exception as e:
            print(f"Debug: Error in fetch_historical_data: {str(e)}")
            raise
        
        if df is None or df.empty:
            print("Debug: No data returned from fetch_historical_data")
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"error": "No data found for the given symbol and date range"}


        print(f"Debug: Got DataFrame with shape: {df.shape}")

        # Calculate dates for monthly analysis
        analysis_end = end_date - pd.DateOffset(days=1)
        analysis_start = end_date - pd.DateOffset(years=1)
        
        print(f"Analysis period: {analysis_start.date()} to {analysis_end.date()}")

        # Get first day of each month in the analysis period
        calculation_dates = pd.date_range(
            start=analysis_start,
            end=analysis_end,
            freq='MS'  # Month Start frequency
        )

        monthly_analysis = []
        option_payloads = []
        transactions_created = []  # To track created transactions

        for calc_date in calculation_dates:
            try:
                monthly_result = calculate_rolling_volatility(df, calc_date)
                stats = monthly_result["volatility_stats"]
                spot = stats["spot"]
                
                # Calculate strike prices based on volatility
                multipliers = payload.multipliers if payload.custom_multiplier else [1.5]
                monthly_strikes = {}
                
                monthly_vol = stats["monthly_volatility"]
                for multiplier in multipliers:
                    lower_sd = (monthly_vol * multiplier)
                    upper_sd = (monthly_vol * multiplier)

                    monthly_strikes[f"range_{multiplier:.1f}sd"] = {
                        "lower" : lower_sd,
                        "upper" : upper_sd
                    }


                    monthly_vol_decimal = stats["monthly_volatility"] / 100
                    lower_price = spot * (1 - monthly_vol_decimal * multiplier)
                    upper_price = spot * (1 + monthly_vol_decimal * multiplier)
                    

                    monthly_strikes[f"range_{multiplier:.1f}sd"] = {
                        "lower_strike": get_nearest_strike(lower_price, method="floor"),
                        "upper_strike": get_nearest_strike(upper_price, method="ceil")
                    }

                     # For spot plus 100
                    spot_plus_100 = spot + 100
                    spot_plus_100_decimal = spot_plus_100 % 100  # Get decimal part
                    upper_strike = int(spot_plus_100 - spot_plus_100_decimal)  # Base hundred
                    if spot_plus_100_decimal >= 50:
                        upper_strike += 100
                    
                    # For spot minus 100
                    spot_minus_100 = spot - 100
                    spot_minus_100_decimal = spot_minus_100 % 100  # Get decimal part
                    lower_strike = int(spot_minus_100 - spot_minus_100_decimal)  # Base hundred
                    if spot_minus_100_decimal >= 50:
                        lower_strike += 100

                    # Add these strikes to your response
                    spot_based_strikes = {
                        "spot": spot,
                        "lower_strike": lower_strike,
                        "upper_strike": upper_strike
                    }

                    
                
                monthly_analysis.append({
                    "date": monthly_result["calculation_date"],
                    "volatility_metrics": stats,
                    "strike_ranges": monthly_strikes,
                    "spot_based_strikes": spot_based_strikes,
                })
                
                # Get first and last dates for this month from df
                month_start = calc_date
                month_end = calc_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)
                
                # Filter df for this month to get actual trading dates
                month_data = df[month_start:month_end]
                if not month_data.empty:
                    trade_date = month_data.index[0]  # First trading day
                    #expiry_date = month_data.index[-1]  # Last trading day
                    # Get the last Thursday of the month using get_monthly_expiry
                    expiry_date = get_monthly_expiry(month_start)  # Pass the first day of month
                    

                    # Add payloads for volatility-based strikes (from strike_ranges)
                    for range_key, strikes in monthly_strikes.items():
                        # Upper strike CE buy
                        option_payloads.append({
                            "symbol": "NIFTY" if payload.symbol == "NSE:NIFTY50-INDEX" else payload.symbol,
                            "strike_price": strikes["upper_strike"],
                            "option_type": "CE",
                            "lots": 1, # later we make it dynamic
                            "trade_date": trade_date.strftime("%Y-%m-%d"),
                            "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                            "instrument": "OPTIDX",
                        })
                        
                        # Lower strike PE sell
                        option_payloads.append({
                            "symbol": "NIFTY" if payload.symbol == "NSE:NIFTY50-INDEX" else payload.symbol,
                            "strike_price": strikes["lower_strike"],
                            "option_type": "PE",
                            "lots": -10,
                            "trade_date": trade_date.strftime("%Y-%m-%d"),
                            "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                            "instrument": "OPTIDX",
                        })
                    
                    # Add payloads for spot-based strikes
                    # Upper strike CE buy
                    option_payloads.append({
                        "symbol": "NIFTY" if payload.symbol == "NSE:NIFTY50-INDEX" else payload.symbol,
                        "strike_price": spot_based_strikes["upper_strike"],
                        "option_type": "CE",
                        "lots": 1,
                        "trade_date": trade_date.strftime("%Y-%m-%d"),
                        "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                        "instrument": "OPTIDX",
                    })
                    
                    # Lower strike PE sell
                    option_payloads.append({
                        "symbol": "NIFTY" if payload.symbol == "NSE:NIFTY50-INDEX" else payload.symbol,
                        "strike_price": spot_based_strikes["lower_strike"],
                        "option_type": "PE",
                        "lots": -10,
                        "trade_date": trade_date.strftime("%Y-%m-%d"),
                        "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                        "instrument": "OPTIDX",
                    })
                


            except Exception as e:
                print(f"Error calculating volatility for {calc_date}: {str(e)}")
                continue

         # Sort option_payloads by calculation_month for clarity
        #option_payloads = sorted(option_payloads, key=lambda x: x["calculation_month"])

        # Create transactions for each option payload
        print(f"Debug: Creating {len(option_payloads)} transactions using new service")
        
        transactions_created = await create_transactions_batch_concurrent(
            option_payloads=option_payloads,
            request_user_id=request_user_id,
            batch_size=5  # Reduced for first run when cache is empty
        )
        
        # Count successful and failed transactions
        successful_count = len([t for t in transactions_created if t.get("status") == "success"])
        failed_count = len([t for t in transactions_created if t.get("status") == "failed"])
        
        print(f"Debug: Transaction results - Success: {successful_count}, Failed: {failed_count}")

        return {
            "symbol": payload.symbol,
            "analysis_period": {
                "start": analysis_start.strftime("%Y-%m-%d"),
                "end": analysis_end.strftime("%Y-%m-%d")
            },
            "monthly_analysis": monthly_analysis,
            "option_transactions": option_payloads,
            "transactions_created": transactions_created,
            "transaction_summary": {
                "total": len(option_payloads),
                "successful": successful_count,
                "failed": failed_count,
                "cache_efficiency": "First run will fetch from NSE, subsequent runs will use cache"
            }
        }

    except Exception as e:
        print(f"Error in volatility calculation: {str(e)}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": str(e)}



# async def fetch_single_contract(session, contract):
#     """Fetch a single option contract using cache-first approach"""
#     try:
#         # Convert string dates back to datetime objects
#         from_date = datetime.strptime(contract["from_date"], "%d-%m-%Y")
#         to_date = datetime.strptime(contract["to_date"], "%d-%m-%Y") 
#         expiry_date = datetime.strptime(contract["expiry_date"], "%d-%b-%Y")
        
#         # Use cache-first approach
#         result = await get_option_data_with_cache(
#             symbol=contract["symbol"],
#             from_date=from_date,
#             to_date=to_date,
#             expiry_date=expiry_date,
#             option_type=contract["option_type"],
#             strike_price=contract["strike_price"]
#         )
        
#         return {
#             **contract,
#             "data": result,
#             "status": "success" if result else "failed",
#             "source": "cache_or_nse"
#         }
#     except Exception as e:
#         logger.error(f"Error fetching contract {contract}: {str(e)}")
#         return {
#             **contract,
#             "data": None,
#             "status": "failed",
#             "error": str(e)
#         }

# async def fetch_multiple_contracts_concurrent(contracts_list):
#     """Fetch multiple option contracts concurrently"""
#     async with aiohttp.ClientSession() as session:
#         tasks = []
#         for contract in contracts_list:
#             task = fetch_single_contract(session, contract)
#             tasks.append(task)
        
#         # Execute all API calls concurrently
#         results = await asyncio.gather(*tasks, return_exceptions=True)
#         return results