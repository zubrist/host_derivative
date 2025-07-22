
## 1. Single-Leg Strategies

### Buy Call
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25550,
      "option_type": "CE",
      "action": "BUY",
      "premium": 103.1,
      "quantity": 75
    }
  ]
}
```

### Sell Call
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25400,
      "option_type": "CE",
      "action": "SELL",
      "premium": 178.85,
      "quantity": 75
    }
  ]
}
```

### Buy Put
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25350,
      "option_type": "PE",
      "action": "BUY",
      "premium": 83.35,
      "quantity": 75
    }
  ]
}
```

### Sell Put
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25200,
      "option_type": "PE",
      "action": "SELL",
      "premium": 100.1,
      "quantity": 75
    }
  ]
}
```

## 2. Two-Leg Strategies

### Bull Call Spread
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25450,
      "option_type": "CE",
      "action": "BUY",
      "premium": 150.5,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25650,
      "option_type": "CE",
      "action": "SELL",
      "premium": 68.1,
      "quantity": 75
    }
  ]
}
```

### Bear Call Spread
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25550,
      "option_type": "CE",
      "action": "SELL",
      "premium": 103.1,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25700,
      "option_type": "CE",
      "action": "BUY",
      "premium": 54.75,
      "quantity": 75
    }
  ]
}
```

### Bull Put Spread
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25400,
      "option_type": "PE",
      "action": "SELL",
      "premium": 101.2,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25350,
      "option_type": "PE",
      "action": "BUY",
      "premium": 83.35,
      "quantity": 75
    }
  ]
}
```

### Bear Put Spread
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25400,
      "option_type": "PE",
      "action": "BUY",
      "premium": 101.2,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25250,
      "option_type": "PE",
      "action": "SELL",
      "premium": 55.6,
      "quantity": 75
    }
  ]
}
```

## 3. Three-Leg Strategies

### Call Ratio Back Spread
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25600,
      "option_type": "CE",
      "action": "SELL",
      "premium": 84.9,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25700,
      "option_type": "CE",
      "action": "BUY",
      "premium": 54.75,
      "quantity": 150
    }
  ]
}
```

### Put Ratio Back Spread
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25500,
      "option_type": "PE",
      "action": "SELL",
      "premium": 147.15,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25400,
      "option_type": "PE",
      "action": "BUY",
      "premium": 101.2,
      "quantity": 150
    }
  ]
}
```

### Bull Butterfly
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25700,
      "option_type": "CE",
      "action": "BUY",
      "premium": 37.35,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25950,
      "option_type": "CE",
      "action": "SELL",
      "premium": 9.4,
      "quantity": 150
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 26200,
      "option_type": "CE",
      "action": "BUY",
      "premium": 2.6,
      "quantity": 75
    }
  ]
}
```

### Bear Butterfly
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25200,
      "option_type": "PE",
      "action": "BUY",
      "premium": 33.75,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 24950,
      "option_type": "PE",
      "action": "SELL",
      "premium": 12.15,
      "quantity": 150
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 24700,
      "option_type": "PE",
      "action": "BUY",
      "premium": 5.3,
      "quantity": 75
    }
  ]
}
```

## 4. Four-Leg Strategies

### Bull Condor
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25650,
      "option_type": "CE",
      "action": "BUY",
      "premium": 68.1,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25900,
      "option_type": "CE",
      "action": "SELL",
      "premium": 21.1,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 26150,
      "option_type": "CE",
      "action": "SELL",
      "premium": 5.5,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 26400,
      "option_type": "CE",
      "action": "BUY",
      "premium": 1.85,
      "quantity": 75
    }
  ]
}
```

### Bear Condor
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25400,
      "option_type": "PE",
      "action": "BUY",
      "premium": 86.3,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25300,
      "option_type": "PE",
      "action": "SELL",
      "premium": 53.95,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25200,
      "option_type": "PE",
      "action": "SELL",
      "premium": 33.75,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25100,
      "option_type": "PE",
      "action": "BUY",
      "premium": 21.9,
      "quantity": 75
    }
  ]
}
```

## 5. Custom Strategy (Mixed Legs)
```json
{
  "legs": [
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25550,
      "option_type": "CE",
      "action": "BUY",
      "premium": 103.1,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25300,
      "option_type": "PE",
      "action": "BUY",
      "premium": 67.45,
      "quantity": 75
    },
    {
      "symbol": "NIFTY",
      "expiry": "10-Jul-2025",
      "strike": 25700,
      "option_type": "CE",
      "action": "SELL",
      "premium": 54.75,
      "quantity": 75
    }
  ]
}
```

## Usage Notes

1. Send these payloads as POST requests to your endpoint: `/api/v1_0/breakeven_profit`
2. The API will automatically identify the strategy based on the legs and return:
   - Strategy name
   - Breakeven point(s)
   - Maximum profit
   - Maximum loss
   - Profit zones
   - Other strategy-specific details

3. For testing multiple strikes or expiries, simply modify the relevant fields in the legs.

4. For different lot sizes, adjust the `quantity` field (default is 75 for NIFTY).

These payloads represent realistic market scenarios and should provide a good foundation for testing your strategy analyzer API.