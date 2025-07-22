"""
Safestrike Breakeven Adjustment Tool
Calculates additional positions needed to shift effective breakeven to recommended strike
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
import itertools
import logging
from dataclasses import dataclass

from .greeks_calculator import GreeksCalculator
from .safestrike_recommendation import SafestrikeRecommendation
from ..routers.break_even import find_breakeven_points, OptionLeg

logger = logging.getLogger(__name__)

@dataclass
class AdditionalPosition:
    """Represents an additional position to be added"""
    symbol: str
    strike: float
    option_type: str  # "CE" or "PE"
    action: str  # "BUY" or "SELL"
    quantity: int
    premium: float
    market_lot: int
    greeks: Dict[str, float]

@dataclass
class BreakevenAdjustmentResult:
    """Result of breakeven adjustment calculation"""
    original_breakeven: List[float]
    target_breakeven: float
    recommended_positions: List[AdditionalPosition]
    new_breakeven: List[float]
    theta_gamma_ratio: float
    total_additional_premium: float
    portfolio_greeks_before: Dict[str, float]
    portfolio_greeks_after: Dict[str, float]
    confidence_score: float
    warnings: List[str]

class SafestrikeBreakevenAdjuster:
    """
    Main tool for calculating breakeven adjustments using Safestrike recommendations
    """
    
    def __init__(self, greeks_calculator: GreeksCalculator = None, 
                 safestrike_service: SafestrikeRecommendation = None):
        self.greeks_calculator = greeks_calculator or GreeksCalculator()
        self.safestrike_service = safestrike_service or SafestrikeRecommendation()
        
        # Configuration for position enumeration
        self.max_additional_legs = 3  # Maximum additional legs to consider
        self.strike_range_percent = 0.1  # ±10% from current spot for strike enumeration
        self.max_combinations = 100  # Limit combinations for performance
        
    def calculate_breakeven_adjustment(self, 
                                     current_positions: List[Dict],
                                     symbol: str,
                                     current_spot: float,
                                     expiry_date: date,
                                     target_breakeven: Optional[float] = None) -> List[BreakevenAdjustmentResult]:
        """
        Calculate additional positions needed to shift breakeven to target
        
        Args:
            current_positions: List of current open positions
            symbol: Underlying symbol
            current_spot: Current spot price
            expiry_date: Target expiry date
            target_breakeven: Target breakeven (if None, use Safestrike recommendation)
            
        Returns:
            List of top adjustment results ranked by Theta/Gamma ratio
        """
        try:
            # Step 1: Get target breakeven from Safestrike if not provided
            if target_breakeven is None:
                target_breakeven = self.safestrike_service.get_safestrike_primary(
                    symbol, current_spot, expiry_date
                )
            
            # Step 2: Calculate current portfolio breakeven and Greeks
            current_legs = self._convert_positions_to_legs(current_positions)
            current_breakeven = find_breakeven_points(current_legs)
            current_portfolio_greeks = self._calculate_portfolio_greeks(current_positions, current_spot, expiry_date)
            
            logger.info(f"Current breakeven: {current_breakeven}, Target: {target_breakeven}")
            
            # Step 3: Generate possible additional positions
            possible_positions = self._generate_possible_positions(
                symbol, current_spot, expiry_date, target_breakeven
            )
            
            # Step 4: Enumerate combinations of additional positions
            position_combinations = self._enumerate_position_combinations(possible_positions)
            
            # Step 5: Evaluate each combination
            results = []
            for combination in position_combinations[:self.max_combinations]:
                result = self._evaluate_combination(
                    current_legs, current_portfolio_greeks, combination, 
                    target_breakeven, current_spot, expiry_date
                )
                if result:
                    results.append(result)
            
            # Step 6: Rank by Theta/Gamma ratio and return top 5
            results.sort(key=lambda x: x.theta_gamma_ratio, reverse=True)
            return results[:5]
            
        except Exception as e:
            logger.error(f"Error in breakeven adjustment calculation: {str(e)}")
            return []
    
    def _convert_positions_to_legs(self, positions: List[Dict]) -> List[OptionLeg]:
        """Convert position format to OptionLeg format"""
        legs = []
        for pos in positions:
            action = "BUY" if pos.get("quantity", 0) > 0 else "SELL"
            legs.append(OptionLeg(
                symbol=pos.get("symbol", ""),
                expiry=pos.get("expiry", ""),
                strike=float(pos.get("strike", 0)),
                option_type=pos.get("option_type", "CE"),
                action=action,
                quantity=abs(pos.get("quantity", 0)),
                premium=float(pos.get("premium", 0))
            ))
        return legs
    
    def _calculate_portfolio_greeks(self, positions: List[Dict], spot: float, expiry_date: date) -> Dict[str, float]:
        """Calculate current portfolio Greeks"""
        portfolio_positions = []
        
        for pos in positions:
            time_to_expiry = self.greeks_calculator.get_time_to_expiry_years(expiry_date)
            greeks = self.greeks_calculator.calculate_all_greeks(
                S=spot,
                K=float(pos.get("strike", 0)),
                T=time_to_expiry,
                r=0.065,  # Risk-free rate
                sigma=0.15,  # Default volatility - replace with actual IV
                option_type=pos.get("option_type", "CE")
            )
            
            portfolio_positions.append({
                "quantity": pos.get("quantity", 0),
                "market_lot": pos.get("market_lot", 75),
                "greeks": greeks
            })
        
        return self.greeks_calculator.calculate_portfolio_greeks(portfolio_positions)
    
    def _generate_possible_positions(self, symbol: str, spot: float, expiry_date: date, target_strike: float) -> List[AdditionalPosition]:
        """Generate possible additional positions to consider"""
        positions = []
        
        # Calculate strike range
        strike_range = spot * self.strike_range_percent
        min_strike = max(spot - strike_range, 0)
        max_strike = spot + strike_range
        
        # Generate strikes in 50-point intervals for NIFTY
        strike_interval = 50 if symbol == "NIFTY" else 100
        strikes = []
        
        current_strike = int(min_strike / strike_interval) * strike_interval
        while current_strike <= max_strike:
            strikes.append(current_strike)
            current_strike += strike_interval
        
        # Add target strike if not in list
        target_rounded = int(target_strike / strike_interval) * strike_interval
        if target_rounded not in strikes:
            strikes.append(target_rounded)
        
        # Generate positions for each strike
        for strike in strikes:
            for option_type in ["CE", "PE"]:
                for action in ["BUY", "SELL"]:
                    for quantity in [1, 2, 3]:  # Different lot sizes
                        
                        # Calculate theoretical premium and Greeks
                        time_to_expiry = self.greeks_calculator.get_time_to_expiry_years(expiry_date)
                        greeks = self.greeks_calculator.calculate_all_greeks(
                            S=spot, K=strike, T=time_to_expiry, r=0.065, sigma=0.15, option_type=option_type
                        )
                        
                        # Simplified premium calculation (replace with actual market data)
                        premium = self._estimate_premium(spot, strike, time_to_expiry, option_type)
                        
                        positions.append(AdditionalPosition(
                            symbol=symbol,
                            strike=strike,
                            option_type=option_type,
                            action=action,
                            quantity=quantity,
                            premium=premium,
                            market_lot=75,  # NIFTY lot size
                            greeks=greeks
                        ))
        
        return positions
    
    def _estimate_premium(self, spot: float, strike: float, time_to_expiry: float, option_type: str) -> float:
        """Estimate option premium (simplified - replace with actual market data)"""
        intrinsic = 0
        if option_type == "CE" and spot > strike:
            intrinsic = spot - strike
        elif option_type == "PE" and strike > spot:
            intrinsic = strike - spot
        
        # Simple time value estimation
        time_value = max(0, abs(spot - strike) * 0.1 * time_to_expiry)
        
        return max(intrinsic + time_value, 0.1)  # Minimum premium of 0.1
    
    def _enumerate_position_combinations(self, positions: List[AdditionalPosition]) -> List[List[AdditionalPosition]]:
        """Generate combinations of additional positions"""
        combinations = []
        
        # Single positions
        for pos in positions:
            combinations.append([pos])
        
        # Two-position combinations
        for pos1, pos2 in itertools.combinations(positions, 2):
            # Avoid redundant combinations
            if self._is_valid_combination([pos1, pos2]):
                combinations.append([pos1, pos2])
        
        # Three-position combinations (limited)
        limited_positions = positions[:20]  # Limit for performance
        for pos1, pos2, pos3 in itertools.combinations(limited_positions, 3):
            if self._is_valid_combination([pos1, pos2, pos3]):
                combinations.append([pos1, pos2, pos3])
        
        return combinations
    
    def _is_valid_combination(self, combination: List[AdditionalPosition]) -> bool:
        """Check if combination is valid (basic filters)"""
        # Avoid having too many positions at same strike
        strikes = [pos.strike for pos in combination]
        if len(strikes) != len(set(strikes)):
            return False
        
        # Other validation rules can be added here
        return True
    
    def _evaluate_combination(self, 
                            current_legs: List[OptionLeg],
                            current_greeks: Dict[str, float],
                            additional_positions: List[AdditionalPosition],
                            target_breakeven: float,
                            spot: float,
                            expiry_date: date) -> Optional[BreakevenAdjustmentResult]:
        """Evaluate a combination of additional positions"""
        try:
            # Convert additional positions to legs
            additional_legs = []
            for pos in additional_positions:
                additional_legs.append(OptionLeg(
                    symbol=pos.symbol,
                    expiry=expiry_date.strftime("%Y-%m-%d"),
                    strike=pos.strike,
                    option_type=pos.option_type,
                    action=pos.action,
                    quantity=pos.quantity,
                    premium=pos.premium
                ))
            
            # Combine with current legs
            combined_legs = current_legs + additional_legs
            
            # Calculate new breakeven
            new_breakeven = find_breakeven_points(combined_legs)
            
            # Check if we're close to target breakeven
            if not new_breakeven or not any(abs(be - target_breakeven) < 100 for be in new_breakeven):
                return None
            
            # Calculate new portfolio Greeks
            additional_portfolio_positions = []
            for pos in additional_positions:
                sign = 1 if pos.action == "BUY" else -1
                additional_portfolio_positions.append({
                    "quantity": pos.quantity * sign,
                    "market_lot": pos.market_lot,
                    "greeks": pos.greeks
                })
            
            new_portfolio_greeks = self.greeks_calculator.calculate_portfolio_greeks(additional_portfolio_positions)
            
            # Combine with current Greeks
            combined_greeks = {}
            for greek in current_greeks:
                combined_greeks[greek] = current_greeks[greek] + new_portfolio_greeks[greek]
            
            # Calculate Theta/Gamma ratio
            theta_gamma_ratio = self.greeks_calculator.calculate_theta_gamma_ratio(
                combined_greeks["theta"], combined_greeks["gamma"]
            )
            
            # Calculate total additional premium
            total_premium = sum(pos.premium * pos.quantity * pos.market_lot * 
                              (1 if pos.action == "BUY" else -1) for pos in additional_positions)
            
            # Calculate confidence score (simplified)
            confidence = self._calculate_confidence_score(new_breakeven, target_breakeven, combined_greeks)
            
            return BreakevenAdjustmentResult(
                original_breakeven=find_breakeven_points(current_legs),
                target_breakeven=target_breakeven,
                recommended_positions=additional_positions,
                new_breakeven=new_breakeven,
                theta_gamma_ratio=theta_gamma_ratio,
                total_additional_premium=total_premium,
                portfolio_greeks_before=current_greeks,
                portfolio_greeks_after=combined_greeks,
                confidence_score=confidence,
                warnings=self._generate_warnings(additional_positions, combined_greeks)
            )
            
        except Exception as e:
            logger.error(f"Error evaluating combination: {str(e)}")
            return None
    
    def _calculate_confidence_score(self, new_breakeven: List[float], target: float, greeks: Dict[str, float]) -> float:
        """Calculate confidence score for the adjustment"""
        # Distance from target
        closest_breakeven = min(new_breakeven, key=lambda x: abs(x - target))
        distance_score = max(0, 100 - abs(closest_breakeven - target))
        
        # Greeks stability (prefer lower gamma for more stable positions)
        gamma_score = max(0, 100 - abs(greeks.get("gamma", 0)) * 1000)
        
        # Simple average
        return (distance_score + gamma_score) / 2
    
    def _generate_warnings(self, positions: List[AdditionalPosition], greeks: Dict[str, float]) -> List[str]:
        """Generate warnings for the position combination"""
        warnings = []
        
        if abs(greeks.get("gamma", 0)) > 0.1:
            warnings.append("High gamma - position may be sensitive to spot moves")
        
        if greeks.get("theta", 0) < -100:
            warnings.append("High negative theta - significant time decay")
        
        if len(positions) > 2:
            warnings.append("Complex strategy with multiple legs - monitor carefully")
        
        return warnings
