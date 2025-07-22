"""
Safestrike Breakeven Adjustment API Endpoint
FastAPI router for the Safestrike breakeven adjustment tool
"""

from fastapi import APIRouter, HTTPException, Header, status, Depends
from typing import List, Dict, Optional
from datetime import date, datetime
from pydantic import BaseModel
import logging

from ..services.safestrike_adjuster import SafestrikeBreakevenAdjuster, AdditionalPosition, BreakevenAdjustmentResult
from ..services.greeks_calculator import GreeksCalculator
from ..services.safestrike_recommendation import SafestrikeRecommendation
from ..services.position_service import get_current_user_positions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1_0/safestrike", tags=["Safestrike Breakeven Adjustment"])

# Pydantic models for request/response
class SafestrikeAdjustmentRequest(BaseModel):
    symbol: str = "NIFTY"
    current_spot: float
    expiry_date: str  # YYYY-MM-DD format
    target_breakeven: Optional[float] = None  # If None, uses Safestrike recommendation
    max_additional_legs: Optional[int] = 3
    recommendation_method: Optional[str] = "volatility_based"

class PositionResponse(BaseModel):
    symbol: str
    strike: float
    option_type: str
    action: str
    quantity: int
    premium: float
    market_lot: int
    greeks: Dict[str, float]

class AdjustmentResultResponse(BaseModel):
    original_breakeven: List[float]
    target_breakeven: float
    recommended_positions: List[PositionResponse]
    new_breakeven: List[float]
    theta_gamma_ratio: float
    total_additional_premium: float
    portfolio_greeks_before: Dict[str, float]
    portfolio_greeks_after: Dict[str, float]
    confidence_score: float
    warnings: List[str]

class SafestrikeAdjustmentResponse(BaseModel):
    status: str
    message: str
    current_positions_count: int
    safestrike_recommendation: float
    adjustment_results: List[AdjustmentResultResponse]
    metadata: Dict[str, any]

@router.post("/breakeven_adjustment", 
             response_model=SafestrikeAdjustmentResponse,
             status_code=status.HTTP_200_OK)
async def calculate_safestrike_breakeven_adjustment(
    request: SafestrikeAdjustmentRequest,
    request_user_id: str = Header(None)
):
    """
    Calculate additional positions needed to shift effective breakeven to Safestrike recommendation
    
    This endpoint:
    1. Fetches current open positions for the user
    2. Gets Safestrike recommendation for target strike
    3. Enumerates possible additional position combinations
    4. Ranks combinations by Theta/Gamma ratio
    5. Returns top 5 adjustment strategies
    """
    
    if not request_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="request-user-id header is required"
        )
    
    try:
        # Parse expiry date
        expiry_date = datetime.strptime(request.expiry_date, "%Y-%m-%d").date()
        
        # Initialize services
        greeks_calculator = GreeksCalculator()
        safestrike_service = SafestrikeRecommendation()
        adjuster = SafestrikeBreakevenAdjuster(greeks_calculator, safestrike_service)
        
        # Set configuration
        if request.max_additional_legs:
            adjuster.max_additional_legs = request.max_additional_legs
        
        # Fetch current open positions
        current_positions = await get_current_user_positions(request_user_id)
        
        if not current_positions:
            return SafestrikeAdjustmentResponse(
                status="success",
                message="No open positions found for adjustment",
                current_positions_count=0,
                safestrike_recommendation=0,
                adjustment_results=[],
                metadata={"request_params": request.dict()}
            )
        
        # Get Safestrike recommendation
        safestrike_recommendation = safestrike_service.get_recommended_strike(
            request.symbol, 
            request.current_spot, 
            expiry_date, 
            request.recommendation_method
        )
        
        # Use target breakeven from request or Safestrike recommendation
        target_breakeven = request.target_breakeven or safestrike_recommendation
        
        logger.info(f"Processing Safestrike adjustment for user {request_user_id}: "
                   f"spot={request.current_spot}, target={target_breakeven}, "
                   f"positions={len(current_positions)}")
        
        # Calculate breakeven adjustments
        adjustment_results = adjuster.calculate_breakeven_adjustment(
            current_positions=current_positions,
            symbol=request.symbol,
            current_spot=request.current_spot,
            expiry_date=expiry_date,
            target_breakeven=target_breakeven
        )
        
        # Convert results to response format
        response_results = []
        for result in adjustment_results:
            positions_response = [
                PositionResponse(
                    symbol=pos.symbol,
                    strike=pos.strike,
                    option_type=pos.option_type,
                    action=pos.action,
                    quantity=pos.quantity,
                    premium=pos.premium,
                    market_lot=pos.market_lot,
                    greeks=pos.greeks
                ) for pos in result.recommended_positions
            ]
            
            response_results.append(AdjustmentResultResponse(
                original_breakeven=result.original_breakeven,
                target_breakeven=result.target_breakeven,
                recommended_positions=positions_response,
                new_breakeven=result.new_breakeven,
                theta_gamma_ratio=result.theta_gamma_ratio,
                total_additional_premium=result.total_additional_premium,
                portfolio_greeks_before=result.portfolio_greeks_before,
                portfolio_greeks_after=result.portfolio_greeks_after,
                confidence_score=result.confidence_score,
                warnings=result.warnings
            ))
        
        # Prepare metadata
        metadata = {
            "request_params": request.dict(),
            "processing_timestamp": datetime.now().isoformat(),
            "positions_analyzed": len(current_positions),
            "combinations_evaluated": len(adjustment_results),
            "safestrike_validation": safestrike_service.validate_safestrike_conditions(
                request.symbol, request.current_spot, safestrike_recommendation, expiry_date
            )
        }
        
        return SafestrikeAdjustmentResponse(
            status="success",
            message=f"Found {len(response_results)} adjustment strategies",
            current_positions_count=len(current_positions),
            safestrike_recommendation=safestrike_recommendation,
            adjustment_results=response_results,
            metadata=metadata
        )
        
    except ValueError as e:
        logger.error(f"Invalid date format in request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Use YYYY-MM-DD: {str(e)}"
        )
    
    except Exception as e:
        logger.error(f"Error in Safestrike breakeven adjustment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/recommendation/{symbol}",
            status_code=status.HTTP_200_OK)
async def get_safestrike_recommendation(
    symbol: str,
    spot_price: float,
    expiry_date: str,
    method: str = "volatility_based"
):
    """
    Get Safestrike recommendation for a given symbol and conditions
    """
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").date()
        safestrike_service = SafestrikeRecommendation()
        
        # Get single recommendation
        recommendation = safestrike_service.get_recommended_strike(symbol, spot_price, expiry, method)
        
        # Get multiple recommendations for comparison
        multiple_recommendations = safestrike_service.get_multiple_recommendations(symbol, spot_price, expiry)
        
        # Get validation
        validation = safestrike_service.validate_safestrike_conditions(symbol, spot_price, recommendation, expiry)
        
        return {
            "status": "success",
            "symbol": symbol,
            "spot_price": spot_price,
            "expiry_date": expiry_date,
            "primary_recommendation": recommendation,
            "all_recommendations": multiple_recommendations,
            "validation": validation,
            "method_used": method
        }
        
    except Exception as e:
        logger.error(f"Error getting Safestrike recommendation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting recommendation: {str(e)}"
        )

@router.get("/greeks",
            status_code=status.HTTP_200_OK)
async def calculate_position_greeks(
    symbol: str,
    strike: float,
    spot_price: float,
    expiry_date: str,
    option_type: str = "CE",
    volatility: float = 0.15
):
    """
    Calculate Greeks for a specific option position
    """
    try:
        expiry = datetime.strptime(expiry_date, "%Y-%m-%d").date()
        greeks_calculator = GreeksCalculator()
        
        time_to_expiry = greeks_calculator.get_time_to_expiry_years(expiry)
        
        greeks = greeks_calculator.calculate_all_greeks(
            S=spot_price,
            K=strike,
            T=time_to_expiry,
            r=0.065,
            sigma=volatility,
            option_type=option_type
        )
        
        return {
            "status": "success",
            "symbol": symbol,
            "strike": strike,
            "spot_price": spot_price,
            "option_type": option_type,
            "expiry_date": expiry_date,
            "time_to_expiry_years": time_to_expiry,
            "volatility": volatility,
            "greeks": greeks
        }
        
    except Exception as e:
        logger.error(f"Error calculating Greeks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating Greeks: {str(e)}"
        )
