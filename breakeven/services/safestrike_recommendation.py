"""
Safestrike Recommendation Engine
Provides recommended strike prices based on volatility analysis and market conditions
"""

import math
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SafestrikeRecommendation:
    """
    Generates recommended strike prices based on various algorithms and market conditions
    """
    
    def __init__(self, nse_service=None, volatility_service=None):
        self.nse_service = nse_service
        self.volatility_service = volatility_service
    
    def get_recommended_strike(self, symbol: str, current_spot: float, 
                             expiry_date: date, method: str = "volatility_based") -> float:
        """
        Get recommended strike based on specified method
        
        Args:
            symbol: Underlying symbol (e.g., "NIFTY")
            current_spot: Current spot price
            expiry_date: Option expiry date
            method: Recommendation method
            
        Returns:
            Recommended strike price
        """
        if method == "volatility_based":
            return self._get_volatility_based_strike(symbol, current_spot, expiry_date)
        elif method == "atm":
            return self._get_atm_strike(current_spot)
        elif method == "support_resistance":
            return self._get_support_resistance_strike(symbol, current_spot)
        elif method == "momentum":
            return self._get_momentum_based_strike(symbol, current_spot)
        else:
            # Default to ATM
            return self._get_atm_strike(current_spot)
    
    def _get_volatility_based_strike(self, symbol: str, current_spot: float, expiry_date: date) -> float:
        """
        Calculate strike based on volatility analysis
        Similar to your existing volatility calculation logic
        """
        try:
            # Calculate days to expiry
            days_to_expiry = (expiry_date - date.today()).days
            if days_to_expiry <= 0:
                return self._get_atm_strike(current_spot)
            
            # Use simplified volatility calculation (you can integrate with your existing volatility service)
            # For now, using a conservative approach
            implied_volatility = 0.15  # 15% default - replace with actual IV calculation
            
            # Calculate expected move (1 standard deviation)
            time_to_expiry = days_to_expiry / 365.0
            expected_move = current_spot * implied_volatility * math.sqrt(time_to_expiry)
            
            # Recommend strike at 1 standard deviation based on market bias
            # For now, using spot + 0.5 * expected_move as a neutral recommendation
            recommended_price = current_spot + (0.5 * expected_move)
            
            return self._round_to_nearest_strike(recommended_price)
            
        except Exception as e:
            logger.error(f"Error calculating volatility-based strike: {str(e)}")
            return self._get_atm_strike(current_spot)
    
    def _get_atm_strike(self, current_spot: float) -> float:
        """Get At-The-Money strike"""
        return self._round_to_nearest_strike(current_spot)
    
    def _get_support_resistance_strike(self, symbol: str, current_spot: float) -> float:
        """
        Calculate strike based on support/resistance levels
        Placeholder for future implementation with technical analysis
        """
        # For now, return a strike slightly above current spot
        return self._round_to_nearest_strike(current_spot * 1.02)
    
    def _get_momentum_based_strike(self, symbol: str, current_spot: float) -> float:
        """
        Calculate strike based on momentum indicators
        Placeholder for future implementation with momentum analysis
        """
        # For now, return a strike based on recent trend (simplified)
        return self._round_to_nearest_strike(current_spot * 1.01)
    
    def _round_to_nearest_strike(self, price: float, interval: int = 50) -> float:
        """
        Round price to nearest strike interval
        
        Args:
            price: Price to round
            interval: Strike interval (50 or 100 for NIFTY)
            
        Returns:
            Rounded strike price
        """
        return round(price / interval) * interval
    
    def get_multiple_recommendations(self, symbol: str, current_spot: float, 
                                   expiry_date: date) -> Dict[str, float]:
        """
        Get multiple strike recommendations using different methods
        
        Returns:
            Dict with different recommendation methods and their strikes
        """
        recommendations = {
            "atm": self.get_recommended_strike(symbol, current_spot, expiry_date, "atm"),
            "volatility_based": self.get_recommended_strike(symbol, current_spot, expiry_date, "volatility_based"),
            "support_resistance": self.get_recommended_strike(symbol, current_spot, expiry_date, "support_resistance"),
            "momentum": self.get_recommended_strike(symbol, current_spot, expiry_date, "momentum")
        }
        
        return recommendations
    
    def get_safestrike_primary(self, symbol: str, current_spot: float, 
                             expiry_date: date) -> float:
        """
        Get primary Safestrike recommendation
        This would be the main recommendation for the breakeven adjustment tool
        
        Returns:
            Primary recommended strike
        """
        # For now, use volatility-based as primary
        # You can enhance this with your proprietary Safestrike algorithm
        return self.get_recommended_strike(symbol, current_spot, expiry_date, "volatility_based")
    
    def validate_safestrike_conditions(self, symbol: str, current_spot: float, 
                                     recommended_strike: float, expiry_date: date) -> Dict[str, any]:
        """
        Validate conditions for Safestrike recommendation
        
        Returns:
            Dict with validation results and confidence metrics
        """
        days_to_expiry = (expiry_date - date.today()).days
        
        # Distance from current spot
        distance_percent = abs(recommended_strike - current_spot) / current_spot * 100
        
        # Basic validation rules
        validations = {
            "is_valid": True,
            "confidence": "medium",
            "warnings": [],
            "distance_from_spot_percent": round(distance_percent, 2),
            "days_to_expiry": days_to_expiry
        }
        
        # Validation rules
        if days_to_expiry < 1:
            validations["warnings"].append("Very close to expiry - high time decay risk")
            validations["confidence"] = "low"
        
        if distance_percent > 10:
            validations["warnings"].append("Strike is far from current spot - consider closer strikes")
            validations["confidence"] = "low"
        
        if distance_percent < 1:
            validations["confidence"] = "high"
        
        return validations
