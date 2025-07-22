import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Tuple, Literal
import ipywidgets as widgets
from IPython.display import display

@dataclass
class OptionPosition:
    """Class to represent an option position"""
    name: str  # Name/identifier for the position
    option_type: Literal["CE", "PE"]  # Call or Put
    action: Literal[1, -1]  # 1 for Buy, -1 for Sell
    strike: float  # Strike price
    premium: float  # Premium paid (if Buy) or received (if Sell)
    color: str = None  # Color for plotting
    
    def payoff(self, spot_price):
        """Calculate the payoff for this option at given spot price"""
        if self.option_type == "CE":  # Call option
            intrinsic = max(0, spot_price - self.strike)
        else:  # Put option
            intrinsic = max(0, self.strike - spot_price)
        
        # Total P&L includes premium effect
        return self.action * intrinsic - self.action * self.premium
    
    def breakeven(self):
        """Calculate breakeven point for this option"""
        if self.option_type == "CE":
            if self.action == 1:  # Long Call
                return self.strike + self.premium
            else:  # Short Call
                return self.strike + self.premium
        else:  # Put
            if self.action == 1:  # Long Put
                return self.strike - self.premium
            else:  # Short Put
                return self.strike - self.premium
    
    def __str__(self):
        action_str = "Buy" if self.action == 1 else "Sell"
        return f"{action_str} {self.option_type} @ {self.strike} (Premium: {self.premium})"


class BreakevenAnalyzer:
    def __init__(self, positions: List[OptionPosition]):
        self.positions = positions
        self.min_strike = min(p.strike for p in positions)
        self.max_strike = max(p.strike for p in positions)
        
        # Automatically assign colors if not provided
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
                 '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', 
                 '#bcbd22', '#17becf']
        
        for i, pos in enumerate(self.positions):
            if pos.color is None:
                pos.color = colors[i % len(colors)]

    def analyze(self, price_range=None, num_points=1000):
        """Analyze P&L across price range"""
        # Set price range if not provided
        if price_range is None:
            padding = max(5000, (self.max_strike - self.min_strike) * 0.2)
            price_range = (max(0, self.min_strike - padding), 
                          self.max_strike + padding)
        
        prices = np.linspace(price_range[0], price_range[1], num_points)
        
        # Calculate P&L for each position and total
        results = pd.DataFrame({'price': prices})
        
        # Individual P&L
        for pos in self.positions:
            results[pos.name] = [pos.payoff(price) for price in prices]
        
        # Total P&L
        results['total'] = results[[pos.name for pos in self.positions]].sum(axis=1)
        
        return results
    
    def find_breakevens(self, results):
        """Find approximate breakeven points from results dataframe"""
        breakevens = {}
        
        # For total P&L
        sign_changes = np.where(np.diff(np.signbit(results['total'])))[0]
        breakeven_points = []
        
        for idx in sign_changes:
            # Linear interpolation to find more precise breakeven
            p1, p2 = results['price'].iloc[idx], results['price'].iloc[idx+1]
            v1, v2 = results['total'].iloc[idx], results['total'].iloc[idx+1]
            
            # Avoid division by zero
            if v1 == v2:
                breakeven = p1
            else:
                # Find where the line crosses zero
                breakeven = p1 - v1 * (p2 - p1) / (v2 - v1)
            
            breakeven_points.append(breakeven)
        
        breakevens['total'] = breakeven_points
        
        # For individual positions
        for pos in self.positions:
            sign_changes = np.where(np.diff(np.signbit(results[pos.name])))[0]
            pos_breakevens = []
            
            for idx in sign_changes:
                p1, p2 = results['price'].iloc[idx], results['price'].iloc[idx+1]
                v1, v2 = results[pos.name].iloc[idx], results[pos.name].iloc[idx+1]
                
                if v1 == v2:
                    breakeven = p1
                else:
                    breakeven = p1 - v1 * (p2 - p1) / (v2 - v1)
                
                pos_breakevens.append(breakeven)
            
            breakevens[pos.name] = pos_breakevens
        
        return breakevens
    
    def visualize(self, results, breakevens):
        """Create a visualization of the P&L curves and breakeven points"""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1]})
        
        # Plot individual position P&L
        for pos in self.positions:
            ax1.plot(results['price'], results[pos.name], 
                    label=f"{pos.name}: {pos}", 
                    color=pos.color, alpha=0.7)
        
        # Plot total P&L with thicker line
        ax1.plot(results['price'], results['total'], 
                label='Total P&L', color='black', linewidth=2.5)
        
        # Zero line and grid
        ax1.axhline(y=0, color='r', linestyle='-', alpha=0.3)
        ax1.grid(True, linestyle='--', alpha=0.6)
        
        # Mark breakeven points for total P&L
        for be in breakevens['total']:
            ax1.axvline(x=be, color='r', linestyle='--', alpha=0.7)
            ax1.text(be, results['total'].max() * 0.9, 
                    f'BE: {be:.2f}', rotation=90, 
                    backgroundcolor='white', alpha=0.7)
        
        # Add strike prices as vertical lines
        for pos in self.positions:
            ax1.axvline(x=pos.strike, color=pos.color, linestyle=':', alpha=0.5)
            ax1.text(pos.strike, results['total'].min() * 0.9, 
                    f'K: {pos.strike}', rotation=90, 
                    color=pos.color, backgroundcolor='white', alpha=0.7)
        
        # Profitability heatmap in bottom subplot
        x = results['price']
        y_positions = np.arange(len(self.positions) + 1)  # +1 for total
        
        # Create the heatmap data
        heatmap_data = np.zeros((len(self.positions) + 1, len(x)))
        
        for i, pos in enumerate(self.positions):
            heatmap_data[i] = np.where(results[pos.name] > 0, 1, -1)
        
        heatmap_data[-1] = np.where(results['total'] > 0, 1, -1)
        
        # Plot the heatmap
        pos_cmap = plt.cm.RdYlGn  # Red for negative, green for positive
        
        im = ax2.imshow(heatmap_data, aspect='auto', cmap=pos_cmap, 
                       extent=[min(x), max(x), -0.5, len(self.positions) + 0.5],
                       vmin=-1, vmax=1)
        
        # Add position labels to y-axis
        position_labels = [pos.name for pos in self.positions] + ['Total']
        ax2.set_yticks(np.arange(len(position_labels)))
        ax2.set_yticklabels(position_labels)
        
        # Styling and labels
        ax1.set_title('Option Positions P&L Analysis', fontsize=16)
        ax1.set_ylabel('P&L', fontsize=12)
        ax1.legend(loc='upper left', bbox_to_anchor=(1.01, 1))
        
        ax2.set_title('Profitability Zones (Green=Profit, Red=Loss)', fontsize=12)
        ax2.set_xlabel('Underlying Price', fontsize=12)
        
        plt.tight_layout()
        plt.show()
        
        return fig


# Interactive version of the BreakevenAnalyzer
class InteractiveBreakevenAnalyzer:
    def __init__(self, positions: List[OptionPosition]):
        self.positions = positions
        self.min_strike = min(p.strike for p in positions)
        self.max_strike = max(p.strike for p in positions)
        
        # Automatically assign colors if not provided
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', 
                 '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', 
                 '#bcbd22', '#17becf']
        
        for i, pos in enumerate(self.positions):
            if pos.color is None:
                pos.color = colors[i % len(colors)]
        
        # Create figure and axis for interactive plot
        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.init_plot()
        
    def init_plot(self):
        """Initialize the plot with static elements"""
        self.ax.set_title('Option Positions P&L Analysis', fontsize=16)
        self.ax.set_ylabel('P&L', fontsize=12)
        self.ax.set_xlabel('Underlying Price', fontsize=12)
        self.ax.grid(True, linestyle='--', alpha=0.6)
        
    def analyze(self, price_range=None, num_points=1000):
        """Analyze P&L across price range"""
        # Set price range if not provided
        if price_range is None:
            padding = max(5000, (self.max_strike - self.min_strike) * 0.2)
            price_range = (max(0, self.min_strike - padding), 
                          self.max_strike + padding)
        
        prices = np.linspace(price_range[0], price_range[1], num_points)
        
        # Calculate P&L for each position and total
        results = pd.DataFrame({'price': prices})
        
        # Individual P&L
        for pos in self.positions:
            results[pos.name] = [pos.payoff(price) for price in prices]
        
        # Total P&L
        results['total'] = results[[pos.name for pos in self.positions]].sum(axis=1)
        
        return results
    
    def find_breakevens(self, results):
        """Find approximate breakeven points from results dataframe"""
        breakevens = {}
        
        # For total P&L
        sign_changes = np.where(np.diff(np.signbit(results['total'])))[0]
        breakeven_points = []
        
        for idx in sign_changes:
            # Linear interpolation to find more precise breakeven
            p1, p2 = results['price'].iloc[idx], results['price'].iloc[idx+1]
            v1, v2 = results['total'].iloc[idx], results['total'].iloc[idx+1]
            
            # Avoid division by zero
            if v1 == v2:
                breakeven = p1
            else:
                # Find where the line crosses zero
                breakeven = p1 - v1 * (p2 - p1) / (v2 - v1)
            
            breakeven_points.append(breakeven)
        
        breakevens['total'] = breakeven_points
        
        # For individual positions
        for pos in self.positions:
            sign_changes = np.where(np.diff(np.signbit(results[pos.name])))[0]
            pos_breakevens = []
            
            for idx in sign_changes:
                p1, p2 = results['price'].iloc[idx], results['price'].iloc[idx+1]
                v1, v2 = results[pos.name].iloc[idx], results[pos.name].iloc[idx+1]
                
                if v1 == v2:
                    breakeven = p1
                else:
                    breakeven = p1 - v1 * (p2 - p1) / (v2 - v1)
                
                pos_breakevens.append(breakeven)
            
            breakevens[pos.name] = pos_breakevens
        
        return breakevens
    
    def visualize_interactive(self, price_lower=None, price_upper=None, positions_to_show=None):
        """Create an interactive visualization of the P&L curves and breakeven points"""
        self.ax.clear()
        self.init_plot()
        
        # Set default price range if not provided
        if price_lower is None or price_upper is None:
            padding = max(5000, (self.max_strike - self.min_strike) * 0.2)
            price_lower = max(0, self.min_strike - padding)
            price_upper = self.max_strike + padding
        
        # Default to showing all positions if none specified
        if positions_to_show is None:
            positions_to_show = [pos.name for pos in self.positions] + ['total']
        
        price_range = (price_lower, price_upper)
        results = self.analyze(price_range=price_range)
        breakevens = self.find_breakevens(results)
        
        # Plot individual position P&L for selected positions
        for pos in self.positions:
            if pos.name in positions_to_show:
                self.ax.plot(results['price'], results[pos.name], 
                        label=f"{pos.name}: {pos}", 
                        color=pos.color, alpha=0.7)
        
        # Plot total P&L if selected
        if 'total' in positions_to_show:
            self.ax.plot(results['price'], results['total'], 
                    label='Total P&L', color='black', linewidth=2.5)
            
            # Mark breakeven points for total P&L
            for be in breakevens['total']:
                self.ax.axvline(x=be, color='r', linestyle='--', alpha=0.7)
                self.ax.text(be, results['total'].max() * 0.9, 
                        f'BE: {be:.2f}', rotation=90, 
                        backgroundcolor='white', alpha=0.7)
        
        # Zero line
        self.ax.axhline(y=0, color='r', linestyle='-', alpha=0.3)
        
        # Add strike prices as vertical lines
        for pos in self.positions:
            if pos.name in positions_to_show:
                self.ax.axvline(x=pos.strike, color=pos.color, linestyle=':', alpha=0.5)
                self.ax.text(pos.strike, min(results[[p.name for p in self.positions]].min().min() * 0.9, -100), 
                        f'K: {pos.strike}', rotation=90, 
                        color=pos.color, backgroundcolor='white', alpha=0.7)
        
        self.ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1))
        self.fig.tight_layout()
        
        # Print breakeven points
        print("\nStrategy Breakeven Points:")
        print(f"Total: {[f'{be:.2f}' for be in breakevens['total']]}")
        
        print("\nIndividual Position Breakeven Points:")
        for pos in self.positions:
            if pos.name in positions_to_show:
                print(f"{pos.name}: {[f'{be:.2f}' for be in breakevens[pos.name]]}")
        
        return self.fig

def create_interactive_analysis(positions):
    """Create an interactive analysis with ipywidgets"""
    analyzer = InteractiveBreakevenAnalyzer(positions)
    
    # Get min and max strike values to set slider ranges
    min_strike = min(p.strike for p in positions)
    max_strike = max(p.strike for p in positions)
    padding = max(5000, (max_strike - min_strike) * 0.2)
    
    # Create price range sliders
    price_lower = widgets.FloatSlider(
        value=max(0, min_strike - padding),
        min=max(0, min_strike - 2*padding),
        max=max_strike,
        step=100,
        description='Min Price:',
        continuous_update=False
    )
    
    price_upper = widgets.FloatSlider(
        value=max_strike + padding,
        min=min_strike,
        max=max_strike + 2*padding,
        step=100,
        description='Max Price:',
        continuous_update=False
    )
    
    # Create checkboxes for positions to show
    position_checkboxes = []
    for pos in positions:
        position_checkboxes.append(
            widgets.Checkbox(
                value=True,
                description=pos.name,
                disabled=False
            )
        )
    
    # Add total P&L checkbox
    total_checkbox = widgets.Checkbox(
        value=True,
        description='Total P&L',
        disabled=False
    )
    
    position_checkboxes.append(total_checkbox)
    
    # Create horizontal box for position checkboxes
    positions_box = widgets.HBox(position_checkboxes)
    
    # Update function for interactive widgets
    def update(lower, upper, *checkboxes):
        # Get selected positions
        selected_positions = []
        for i, checked in enumerate(checkboxes):
            if checked:
                if i < len(positions):
                    selected_positions.append(positions[i].name)
                else:
                    selected_positions.append('total')
        
        # Update visualization
        analyzer.visualize_interactive(lower, upper, selected_positions)
    
    # Create interactive widget
    interactive_plot = widgets.interactive(
        update,
        lower=price_lower,
        upper=price_upper,
        *position_checkboxes
    )
    
    # Display widgets
    display(widgets.VBox([
        widgets.HBox([price_lower, price_upper]),
        widgets.Label('Select positions to display:'),
        positions_box,
        interactive_plot
    ]))

# Example usage
if __name__ == "__main__":
    positions = [
        OptionPosition("CE1", "CE", -1, 23000, 120, "#FF5733"),  # Sell Call 
        OptionPosition("CE2", "CE", -1, 24000, 80),   # Sell Call
        OptionPosition("CE3", "CE", -1, 25000, 50),   # Sell Call
        OptionPosition("CE4", "CE", -1, 26000, 30),   # Sell Call
        OptionPosition("PE1", "PE", -1, 22000, 100, "#33A8FF"),  # Sell Put
        OptionPosition("PE2", "PE", -1, 21000, 70),   # Sell Put
        OptionPosition("PE3", "PE", -1, 20000, 50),   # Sell Put
        OptionPosition("PE4", "PE", 1, 19000, 30),    # Buy Put
    ]
    
    # Static analysis
    analyzer = BreakevenAnalyzer(positions)
    results = analyzer.analyze()
    breakevens = analyzer.find_breakevens(results)
    analyzer.visualize(results, breakevens)
    
    # Interactive analysis
    create_interactive_analysis(positions)