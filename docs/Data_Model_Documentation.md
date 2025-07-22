# Data Model Documentation

## Overview
This document describes the data structures used in the NSE module of the application, including the models for NIFTY, BANKNIFTY, and FINNIFTY.

## Models

### 1. NIFTY
- **Table Name**: `NIFTY`
- **Description**: Represents the NIFTY options data.

#### Attributes
| Attribute         | Type    | Description                                      |
|-------------------|---------|--------------------------------------------------|
| `id`              | Integer | Auto-incrementing ID (Primary Key).             |
| `symbol`          | String  | Symbol name (e.g., "NIFTY").                    |
| `date`            | Date    | Date of the record.                             |
| `expiry`          | String  | Expiry date of the option.                      |
| `option_type`     | String  | Type of option (e.g., "CE", "PE").             |
| `strike_price`    | Integer | Strike price of the option.                     |
| `open`            | Float   | Opening price of the option.                    |
| `high`            | Float   | Highest price during the trading session.       |
| `low`             | Float   | Lowest price during the trading session.        |
| `close`           | Float   | Closing price of the option.                     |
| `ltp`             | Float   | Last traded price.                              |
| `change_in_oi`    | Float   | Change in open interest.                        |
| `closing_price`   | Float   | Closing price of the option.                    |
| `last_traded_price`| Float  | Last traded price of the option.                |
| `market_lot`      | Integer | Market lot size for the option.                 |
| `open_int`        | Float   | Open interest for the option.                   |
| `prev_cls`        | Float   | Previous closing price.                         |
| `settle_price`    | Float   | Settlement price of the option.                 |
| `tot_traded_qty`  | Float   | Total traded quantity.                          |
| `tot_traded_val`  | Float   | Total traded value.                             |
| `trade_high_price`| Float   | Highest trade price during the session.        |
| `trade_low_price` | Float   | Lowest trade price during the session.         |
| `underlying_value`| Float   | Underlying asset value.                         |

### 2. BANKNIFTY
- **Table Name**: `BANKNIFTY`
- **Description**: Represents the BANKNIFTY options data.

#### Attributes
| Attribute         | Type    | Description                                      |
|-------------------|---------|--------------------------------------------------|
| `id`              | Integer | Auto-incrementing ID (Primary Key).             |
| `symbol`          | String  | Symbol name (e.g., "BANKNIFTY").                |
| `date`            | Date    | Date of the record.                             |
| `expiry`          | String  | Expiry date of the option.                      |
| `option_type`     | String  | Type of option (e.g., "CE", "PE").             |
| `strike_price`    | Integer | Strike price of the option.                     |
| `open`            | Float   | Opening price of the option.                    |
| `high`            | Float   | Highest price during the trading session.       |
| `low`             | Float   | Lowest price during the trading session.        |
| `close`           | Float   | Closing price of the option.                     |
| `ltp`             | Float   | Last traded price.                              |
| `change_in_oi`    | Float   | Change in open interest.                        |
| `closing_price`   | Float   | Closing price of the option.                    |
| `last_traded_price`| Float  | Last traded price of the option.                |
| `market_lot`      | Integer | Market lot size for the option.                 |
| `open_int`        | Float   | Open interest for the option.                   |
| `prev_cls`        | Float   | Previous closing price.                         |
| `settle_price`    | Float   | Settlement price of the option.                 |
| `tot_traded_qty`  | Float   | Total traded quantity.                          |
| `tot_traded_val`  | Float   | Total traded value.                             |
| `trade_high_price`| Float   | Highest trade price during the session.        |
| `trade_low_price` | Float   | Lowest trade price during the session.         |
| `underlying_value`| Float   | Underlying asset value.                         |

### 3. FINNIFTY
- **Table Name**: `FINNIFTY`
- **Description**: Represents the FINNIFTY options data.

#### Attributes
| Attribute         | Type    | Description                                      |
|-------------------|---------|--------------------------------------------------|
| `id`              | Integer | Auto-incrementing ID (Primary Key).             |
| `symbol`          | String  | Symbol name (e.g., "FINNIFTY").                 |
| `date`            | Date    | Date of the record.                             |
| `expiry`          | String  | Expiry date of the option.                      |
| `option_type`     | String  | Type of option (e.g., "CE", "PE").             |
| `strike_price`    | Integer | Strike price of the option.                     |
| `open`            | Float   | Opening price of the option.                    |
| `high`            | Float   | Highest price during the trading session.       |
| `low`             | Float   | Lowest price during the trading session.        |
| `close`           | Float   | Closing price of the option.                     |
| `ltp`             | Float   | Last traded price.                              |
| `change_in_oi`    | Float   | Change in open interest.                        |
| `closing_price`   | Float   | Closing price of the option.                    |
| `last_traded_price`| Float  | Last traded price of the option.                |
| `market_lot`      | Integer | Market lot size for the option.                 |
| `open_int`        | Float   | Open interest for the option.                   |
| `prev_cls`        | Float   | Previous closing price.                         |
| `settle_price`    | Float   | Settlement price of the option.                 |
| `tot_traded_qty`  | Float   | Total traded quantity.                          |
| `tot_traded_val`  | Float   | Total traded value.                             |
| `trade_high_price`| Float   | Highest trade price during the session.        |
| `trade_low_price` | Float   | Lowest trade price during the session.         |
| `underlying_value`| Float   | Underlying asset value.                         |

## Pydantic Models
- **NIFTY_Pydantic**: Pydantic model for the NIFTY data.
- **BANKNIFTY_Pydantic**: Pydantic model for the BANKNIFTY data.
- **FINNIFTY_Pydantic**: Pydantic model for the FINNIFTY data.

These models are used for data validation and serialization in API requests and responses.
