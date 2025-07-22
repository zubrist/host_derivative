import math
from scipy.stats import norm
import logging

logger = logging.getLogger(__name__)

class BlackScholesService:
    def __init__(self):
        self.MAX_ITERATIONS = 100
        self.PRECISION = 0.000001

    def calculate_option_price(self, S: float, K: float, T: float, r: float, sigma: float, option_type: str = "CE") -> float:
        """
        Calculate Option Price using Black-Scholes Model
        
        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (in years)
            r: Risk-free interest rate
            sigma: Volatility
            option_type: "CE" for Call, "PE" for Put
            
        Returns:
            float: Option premium
        """
        try:
            logger.info(f"BS Inputs - S:{S}, K:{K}, T:{T}, r:{r}, sigma:{sigma}, type:{option_type}")
            
            if T <= 0:
                raise ValueError("Time to expiry must be positive")
            if sigma <= 0:
                raise ValueError("Volatility must be positive")
            if S <= 0 or K <= 0:
                raise ValueError("Stock and strike prices must be positive")
                
            d1 = (math.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            
            logger.info(f"d1: {d1}, d2: {d2}")
            
            if option_type.upper() == "CE":
                # Call option
                option_price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
            elif option_type.upper() == "PE":
                # Put option
                option_price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            else:
                raise ValueError("option_type must be 'CE' or 'PE'")
            
            logger.info(f"Calculated {option_type} price: {option_price}")
            
            return round(option_price, 2)
        
        except Exception as e:
            logger.error(f"Error calculating {option_type} option price: {str(e)}")
            raise

    # Keep backward compatibility
    def calculate_call_option_price(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        return self.calculate_option_price(S, K, T, r, sigma, "CE")

    def calculate_put_option_price(self, S: float, K: float, T: float, r: float, sigma: float) -> float:
        return self.calculate_option_price(S, K, T, r, sigma, "PE")

    def calculate_implied_volatility(self, market_price: float, S: float, K: float, 
                                   T: float, r: float, option_type: str = "CE") -> float:
        """
        Calculate implied volatility using Newton-Raphson method
        """
        try:
            logger.info(f"IV Inputs - market_price:{market_price}, S:{S}, K:{K}, T:{T}, r:{r}, type:{option_type}")
            
            if market_price <= 0:
                raise ValueError("Market price must be positive")
                
            sigma = 0.5  # Initial guess
            
            for i in range(self.MAX_ITERATIONS):
                price = self.calculate_option_price(S, K, T, r, sigma, option_type)
                diff = market_price - price
                
                logger.info(f"Iteration {i}: sigma={sigma}, price={price}, diff={diff}")
                
                if abs(diff) < self.PRECISION:
                    logger.info(f"Converged after {i} iterations")
                    return sigma
                
                # Calculate vega (same for both calls and puts)
                d1 = (math.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
                vega = S * math.sqrt(T) * norm.pdf(d1)
                
                if vega == 0:
                    logger.warning("Vega is zero, cannot continue")
                    break
                    
                # Update volatility
                sigma = sigma + diff/vega
                
                # Ensure volatility stays within reasonable bounds
                if sigma <= 0:
                    sigma = 0.0001
                elif sigma > 5:  # 500% volatility cap
                    logger.warning("Volatility capped at 500%")
                    return 5.0
                    
            logger.warning(f"IV calculation did not converge after {self.MAX_ITERATIONS} iterations")
            return sigma
            
        except Exception as e:
            logger.error(f"Error calculating implied volatility for {option_type}: {str(e)}")
            raise