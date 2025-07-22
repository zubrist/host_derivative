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
import aiohttp
from fastapi import BackgroundTasks
import os
from dotenv import load_dotenv


# import from our files
from db.models.break_even import *


# Configure Logging
logging.basicConfig(level=logging.DEBUG) # Keep this for root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # Explicitly set level for this specific logger

# Load environment variables
load_dotenv()

# Strategy Simulation Router
router = APIRouter()



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
        
        # Include premium effect if premium is available
        if leg.premium is not None:
            premium_effect = -multiplier * leg.premium * leg.quantity
            total += premium_effect
        
        total += leg_payoff
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
    
    # Find max profit and loss within the finite range
    max_profit_in_range = max(payoffs)
    min_payoff = min(payoffs)
    max_loss_in_range = abs(min_payoff) if min_payoff < 0 else 0
    
    # Find prices at max profit and max loss within range
    max_profit_price = prices[payoffs.index(max_profit_in_range)]
    if min_payoff < 0:
        max_loss_price = prices[payoffs.index(min_payoff)]
    else:
        max_loss_price = None
    
    # Check for unlimited profit/loss potential by analyzing strategy characteristics
    has_unlimited_profit = check_unlimited_profit_potential(legs)
    has_unlimited_loss = check_unlimited_loss_potential(legs)
    
    # Set max profit
    if has_unlimited_profit:
        response.max_profit = "Unlimited"
        response.details["max_profit_note"] = "Theoretical maximum profit is unlimited"
    else:
        response.max_profit = round(max_profit_in_range, 2)
        response.details["max_profit_at"] = round(max_profit_price, 2)
    
    # Set max loss
    if has_unlimited_loss:
        response.max_loss = "Unlimited"
        response.details["max_loss_note"] = "Theoretical maximum loss is unlimited"
    else:
        response.max_loss = round(max_loss_in_range, 2)
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
        if has_unlimited_profit:
            profit_zones.append({"between": [round(current_zone["from"], 2), "Unlimited"]})
        else:
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
    
    # Calculate risk-reward ratio if both max profit and max loss are numeric and non-zero
    if (isinstance(response.max_profit, (int, float)) and response.max_profit > 0 and 
        isinstance(response.max_loss, (int, float)) and response.max_loss > 0):
        response.risk_reward_ratio = round(response.max_profit / response.max_loss, 2)
    elif response.max_profit == "Unlimited" and isinstance(response.max_loss, (int, float)) and response.max_loss > 0:
        response.risk_reward_ratio = "Unlimited"
    elif isinstance(response.max_profit, (int, float)) and response.max_loss == "Unlimited":
        response.risk_reward_ratio = 0.0
    
    return response


# New API endpoint specifically for numerical analysis
@router.post("/api/v1_0/analyze_custom_strategy", status_code=status.HTTP_200_OK, response_model=Dict)
async def analyze_custom_strategy(
    request: Request,
    strategy_request: StrategyRequest,
    response: Response,
    background_tasks: BackgroundTasks
) -> Dict:
    """
    Analyzes any options strategy using numerical methods, regardless of whether it's a recognized pattern.
    
    Args:
        request: The FastAPI request object
        strategy_request: A StrategyRequest object containing the legs of the strategy
        response: The FastAPI response object
        background_tasks: FastAPI background tasks for async operations
        
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
        
        # Create a copy of the legs to avoid modifying the original request
        legs_with_prices = []
        
        # Get today's date for price lookup
        today = datetime.now().date()
        
        # Format dates for NSE API with fallback logic
        now = datetime.now()
        market_close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        # Primary date logic (after market close)
        if now > market_close_time:
            from_date_primary = today.strftime('%d-%m-%Y')  # Today
            to_date_primary = (today + timedelta(days=1)).strftime('%d-%m-%Y')  # Tomorrow
        else:
            from_date_primary = (today - timedelta(days=1)).strftime('%d-%m-%Y')  # Yesterday
            to_date_primary = today.strftime('%d-%m-%Y')  # Today
        
        # Fallback date logic (previous trading day)
        from_date_fallback = (today - timedelta(days=1)).strftime('%d-%m-%Y')  # Yesterday
        to_date_fallback = today.strftime('%d-%m-%Y')  # Today
        
        year = today.year

        # Create an HTTP client session for making requests
        async with aiohttp.ClientSession() as session:
            # Process each leg to fetch current price if not provided
            for leg in strategy_request.legs:
                # Create a copy of the leg
                updated_leg = leg.copy()
                
                # Check if premium is provided and non-zero
                if leg.premium is None or leg.premium == 0:
                    try:
                        # Format the expiry date for the API
                        try:
                            # Try multiple date formats
                            expiry_obj = datetime.strptime(leg.expiry, "%d-%b-%Y")
                        except ValueError:
                            expiry_obj = datetime.strptime(leg.expiry, "%d-%B-%Y")
                        
                        expiry_formatted = expiry_obj.strftime("%d-%b-%Y")
                        
                        # Replace the hardcoded URL with an environment variable or use service discovery
                        api_base_url = os.getenv("NSE_API_URL", "http://nse:8000")  # Default to Docker service name
                        
                        price_fetched = False
                        
                        # Try primary date range first
                        api_url_primary = f"{api_base_url}/api/v1_0/search-data/{from_date_primary}/{to_date_primary}/OPTIDX/{leg.symbol}/{year}/{expiry_formatted}/{leg.option_type}/{int(leg.strike)}"
                        logger.debug(f"Trying primary URL: {api_url_primary}")
                        
                        # Make the primary API request
                        try:
                            async with session.get(api_url_primary) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    
                                    if data.get("status") == "success" and data.get("data"):
                                        option_data = data["data"][0]
                                        
                                        # Get the last traded price
                                        price = float(option_data.get("FH_LAST_TRADED_PRICE", 0))
                                        if price == 0:
                                            # Try closing price if last traded is 0
                                            price = float(option_data.get("FH_CLOSING_PRICE", 0))
                                        
                                        if price > 0:
                                            updated_leg.premium = price
                                            logger.info(f"Fetched price for {leg.symbol} {leg.strike} {leg.option_type}: {price} (primary)")
                                            price_fetched = True
                                        else:
                                            logger.warning(f"Zero price returned from primary API for {leg.symbol} {leg.strike} {leg.option_type}")
                                    else:
                                        logger.warning(f"No data returned from primary API for {leg.symbol} {leg.strike} {leg.option_type}")
                                else:
                                    logger.warning(f"Primary API request failed with status {resp.status}")
                        except Exception as e:
                            logger.warning(f"Primary API request failed with exception: {str(e)}")
                        
                        # If primary failed, try fallback date range
                        if not price_fetched:
                            api_url_fallback = f"{api_base_url}/api/v1_0/search-data/{from_date_fallback}/{to_date_fallback}/OPTIDX/{leg.symbol}/{year}/{expiry_formatted}/{leg.option_type}/{int(leg.strike)}"
                            logger.debug(f"Trying fallback URL: {api_url_fallback}")
                            
                            try:
                                async with session.get(api_url_fallback) as resp:
                                    if resp.status == 200:
                                        data = await resp.json()
                                        
                                        if data.get("status") == "success" and data.get("data"):
                                            option_data = data["data"][0]
                                            
                                            # Get the last traded price
                                            price = float(option_data.get("FH_LAST_TRADED_PRICE", 0))
                                            if price == 0:
                                                # Try closing price if last traded is 0
                                                price = float(option_data.get("FH_CLOSING_PRICE", 0))
                                            
                                            if price > 0:
                                                updated_leg.premium = price
                                                logger.info(f"Fetched price for {leg.symbol} {leg.strike} {leg.option_type}: {price} (fallback)")
                                                price_fetched = True
                                            else:
                                                logger.warning(f"Zero price returned from fallback API for {leg.symbol} {leg.strike} {leg.option_type}")
                                        else:
                                            logger.warning(f"No data returned from fallback API for {leg.symbol} {leg.strike} {leg.option_type}")
                                    else:
                                        logger.warning(f"Fallback API request failed with status {resp.status}")
                            except Exception as e:
                                logger.warning(f"Fallback API request failed with exception: {str(e)}")
                        
                        # If both primary and fallback failed, raise an error
                        if not price_fetched:
                            raise ValueError("Both primary and fallback API requests failed to fetch valid price data")
                                
                    except Exception as e:
                        logger.error(f"Error fetching price for {leg.symbol} {leg.strike} {leg.option_type}: {str(e)}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Could not fetch price for {leg.symbol} {leg.strike} {leg.option_type}. Please provide premium in the request."
                        )
                
                legs_with_prices.append(updated_leg)
        
        # Log the updated legs with fetched prices
        logger.info(f"Strategy legs with prices: {legs_with_prices}")
        
        # Analyze the strategy using numerical methods with the updated legs
        analysis_result = analyze_strategy_numerically(legs_with_prices)
        
        # Try to identify the strategy name for reference
        strategy_name = identify_strategy(legs_with_prices)
        analysis_result.strategy_name = strategy_name
        if strategy_name != "Custom Strategy":
            analysis_result.details["note"] = "Strategy identified and analyzed using numerical methods for precise results."
        
        # Add information about price source
        analysis_result.details["price_source"] = "NSE API (auto-fetched)"
        
        
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


def check_unlimited_profit_potential(legs):
    """
    Check if the strategy has unlimited profit potential.
    
    Args:
        legs: List of OptionLeg objects
        
    Returns:
        bool: True if the strategy has unlimited profit potential
    """
    # Strategies with unlimited profit potential:
    # 1. Net long calls (more bought calls than sold calls)
    # 2. Net short puts (more sold puts than bought puts)
    # 3. Certain combinations where unlimited upside exists
    
    net_call_position = 0
    net_put_position = 0
    
    for leg in legs:
        multiplier = 1 if leg.action == "BUY" else -1
        quantity = leg.quantity * multiplier
        
        if leg.option_type == "CE":
            net_call_position += quantity
        else:  # PE
            net_put_position += quantity
    
    # If we have net long calls, profit is unlimited on upside
    if net_call_position > 0:
        return True
    
    # If we have net short puts, profit is unlimited on upside
    if net_put_position < 0:
        return True
    
    return False


def check_unlimited_loss_potential(legs):
    """
    Check if the strategy has unlimited loss potential.
    
    Args:
        legs: List of OptionLeg objects
        
    Returns:
        bool: True if the strategy has unlimited loss potential
    """
    # Strategies with unlimited loss potential:
    # 1. Net short calls (more sold calls than bought calls)
    # 2. Net long puts (more bought puts than sold puts) - unlimited downside
    # 3. Certain combinations where unlimited downside exists
    
    net_call_position = 0
    net_put_position = 0
    
    for leg in legs:
        multiplier = 1 if leg.action == "BUY" else -1
        quantity = leg.quantity * multiplier
        
        if leg.option_type == "CE":
            net_call_position += quantity
        else:  # PE
            net_put_position += quantity
    
    # If we have net short calls, loss is unlimited on upside
    if net_call_position < 0:
        return True
    
    # If we have net long puts, loss could be significant on downside (stock can go to 0)
    # But this is not truly "unlimited" as stock price can't go below 0
    # We'll be conservative and not mark this as unlimited
    
    return False

