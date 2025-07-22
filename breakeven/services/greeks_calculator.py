"""
Greeks Calculator Service
Calculates option Greeks (Delta, Gamma, Theta, Vega, Rho) using Black-Scholes model
"""

import math
from datetime import datetime, date
from typing import Dict, Optional
import logging

# Simple implementation to replace scipy.stats.norm
class SimpleNorm:
    @staticmethod
    def cdf(x):
        """Cumulative distribution function for standard normal distribution"""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))
    
    @staticmethod
    def pdf(x):
        """Probability density function for standard normal distribution"""
        return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

norm = SimpleNorm()

logger = logging.getLogger(__name__)

class GreeksCalculator:
    """Calculate option Greeks using Black-Scholes model"""
    
    def __init__(self):
        self.risk_free_rate = 0.065  # Default 6.5%
    
    def calculate_all_greeks(self, S: float, K: float, T: float, r: float, sigma: float, option_type: str = "CE") -> Dict[str, float]:
        """
        Calculate all Greeks for an option
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (in years)
            r: Risk-free interest rate
            sigma: Volatility
            option_type: "CE" for Call, "PE" for Put
            
        Returns:
            Dict containing delta, gamma, theta, vega, rho
        """
        try:
            if T <= 0:
                # Option expired
                return {
                    "delta": 0.0,
                    "gamma": 0.0,
                    "theta": 0.0,
                    "vega": 0.0,
                    "rho": 0.0
                }
            
            # Calculate d1 and d2
            d1 = (math.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            
            # Common calculations
            nd1 = norm.cdf(d1)
            nd2 = norm.cdf(d2)
            pdf_d1 = norm.pdf(d1)
            
            if option_type.upper() == "CE":
                # Call option Greeks
                delta = nd1
                gamma = pdf_d1 / (S * sigma * math.sqrt(T))
                theta = -(S * pdf_d1 * sigma) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * nd2
                vega = S * pdf_d1 * math.sqrt(T)
                rho = K * T * math.exp(-r * T) * nd2
                
            else:  # PE
                # Put option Greeks
                delta = nd1 - 1
                gamma = pdf_d1 / (S * sigma * math.sqrt(T))
                theta = -(S * pdf_d1 * sigma) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm.cdf(-d2)
                vega = S * pdf_d1 * math.sqrt(T)
                rho = -K * T * math.exp(-r * T) * norm.cdf(-d2)
            
            # Convert theta to per-day (divide by 365)
            theta_per_day = theta / 365
            
            # Convert vega to per 1% change (divide by 100)
            vega_per_percent = vega / 100
            
            return {
                "delta": round(delta, 6),
                "gamma": round(gamma, 6),
                "theta": round(theta_per_day, 6),  # Per day
                "vega": round(vega_per_percent, 6),  # Per 1%
                "rho": round(rho, 6)
            }
            
        except Exception as e:
            logger.error(f"Error calculating Greeks: {str(e)}")
            return {
                "delta": 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0
            }
    
    def calculate_portfolio_greeks(self, positions: list) -> Dict[str, float]:
        """
        Calculate portfolio-level Greeks
        
        Args:
            positions: List of position dictionaries with Greeks and quantities
            
        Returns:
            Dict with portfolio Greeks
        """
        portfolio_greeks = {
            "delta": 0.0,
            "gamma": 0.0,
            "theta": 0.0,
            "vega": 0.0,
            "rho": 0.0
        }
        
        for position in positions:
            quantity = position.get("quantity", 0)
            market_lot = position.get("market_lot", 1)
            greeks = position.get("greeks", {})
            
            # Total exposure = quantity * market_lot
            total_exposure = quantity * market_lot
            
            for greek in portfolio_greeks:
                portfolio_greeks[greek] += greeks.get(greek, 0) * total_exposure
        
        return {k: round(v, 6) for k, v in portfolio_greeks.items()}
    
    def calculate_theta_gamma_ratio(self, theta: float, gamma: float) -> float:
        """
        Calculate Theta/Gamma ratio for ranking strategies
        
        Args:
            theta: Theta value
            gamma: Gamma value
            
        Returns:
            Theta/Gamma ratio (handles division by zero)
        """
        if abs(gamma) < 1e-10:  # Avoid division by zero
            return float('inf') if theta > 0 else float('-inf')
        
        return round(theta / gamma, 6)
    
    def get_time_to_expiry_years(self, expiry_date, current_date=None) -> float:
        """
        Calculate time to expiry in years
        
        Args:
            expiry_date: Expiry date (datetime or date)
            current_date: Current date (defaults to today)
            
        Returns:
            Time to expiry in years
        """
        if current_date is None:
            current_date = datetime.now().date()
        
        if isinstance(current_date, datetime):
            current_date = current_date.date()
        if isinstance(expiry_date, datetime):
            expiry_date = expiry_date.date()
        
        days_to_expiry = (expiry_date - current_date).days
        return max(0, days_to_expiry / 365.0)
