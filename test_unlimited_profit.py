#!/usr/bin/env python3
"""
Simple test script to verify the unlimited profit detection logic.
"""

# Mock the OptionLeg class for testing
class OptionLeg:
    def __init__(self, symbol, expiry, strike, option_type, action, quantity, premium=None):
        self.symbol = symbol
        self.expiry = expiry
        self.strike = strike
        self.option_type = option_type
        self.action = action
        self.quantity = quantity
        self.premium = premium

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

# Test cases
if __name__ == "__main__":
    # Test case 1: Buy Call (should have unlimited profit)
    print("Test Case 1: Buy Call")
    leg1 = OptionLeg("NIFTY", "10-Jul-2025", 25600, "CE", "BUY", 75, 24.45)
    legs = [leg1]
    
    unlimited_profit = check_unlimited_profit_potential(legs)
    unlimited_loss = check_unlimited_loss_potential(legs)
    
    print(f"Unlimited Profit: {unlimited_profit}")  # Should be True
    print(f"Unlimited Loss: {unlimited_loss}")     # Should be False
    print()
    
    # Test case 2: Sell Call (should have unlimited loss)
    print("Test Case 2: Sell Call")
    leg2 = OptionLeg("NIFTY", "10-Jul-2025", 25600, "CE", "SELL", 75, 24.45)
    legs = [leg2]
    
    unlimited_profit = check_unlimited_profit_potential(legs)
    unlimited_loss = check_unlimited_loss_potential(legs)
    
    print(f"Unlimited Profit: {unlimited_profit}")  # Should be False
    print(f"Unlimited Loss: {unlimited_loss}")     # Should be True
    print()
    
    # Test case 3: Bull Call Spread (should have limited profit and loss)
    print("Test Case 3: Bull Call Spread")
    leg3a = OptionLeg("NIFTY", "10-Jul-2025", 25600, "CE", "BUY", 75, 24.45)
    leg3b = OptionLeg("NIFTY", "10-Jul-2025", 25700, "CE", "SELL", 75, 15.0)
    legs = [leg3a, leg3b]
    
    unlimited_profit = check_unlimited_profit_potential(legs)
    unlimited_loss = check_unlimited_loss_potential(legs)
    
    print(f"Unlimited Profit: {unlimited_profit}")  # Should be False
    print(f"Unlimited Loss: {unlimited_loss}")     # Should be False
    print()
    
    print("All tests completed!")
