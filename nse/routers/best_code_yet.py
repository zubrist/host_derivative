'''
from fastapi import APIRouter, Header, Request, Response, HTTPException, status
from datetime import datetime, timedelta, date
from collections import defaultdict, deque
# Assuming NIFTY model is for fetching prices, if not, adjust accordingly
# from db.models.nse import NIFTY
# from db.models.users import UserTransactions # Not directly used if using execute_native_query
from services.utils import execute_native_query
import logging

# Configure Logging
logging.basicConfig(level=logging.DEBUG) # Keep this for root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # Explicitly set level for this specific logger

# Strategy Simulation Router
router = APIRouter()

async def get_closing_price(
    symbol: str,
    target_date: date,
    expiry_date: date,
    option_type: str,
    strike_price: float
):
    """
    Helper function to fetch the closing price for a given contract on a specific date.
    Adjust table name and column names as per your database schema.
    """
    table_name = symbol.lower()
    # Ensure date formats match DB query requirements
    # The original code used FH_TIMESTAMP with %d-%b-%Y and FH_EXPIRY_DT with %d-%b-%Y
    # Strike price was formatted as f"{strike_price}.00"
    try:
        res = await execute_native_query(
            f"""
            SELECT FH_CLOSING_PRICE 
            FROM {table_name} 
            WHERE FH_TIMESTAMP = %s
            AND FH_EXPIRY_DT = %s
            AND FH_OPTION_TYPE = %s
            AND FH_STRIKE_PRICE = %s
            """,
            [
                target_date.strftime("%d-%b-%Y"),
                expiry_date.strftime("%d-%b-%Y"),
                option_type,
                f"{strike_price:.2f}" # Ensure strike price is formatted correctly
            ]
        )
        if res and res[0]["FH_CLOSING_PRICE"] is not None:
            return float(res[0]["FH_CLOSING_PRICE"])
        else:
            logger.warning(f"No closing price for {symbol} {option_type} {strike_price} Exp:{expiry_date.strftime('%d-%b-%Y')} on {target_date.strftime('%d-%b-%Y')}")
            return None
    except Exception as e:
        logger.error(f"Error fetching closing price for {symbol} {target_date}: {e}")
        return None

@router.get("/api/v1_0/strategy/simulation", status_code=status.HTTP_200_OK)
async def strategy_simulation(
    request: Request,
    response: Response,
    request_user_id: str = Header(None)  # User ID from request header
):
    try:
        positions_raw = await execute_native_query(
            """
            SELECT * FROM user_transactions 
            WHERE user_id = %s AND status='active' 
            ORDER BY trade_date, transaction_time
            """, # Assuming transaction_time exists for intra-day ordering
            [request_user_id]
        )
        
        if not positions_raw:
            return {"status": "success", "message": "No active positions", "data": []}

        # Normalize data and prepare for processing
        positions = []
        all_trade_dates = set()
        all_expiry_dates = set()

        for txn_raw in positions_raw:
            try:
                trade_dt = txn_raw["trade_date"]
                expiry_dt = txn_raw["expiry_date"]

                current_trade_date = trade_dt.date() if isinstance(trade_dt, datetime) else trade_dt
                current_expiry_date = expiry_dt.date() if isinstance(expiry_dt, datetime) else expiry_dt
                
                positions.append({
                    "symbol": txn_raw["symbol"].strip().upper(),
                    "option_type": txn_raw["option_type"].strip().upper(),
                    "strike_price": int(float(txn_raw["strike_price"])),
                    "expiry_date": current_expiry_date,
                    "trade_date": current_trade_date,
                    "lots": int(txn_raw["lots"]), # Can be +ve for BUY, -ve for SELL
                    "entry_price": float(txn_raw["entry_price"]),
                    "market_lot": int(txn_raw["market_lot"]),
                    # "transaction_time": txn_raw.get("transaction_time") # Keep if needed for logging/debugging
                })
                all_trade_dates.add(current_trade_date)
                all_expiry_dates.add(current_expiry_date)
            except Exception as e:
                logger.error(f"Error processing transaction: {txn_raw}. Error: {e}")
                # Decide if to skip this transaction or raise error
                continue
        
        if not positions: # If all raw positions failed processing
             return {"status": "success", "message": "No processable active positions", "data": []}


        earliest_processing_date = min(all_trade_dates) if all_trade_dates else date.today()
        latest_processing_date = max(all_expiry_dates) if all_expiry_dates else date.today()

        queues = defaultdict(deque) # Stores entry_price for long positions
        combo_market_lots = {}      # Stores market_lot_size for each combo

        unrealised_map = defaultdict(lambda: defaultdict(lambda: {"pnl": 0.0, "lots": 0}))
        realised_map = defaultdict(lambda: defaultdict(lambda: {"pnl": 0.0, "lots": 0}))
        
        current_calc_date = earliest_processing_date
        position_idx = 0

        logger.info(f"Starting PnL simulation from {earliest_processing_date} to {latest_processing_date} for user {request_user_id}")

        while current_calc_date <= latest_processing_date or position_idx < len(positions):
            
            # Determine if we are processing a transaction day or a gap day
            next_txn_date = positions[position_idx]["trade_date"] if position_idx < len(positions) else None

            # --- Gap Filling Logic ---
            # If current_calc_date is before the next transaction, or if all transactions are processed
            # and current_calc_date is still before or on latest_processing_date
            is_gap_fill_day = not next_txn_date or current_calc_date < next_txn_date
            if position_idx >= len(positions) and current_calc_date > latest_processing_date: # All txns processed and past last expiry
                break


            if is_gap_fill_day:
                date_str = current_calc_date.strftime("%d-%b-%Y")
                logger.debug(f"GAP FILL Day: {date_str}")
                for combo, q in queues.items():
                    symbol, opt_type, strike, expiry = combo
                    if not q or current_calc_date > expiry: # Skip if queue empty or contract expired
                        if q and current_calc_date > expiry and unrealised_map[date_str][combo]["lots"] > 0 : # Expired, clear lots
                             unrealised_map[date_str][combo]["pnl"] = 0 # PNL becomes 0 on expiry if not closed
                             unrealised_map[date_str][combo]["lots"] = 0
                        continue

                    market_lot_size = combo_market_lots.get(combo)
                    if market_lot_size is None:
                        logger.warning(f"Market lot size not found for {combo} on {date_str}. Skipping unrealised PnL.")
                        continue
                    
                    closing_price = await get_closing_price(symbol, current_calc_date, expiry, opt_type, strike)
                    if closing_price is not None:
                        unp = sum((closing_price - entry_p) * market_lot_size for entry_p in q)
                        avg_entry_price = sum(q) / len(q) if q else 0
                        unp = sum((closing_price - entry_p) * market_lot_size for entry_p in q)
                        unrealised_map[date_str][combo] = {
                            "pnl": unp,
                            "lots": len(q),
                            "closing_price": closing_price,
                            "avg_entry_price_in_queue": avg_entry_price,
                            "market_lot": market_lot_size
                        }
                        logger.debug(f"    GAP_UNR_PnL_CALC: Combo: {combo}, Date: {date_str}")
                        logger.debug(f"      Queue: {list(q)}")
                        logger.debug(f"      ClosingPx: {closing_price}, MarketLot: {market_lot_size}, AvgEntryPx: {avg_entry_price:.2f}")
                        pnl_contributions = [(closing_price - entry_p) * market_lot_size for entry_p in q]
                        logger.debug(f"      PnL Contributions: {pnl_contributions}")
                        logger.debug(f"      Total Unrealised PnL: {unp:.2f}, Lots: {len(q)}")
                    # If closing_price is None, no entry is made for this combo on this date.
                
                if current_calc_date >= latest_processing_date and position_idx >= len(positions): # Ensure loop terminates
                    break
                current_calc_date += timedelta(days=1)
                continue # Move to next day for gap fill or transaction processing

            # --- Transaction Processing Logic ---
            # This part executes if current_calc_date == next_txn_date
            current_calc_date = next_txn_date # Align current_calc_date with transaction date
            date_str = current_calc_date.strftime("%d-%b-%Y")
            logger.debug(f"TRANSACTION Day: {date_str}")

            # Store lot counts at the start of the transaction day for comparison later
            lots_at_start_of_transaction_day = {c: len(q_item) for c, q_item in queues.items()}
            # Track which combos had transactions today
            combos_transacted_today = set()

            txns_on_this_day = []
            while position_idx < len(positions) and positions[position_idx]["trade_date"] == current_calc_date:
                txns_on_this_day.append(positions[position_idx])
                position_idx += 1
            
            for txn in txns_on_this_day:
                contract_combo = (
                    txn["symbol"],
                    txn["option_type"],
                    txn["strike_price"],
                    txn["expiry_date"]
                )
                combos_transacted_today.add(contract_combo) # Mark as transacted

                q = queues[contract_combo]
                market_lot_size = txn["market_lot"]
                combo_market_lots[contract_combo] = market_lot_size # Store/update market lot size

                num_contracts = txn["lots"]
                entry_price = txn["entry_price"]

                if num_contracts > 0: # BUY transaction
                    for _ in range(num_contracts):
                        q.append(entry_price)
                    logger.info(f"  [BUY] {date_str} {contract_combo} +{num_contracts} @ {entry_price:.2f}. New Q size: {len(q)}")
                    logger.debug(f"    BUY_Q_STATE for {contract_combo}: {list(q)}")
                    logger.debug(f"    ALL_QUEUES_POST_BUY: {{k: list(v) for k, v in queues.items() if v}}")

                elif num_contracts < 0: # SELL transaction
                    abs_contracts_to_sell = abs(num_contracts)
                    booked_pnl_for_this_txn = 0.0
                    contracts_realized_count = 0
                    logger.debug(f"  [SELL_INITIATED] {date_str} {contract_combo} Sell {abs_contracts_to_sell} lots @ {entry_price:.2f}. Initial Q: {list(q)}")

                    for i in range(abs_contracts_to_sell):
                        if q:
                            buy_price = q.popleft()
                            pnl_per_contract_lot = (entry_price - buy_price) * market_lot_size
                            logger.debug(f"    SELL_MATCH: Lot {i+1}/{abs_contracts_to_sell} for {contract_combo} - SellPx: {entry_price:.2f}, Matched BuyPx: {buy_price:.2f}, MarketLot: {market_lot_size}, PnL_this_lot: {pnl_per_contract_lot:.2f}")
                            booked_pnl_for_this_txn += pnl_per_contract_lot
                            contracts_realized_count += 1
                        else:
                            logger.warning(f"  [OVERSELL] {date_str} {contract_combo} attempt to sell {abs_contracts_to_sell} but only {contracts_realized_count} available in queue.")
                            break 
                    
                    if contracts_realized_count > 0:
                        realised_map[date_str][contract_combo]["pnl"] += booked_pnl_for_this_txn
                        realised_map[date_str][contract_combo]["lots"] += contracts_realized_count
                        logger.info(f"  [SELL_COMPLETED] {date_str} {contract_combo} -{contracts_realized_count} @ {entry_price:.2f}. Realized PnL: {booked_pnl_for_this_txn:.2f}. New Q size: {len(q)}")
                        logger.debug(f"    SELL_Q_STATE for {contract_combo}: {list(q)}")
                        logger.debug(f"    ALL_QUEUES_POST_SELL: {{k: list(v) for k, v in queues.items() if v}}")


            # --- Post-Transaction/Daily Unrealised PnL Update for current_calc_date ---
            logger.debug(f"  POST_TXN_UNR_PnL_UPDATE Start for Date: {date_str}")
            for combo, q_u in queues.items(): # q_u is the queue state *after* all txns for the day
                symbol, opt_type, strike, expiry = combo
                
                daily_action_str = "NO_CHANGE" # Default for positions not transacted today
                lots_before_today = lots_at_start_of_transaction_day.get(combo, 0)
                lots_now = len(q_u)

                if combo in combos_transacted_today or lots_before_today != lots_now : # If transacted or if lots changed (e.g. expiry reduction)
                    if lots_before_today == 0 and lots_now > 0:
                        daily_action_str = "NEW_POSITION"
                    elif lots_now > lots_before_today:
                        daily_action_str = "ADDED_LOTS"
                    elif lots_now < lots_before_today:
                        if lots_now == 0:
                            daily_action_str = "CLOSED_POSITION"
                        else:
                            daily_action_str = "REDUCED_LOTS"
                    elif lots_now == lots_before_today and lots_now > 0 and combo in combos_transacted_today: # lots same but trades happened
                        daily_action_str = "MODIFIED_NO_NET_LOT_CHANGE"
                
                # Handling expiry for unrealised PnL
                if current_calc_date > expiry: 
                    if lots_before_today > 0 : # If it had lots and expired today
                         unrealised_map[date_str][combo] = {
                            "pnl": 0.0, "lots": 0, "closing_price": 0.0, 
                            "avg_entry_price_in_queue": 0.0, 
                            "market_lot": combo_market_lots.get(combo,0),
                            "daily_action": "EXPIRED"
                        }
                         logger.debug(f"    POST_TXN_UNR_PnL: {combo} EXPIRED on {date_str}. PnL set to 0.")
                    continue # Skip further processing for expired

                market_lot_size_u = combo_market_lots.get(combo)
                if market_lot_size_u is None: 
                    if q_u: logger.warning(f"    Market lot size missing for {combo} during post-txn unrealised calc on {date_str}")
                    continue

                # Current state of the position (lots_now is len(q_u))
                if not q_u: # No open positions for this combo after today's transactions
                    unrealised_map[date_str][combo] = {
                        "pnl": 0.0, "lots": 0, "closing_price": None, 
                        "avg_entry_price_in_queue": 0.0, 
                        "market_lot": market_lot_size_u,
                        "daily_action": daily_action_str if daily_action_str != "NO_CHANGE" or (combo in combos_transacted_today and lots_now == 0) else "NO_OPEN_POSITION"
                    }
                    continue

                closing_price_u = await get_closing_price(symbol, current_calc_date, expiry, opt_type, strike)
                if closing_price_u is not None:
                    avg_entry_price_u = sum(q_u) / len(q_u) # q_u is guaranteed not empty here
                    unp_u = sum((closing_price_u - entry_p_u) * market_lot_size_u for entry_p_u in q_u)
                    unrealised_map[date_str][combo] = {
                        "pnl": unp_u,
                        "lots": len(q_u),
                        "closing_price": closing_price_u,
                        "avg_entry_price_in_queue": avg_entry_price_u,
                        "market_lot": market_lot_size_u,
                        "daily_action": daily_action_str
                    }
                    logger.debug(f"    POST_TXN_UNR_PnL_CALC: Combo: {combo}, Date: {date_str}, Action: {daily_action_str}")
                    logger.debug(f"      Queue: {list(q_u)}")
                    logger.debug(f"      ClosingPx: {closing_price_u}, MarketLot: {market_lot_size_u}, AvgEntryPx: {avg_entry_price_u:.2f}")
                    pnl_contributions_u = [(closing_price_u - entry_p_u) * market_lot_size_u for entry_p_u in q_u]
                    logger.debug(f"      PnL Contributions: {pnl_contributions_u}")
                    logger.debug(f"      Total Unrealised PnL: {unp_u:.2f}, Lots: {len(q_u)}")
                # If closing_price_u is None, no entry is made for this combo on this date.
            
            if current_calc_date >= latest_processing_date and position_idx >= len(positions):
                 break 
            current_calc_date += timedelta(days=1)


        # Build response
        out = []
        all_pnl_dates_str = sorted(
            set(list(unrealised_map.keys()) + list(realised_map.keys())),
            key=lambda d_str: datetime.strptime(d_str, "%d-%b-%Y").date()
        )
        
        cumulative_realized_pnl = 0.0

        for d_str in all_pnl_dates_str:
            # Filter unrealised_map for entries that actually have a calculated PnL for the day
            valid_unrealised_entries_for_day = {
                c: p_data for c, p_data in unrealised_map[d_str].items() if "closing_price" in p_data
            }

            daily_unrealised_total = sum(data["pnl"] for data in valid_unrealised_entries_for_day.values())
            daily_realised_total = sum(data["pnl"] for data in realised_map[d_str].values())
            
            cumulative_realized_pnl += daily_realised_total
            
            total_pnl_for_day = round(daily_unrealised_total + daily_realised_total, 2)

            out.append({
                "date": d_str,
                "unrealised": [
                    {
                        "contract": list(c),
                        "lots": p_data["lots"],
                       # "closing_price": p_data.get("closing_price"),
                        "daily_action": p_data.get("daily_action"), # Display daily action
                        "debug_info": {
                            "entry_price": round(p_data.get("avg_entry_price_in_queue", 0), 2),
                            "closing_price": p_data.get("closing_price"),
                            "market_lot": p_data.get("market_lot"),
                            "pnl_calculation": f"({p_data.get('closing_price', 'N/A')} - {round(p_data.get('avg_entry_price_in_queue', 0), 2)}) * {p_data.get('lots',0)} * {p_data.get('market_lot', 'N/A')}"
                        },
                        "pnl": round(p_data["pnl"], 2)
                    }
                    # Show only if closing_price is available (i.e., PnL was calculated) OR if there was a specific daily_action
                    for c, p_data in unrealised_map[d_str].items() 
                    if p_data.get("closing_price") is not None or (p_data.get("daily_action") and p_data.get("daily_action") not in ["NO_CHANGE", "NO_OPEN_POSITION"])
                ],
                "realised": [
                    {
                        "contract": list(c), # Consider adding action type here too if needed, e.g. "SELL_TO_CLOSE"
                        "lots": p_data["lots"],
                        "pnl": round(p_data["pnl"], 2),
                    }
                    for c, p_data in realised_map[d_str].items() if p_data.get("lots", 0) > 0 
                ],
                "total_unrealised_pnl": round(daily_unrealised_total, 2),
                "total_realized_pnl": round(cumulative_realized_pnl, 2)
            })
        logger.info(f"Successfully completed PnL simulation for user {request_user_id}")
        return {"status": "success", "data": out}
        
    except Exception as e:
        logger.exception(f"Error in strategy_simulation for user {request_user_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
'''


'''
from fastapi import APIRouter, Header, Request, Response, HTTPException, status
from datetime import datetime, timedelta, date
from collections import defaultdict, deque
# Assuming NIFTY model is for fetching prices, if not, adjust accordingly
# from db.models.nse import NIFTY
# from db.models.users import UserTransactions # Not directly used if using execute_native_query
from services.utils import execute_native_query
import logging

# Configure Logging
logging.basicConfig(level=logging.DEBUG) # Keep this for root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # Explicitly set level for this specific logger

# Strategy Simulation Router
router = APIRouter()

async def get_closing_price(
    symbol: str,
    target_date: date,
    expiry_date: date,
    option_type: str,
    strike_price: float
):
    """
    Helper function to fetch the closing price for a given contract on a specific date.
    Adjust table name and column names as per your database schema.
    """
    table_name = symbol.lower()
    # Ensure date formats match DB query requirements
    # The original code used FH_TIMESTAMP with %d-%b-%Y and FH_EXPIRY_DT with %d-%b-%Y
    # Strike price was formatted as f"{strike_price}.00"
    try:
        res = await execute_native_query(
            f"""
            SELECT FH_CLOSING_PRICE 
            FROM {table_name} 
            WHERE FH_TIMESTAMP = %s
            AND FH_EXPIRY_DT = %s
            AND FH_OPTION_TYPE = %s
            AND FH_STRIKE_PRICE = %s
            """,
            [
                target_date.strftime("%d-%b-%Y"),
                expiry_date.strftime("%d-%b-%Y"),
                option_type,
                f"{strike_price:.2f}" # Ensure strike price is formatted correctly
            ]
        )
        if res and res[0]["FH_CLOSING_PRICE"] is not None:
            return float(res[0]["FH_CLOSING_PRICE"])
        else:
            logger.warning(f"No closing price for {symbol} {option_type} {strike_price} Exp:{expiry_date.strftime('%d-%b-%Y')} on {target_date.strftime('%d-%b-%Y')}")
            return None
    except Exception as e:
        logger.error(f"Error fetching closing price for {symbol} {target_date}: {e}")
        return None

@router.get("/api/v1_0/strategy/simulation", status_code=status.HTTP_200_OK)
async def strategy_simulation(
    request: Request,
    response: Response,
    request_user_id: str = Header(None)  # User ID from request header
):
    try:
        positions_raw = await execute_native_query(
            """
            SELECT * FROM user_transactions 
            WHERE user_id = %s AND status='active' 
            ORDER BY trade_date, transaction_time
            """, # Assuming transaction_time exists for intra-day ordering
            [request_user_id]
        )
        
        if not positions_raw:
            return {"status": "success", "message": "No active positions", "data": []}

        # Normalize data and prepare for processing
        positions = []
        all_trade_dates = set()
        all_expiry_dates = set()

        for txn_raw in positions_raw:
            try:
                trade_dt = txn_raw["trade_date"]
                expiry_dt = txn_raw["expiry_date"]

                current_trade_date = trade_dt.date() if isinstance(trade_dt, datetime) else trade_dt
                current_expiry_date = expiry_dt.date() if isinstance(expiry_dt, datetime) else expiry_dt
                
                positions.append({
                    "symbol": txn_raw["symbol"].strip().upper(),
                    "option_type": txn_raw["option_type"].strip().upper(),
                    "strike_price": int(float(txn_raw["strike_price"])),
                    "expiry_date": current_expiry_date,
                    "trade_date": current_trade_date,
                    "lots": int(txn_raw["lots"]), # Can be +ve for BUY, -ve for SELL
                    "entry_price": float(txn_raw["entry_price"]),
                    "market_lot": int(txn_raw["market_lot"]),
                    # "transaction_time": txn_raw.get("transaction_time") # Keep if needed for logging/debugging
                })
                all_trade_dates.add(current_trade_date)
                all_expiry_dates.add(current_expiry_date)
            except Exception as e:
                logger.error(f"Error processing transaction: {txn_raw}. Error: {e}")
                # Decide if to skip this transaction or raise error
                continue
        
        if not positions: # If all raw positions failed processing
             return {"status": "success", "message": "No processable active positions", "data": []}


        earliest_processing_date = min(all_trade_dates) if all_trade_dates else date.today()
        latest_processing_date = max(all_expiry_dates) if all_expiry_dates else date.today()

        # New structure for tracking net positions
        open_positions = defaultdict(lambda: {"net_lots": 0, "avg_entry_price": 0.0, "market_lot": 0, "total_value_at_cost": 0.0})
        
        unrealised_map = defaultdict(lambda: defaultdict(dict)) # Will store more details
        realised_map = defaultdict(lambda: defaultdict(lambda: {"pnl": 0.0, "lots": 0})) # lots here are contracts involved in realization
        
        current_calc_date = earliest_processing_date
        position_idx = 0

        logger.info(f"Starting PnL simulation from {earliest_processing_date} to {latest_processing_date} for user {request_user_id}")

        while current_calc_date <= latest_processing_date or position_idx < len(positions):
            
            # Determine if we are processing a transaction day or a gap day
            next_txn_date = positions[position_idx]["trade_date"] if position_idx < len(positions) else None

            # --- Gap Filling Logic ---
            # If current_calc_date is before the next transaction, or if all transactions are processed
            # and current_calc_date is still before or on latest_processing_date
            is_gap_fill_day = not next_txn_date or current_calc_date < next_txn_date
            if position_idx >= len(positions) and current_calc_date > latest_processing_date: # All txns processed and past last expiry
                break


            if is_gap_fill_day:
                date_str = current_calc_date.strftime("%d-%b-%Y")
                logger.debug(f"GAP FILL Day: {date_str}")
                for combo, pos_details in open_positions.items():
                    symbol, opt_type, strike, expiry = combo
                    
                    if pos_details["net_lots"] == 0 or current_calc_date > expiry:
                        if pos_details["net_lots"] != 0 and current_calc_date > expiry: # Position expired
                            # Realize any remaining PnL at expiry, assuming settlement at 0 if not otherwise defined
                            # This part needs careful thought for shorts if CP is not 0 at expiry
                            # For now, just mark as 0 lots for unrealised. Actual realization at expiry is complex.
                            unrealised_map[date_str][combo] = {
                                "pnl": 0.0, "lots": 0, "closing_price": 0.0, 
                                "avg_entry_price": pos_details["avg_entry_price"], 
                                "market_lot": pos_details["market_lot"],
                                "position_type": "LONG" if pos_details["net_lots"] > 0 else "SHORT",
                                "daily_action": "EXPIRED"
                            }
                            # Potentially realize PnL here if held to expiry
                            # open_positions[combo]["net_lots"] = 0 # Position becomes flat
                            # open_positions[combo]["avg_entry_price"] = 0.0
                        continue

                    market_lot_size = pos_details["market_lot"]
                    if market_lot_size == 0: # Should have been set by a transaction
                        logger.warning(f"Market lot size is 0 for {combo} on {date_str}. Skipping unrealised PnL.")
                        continue
                    
                    closing_price = await get_closing_price(symbol, current_calc_date, expiry, opt_type, strike)
                    if closing_price is not None:
                        unp = 0.0
                        position_type = "FLAT"
                        if pos_details["net_lots"] > 0: # LONG
                            unp = (closing_price - pos_details["avg_entry_price"]) * pos_details["net_lots"] * market_lot_size
                            position_type = "LONG"
                        elif pos_details["net_lots"] < 0: # SHORT
                            unp = (pos_details["avg_entry_price"] - closing_price) * abs(pos_details["net_lots"]) * market_lot_size
                            position_type = "SHORT"
                        
                        unrealised_map[date_str][combo] = {
                            "pnl": unp,
                            "lots": abs(pos_details["net_lots"]),
                            "closing_price": closing_price,
                            "avg_entry_price": pos_details["avg_entry_price"],
                            "market_lot": market_lot_size,
                            "position_type": position_type,
                            # "daily_action" is not set for gap-fill days unless it's expiry
                        }
                        logger.debug(f"    GAP_UNR_PnL_CALC: {combo} {position_type} Lots: {pos_details['net_lots']}, AvgEP: {pos_details['avg_entry_price']:.2f}, CP: {closing_price:.2f}, MktLot: {market_lot_size}, PnL: {unp:.2f}")
                    # If closing_price is None, no entry is made for this combo on this date for unrealised.
                
                if current_calc_date >= latest_processing_date and position_idx >= len(positions):
                    break
                current_calc_date += timedelta(days=1)
                continue # Move to next day for gap fill or transaction processing

            # --- Transaction Processing Logic ---
            # This part executes if current_calc_date == next_txn_date
            current_calc_date = next_txn_date # Align current_calc_date with transaction date
            date_str = current_calc_date.strftime("%d-%b-%Y")
            logger.debug(f"TRANSACTION Day: {date_str}")

            # Store net_lots at the start of the transaction day for daily_action comparison
            net_lots_at_start_of_day = {c: pd["net_lots"] for c, pd in open_positions.items()}
            combos_transacted_today = set()

            txns_on_this_day = []
            while position_idx < len(positions) and positions[position_idx]["trade_date"] == current_calc_date:
                txns_on_this_day.append(positions[position_idx])
                position_idx += 1
            
            for txn in txns_on_this_day:
                contract_combo = (
                    txn["symbol"],
                    txn["option_type"],
                    txn["strike_price"],
                    txn["expiry_date"]
                )
                combos_transacted_today.add(contract_combo) # Mark as transacted

                pos_details = open_positions[contract_combo]
                pos_details["market_lot"] = txn["market_lot"] # Ensure market lot is set/updated

                txn_lots_signed = txn["lots"]
                txn_price = txn["entry_price"]
                
                current_net_lots = pos_details["net_lots"]
                current_avg_price = pos_details["avg_entry_price"]
                current_total_value = pos_details["total_value_at_cost"] # current_avg_price * current_net_lots (use signed lots)

                logger.debug(f"  Processing TXN: {contract_combo}, TxnLots: {txn_lots_signed}, TxnPrice: {txn_price:.2f}. Current Pos: NetLots: {current_net_lots}, AvgEP: {current_avg_price:.2f}")

                # Case 1: Opening new position or adding to existing in same direction
                if current_net_lots == 0 or (txn_lots_signed > 0 and current_net_lots > 0) or (txn_lots_signed < 0 and current_net_lots < 0):
                    new_total_value = current_total_value + (txn_price * txn_lots_signed)
                    pos_details["net_lots"] += txn_lots_signed
                    pos_details["total_value_at_cost"] = new_total_value
                    if pos_details["net_lots"] != 0:
                        pos_details["avg_entry_price"] = new_total_value / pos_details["net_lots"] 
                    else: # Should not happen if opening or adding, but as safeguard
                        pos_details["avg_entry_price"] = 0.0
                    logger.info(f"    ACTION: Add/Open. New Pos: NetLots: {pos_details['net_lots']}, AvgEP: {pos_details['avg_entry_price']:.2f}")

                # Case 2: Closing or reducing existing position (opposite directions)
                else:
                    lots_closed_abs = min(abs(txn_lots_signed), abs(current_net_lots))
                    realized_pnl_this_leg = 0.0

                    if current_net_lots > 0: # Closing/reducing a LONG position with a SELL txn
                        realized_pnl_this_leg = (txn_price - current_avg_price) * lots_closed_abs * pos_details["market_lot"]
                        logger.info(f"    ACTION: Close/Reduce LONG. LotsClosed: {lots_closed_abs}, SellPrice: {txn_price:.2f}, AvgBuyPrice: {current_avg_price:.2f}, PnL: {realized_pnl_this_leg:.2f}")
                    elif current_net_lots < 0: # Closing/reducing a SHORT position with a BUY txn
                        realized_pnl_this_leg = (current_avg_price - txn_price) * lots_closed_abs * pos_details["market_lot"]
                        logger.info(f"    ACTION: Close/Reduce SHORT. LotsClosed: {lots_closed_abs}, BuyPrice: {txn_price:.2f}, AvgSellPrice: {current_avg_price:.2f}, PnL: {realized_pnl_this_leg:.2f}")
                    
                    realised_map[date_str][contract_combo]["pnl"] += realized_pnl_this_leg
                    realised_map[date_str][contract_combo]["lots"] += lots_closed_abs

                    # Update position details
                    pos_details["total_value_at_cost"] = current_avg_price * (current_net_lots + txn_lots_signed) # Value of remaining position at old avg_price
                    pos_details["net_lots"] += txn_lots_signed


                    if pos_details["net_lots"] == 0:
                        pos_details["avg_entry_price"] = 0.0
                        pos_details["total_value_at_cost"] = 0.0
                        logger.debug(f"    POSITION FLATTENED for {contract_combo}")
                    else:
                        # If not flipped, avg_entry_price of remaining part is the same.
                        # If flipped, new position is at txn_price for remaining txn_lots.
                        remaining_txn_lots_signed = txn_lots_signed + (lots_closed_abs if txn_lots_signed < 0 else -lots_closed_abs) # lots of this txn not used for closing
                        if remaining_txn_lots_signed != 0: # Flipped and new position opened
                            pos_details["net_lots"] = remaining_txn_lots_signed # This is the new net_lots
                            pos_details["avg_entry_price"] = txn_price
                            pos_details["total_value_at_cost"] = txn_price * remaining_txn_lots_signed
                            logger.info(f"    POSITION FLIPPED for {contract_combo}. New Pos: NetLots: {pos_details['net_lots']}, AvgEP: {pos_details['avg_entry_price']:.2f}")
                        # else: avg_entry_price remains current_avg_price for the remaining part (already set if not flipped)
                        # This part needs to be very careful: if partially closed, avg_price of remainder is same.
                        # If flipped, avg_price is txn_price for the new leg.
                        # The total_value_at_cost update above handles the reduction of value.
                        # If net_lots is not 0 after reduction, avg_entry_price should remain current_avg_price.
                        # The flip logic is tricky with total_value_at_cost.
                        # Simpler: if net_lots !=0 and sign didn't change, avg_price is same. If sign changed, avg_price is txn_price.
                        if pos_details["net_lots"] != 0:
                             if (pos_details["net_lots"] > 0 and current_net_lots < 0) or \
                                (pos_details["net_lots"] < 0 and current_net_lots > 0) : # Flipped
                                 pos_details["avg_entry_price"] = txn_price
                             # else: avg_entry_price remains current_avg_price (no change needed if not flipped and not flat)
                        logger.debug(f"    Updated Pos: NetLots: {pos_details['net_lots']}, AvgEP: {pos_details['avg_entry_price']:.2f}")


            # --- Post-Transaction/Daily Unrealised PnL Update for current_calc_date ---
            logger.debug(f"  POST_TXN_UNR_PnL_UPDATE Start for Date: {date_str}")
            for combo, pos_details_unr in open_positions.items():
                symbol, opt_type, strike, expiry = combo
                
                current_pos_net_lots = pos_details_unr["net_lots"]
                lots_before_today = net_lots_at_start_of_day.get(combo, 0)
                daily_action_str = "NO_CHANGE"

                if combo in combos_transacted_today or lots_before_today != current_pos_net_lots:
                    if lots_before_today == 0 and current_pos_net_lots != 0:
                        daily_action_str = "NEW_SHORT" if current_pos_net_lots < 0 else "NEW_LONG"
                    elif current_pos_net_lots > lots_before_today and lots_before_today >= 0: # Added to long or flipped from short to long
                        daily_action_str = "ADDED_TO_LONG" if lots_before_today > 0 else ("FLIPPED_TO_LONG" if lots_before_today < 0 else "NEW_LONG")
                    elif current_pos_net_lots < lots_before_today and lots_before_today <= 0: # Added to short or flipped from long to short
                        daily_action_str = "ADDED_TO_SHORT" if lots_before_today < 0 else ("FLIPPED_TO_SHORT" if lots_before_today > 0 else "NEW_SHORT")
                    elif abs(current_pos_net_lots) < abs(lots_before_today):
                        if current_pos_net_lots == 0:
                            daily_action_str = "CLOSED_SHORT" if lots_before_today < 0 else "CLOSED_LONG"
                        else: # Reduced
                            daily_action_str = "REDUCED_SHORT" if current_pos_net_lots < 0 else "REDUCED_LONG"
                    elif current_pos_net_lots == lots_before_today and current_pos_net_lots != 0 and combo in combos_transacted_today :
                        daily_action_str = "MODIFIED_NO_NET_LOT_CHANGE"
                
                position_type_str = "FLAT"
                if current_pos_net_lots > 0: position_type_str = "LONG"
                elif current_pos_net_lots < 0: position_type_str = "SHORT"

                # Handling expiry
                if current_calc_date > expiry:
                    if current_pos_net_lots != 0: # Position was open and expired
                         # Realize PnL at expiry, assuming 0 settlement for now
                        expiry_pnl = 0
                        if current_pos_net_lots > 0: # Expired Long
                            expiry_pnl = (0 - pos_details_unr["avg_entry_price"]) * current_pos_net_lots * pos_details_unr["market_lot"]
                        elif current_pos_net_lots < 0: # Expired Short
                            expiry_pnl = (pos_details_unr["avg_entry_price"] - 0) * abs(current_pos_net_lots) * pos_details_unr["market_lot"]
                        
                        realised_map[date_str][combo]["pnl"] += expiry_pnl
                        realised_map[date_str][combo]["lots"] += abs(current_pos_net_lots)
                        logger.info(f"    EXPIRY_REALIZED for {combo}: PnL {expiry_pnl:.2f} for {abs(current_pos_net_lots)} lots.")
                        
                        open_positions[combo]["net_lots"] = 0 # Flatten position
                        open_positions[combo]["avg_entry_price"] = 0.0
                        open_positions[combo]["total_value_at_cost"] = 0.0
                        
                        unrealised_map[date_str][combo] = {"pnl": 0.0, "lots": 0, "closing_price": 0.0, "avg_entry_price": 0.0, "market_lot": pos_details_unr["market_lot"], "position_type": position_type_str, "daily_action": "EXPIRED"}
                    continue

                if current_pos_net_lots == 0:
                    # If it became flat today due to transactions, action would be set.
                    # If it was already flat and no transactions, it won't be in open_positions to begin with unless it just expired.
                    # Ensure an entry if it was transacted to flat today.
                    if combo in combos_transacted_today:
                         unrealised_map[date_str][combo] = {"pnl": 0.0, "lots": 0, "closing_price": None, "avg_entry_price": 0.0, "market_lot": pos_details_unr["market_lot"], "position_type": "FLAT", "daily_action": daily_action_str}
                    continue

                market_lot_size_u = pos_details_unr["market_lot"]
                closing_price_u = await get_closing_price(symbol, current_calc_date, expiry, opt_type, strike)

                if closing_price_u is not None:
                    unp_u = 0.0
                    if current_pos_net_lots > 0: # LONG
                        unp_u = (closing_price_u - pos_details_unr["avg_entry_price"]) * current_pos_net_lots * market_lot_size_u
                    elif current_pos_net_lots < 0: # SHORT
                        unp_u = (pos_details_unr["avg_entry_price"] - closing_price_u) * abs(current_pos_net_lots) * market_lot_size_u
                    
                    unrealised_map[date_str][combo] = {
                        "pnl": unp_u,
                        "lots": abs(current_pos_net_lots),
                        "closing_price": closing_price_u,
                        "avg_entry_price": pos_details_unr["avg_entry_price"],
                        "market_lot": market_lot_size_u,
                        "position_type": position_type_str,
                        "daily_action": daily_action_str
                    }
                    logger.debug(f"    POST_TXN_UNR_PnL_CALC: {combo} {position_type_str} Lots:{current_pos_net_lots}, AvgEP:{pos_details_unr['avg_entry_price']:.2f}, CP:{closing_price_u:.2f}, PnL:{unp_u:.2f}, Action:{daily_action_str}")
                # If closing_price_u is None, no entry for unrealised on this day.
            
            if current_calc_date >= latest_processing_date and position_idx >= len(positions):
                break 
            current_calc_date += timedelta(days=1)

        # Build response
        out = []
        all_pnl_dates_str = sorted(
            set(list(unrealised_map.keys()) + list(realised_map.keys())),
            key=lambda d_str: datetime.strptime(d_str, "%d-%b-%Y").date()
        )
        
        cumulative_realized_pnl = 0.0

        for d_str in all_pnl_dates_str:
            daily_unrealised_pnl_sum = sum(data.get("pnl",0) for data in unrealised_map[d_str].values() if data.get("closing_price") is not None or data.get("daily_action") == "EXPIRED")
            daily_realised_pnl_sum = sum(data.get("pnl",0) for data in realised_map[d_str].values())
            
            cumulative_realized_pnl += daily_realised_pnl_sum
            
            response_unrealised_list = []
            for c, p_data in unrealised_map[d_str].items():
                # Show if PnL was calculated (closing_price is not None) OR if there was a significant daily_action
                if p_data.get("closing_price") is not None or \
                   (p_data.get("daily_action") and p_data.get("daily_action") not in ["NO_CHANGE", "NO_OPEN_POSITION"]):
                    
                    contract_display_list = list(c)
                    if "position_type" in p_data:
                         contract_display_list.append(p_data["position_type"])
                    
                    pnl_calc_str = "N/A"
                    if p_data.get("closing_price") is not None and p_data.get("market_lot") is not None and p_data.get("lots") is not None:
                        if p_data.get("position_type") == "LONG":
                            pnl_calc_str = f"({p_data.get('closing_price', 'N/A')} - {round(p_data.get('avg_entry_price', 0), 2)}) * {p_data.get('lots',0)} * {p_data.get('market_lot', 'N/A')}"
                        elif p_data.get("position_type") == "SHORT":
                            pnl_calc_str = f"({round(p_data.get('avg_entry_price', 0), 2)} - {p_data.get('closing_price', 'N/A')}) * {p_data.get('lots',0)} * {p_data.get('market_lot', 'N/A')}"


                    response_unrealised_list.append({
                        "contract": contract_display_list,
                        "lots": p_data.get("lots",0),
                        "daily_action": p_data.get("daily_action"),
                        "debug_info": {
                            "entry_price": round(p_data.get("avg_entry_price", 0), 2),
                            "closing_price": p_data.get("closing_price"),
                            "market_lot": p_data.get("market_lot"),
                            "pnl_calculation": pnl_calc_str
                        },
                        "pnl": round(p_data.get("pnl",0), 2)
                    })

            response_realised_list = []
            for c, p_data in realised_map[d_str].items():
                if p_data.get("lots", 0) > 0:
                    # Need to determine if it was a closed LONG or SHORT.
                    # This info is not directly in realised_map. For now, just basic contract.
                    # This could be improved if we store original position type with realised PnL.
                    contract_display_list = list(c) # Placeholder, ideally show LONG/SHORT closed
                    response_realised_list.append({
                        "contract": contract_display_list,
                        "lots": p_data["lots"],
                        "pnl": round(p_data.get("pnl",0), 2),
                    })


            out.append({
                "date": d_str,
                "unrealised": response_unrealised_list,
                "realised": response_realised_list,
                "total_unrealised_pnl": round(daily_unrealised_pnl_sum, 2),
                "total_realized_pnl": round(daily_realised_pnl_sum, 2), # Daily realized
                "cumulative_total_realized_pnl": round(cumulative_realized_pnl, 2) # Cumulative
            })
        logger.info(f"Successfully completed PnL simulation for user {request_user_id}")
        return {"status": "success", "data": out}
        
    except Exception as e:
        logger.exception(f"Error in strategy_simulation for user {request_user_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
'''