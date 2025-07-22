from fastapi import APIRouter, Header, Request, Response, HTTPException, status, Depends
from datetime import datetime, timedelta, date
from collections import defaultdict, deque
from pydantic import BaseModel, Field , ValidationError
from services.utils import execute_native_query
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from scipy.optimize import brentq
from scipy import interpolate

# import from our files
from db.models.break_even import *

# Configure Logging
logging.basicConfig(level=logging.DEBUG) # Keep this for root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # Explicitly set level for this specific logger

# Strategy Simulation Router
router = APIRouter()



# --- Break-Even Calculation Functions ---
def calculate_long_call_breakeven(option: OptionTransaction) -> float:
    """
    Calculates the break-even point for a long call option.
    BE = Strike Price + Premium
    """
    return option.strike_price + option.entry_price

def calculate_short_call_breakeven(option: OptionTransaction) -> float:
    """
    Calculates the break-even point for a short call option.
    BE = Strike Price + Premium
    """
    return option.strike_price + option.entry_price  # Break-even for short call is same as long call

def calculate_long_put_breakeven(option: OptionTransaction) -> float:
    """
    Calculates the break-even point for a long put option.
    BE = Strike Price - Premium
    """
    return option.strike_price - option.premium

def calculate_short_put_breakeven(option: OptionTransaction) -> float:
    """
    Calculates the break-even point for a short put option.
    BE = Strike Price - Premium
    """
    return option.strike_price + option.premium


# --- Strategy Mapping ---
strategy_functions = {
    "CE": {
        "LONG": calculate_long_call_breakeven,
        "SHORT": calculate_short_call_breakeven,
    },
    "PE": {
        "LONG": calculate_long_put_breakeven,
        "SHORT": calculate_short_put_breakeven,
    },
    # Added for consistency and clarity.  Important for the core logic.
}

# --- Strategy Identification and Analysis Functions ---
def identify_strategy(legs: List[OptionLeg]) -> str:
    """
    Identifies the options strategy based on the legs provided.
    
    Args:
        legs: List of OptionLeg objects
        
    Returns:
        str: The name of the identified strategy
    """
    # Sort legs by strike price for easier analysis
    ce_legs = sorted([leg for leg in legs if leg.option_type == "CE"], key=lambda x: x.strike)
    pe_legs = sorted([leg for leg in legs if leg.option_type == "PE"], key=lambda x: x.strike, reverse=True)
    
    buy_ce = [leg for leg in ce_legs if leg.action == "BUY"]
    sell_ce = [leg for leg in ce_legs if leg.action == "SELL"]
    buy_pe = [leg for leg in pe_legs if leg.action == "BUY"]
    sell_pe = [leg for leg in pe_legs if leg.action == "SELL"]
    
    # Single leg strategies
    if len(legs) == 1:
        leg = legs[0]
        if leg.action == "BUY" and leg.option_type == "CE":
            return "Buy Call"
        elif leg.action == "SELL" and leg.option_type == "CE":
            return "Sell Call"
        elif leg.action == "BUY" and leg.option_type == "PE":
            return "Buy Put"
        elif leg.action == "SELL" and leg.option_type == "PE":
            return "Sell Put"
    
    # Two-leg strategies
    elif len(legs) == 2:
        # Check for spreads with same option type
        if len(ce_legs) == 2 and len(pe_legs) == 0:
            if len(buy_ce) == 1 and len(sell_ce) == 1:
                if buy_ce[0].strike < sell_ce[0].strike:
                    return "Bull Call Spread"
                else:
                    return "Bear Call Spread"
        
        elif len(pe_legs) == 2 and len(ce_legs) == 0:
            if len(buy_pe) == 1 and len(sell_pe) == 1:
                if buy_pe[0].strike > sell_pe[0].strike:
                    return "Bear Put Spread"
                else:
                    return "Bull Put Spread"
    
    # Three-leg strategies
    elif len(legs) == 3:
        # Check for butterfly with calls
        if len(ce_legs) == 3 and len(pe_legs) == 0:
            if len(buy_ce) == 2 and len(sell_ce) == 1 and sell_ce[0].quantity == buy_ce[0].quantity * 2:
                return "Bull Butterfly"
        
        # Check for butterfly with puts
        elif len(pe_legs) == 3 and len(ce_legs) == 0:
            if len(buy_pe) == 2 and len(sell_pe) == 1 and sell_pe[0].quantity == buy_pe[0].quantity * 2:
                return "Bear Butterfly"
        
        # Check for ratio back spreads
        elif len(ce_legs) == 2 and len(pe_legs) == 0:
            if len(buy_ce) == 1 and len(sell_ce) == 1 and buy_ce[0].quantity == 2 * sell_ce[0].quantity:
                if buy_ce[0].strike > sell_ce[0].strike:
                    return "Call Ratio Back Spread"
        
        elif len(pe_legs) == 2 and len(ce_legs) == 0:
            if len(buy_pe) == 1 and len(sell_pe) == 1 and buy_pe[0].quantity == 2 * sell_pe[0].quantity:
                if buy_pe[0].strike < sell_pe[0].strike:
                    return "Put Ratio Back Spread"
    
    # Four-leg strategies
    elif len(legs) == 4:
        # Check for condors
        if len(ce_legs) == 4 and len(pe_legs) == 0:
            if len(buy_ce) == 2 and len(sell_ce) == 2:
                # Ensure correct order of strikes
                strikes = [leg.strike for leg in ce_legs]
                if len(set(strikes)) == 4 and sorted(strikes) == strikes:
                    return "Bull Condor"
        
        elif len(pe_legs) == 4 and len(ce_legs) == 0:
            if len(buy_pe) == 2 and len(sell_pe) == 2:
                # Ensure correct order of strikes
                strikes = [leg.strike for leg in pe_legs]
                if len(set(strikes)) == 4 and sorted(strikes, reverse=True) == strikes:
                    return "Bear Condor"
    
    # If no specific strategy is identified
    return "Custom Strategy"

def analyze_strategy(strategy_name: str, legs: List[OptionLeg]) -> StrategyResponse:
    """
    Analyzes a given options strategy and calculates key metrics.
    
    Args:
        strategy_name: The name of the strategy
        legs: List of OptionLeg objects
        
    Returns:
        StrategyResponse: Analysis results including breakeven points, max profit, max loss, etc.
    """
    response = StrategyResponse(
        strategy_name=strategy_name,
        breakeven_points=[],
        max_profit=0,
        max_loss=0,
        profit_zones=[],
        legs=legs,
        details={}
    )
    
    # Sort legs by strike for easier calculations
    ce_legs = sorted([leg for leg in legs if leg.option_type == "CE"], key=lambda x: x.strike)
    pe_legs = sorted([leg for leg in legs if leg.option_type == "PE"], key=lambda x: x.strike, reverse=True)
    
    # Calculate net premium
    net_premium = sum(
        [leg.premium * leg.quantity * (-1 if leg.action == "BUY" else 1) for leg in legs]
    ) / sum([leg.quantity for leg in legs])
    
    response.details["net_premium"] = net_premium
    
    # Single-leg strategies
    if strategy_name == "Buy Call":
        leg = legs[0]
        breakeven = leg.strike + leg.premium
        response.breakeven_points = [breakeven]
        response.max_profit = "Unlimited"
        response.max_loss = leg.premium * leg.quantity
        response.profit_zones = [{"above": breakeven}]
        
    elif strategy_name == "Sell Call":
        leg = legs[0]
        breakeven = leg.strike + leg.premium
        response.breakeven_points = [breakeven]
        response.max_profit = leg.premium * leg.quantity
        response.max_loss = "Unlimited"
        response.profit_zones = [{"below": breakeven}]
        
    elif strategy_name == "Buy Put":
        leg = legs[0]
        breakeven = leg.strike - leg.premium
        response.breakeven_points = [breakeven]
        response.max_profit = "Unlimited"
        response.max_loss = leg.premium * leg.quantity
        response.profit_zones = [{"below": breakeven}]
        
    elif strategy_name == "Sell Put":
        leg = legs[0]
        breakeven = leg.strike - leg.premium
        response.breakeven_points = [breakeven]
        response.max_profit = leg.premium * leg.quantity
        response.max_loss = "Unlimited"
        response.profit_zones = [{"above": breakeven}]
    
    # Spread strategies
    elif strategy_name == "Bull Call Spread":
        lower_strike = ce_legs[0].strike
        higher_strike = ce_legs[1].strike
        spread_width = higher_strike - lower_strike

        # Calculate net premium per contract directly
        buy_premium = ce_legs[0].premium  # Premium paid for the lower strike call
        sell_premium = ce_legs[1].premium  # Premium received for the higher strike call
        net_premium = buy_premium - sell_premium  # Net cost per contract
        
        
        # Calculate breakeven, max profit, max loss
        breakeven = lower_strike + abs(net_premium)
        max_profit = (spread_width - abs(net_premium)) * legs[0].quantity
        max_loss = abs(net_premium) * legs[0].quantity
        
        response.breakeven_points = [breakeven]
        response.max_profit = max_profit
        response.max_loss = max_loss
        response.profit_zones = [{"between": [breakeven, higher_strike]}]
        
    elif strategy_name == "Bear Call Spread":
        lower_strike = ce_legs[0].strike
        higher_strike = ce_legs[1].strike
        spread_width = higher_strike - lower_strike
        
        # Calculate breakeven, max profit, max loss
        breakeven = lower_strike + abs(net_premium)
        max_profit = abs(net_premium) * legs[0].quantity
        max_loss = (spread_width - abs(net_premium)) * legs[0].quantity
        
        response.breakeven_points = [breakeven]
        response.max_profit = max_profit
        response.max_loss = max_loss
        response.profit_zones = [{"below": breakeven}]
        
    elif strategy_name == "Bull Put Spread":
        lower_strike = pe_legs[1].strike
        higher_strike = pe_legs[0].strike
        spread_width = higher_strike - lower_strike
        
        # Calculate breakeven, max profit, max loss
        breakeven = higher_strike - abs(net_premium)
        max_profit = abs(net_premium) * legs[0].quantity
        max_loss = (spread_width - abs(net_premium)) * legs[0].quantity
        
        response.breakeven_points = [breakeven]
        response.max_profit = max_profit
        response.max_loss = max_loss
        response.profit_zones = [{"above": breakeven}]
        
    elif strategy_name == "Bear Put Spread":
        lower_strike = pe_legs[1].strike
        higher_strike = pe_legs[0].strike
        spread_width = higher_strike - lower_strike
        
        # Calculate breakeven, max profit, max loss
        breakeven = higher_strike - abs(net_premium)
        max_profit = (spread_width - abs(net_premium)) * legs[0].quantity
        max_loss = abs(net_premium) * legs[0].quantity
        
        response.breakeven_points = [breakeven]
        response.max_profit = max_profit
        response.max_loss = max_loss
        response.profit_zones = [{"between": [lower_strike, breakeven]}]
    
    # Butterfly strategies
    elif strategy_name == "Bull Butterfly":
        lower_strike = ce_legs[0].strike
        middle_strike = ce_legs[1].strike
        higher_strike = ce_legs[2].strike
        
        lower_breakeven = lower_strike + abs(net_premium)
        upper_breakeven = higher_strike - abs(net_premium)
        max_profit = (middle_strike - lower_strike - abs(net_premium)) * legs[0].quantity
        max_loss = abs(net_premium) * legs[0].quantity
        
        response.breakeven_points = [lower_breakeven, upper_breakeven]
        response.max_profit = max_profit
        response.max_loss = max_loss
        response.profit_zones = [{"between": [lower_breakeven, upper_breakeven]}]
        response.details["max_profit_at"] = middle_strike
        
    elif strategy_name == "Bear Butterfly":
        higher_strike = pe_legs[0].strike
        middle_strike = pe_legs[1].strike
        lower_strike = pe_legs[2].strike
        
        lower_breakeven = lower_strike + abs(net_premium)
        upper_breakeven = higher_strike - abs(net_premium)
        max_profit = (higher_strike - middle_strike - abs(net_premium)) * legs[0].quantity
        max_loss = abs(net_premium) * legs[0].quantity
        
        response.breakeven_points = [lower_breakeven, upper_breakeven]
        response.max_profit = max_profit
        response.max_loss = max_loss
        response.profit_zones = [{"between": [lower_breakeven, upper_breakeven]}]
        response.details["max_profit_at"] = middle_strike
    
    # Ratio Back Spread strategies
    elif strategy_name == "Call Ratio Back Spread":
        sell_strike = ce_legs[0].strike
        buy_strike = ce_legs[1].strike
        spread_width = buy_strike - sell_strike
        
        is_premium_paid = net_premium < 0
        
        if is_premium_paid:
            # Premium paid scenario
            breakeven = buy_strike + abs(net_premium) / (legs[1].quantity / legs[0].quantity - 1)
            max_loss = spread_width + abs(net_premium)
            
            response.breakeven_points = [breakeven]
            response.max_profit = "Unlimited"
            response.max_loss = max_loss * legs[0].quantity
            response.profit_zones = [{"above": breakeven}]
        else:
            # Premium received scenario
            lower_breakeven = sell_strike - (net_premium / (legs[1].quantity / legs[0].quantity - 1))
            upper_breakeven = buy_strike + net_premium
            max_loss = spread_width - net_premium
            
            response.breakeven_points = [lower_breakeven, upper_breakeven]
            response.max_profit = "Unlimited"
            response.max_loss = max_loss * legs[0].quantity
            response.profit_zones = [
                {"below": lower_breakeven},
                {"above": upper_breakeven}
            ]
        
    elif strategy_name == "Put Ratio Back Spread":
        sell_strike = pe_legs[0].strike
        buy_strike = pe_legs[1].strike
        spread_width = sell_strike - buy_strike
        
        is_premium_paid = net_premium < 0
        
        if is_premium_paid:
            # Premium paid scenario
            breakeven = buy_strike - (spread_width + abs(net_premium))
            max_loss = spread_width + abs(net_premium)
            
            response.breakeven_points = [breakeven]
            response.max_profit = "Unlimited"
            response.max_loss = max_loss * legs[0].quantity
            response.profit_zones = [{"below": breakeven}]
        else:
            # Premium received scenario
            lower_breakeven = buy_strike - spread_width + net_premium
            upper_breakeven = sell_strike - net_premium
            max_loss = spread_width - net_premium
            
            response.breakeven_points = [lower_breakeven, upper_breakeven]
            response.max_profit = "Unlimited"
            response.max_loss = max_loss * legs[0].quantity
            response.profit_zones = [
                {"below": lower_breakeven},
                {"between": [upper_breakeven, sell_strike]}
            ]
    
    # Condor strategies
    elif strategy_name == "Bull Condor":
        strike1 = ce_legs[0].strike
        strike2 = ce_legs[1].strike
        strike3 = ce_legs[2].strike
        strike4 = ce_legs[3].strike
        
        lower_breakeven = strike1 + abs(net_premium)
        upper_breakeven = strike4 - abs(net_premium)
        max_profit = (strike2 - strike1) - abs(net_premium)
        max_loss = abs(net_premium)
        
        response.breakeven_points = [lower_breakeven, upper_breakeven]
        response.max_profit = max_profit * legs[0].quantity
        response.max_loss = max_loss * legs[0].quantity
        response.profit_zones = [{"between": [lower_breakeven, upper_breakeven]}]
        response.details["max_profit_zone"] = {"between": [strike2, strike3]}
        
    elif strategy_name == "Bear Condor":
        strike1 = pe_legs[0].strike
        strike2 = pe_legs[1].strike
        strike3 = pe_legs[2].strike
        strike4 = pe_legs[3].strike
        
        lower_breakeven = strike4 + abs(net_premium)
        upper_breakeven = strike1 - abs(net_premium)
        max_profit = (strike1 - strike2) - abs(net_premium)
        max_loss = abs(net_premium)
        
        response.breakeven_points = [lower_breakeven, upper_breakeven]
        response.max_profit = max_profit * legs[0].quantity
        response.max_loss = max_loss * legs[0].quantity
        response.profit_zones = [{"between": [lower_breakeven, upper_breakeven]}]
        response.details["max_profit_zone"] = {"between": [strike3, strike2]}
    
    # Custom or unrecognized strategy
    else:
        response.details["warning"] = "This appears to be a custom or unrecognized strategy. Basic calculations may not fully represent its characteristics."
        
        # Basic calculations based on net premium
        if net_premium > 0:  # Net credit
            response.max_profit = net_premium * sum([leg.quantity for leg in legs]) / len(legs)
            response.details["max_profit_note"] = "This is an estimate based on net premium received."
        else:  # Net debit
            response.max_loss = abs(net_premium) * sum([leg.quantity for leg in legs]) / len(legs)
            response.details["max_loss_note"] = "This is an estimate based on net premium paid."
    
    # Calculate risk-reward ratio if both max profit and max loss are numerical
    if isinstance(response.max_profit, (int, float)) and isinstance(response.max_loss, (int, float)) and response.max_loss > 0:
        response.risk_reward_ratio = round(response.max_profit / response.max_loss, 2)
    
    return response


# # --- Database Interaction ---
# async def fetch_all_transactions(user_id: int):
#     query = """
#         SELECT strike_price, entry_price, lots, option_type
#         FROM user_transactions
#         WHERE user_id = %s AND status = 'active';
#     """
#     params = (user_id,)
#     results = await execute_native_query(query, params)
#     return results


# --- Database Interaction ---
async def fetch_all_transactions(user_id: str) -> List[Dict]:
    """
    Fetches active option transactions for a given user from the database.

    Args:
        user_id (str): The user ID.

    Returns:
        List[Dict]: A list of dictionaries, where each dictionary represents a transaction
                      with 'strike_price', 'entry_price', 'lots', and 'option_type' keys.
                      Returns an empty list if no active transactions are found.
                      Handles database errors and logs them.
    """
    query = """
        SELECT strike_price, entry_price, lots, option_type,
               CASE
                 WHEN option_type = 'CE' THEN 'CE'
                 WHEN option_type = 'PE' THEN 'PE'
                 ELSE NULL
               END as option_category,
               CASE
                 WHEN lots > 0 THEN 'LONG'
                 WHEN lots < 0 THEN 'SHORT'
                 ELSE NULL
               END as position_type
        FROM user_transactions
        WHERE user_id = %s AND status = 'active';
    """
    params = (user_id,)
    try:
        results = await execute_native_query(query, params)
        return results
    except Exception as e:
        logger.error(f"Database error fetching transactions for user {user_id}: {e}")
        raise  # Re-raise the exception to be handled by FastAPI's exception middleware
        #  Important:  Don't return [] on error.  Propagate the exception.



@router.get("/api/v1_0/break_even_calculator", status_code=status.HTTP_200_OK)
async def break_even_calculation(
    request: Request,
    response: Response,
    request_user_id: str = Header(None)
) -> Dict:
    """
    Calculates the break-even points for a user's active option positions.

    Args:
        request (Request): The incoming request object (not directly used here, but may be useful for context).
        response (Response): The response object (can be used to set headers or status codes if needed).
        request_user_id (str, optional): The user ID from the request header. Defaults to None.

    Returns:
        Dict: A dictionary containing the break-even points for each option position.  The keys of the
              dictionary are strings representing the option contract (e.g., "CE 23500").
              The values are the calculated break-even points (float).
              Returns:
              {
                "status": "success",
                "data": {
                    "CE 23500": 23517.05,
                    "PE 23000": 22985.20,
                    ...
                }
              }
        Raises:
            HTTPException (status_code=500): If there is an error during the process (e.g., database error).
    """
    try:
        # 1. Fetch all active transactions for the user.
        transactions = await fetch_all_transactions(request_user_id)

        # 2. Process the transactions and calculate break-even points.
        break_even_data = {}
        for transaction in transactions:
            try:
                # Construct an OptionTransaction object for easier handling.
                option_data = OptionTransaction(
                    strike_price=transaction["strike_price"],
                    entry_price=transaction["entry_price"],
                    lots=transaction["lots"],
                    option_type=transaction["option_category"], # Use the calculated column
                )

                # Determine LONG or SHORT position
                position_type = transaction["position_type"]

                # Get the appropriate break-even calculation function.
                calculation_function = strategy_functions[option_data.option_type][position_type]

                # Calculate the break-even point.
                break_even_point = calculation_function(option_data)

                # Create a unique key for the option contract.
                contract_key = f"{option_data.option_type} {int(option_data.strike_price)}"  # Convert strike_price to int

                # Store the break-even point.
                break_even_data[contract_key] = break_even_point

            except KeyError as e:
                logger.error(f"KeyError processing transaction: {transaction}. Error: {e}")
                #  Important:  Instead of skipping, log the error and consider:
                #  1.  Returning an error to the user (HTTPException)
                #  2.  Continuing, but with a clear indication in the response that some transactions failed.
                #  Here, we'll skip, but log.
                continue  # Skip to the next transaction
            except Exception as e:
                logger.error(f"Error calculating break-even for transaction: {transaction}. Error: {e}")
                continue

        # 3. Return the break-even data in the response.
        return {
            "status": "success",
            "data": break_even_data
        }

    except HTTPException as e:
        #  Catch the HTTPException that might be raised by fetch_all_transactions
        raise e
    except Exception as e:
        # 4. Handle any errors that occur during the process.  Log the error and raise an HTTPException.
        logger.exception(f"Error in break_even_calculation for user {request_user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while calculating break-even points."
        )


@router.post("/api/v1_0/breakeven_profit", status_code=status.HTTP_200_OK, response_model=Dict)
async def analyze_options_strategy(
    request: Request,
    strategy_request: StrategyRequest,
    response: Response
) -> Dict:
    """
    Analyzes an options strategy based on the provided legs.
    
    Args:
        request: The FastAPI request object
        strategy_request: A StrategyRequest object containing the legs of the strategy
        response: The FastAPI response object
        
    Returns:
        Dict: A dictionary containing the strategy analysis results
        {
            "status": "success",
            "data": {
                "strategy_name": "Bull Call Spread",
                "breakeven_points": [25782.75],
                "max_profit": 16687.5,
                "max_loss": 5625.0,
                "profit_zones": [{"between": [25782.75, 25950]}],
                "risk_reward_ratio": 2.97,
                "details": {
                    "net_premium": 75.0,
                    ...
                }
            }
        }
        
    Raises:
        HTTPException: If there is an error during the analysis process
    """
    try:
        logger.debug(f"Received strategy analysis request with {len(strategy_request.legs)} legs")
        
        # Check if any legs were provided
        if not strategy_request.legs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No option legs provided for analysis"
            )
        
        # Identify the strategy
        strategy_name = identify_strategy(strategy_request.legs)
        logger.info(f"Identified strategy: {strategy_name}")
        
        # Analyze the strategy
        analysis_result = analyze_strategy(strategy_name, strategy_request.legs)
        
        # Return the analysis result
        return {
            "status": "success",
            "data": analysis_result
        }
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request data: {str(e)}"
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        logger.exception(f"Error in analyze_options_strategy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while analyzing the options strategy: {str(e)}"
        )


def combined_payoff(spot_price, legs):
    """
    Calculate the combined payoff for all option legs at a given spot price.
    
    Args:
        spot_price: The spot price of the underlying at expiry
        legs: List of OptionLeg objects
        
    Returns:
        float: The total P&L at the given spot price
    """
    total = 0
    for leg in legs:
        # Calculate intrinsic value at expiry
        if leg.option_type == "CE":
            intrinsic = max(0, spot_price - leg.strike)
        else:  # PE
            intrinsic = max(0, leg.strike - spot_price)
        
        # Apply action multiplier and quantity
        multiplier = 1 if leg.action == "BUY" else -1
        leg_payoff = multiplier * intrinsic * leg.quantity
        
        # Include premium effect
        premium_effect = -multiplier * leg.premium * leg.quantity
        
        total += leg_payoff + premium_effect
    return total

def find_breakeven_points(legs, min_price=None, max_price=None, samples=1000):
    """
    Find all breakeven points (where payoff = 0) for an options strategy.
    
    Args:
        legs: List of OptionLeg objects
        min_price: Lower bound for price search (optional)
        max_price: Upper bound for price search (optional)
        samples: Number of price samples to evaluate
        
    Returns:
        list: Sorted list of breakeven prices
    """
    # Determine price range if not provided
    if min_price is None or max_price is None:
        strikes = [leg.strike for leg in legs]
        min_strike = min(strikes)
        max_strike = max(strikes)
        
        # Add buffer around strikes (±20%)
        buffer = max(2000, (max_strike - min_strike) * 0.2)  # Minimum buffer of 2000 points
        
        if min_price is None:
            min_price = max(0, min_strike - buffer)
        if max_price is None:
            max_price = max_strike + buffer
    
    # Function to evaluate payoff at a specific price
    def payoff_at_price(price):
        return combined_payoff(price, legs)
    
    # Sample points to find regions where P&L changes sign
    prices = np.linspace(min_price, max_price, samples)
    payoffs = [payoff_at_price(price) for price in prices]
    
    # Find potential breakeven intervals
    breakeven_intervals = []
    for i in range(1, len(prices)):
        if payoffs[i-1] * payoffs[i] <= 0:  # Sign change indicates a zero crossing
            breakeven_intervals.append((prices[i-1], prices[i]))
    
    # Use numerical method to find precise breakeven points
    breakevens = []
    for lower, upper in breakeven_intervals:
        try:
            # Use root-finding to get precise breakeven
            breakeven = brentq(payoff_at_price, lower, upper)
            breakevens.append(round(breakeven, 2))
        except ValueError:
            # If the function doesn't actually cross zero, skip
            continue
    
    return sorted(breakevens)

def analyze_strategy_numerically(legs):
    """
    Analyzes any options strategy using numerical methods to calculate key metrics.
    
    Args:
        legs: List of OptionLeg objects
        
    Returns:
        StrategyResponse: Analysis results including breakeven points, max profit, max loss, etc.
    """
    response = StrategyResponse(
        strategy_name="Custom Strategy",
        breakeven_points=[],
        max_profit=0,
        max_loss=0,
        profit_zones=[],
        legs=legs,
        details={}
    )
    
    # Determine reasonable price range based on strikes
    strikes = [leg.strike for leg in legs]
    min_strike = min(strikes)
    max_strike = max(strikes)
    
    # Add buffer for analysis (±20% with minimum of 2000 points)
    buffer = max(2000, (max_strike - min_strike) * 0.2)
    min_price = max(0, min_strike - buffer)
    max_price = max_strike + buffer
    
    # Calculate breakeven points
    breakevens = find_breakeven_points(legs, min_price, max_price)
    response.breakeven_points = breakevens
    
    # Calculate payoff at a range of prices to find max profit and loss
    step = (max_price - min_price) / 1000
    prices = np.arange(min_price, max_price + step, step)
    payoffs = [combined_payoff(price, legs) for price in prices]
    
    # Find max profit and loss
    max_profit = max(payoffs)
    min_payoff = min(payoffs)
    max_loss = abs(min_payoff) if min_payoff < 0 else 0
    
    # Find prices at max profit and max loss
    max_profit_price = prices[payoffs.index(max_profit)]
    if min_payoff < 0:
        max_loss_price = prices[payoffs.index(min_payoff)]
    else:
        max_loss_price = None
    
    response.max_profit = round(max_profit, 2)
    response.max_loss = round(max_loss, 2)
    
    response.details["max_profit_at"] = round(max_profit_price, 2)
    if max_loss_price:
        response.details["max_loss_at"] = round(max_loss_price, 2)
    
    # Determine profit zones (where payoff > 0)
    profit_zones = []
    current_zone = None
    
    for i in range(len(prices)):
        if payoffs[i] > 0 and current_zone is None:
            current_zone = {"from": prices[i]}
        elif payoffs[i] <= 0 and current_zone is not None:
            current_zone["to"] = prices[i-1]
            profit_zones.append({"between": [round(current_zone["from"], 2), round(current_zone["to"], 2)]})
            current_zone = None
    
    # Handle case where profit extends to the end of the range
    if current_zone is not None:
        profit_zones.append({"between": [round(current_zone["from"], 2), round(max_price, 2)]})
    
    response.profit_zones = profit_zones
    
    # Calculate payoff curve data for visualization (optional)
    curve_samples = 50  # Reduced number of points for API response
    curve_prices = np.linspace(min_price, max_price, curve_samples)
    curve_payoffs = [combined_payoff(price, legs) for price in curve_prices]
    
    response.details["payoff_curve"] = {
        "prices": [round(p, 2) for p in curve_prices],
        "payoffs": [round(p, 2) for p in curve_payoffs]
    }
    
    # Calculate risk-reward ratio if both max profit and max loss are non-zero
    if response.max_profit > 0 and response.max_loss > 0:
        response.risk_reward_ratio = round(response.max_profit / response.max_loss, 2)
    
    return response

# New API endpoint specifically for numerical analysis
@router.post("/api/v1_0/analyze_custom_strategy", status_code=status.HTTP_200_OK, response_model=Dict)
async def analyze_custom_strategy(
    request: Request,
    strategy_request: StrategyRequest,
    response: Response
) -> Dict:
    """
    Analyzes any options strategy using numerical methods, regardless of whether it's a recognized pattern.
    
    Args:
        request: The FastAPI request object
        strategy_request: A StrategyRequest object containing the legs of the strategy
        response: The FastAPI response object
        
    Returns:
        Dict: A dictionary containing the strategy analysis results
        
    Raises:
        HTTPException: If there is an error during the analysis process
    """
    try:
        logger.debug(f"Received custom strategy analysis request with {len(strategy_request.legs)} legs")
        
        # Check if any legs were provided
        if not strategy_request.legs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No option legs provided for analysis"
            )
        
        # Analyze the strategy using numerical methods
        analysis_result = analyze_strategy_numerically(strategy_request.legs)
        
        # Try to identify the strategy name for reference
        strategy_name = identify_strategy(strategy_request.legs)
        if strategy_name != "Custom Strategy":
            analysis_result.details["possible_match"] = strategy_name
            analysis_result.details["note"] = "This strategy resembles a known pattern, but numerical analysis was used for precise results."
        
        # Return the analysis result
        return {
            "status": "success",
            "data": analysis_result
        }
        
    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request data: {str(e)}"
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        logger.exception(f"Error in analyze_custom_strategy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while analyzing the options strategy: {str(e)}"
        )

