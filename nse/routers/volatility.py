from fastapi import APIRouter , HTTPException, status, Request ,Response, Depends, Header
from pydantic import BaseModel, Field
from services.fyers_service import get_token, fetch_historical_data, calculate_volatility, calculate_month_specific_volatility, get_nearest_strike, get_next_trading_day, get_monthly_expiry, get_yearly_breakdown, calculate_rolling_volatility
from fastapi import Query
import pandas as pd
from typing import Optional, List
from services.utils import execute_native_query
from routers.users import create_transection  # Add this import if not already present
import asyncio
import traceback



router = APIRouter()


@router.get("/api/v1_0/fyres/access_token", status_code=status.HTTP_200_OK)
async def access_token(response: Response, request: Request):
    try:
        token = get_token()
        print("Token: ", token)
        return {"access_token": token}
    except Exception as e:
        print("Error in getting access token")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": "Error in getting access token"}
    

class TransactionCreate(BaseModel):
    symbol: str
    strike_price: float
    option_type: str
    lots: int
    trade_date: str
    expiry_date: str
    instrument: str

class VolatilityRequest(BaseModel):
    symbol: str
    #start_date: str
    end_date: str
    years_of_data: int
    custom_multiplier: bool = Field(False, description="Flag to enable custom multipliers.")
    multipliers: Optional[List[float]] = Field(
        None,
        description="List of custom standard deviation multipliers (e.g., [0.5, 2.0]). "
                    "Only used if custom_multiplier is True."
    )




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
        dates = df.index.tolist();

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

'''
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
        for option in option_payloads:
            try:
                trans_payload = TransactionCreate(
                    symbol=option["symbol"],
                    strike_price=option["strike_price"],
                    option_type=option["option_type"],
                    lots=option["lots"],
                    trade_date=option["trade_date"],
                    expiry_date=option["expiry_date"],
                    instrument=option["instrument"]
                )

                result = await create_transection(
                    trans_payload=trans_payload,
                    request=request,
                    response=response,
                    request_user_id=request_user_id
                )
                transactions_created.append({
                    "status": "success",
                    "transaction_id": result.get("transaction_id"),
                    "strike": option["strike_price"],
                    "type": option["option_type"],
                    "lots": option["lots"]
                })
            except Exception as e:
                print(f"Failed to create transaction for strike {option['strike_price']}: {str(e)}")
                transactions_created.append({
                    "status": "failed",
                    "strike": option["strike_price"],
                    "type": option["option_type"],
                    "lots": option["lots"],
                    "error": str(e)
                })

        return {
            "symbol": payload.symbol,
            "analysis_period": {
                "start": analysis_start.strftime("%Y-%m-%d"),
                "end": analysis_end.strftime("%Y-%m-%d")
            },
            "monthly_analysis": monthly_analysis,
            "option_transactions": option_payloads,
            "transactions_created": transactions_created
        }

    except Exception as e:
        print(f"Error in volatility calculation: {str(e)}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": str(e)}
        '''

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
        transactions_created = []  # To track created transactions

        # Process each month sequentially
        for calc_date in calculation_dates:
            try:
                #print(f"Debug: Processing month starting {calc_date.date()}")

                # Calculate rolling volatility for the current month
                monthly_result = calculate_rolling_volatility(df, calc_date)
                stats = monthly_result["volatility_stats"]
                spot = stats["spot"]

                # Print debug information for the current month
                # print(f"Debug: Calculating volatility for month: {calc_date.strftime('%Y-%m')}")
                # #print(f"Debug: Using data from {calc_date.strftime('%Y-%m-%d')} to {(calc_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)).strftime('%Y-%m-%d')}")
                # print(f"Debug: Spot price: {spot}")
                # print(f"Debug: Monthly volatility: {stats['monthly_volatility']}")

                # Calculate strike prices based on volatility
                multipliers = payload.multipliers if payload.custom_multiplier else [1.5]
                monthly_strikes = {}
                monthly_vol = stats["monthly_volatility"]

                for multiplier in multipliers:
                    monthly_vol_decimal = monthly_vol / 100
                    lower_price = spot * (1 - monthly_vol_decimal * multiplier)
                    upper_price = spot * (1 + monthly_vol_decimal * multiplier)

                    monthly_strikes[f"range_{multiplier:.1f}sd"] = {
                        "lower_strike": get_nearest_strike(lower_price, method="floor"),
                        "upper_strike": get_nearest_strike(upper_price, method="ceil")
                    }

                # Spot-based strikes
                spot_plus_100 = spot + 100
                spot_minus_100 = spot - 100
                spot_based_strikes = {
                    "spot": spot,
                    "lower_strike": get_nearest_strike(spot_minus_100, method="floor"),
                    "upper_strike": get_nearest_strike(spot_plus_100, method="ceil")
                }

                # Add monthly analysis
                monthly_analysis.append({
                    "date": monthly_result["calculation_date"],
                    "volatility_metrics": stats,
                    "strike_ranges": monthly_strikes,
                    "spot_based_strikes": spot_based_strikes,
                })

                # Get first and last dates for this month from df
                month_start = calc_date
                month_end = calc_date + pd.DateOffset(months=1) - pd.DateOffset(days=1)
                month_data = df[month_start:month_end]

                if not month_data.empty:
                    trade_date = month_data.index[0]  # First trading day
                    print(f"Selected trade_date: {trade_date}")  # Should always be a trading day
                    expiry_date = get_monthly_expiry(month_start)  # Last Thursday of the month

                    # Print debug information for trading dates
                    print(f"Debug: Trade date: {trade_date.strftime('%Y-%m-%d')}")
                    print(f"Debug: Expiry date: {expiry_date.strftime('%Y-%m-%d')}")

                    # Create option payloads for the current month
                    option_payloads = []
                    for range_key, strikes in monthly_strikes.items():

                        # Debug: Print the strikes being used
                        print(f"Debug: Processing strikes for range {range_key}")
                        print(f"Debug: Upper strike: {strikes['upper_strike']}, Lower strike: {strikes['lower_strike']}")

                        # Upper strike CE buy
                        option_payloads.append({
                            "symbol": "NIFTY" if payload.symbol == "NSE:NIFTY50-INDEX" else payload.symbol,
                            "strike_price": strikes["upper_strike"],
                            "option_type": "CE",
                            "lots": 1,
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

                    # Spot-based strikes

                    print(f"Debug: Spot-based strikes")
                    print(f"Debug: Upper strike: {spot_based_strikes['upper_strike']}, Lower strike: {spot_based_strikes['lower_strike']}")

                    option_payloads.append({
                        "symbol": "NIFTY" if payload.symbol == "NSE:NIFTY50-INDEX" else payload.symbol,
                        "strike_price": spot_based_strikes["upper_strike"],
                        "option_type": "CE",
                        "lots": 1,
                        "trade_date": trade_date.strftime("%Y-%m-%d"),
                        "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                        "instrument": "OPTIDX",
                    })
                    
                    option_payloads.append({
                        "symbol": "NIFTY" if payload.symbol == "NSE:NIFTY50-INDEX" else payload.symbol,
                        "strike_price": spot_based_strikes["lower_strike"],
                        "option_type": "PE",
                        "lots": -10,
                        "trade_date": trade_date.strftime("%Y-%m-%d"),
                        "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                        "instrument": "OPTIDX",
                    })

                    # Create transactions for the current month
                    for option in option_payloads:
                        try:
                            # Check if the transaction already exists to avoid duplicates
                            existing_transaction_query = f"""
                            SELECT COUNT(*) FROM user_transactions
                            WHERE symbol = '{option["symbol"]}'
                              AND strike_price = {option["strike_price"]}
                              AND option_type = '{option["option_type"]}'
                              AND instrument = '{option["instrument"]}'
                              AND expiry_date = '{option["expiry_date"]}'
                            """
                            print(f"Debug: SQL Query: {existing_transaction_query.strip()}")
                            query_result = await execute_native_query(existing_transaction_query, ())
        
                            # Extract the count value from the query result
                            existing_transaction_count = query_result[0]['COUNT(*)'] if query_result and isinstance(query_result, list) else 0

                            print(f"Debug: Checking existing transaction for {option['symbol']} {option['strike_price']} {option['option_type']}. Count: {existing_transaction_count}")

                            if existing_transaction_count > 0:
                                print(f"Debug: Transaction already exists, skipping creation for {option['symbol']} {option['strike_price']} {option['option_type']} {option['instrument']}")
                                transactions_created.append({
                                    "status": "skipped",
                                    "strike": option["strike_price"],
                                    "type": option["option_type"],
                                    "lots": option["lots"]
                                })
                                continue

                            # --- Retry Logic for Transaction Creation ---
                            max_attempts = 3  # 1 initial attempt + 2 retries
                            transaction_successful = False
                            
                            trans_payload = TransactionCreate(
                                symbol=option["symbol"],
                                strike_price=option["strike_price"],
                                option_type=option["option_type"],
                                lots=option["lots"],
                                trade_date=option["trade_date"],
                                expiry_date=option["expiry_date"],
                                instrument=option["instrument"]
                            )

                            for attempt in range(1, max_attempts + 1):
                                print(f"Debug: Attempt {attempt}/{max_attempts} for transaction: {option['symbol']} {option['strike_price']} {option['option_type']}")
                                try:
                                    # Log payload sent to create_transection
                                    print(f"Debug: Payload sent to create_transection: {trans_payload.dict()}")
                                    result = await create_transection(
                                        trans_payload=trans_payload,
                                        request=request,
                                        response=response,
                                        request_user_id=request_user_id
                                    )
                                    # Log full response from create_transection
                                    print(f"Debug: Response from create_transection: {result}")

                                    if isinstance(result, dict) and result.get("transaction_id"):
                                        print(f"Debug: Attempt {attempt} SUCCEEDED. Transaction ID: {result.get('transaction_id')}")
                                        transactions_created.append({
                                            "status": "success",
                                            "transaction_id": result.get("transaction_id"),
                                            "strike": option["strike_price"],
                                            "type": option["option_type"],
                                            "lots": option["lots"]
                                        })
                                        transaction_successful = True
                                        break  # Exit retry loop on success
                                    else:
                                        print(f"Debug: Attempt {attempt} FAILED. Received non-success response: {result}")
                                        if attempt < max_attempts:
                                            print("Debug: Retrying in 1 second...")
                                            await asyncio.sleep(1)
                                        
                                except Exception as e:
                                    print(f"Debug: Attempt {attempt} FAILED with exception: {str(e)}")
                                    print(traceback.format_exc())
                                    if attempt < max_attempts:
                                        print("Debug: Retrying in 1 second...")
                                        await asyncio.sleep(1)

                            if not transaction_successful:
                                print(f"Debug: All {max_attempts} attempts failed for {option['symbol']} {option['strike_price']} {option['option_type']}. Skipping.")
                                transactions_created.append({
                                    "status": "failed",
                                    "strike": option["strike_price"],
                                    "type": option["option_type"],
                                    "lots": option["lots"],
                                    "error": f"Transaction failed after {max_attempts} attempts."
                                })
                        except Exception as e:
                            # This outer catch is for errors in the checking logic or other unexpected issues
                            print(f"Failed to process transaction for strike {option['strike_price']}: {str(e)}")
                            print(traceback.format_exc())
                            transactions_created.append({
                                "status": "failed",
                                "strike": option["strike_price"],
                                "type": option["option_type"],
                                "lots": option["lots"],
                                "error": str(e)
                            })

            except Exception as e:
                print(f"Error calculating volatility for {calc_date}: {str(e)}")
                continue

        return {
            "symbol": payload.symbol,
            "analysis_period": {
                "start": analysis_start.strftime("%Y-%m-%d"),
                "end": analysis_end.strftime("%Y-%m-%d")
            },
            "monthly_analysis": monthly_analysis,
            "transactions_created": transactions_created
        }

    except Exception as e:
        print(f"Error in volatility calculation: {str(e)}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": str(e)}



@router.get("/api/v1_0/fyres/volatility_of_month/{month}/{year}/{symbol}", status_code=status.HTTP_200_OK)
async def volatility_of_month(
    month: str,
    year: str,
    symbol: str,  # NSE:NIFTY50-INDEX
    response: Response,
    request: Request,
    request_user_id: str = Header(None)
):
    """
    Calculate volatility metrics for a specific month/year using 12 months of historical data.
    
    Args:
        month: Month in "MM" format (e.g., "01" for January)
        year: Year in "YY" format (e.g., "24" for 2024)
        symbol: Stock symbol (e.g., "NSE:NIFTY50-INDEX")
        
    Returns:
        Volatility metrics, strike prices, and transaction information for the requested month
    """
    try:
        print(f"Debug: Starting volatility calculation for month {month}/{year}")
        
        # Convert 2-digit year to 4-digit
        full_year = f"20{year}"
        
        # Validate month and year format
        if len(month) != 2 or len(year) != 2 or not month.isdigit() or not year.isdigit():
            print(f"Debug: Invalid month/year format: {month}/{year}")
            raise HTTPException(
                status_code=400,
                detail="Month must be in MM format (e.g., '01') and year in YY format (e.g., '24')"
            )
        
        # Convert month and year to integers for validation
        month_int = int(month)
        year_int = int(full_year)
        
        if month_int < 1 or month_int > 12:
            print(f"Debug: Invalid month value: {month_int}")
            raise HTTPException(status_code=400, detail="Month must be between 01 and 12")
            
        # Construct target date (first day of the month)
        target_date_str = f"{full_year}-{month}-01"
        print(f"Debug: Target month: {target_date_str}")
        
        try:
            target_date = pd.to_datetime(target_date_str)
        except Exception as e:
            print(f"Debug: Error parsing target date: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
        
        # Calculate the data range (year prior to target month up to END of target month)
        prior_year = int(full_year) - 1
        target_month_int = int(month)

        start_date_str = f"{prior_year}-{month}-01"  # Start from same month, prior year
        # Calculate last day of target month
        import calendar
        last_day = calendar.monthrange(int(full_year), target_month_int)[1]
        end_date_str = f"{full_year}-{month}-{last_day:02d}"

        start_date = pd.to_datetime(start_date_str)
        end_date = pd.to_datetime(end_date_str)

        print(f"Debug: Fetch period: {start_date_str} to {end_date_str}")
        
        # Fetch historical data up to the END of the target month
        df = fetch_historical_data(
            symbol=symbol,
            end_date_str=end_date_str,
            years_of_data=1
        )
        
        if df is None or df.empty:
            print("Debug: No data returned from fetch_historical_data")
            raise HTTPException(status_code=404, detail="No historical data found for the analysis period")
        
        print(f"Debug: Got DataFrame with shape: {df.shape}")
        
        # Calculate volatility metrics for the target month
        # Note: We're using historical data to predict volatility for the target month
        try:
            print(f"Debug: Calculating volatility for target month: {target_date.strftime('%Y-%m')}")
            # Use data from the prior year to calculate volatility for the target month
            monthly_result = calculate_month_specific_volatility(df, target_date, simulation_enabled=False)
            stats = monthly_result["volatility_stats"]
            spot = stats["spot"]
            
            # Print volatility metrics with proper key names
            print(f"Mean: {stats['mean']}")
            print(f"variance: {stats.get('variance', stats.get('daily_variance', 0))}")
            print(f"dailyVolatility: {stats['daily_volatility']}")
            print(f"monthlyVolatility: {stats['monthly_volatility']}")
            print(f"spot: {spot}")
        except Exception as e:
            print(f"Debug: Error calculating volatility metrics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error calculating volatility: {str(e)}")
        
        # Calculate strike prices based on volatility
        monthly_strikes = {}
        monthly_vol = stats["monthly_volatility"]
        monthly_vol_decimal = monthly_vol / 100
        
        # Use fixed multiplier of 1.5 as per example
        multiplier = 1.5  # TODO: Make this dynamic
        
        # Calculate volatility-based strikes
        try:
            lower_price = spot * (1 - monthly_vol_decimal * multiplier)
            upper_price = spot * (1 + monthly_vol_decimal * multiplier)
            
            monthly_strikes[f"range_{multiplier:.1f}sd"] = {
                "lower_strike": get_nearest_strike(lower_price, method="floor"),
                "upper_strike": get_nearest_strike(upper_price, method="ceil")
            }
            
            # Calculate spot-based strikes (spot±100)
            spot_based_strikes = {
                "spot": spot,
                "lower_strike": get_nearest_strike(spot - 100, method="floor"),
                "upper_strike": get_nearest_strike(spot + 100, method="ceil")
            }
            
            # Debug strike information
            print(f"Debug: Processing strikes for range range_{multiplier:.1f}sd")
            print(f"Debug: Upper strike: {monthly_strikes[f'range_{multiplier:.1f}sd']['upper_strike']}, " 
                  f"Lower strike: {monthly_strikes[f'range_{multiplier:.1f}sd']['lower_strike']}")
            print(f"Debug: Spot-based strikes")
            print(f"Debug: Upper strike: {spot_based_strikes['upper_strike']}, " 
                  f"Lower strike: {spot_based_strikes['lower_strike']}")
        except Exception as e:
            print(f"Debug: Error calculating strike prices: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error calculating strike prices: {str(e)}")
        
        # Determine trade dates and expiry
        try:
            # Find first available trading day in the target month
            month_start = pd.to_datetime(f"{full_year}-{month}-01")
            month_end = pd.to_datetime(f"{full_year}-{month}-{last_day:02d}")
            month_data = df[month_start:month_end]
            if not month_data.empty:
                trade_date = month_data.index[0]  # First trading day in month
                print(f"Selected trade_date: {trade_date}")
            else:
                last_available = df.index.max().strftime('%Y-%m-%d')
                raise HTTPException(
                    status_code=404,
                    detail=f"No trading days found in the target month ({month}/{year}). Last available date is {last_available}."
                )

            # Get expiry (last Thursday of target month)
            expiry_date = get_monthly_expiry(target_date)

            print(f"Debug: Trade date: {trade_date.strftime('%Y-%m-%d')}")
            print(f"Debug: Expiry date: {expiry_date.strftime('%Y-%m-%d')}")
        except Exception as e:
            print(f"Debug: Error determining trading dates: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error determining trading dates: {str(e)}")
        
        # Create option payloads
        option_payloads = []
        symbol_for_option = "NIFTY"  # For NSE:NIFTY50-INDEX
        
        # ORIGINAL LOGIC (COMMENTED OUT) - Before modification for volatility/spot-based strike behavior
        # # Add volatility-based strikes to payloads
        # for range_key, strikes in monthly_strikes.items():
        #     option_payloads.append({
        #         "symbol": symbol_for_option,
        #         "strike_price": strikes["upper_strike"],
        #         "option_type": "CE",
        #         "lots": 1,  # BUY CE
        #         "trade_date": trade_date.strftime("%Y-%m-%d"),
        #         "expiry_date": expiry_date.strftime("%Y-%m-%d"),
        #         "instrument": "OPTIDX",
        #     })
        #     
        #     option_payloads.append({
        #         "symbol": symbol_for_option,
        #         "strike_price": strikes["lower_strike"],
        #         "option_type": "PE",
        #         "lots": -10,  # SELL PE
        #         "trade_date": trade_date.strftime("%Y-%m-%d"),
        #         "expiry_date": expiry_date.strftime("%Y-%m-%d"),
        #         "instrument": "OPTIDX",
        #     })
        # 
        # # Add spot-based strikes to payloads
        # option_payloads.append({
        #     "symbol": symbol_for_option,
        #     "strike_price": spot_based_strikes["upper_strike"],
        #     "option_type": "CE",
        #     "lots": 1,  # BUY CE
        #     "trade_date": trade_date.strftime("%Y-%m-%d"),
        #     "expiry_date": expiry_date.strftime("%Y-%m-%d"),
        #     "instrument": "OPTIDX",
        # })
        # 
        # option_payloads.append({
        #     "symbol": symbol_for_option,
        #     "strike_price": spot_based_strikes["lower_strike"],
        #     "option_type": "PE",
        #     "lots": -10,  # SELL PE
        #     "trade_date": trade_date.strftime("%Y-%m-%d"),
        #     "expiry_date": expiry_date.strftime("%Y-%m-%d"),
        #     "instrument": "OPTIDX",
        # })
        
        # NEW LOGIC - Modified for volatility/spot-based strike behavior
        # For volatility-based strikes (1.5sd): Both SELL (PE and CE)
        # For spot-based strikes: Both BUY (PE and CE)
        
        # Add volatility-based strikes to payloads - BOTH SELL
        for range_key, strikes in monthly_strikes.items():
            option_payloads.append({
                "symbol": symbol_for_option,
                "strike_price": strikes["upper_strike"],
                "option_type": "CE",
                "lots": -10,  # SELL CE (changed from BUY)
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                "instrument": "OPTIDX",
            })
            
            option_payloads.append({
                "symbol": symbol_for_option,
                "strike_price": strikes["lower_strike"],
                "option_type": "PE",
                "lots": -10,  # SELL PE (unchanged)
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                "instrument": "OPTIDX",
            })
        
        # Add spot-based strikes to payloads - BOTH BUY
        option_payloads.append({
            "symbol": symbol_for_option,
            "strike_price": spot_based_strikes["upper_strike"],
            "option_type": "CE",
            "lots": 1,  # BUY CE (unchanged)
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "expiry_date": expiry_date.strftime("%Y-%m-%d"),
            "instrument": "OPTIDX",
        })
        
        option_payloads.append({
            "symbol": symbol_for_option,
            "strike_price": spot_based_strikes["lower_strike"],
            "option_type": "PE",
            "lots": 1,  # BUY PE (changed from SELL)
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "expiry_date": expiry_date.strftime("%Y-%m-%d"),
            "instrument": "OPTIDX",
        })
        
        # Create transactions with retry logic
        transactions_created = []
        
        for option in option_payloads:
            try:
                # Check if transaction already exists to avoid duplicates
                existing_transaction_query = f"""
                SELECT COUNT(*) FROM user_transactions
                WHERE symbol = '{option["symbol"]}'
                  AND strike_price = {option["strike_price"]}
                  AND option_type = '{option["option_type"]}'
                  AND instrument = '{option["instrument"]}'
                  AND expiry_date = '{option["expiry_date"]}'
                """
                
                query_result = await execute_native_query(existing_transaction_query, ())
                existing_transaction_count = query_result[0]['COUNT(*)'] if query_result and isinstance(query_result, list) else 0
                
                print(f"Debug: Checking existing transaction for {option['symbol']} {option['strike_price']} {option['option_type']}. Count: {existing_transaction_count}")
                
                if existing_transaction_count > 0:
                    print(f"Debug: Transaction already exists, skipping creation for {option['symbol']} {option['strike_price']} {option['option_type']} {option['instrument']}")
                    transactions_created.append({
                        "status": "skipped",
                        "strike": option["strike_price"],
                        "type": option["option_type"],
                        "lots": option["lots"]
                    })
                    continue
                
                # Retry logic for transaction creation
                max_attempts = 3  # 1 initial attempt + 2 retries
                transaction_successful = False
                
                trans_payload = TransactionCreate(
                    symbol=option["symbol"],
                    strike_price=option["strike_price"],
                    option_type=option["option_type"],
                    lots=option["lots"],
                    trade_date=option["trade_date"],
                    expiry_date=option["expiry_date"],
                    instrument=option["instrument"]
                )
                
                for attempt in range(1, max_attempts + 1):
                    print(f"Debug: Attempt {attempt}/{max_attempts} for transaction: {option['symbol']} {option['strike_price']} {option['option_type']}")
                    try:
                        # Log payload sent to create_transection
                        print(f"Debug: Payload sent to create_transection: {trans_payload.dict()}")
                        result = await create_transection(
                            trans_payload=trans_payload,
                            request=request,
                            response=response,
                            request_user_id=request_user_id
                        )
                        # Log full response from create_transection
                        print(f"Debug: Response from create_transection: {result}")

                        if isinstance(result, dict) and result.get("transaction_id"):
                            print(f"Debug: Attempt {attempt} SUCCEEDED. Transaction ID: {result.get('transaction_id')}")
                            transactions_created.append({
                                "status": "success",
                                "transaction_id": result.get("transaction_id"),
                                "strike": option["strike_price"],
                                "type": option["option_type"],
                                "lots": option["lots"]
                            })
                            transaction_successful = True
                            break  # Exit retry loop on success
                        else:
                            print(f"Debug: Attempt {attempt} FAILED. Received non-success response: {result}")
                            if attempt < max_attempts:
                                print("Debug: Retrying in 1 second...")
                                await asyncio.sleep(1)
                    
                    except Exception as e:
                        print(f"Debug: Attempt {attempt} FAILED with exception: {str(e)}")
                        print(traceback.format_exc())
                        if attempt < max_attempts:
                            print("Debug: Retrying in 1 second...")
                            await asyncio.sleep(1)

                if not transaction_successful:
                    print(f"Debug: All {max_attempts} attempts failed for {option['symbol']} {option['strike_price']} {option['option_type']}. Skipping.")
                    transactions_created.append({
                        "status": "failed",
                        "strike": option["strike_price"],
                        "type": option["option_type"],
                        "lots": option["lots"],
                        "error": f"Transaction failed after {max_attempts} attempts."
                    })
            
            except Exception as e:
                print(f"Failed to process transaction for strike {option['strike_price']}: {str(e)}")
                transactions_created.append({
                    "status": "failed",
                    "strike": option["strike_price"],
                    "type": option["option_type"],
                    "lots": option["lots"],
                    "error": str(e)
                })
        
        # Prepare and return the final response
        return {
            "symbol": symbol,
            "target_month": f"{full_year}-{month}",
            "analysis_period": {
                "start": start_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            },
            "volatility_metrics": {
                "mean": stats["mean"],
                # Use .get() to handle possible missing key with a fallback
                "variance": stats.get("variance", stats.get("daily_variance", 0)),
                "daily_volatility": stats["daily_volatility"],
                "monthly_volatility": stats["monthly_volatility"],
                "spot": spot
            },
            "strikes": {
                "volatility_based_strikes": monthly_strikes,
                "spot_based_strikes": spot_based_strikes
            },
            "trading_dates": {
                "trade_date": trade_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date.strftime("%Y-%m-%d")
            },
            "transactions_created": transactions_created
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status codes and details
        raise
    except Exception as e:
        print(f"Error in volatility_of_month: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")