from fastapi import APIRouter, HTTPException, status 
from datetime import date , datetime , timedelta
import logging
from services.black_scholes import BlackScholesService
from services.nse_service import NSE
from db.models.implied_volatility import ImpliedVolatilityRequest,ImpliedVolatilityResponse , OptionDetails


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/v1_0/implied_volatility", response_model=ImpliedVolatilityResponse,status_code=status.HTTP_200_OK)
async def calculate_implied_volatility(payload: ImpliedVolatilityRequest):
    """
    Calculate implied volatility by matching calculated premium with market premium
    """
    try:

        # Convert string date to date object
        expiry_date = datetime.strptime(payload.expiry_date, "%Y-%m-%d")


        # Initialize services
        bs_service = BlackScholesService()
        nse_service = NSE()

        # Fetch data for both CE and PE
        call_data = None
        put_data = None
        underlying_value = None
        
        # In the router, replace the test_date logic with:
        if payload.market_data_date:
            test_date = datetime.strptime(payload.market_data_date, "%Y-%m-%d")
            logger.info(f"Using provided date for market data: {test_date.strftime('%Y-%m-%d')}")
        else:
            # Use previous trading day by default
            today = datetime.now()
            test_date = today - timedelta(days=1)  # Previous day
            logger.info(f"Using previous day for market data: {test_date.strftime('%Y-%m-%d')}")

        # Calculate time to expiry in years
        days_to_expiry = (expiry_date - test_date).days
        #days_to_expiry = (expiry_date - date.today()).days
        T = days_to_expiry / 365.0

        logger.info(f"Days to expiry: {days_to_expiry}, T: {T}")
        if T <= 0:
            raise HTTPException(status_code=400, detail="Expiry date must be in the future")

        
        # Fetch market data from NSE
       # from_date = datetime.now().date()
        from_date = test_date
        async with NSE() as nse_service:
            logger.info("Fetching CE (Call) option data...")
            call_market_data = await nse_service.get_historical_data(
                symbol=payload.symbol,
                from_date=from_date,
                to_date=from_date,
                expiry_date=expiry_date,
                option_type="CE",
                strike_price=payload.strike_price
            )
            
            # Fetch Put (PE) data
            logger.info("Fetching PE (Put) option data...")
            put_market_data = await nse_service.get_historical_data(
                symbol=payload.symbol,
                from_date=from_date,
                to_date=from_date,
                expiry_date=expiry_date,
                option_type="PE",
                strike_price=payload.strike_price
            )

        logger.info(f"Market data received: {len(call_market_data) if call_market_data else 0} records")

        if not call_market_data:
            raise HTTPException(status_code=404, detail="No market data available")

        # fetched data from nse
        logger.info(f"Call Market data fetched: {call_market_data}")

        

        # Get last traded price from market data
        call_market_premium = float(call_market_data[0]['FH_LAST_TRADED_PRICE'])
        # Get underlying value from call data
        underlying_value = float(call_market_data[0]['FH_UNDERLYING_VALUE'])
        logger.info(f"Market premium (LTP): {call_market_premium}")
        logger.info(f"Underlying value: {underlying_value}")


        # Calculate implied volatility
        call_iv = bs_service.calculate_implied_volatility(
            market_price=call_market_premium,
            S=payload.spot_price,
            K=payload.strike_price,
            T=T,
            r=payload.risk_free_rate,
            option_type="CE"
        )
        
        # Calculate option premium with the found implied volatility
        call_calculated_premium = bs_service.calculate_call_option_price(
            S=payload.spot_price,
            K=payload.strike_price,
            T=T,
            r=payload.risk_free_rate,
            sigma=call_iv
        )
        
        # Check if convergence was achieved (difference < 5)
        convergence_achieved = abs(call_calculated_premium - call_market_premium) < 5


        call_data = OptionDetails(
            option_type="CE",
            implied_volatility=round(call_iv * 100, 2),  # Convert to percentage
            calculated_premium=round(call_calculated_premium, 2),
            market_premium=call_market_premium,
            convergence_achieved=convergence_achieved
        )

        logger.info(f"Market data fetched: {put_market_data}" if put_market_data else "No Put data available")
        logger.info(f"Put market data: {put_market_data}")

        if not put_market_data:
            raise HTTPException(status_code=404, detail="No Put market data available")
        
        # Get PUT market premium - FIXED: Use put_market_data instead of call data
        put_market_premium = float(put_market_data[0]['FH_LAST_TRADED_PRICE'])
        logger.info(f"Put Market premium (LTP): {put_market_premium}")
        
        # Calculate Put IV
        put_iv = bs_service.calculate_implied_volatility(
            market_price=put_market_premium,
            S=payload.spot_price,
            K=payload.strike_price,
            T=T,
            r=payload.risk_free_rate,
            option_type="PE"
        )
        # Calculate Put option premium with the found implied volatility
        put_calculated_premium = bs_service.calculate_put_option_price(
            S=payload.spot_price,
            K=payload.strike_price,
            T=T,
            r=payload.risk_free_rate,
            sigma=put_iv
        )

        # Check PUT convergence
        put_convergence_achieved = abs(put_calculated_premium - put_market_premium) < 5

        put_data = OptionDetails(
            option_type="PE",
            implied_volatility=round(put_iv * 100, 2),  # Convert to percentage
            calculated_premium=round(put_calculated_premium, 2),
            market_premium=put_market_premium,
            convergence_achieved=put_convergence_achieved
        )
        
        result = ImpliedVolatilityResponse(
            symbol=payload.symbol,
            strike_price=payload.strike_price,
            expiry_date=payload.expiry_date,
            market_data_date=payload.market_data_date or test_date.strftime("%Y-%m-%d"),
            call_option=call_data,
            put_option=put_data,
            iterations=bs_service.MAX_ITERATIONS,
            spot_price=payload.spot_price,  # FIXED: Added missing field
            underlying_value=underlying_value  # FIXED: Added missing field
            
        )
        logger.info(f"Returning result: {result}")
        return result

    except Exception as e:
        logger.error(f"Error calculating implied volatility: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))