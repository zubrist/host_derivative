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

        # --- Data Structures for Hybrid FIFO (Realized) + Average (Unrealized Net) ---
        # Stores (price, quantity) tuples for each transaction layer
        position_layers = defaultdict(lambda: {"long": deque(), "short": deque()}) 
        
        # Stores the current net state of the position for unrealized PnL and overall tracking
        # avg_entry_price here will be the weighted average of all open layers
        # market_lot will be set by the first transaction for the combo
        open_positions = defaultdict(lambda: {"net_lots": 0, "avg_entry_price": 0.0, "market_lot": 0})

        unrealised_map = defaultdict(lambda: defaultdict(dict)) 
        realised_map = defaultdict(lambda: defaultdict(list)) # Stores detailed realization events
        
        current_calc_date = earliest_processing_date
        position_idx = 0

        logger.info(f"Starting PnL simulation from {earliest_processing_date} to {latest_processing_date} for user {request_user_id}")

        # --- Helper function to update open_positions summary based on position_layers ---
        def _update_open_position_summary(combo_key, current_market_lot_if_known=None):
            if combo_key not in position_layers and combo_key not in open_positions: # No activity at all
                return

            long_layers = position_layers[combo_key]["long"]
            short_layers = position_layers[combo_key]["short"]
            
            total_long_qty = sum(qty for _, qty in long_layers)
            total_short_qty = sum(qty for _, qty in short_layers)
            
            net_qty = total_long_qty - total_short_qty
            open_positions[combo_key]["net_lots"] = net_qty
            
            # Preserve or set market_lot
            if current_market_lot_if_known is not None and current_market_lot_if_known != 0:
                open_positions[combo_key]["market_lot"] = current_market_lot_if_known
            elif open_positions[combo_key]["market_lot"] == 0 and (long_layers or short_layers):
                # Attempt to get market_lot from layers if not set (should be set by txn)
                # This part is tricky as layers only store price/qty. Market lot is per-combo.
                # For now, assume market_lot is set on open_positions[combo_key] by the first transaction.
                pass


            if net_qty == 0:
                open_positions[combo_key]["avg_entry_price"] = 0.0
            elif net_qty > 0: # Net long
                if total_long_qty > 0: # Should always be true if net_qty > 0
                    weighted_sum_price = sum(price * qty for price, qty in long_layers)
                    # Deduct value of any short layers if they exist (complex netting, for now assume only one side has layers if net is non-zero)
                    # This simplified avg_entry_price assumes if net_qty > 0, only long_layers contribute to its avg price.
                    # A true net average would be (sum_long_value - sum_short_value) / (total_long_qty - total_short_qty)
                    # For now, if net long, average of long layers. If net short, average of short layers.
                    open_positions[combo_key]["avg_entry_price"] = weighted_sum_price / total_long_qty
                else:
                     open_positions[combo_key]["avg_entry_price"] = 0.0 # Should not happen
            else: # Net short (net_qty < 0)
                if total_short_qty > 0: # Should always be true if net_qty < 0
                    weighted_sum_price = sum(price * qty for price, qty in short_layers)
                    open_positions[combo_key]["avg_entry_price"] = weighted_sum_price / total_short_qty
                else:
                    open_positions[combo_key]["avg_entry_price"] = 0.0 # Should not happen
            
            logger.debug(f"    _update_open_position_summary for {combo_key}: NetLots: {open_positions[combo_key]['net_lots']}, AvgEP: {open_positions[combo_key]['avg_entry_price']:.2f}, MktLot: {open_positions[combo_key]['market_lot']}")


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

            # Store net_lots from open_positions (summary) at the start of the transaction day
            net_lots_summary_at_start_of_day = {c: summary["net_lots"] for c, summary in open_positions.items()}
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

                # --- New Transaction Processing Logic using position_layers (FIFO for Realized) ---
                # Ensure market_lot is set in open_positions for the combo
                open_positions[contract_combo]["market_lot"] = txn["market_lot"]
                
                txn_lots_signed = txn["lots"]
                txn_price = txn["entry_price"]
                market_lot = txn["market_lot"]

                logger.debug(f"  Processing TXN: {contract_combo}, TxnLots: {txn_lots_signed}, TxnPrice: {txn_price:.2f}")

                if txn_lots_signed > 0: # BUY Transaction
                    buy_lots_to_process = txn_lots_signed
                    
                    # Phase 1: Try to close/reduce existing short layers
                    short_layers_q = position_layers[contract_combo]["short"]
                    while short_layers_q and buy_lots_to_process > 0:
                        short_layer_price, short_layer_qty = short_layers_q[0]
                        lots_to_cover_from_layer = min(buy_lots_to_process, short_layer_qty)
                        
                        real_pnl = (short_layer_price - txn_price) * lots_to_cover_from_layer * market_lot
                        realised_map[date_str][contract_combo].append({
                            "pnl_leg": real_pnl, "lots_leg": lots_to_cover_from_layer, "exit_price": txn_price,
                            "entry_price_closed_portion": short_layer_price, "market_lot": market_lot,
                            "closed_position_type": "SHORT"
                        })
                        logger.info(f"    TXN_REALIZED (Cover Short): {contract_combo} Covered {lots_to_cover_from_layer} lots @ {txn_price:.2f} against short entry @ {short_layer_price:.2f}. PnL: {real_pnl:.2f}")

                        buy_lots_to_process -= lots_to_cover_from_layer
                        if lots_to_cover_from_layer == short_layer_qty:
                            short_layers_q.popleft()
                        else:
                            short_layers_q[0] = (short_layer_price, short_layer_qty - lots_to_cover_from_layer)
                    
                    # Phase 2: If BUY lots still remain, add to LONG layers
                    if buy_lots_to_process > 0:
                        position_layers[contract_combo]["long"].append((txn_price, buy_lots_to_process))
                        logger.info(f"    TXN_OPEN/ADD_LONG: {contract_combo} Added {buy_lots_to_process} LONG lots @ {txn_price:.2f}")

                elif txn_lots_signed < 0: # SELL Transaction
                    sell_lots_to_process_abs = abs(txn_lots_signed)
                    
                    # Phase 1: Try to close/reduce existing LONG layers
                    long_layers_q = position_layers[contract_combo]["long"]
                    while long_layers_q and sell_lots_to_process_abs > 0:
                        long_layer_price, long_layer_qty = long_layers_q[0]
                        lots_to_close_from_layer = min(sell_lots_to_process_abs, long_layer_qty)

                        real_pnl = (txn_price - long_layer_price) * lots_to_close_from_layer * market_lot
                        realised_map[date_str][contract_combo].append({
                            "pnl_leg": real_pnl, "lots_leg": lots_to_close_from_layer, "exit_price": txn_price,
                            "entry_price_closed_portion": long_layer_price, "market_lot": market_lot,
                            "closed_position_type": "LONG"
                        })
                        logger.info(f"    TXN_REALIZED (Close Long): {contract_combo} Closed {lots_to_close_from_layer} LONG lots @ {txn_price:.2f} against entry @ {long_layer_price:.2f}. PnL: {real_pnl:.2f}")
                        
                        sell_lots_to_process_abs -= lots_to_close_from_layer
                        if lots_to_close_from_layer == long_layer_qty:
                            long_layers_q.popleft()
                        else:
                            long_layers_q[0] = (long_layer_price, long_layer_qty - lots_to_close_from_layer)
                    
                    # Phase 2: If SELL lots still remain (abs), add to SHORT layers
                    if sell_lots_to_process_abs > 0:
                        position_layers[contract_combo]["short"].append((txn_price, sell_lots_to_process_abs))
                        logger.info(f"    TXN_OPEN/ADD_SHORT: {contract_combo} Added {sell_lots_to_process_abs} SHORT lots @ {txn_price:.2f}")
                
                # After processing the transaction, update the summary in open_positions
                _update_open_position_summary(contract_combo, market_lot)
            
            # --- Post-Transaction/Daily Unrealised PnL Update for current_calc_date ---
            logger.debug(f"  POST_TXN_UNR_PnL_UPDATE Start for Date: {date_str}")
            # Iterate through all combos that might have an open position or had activity
            all_relevant_combos_for_mtm = set(open_positions.keys()) | set(position_layers.keys())

            for combo in all_relevant_combos_for_mtm:
                _update_open_position_summary(combo) # Ensure summary is fresh
                pos_summary_unr = open_positions[combo]
                symbol, opt_type, strike, expiry = combo
                
                current_pos_net_lots = pos_summary_unr["net_lots"]
                # Use net_lots_summary_at_start_of_day for daily_action
                lots_before_today = net_lots_summary_at_start_of_day.get(combo, 0)
                # symbol, opt_type, strike, expiry = combo # Redundant assignment removed
                
                # current_pos_net_lots = pos_details_unr["net_lots"] # Corrected below
                # lots_before_today = net_lots_at_start_of_day.get(combo, 0) # Corrected variable name below
                # Use the already assigned current_pos_net_lots from line 352
                # Use the correct variable name for lots_before_today from line 353
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
                            expiry_pnl = (0 - pos_summary_unr["avg_entry_price"]) * current_pos_net_lots * pos_summary_unr["market_lot"]
                        elif current_pos_net_lots < 0: # Expired Short
                            expiry_pnl = (pos_summary_unr["avg_entry_price"] - 0) * abs(current_pos_net_lots) * pos_summary_unr["market_lot"]
                        
                        # Assuming realised_map[date_str][combo] is initialized elsewhere if needed before +=
                        # If it might not exist, need to handle that (e.g., use defaultdict or check existence)
                        # For now, assuming it exists or the logic implies it should.
                        # Also, realised_map stores a list of dicts, not a single dict with 'pnl' and 'lots'.
                        # This expiry realization logic might need adjustment based on realised_map structure.
                        # Let's add a new event for expiry realization instead of modifying potentially non-existent keys.
                        realised_map[date_str][combo].append({
                             "pnl_leg": expiry_pnl, "lots_leg": abs(current_pos_net_lots), "exit_price": 0, # Assuming 0 settlement
                             "entry_price_closed_portion": pos_summary_unr["avg_entry_price"], "market_lot": pos_summary_unr["market_lot"],
                             "closed_position_type": "LONG" if current_pos_net_lots > 0 else "SHORT",
                             "reason": "EXPIRY"
                        })
                        # realised_map[date_str][combo]["pnl"] += expiry_pnl # Original incorrect logic
                        # realised_map[date_str][combo]["lots"] += abs(current_pos_net_lots) # Original incorrect logic
                        logger.info(f"    EXPIRY_REALIZED for {combo}: PnL {expiry_pnl:.2f} for {abs(current_pos_net_lots)} lots.")
                        
                        open_positions[combo]["net_lots"] = 0 # Flatten position
                        open_positions[combo]["avg_entry_price"] = 0.0
                        # open_positions[combo]["total_value_at_cost"] = 0.0 # This key doesn't seem to be used elsewhere
                        
                        unrealised_map[date_str][combo] = {"pnl": 0.0, "lots": 0, "closing_price": 0.0, "avg_entry_price": 0.0, "market_lot": pos_summary_unr["market_lot"], "position_type": position_type_str, "daily_action": "EXPIRED"}
                    continue

                if current_pos_net_lots == 0:
                    # If it became flat today due to transactions, action would be set.
                    # If it was already flat and no transactions, it won't be in open_positions to begin with unless it just expired.
                    # Ensure an entry if it was transacted to flat today.
                    if combo in combos_transacted_today:
                         unrealised_map[date_str][combo] = {"pnl": 0.0, "lots": 0, "closing_price": None, "avg_entry_price": 0.0, "market_lot": pos_summary_unr.get("market_lot", 0), "position_type": "FLAT", "daily_action": daily_action_str} # Use .get for safety if combo was removed
                    continue

                market_lot_size_u = pos_summary_unr["market_lot"]
                closing_price_u = await get_closing_price(symbol, current_calc_date, expiry, opt_type, strike)

                if closing_price_u is not None:
                    unp_u = 0.0
                    if current_pos_net_lots > 0: # LONG
                        unp_u = (closing_price_u - pos_summary_unr["avg_entry_price"]) * current_pos_net_lots * market_lot_size_u
                    elif current_pos_net_lots < 0: # SHORT
                        unp_u = (pos_summary_unr["avg_entry_price"] - closing_price_u) * abs(current_pos_net_lots) * market_lot_size_u
                    
                    unrealised_map[date_str][combo] = {
                        "pnl": unp_u,
                        "lots": abs(current_pos_net_lots),
                        "closing_price": closing_price_u,
                        "avg_entry_price": pos_summary_unr["avg_entry_price"],
                        "market_lot": market_lot_size_u,
                        "position_type": position_type_str,
                        "daily_action": daily_action_str
                    }
                    logger.debug(f"    POST_TXN_UNR_PnL_CALC: {combo} {position_type_str} Lots:{current_pos_net_lots}, AvgEP:{pos_summary_unr['avg_entry_price']:.2f}, CP:{closing_price_u:.2f}, PnL:{unp_u:.2f}, Action:{daily_action_str}")
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
            # Sum PnL from all realization events for the day
            daily_realised_pnl_sum = sum(event["pnl_leg"] for events_list in realised_map[d_str].values() for event in events_list)
            
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
            for c, events_list in realised_map[d_str].items():
                for event_data in events_list:
                    # Each event_data is a dict from the list stored in realised_map
                    if event_data.get("lots_leg", 0) > 0:
                        closed_type = event_data.get("closed_position_type", "UNKNOWN")
                        contract_display_list = list(c) + [f"CLOSED_{closed_type}"]

                        ep_closed = event_data.get('entry_price_closed_portion')
                        exit_p = event_data.get('exit_price')
                        ev_lots = event_data.get('lots_leg')
                        ev_ml = event_data.get('market_lot')
                        pnl_calc_str_realised = "N/A"

                        if closed_type == "LONG": # Realized from selling a long
                            pnl_calc_str_realised = f"({exit_p:.2f} - {ep_closed:.2f}) * {ev_lots} * {ev_ml}"
                        elif closed_type == "SHORT": # Realized from buying back a short
                            pnl_calc_str_realised = f"({ep_closed:.2f} - {exit_p:.2f}) * {ev_lots} * {ev_ml}"

                        response_realised_list.append({
                            "contract": contract_display_list,
                            "lots": event_data["lots_leg"],
                            "pnl": round(event_data["pnl_leg"], 2),
                            "debug_info": {
                                "entry_price_closed": round(ep_closed, 2) if ep_closed is not None else None,
                                "exit_price": round(exit_p, 2) if exit_p is not None else None,
                                "market_lot": ev_ml,
                                "pnl_calculation": pnl_calc_str_realised
                            }
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









@router.get("/api/v1_0/strategy/simulation/monthly/{month}/{year}", status_code=status.HTTP_200_OK)
async def monthly_strategy_simulation(
    month: str,
    year: str,
    request: Request,
    response: Response,
    request_user_id: str = Header(None)
):
    """
    Simulates trading performance for a specific month, with all positions realized at month-end.
    
    Args:
        month: Month in "MM" format (e.g., "01" for January)
        year: Year in "YYYY" format (e.g., "2024")
        
    Returns:
        Daily PnL breakdown for the specified month with all positions realized on the last day.
    """
    try:
        logger.info(f"Starting monthly simulation for {month}/{year} for user {request_user_id}")
        
        # Validate month and year format
        if len(month) != 2 or not month.isdigit() or int(month) < 1 or int(month) > 12:
            raise HTTPException(status_code=400, detail="Month must be in MM format (e.g., '01') and between 01-12")
            
        if len(year) != 4 or not year.isdigit():
            raise HTTPException(status_code=400, detail="Year must be in YYYY format (e.g., '2024')")
        
        # Calculate start and end dates for the month
        month_int = int(month)
        year_int = int(year)
        
        # First day of the specified month
        start_date = date(year_int, month_int, 1)
        
        # Last day of the specified month
        if month_int == 12:
            next_month_start = date(year_int + 1, 1, 1)
        else:
            next_month_start = date(year_int, month_int + 1, 1)
        end_date = next_month_start - timedelta(days=1)
        
        logger.info(f"Monthly simulation period: {start_date} to {end_date}")
        
        # Get active positions before the start date
        positions_before_month = await execute_native_query(
            """
            SELECT * FROM user_transactions 
            WHERE user_id = %s AND status='active' AND trade_date < %s
            ORDER BY trade_date, transaction_time
            """,
            [request_user_id, start_date]
        )
        
        # Get transactions during the month
        positions_during_month = await execute_native_query(
            """
            SELECT * FROM user_transactions 
            WHERE user_id = %s AND status='active' AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date, transaction_time
            """,
            [request_user_id, start_date, end_date]
        )
        
        # Combine positions with those from before the month
        positions_raw = positions_before_month + positions_during_month
        
        if not positions_raw:
            return {
                "status": "success", 
                "message": f"No active positions for {month}/{year}", 
                "data": []
            }

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
                    "lots": int(txn_raw["lots"]),
                    "entry_price": float(txn_raw["entry_price"]),
                    "market_lot": int(txn_raw["market_lot"]),
                })
                all_trade_dates.add(current_trade_date)
                all_expiry_dates.add(current_expiry_date)
            except Exception as e:
                logger.error(f"Error processing transaction: {txn_raw}. Error: {e}")
                continue
        
        if not positions:
            return {
                "status": "success", 
                "message": f"No processable positions for {month}/{year}", 
                "data": []
            }

        # Set processing dates to be within the month
        earliest_processing_date = start_date
        latest_processing_date = end_date

        # --- Data Structures for Hybrid FIFO (Realized) + Average (Unrealized Net) ---
        position_layers = defaultdict(lambda: {"long": deque(), "short": deque()}) 
        open_positions = defaultdict(lambda: {"net_lots": 0, "avg_entry_price": 0.0, "market_lot": 0})
        unrealised_map = defaultdict(lambda: defaultdict(dict)) 
        realised_map = defaultdict(lambda: defaultdict(list))
        
        current_calc_date = earliest_processing_date
        position_idx = 0

        # --- Helper function to update open_position_summary based on position_layers ---
        def _update_open_position_summary(combo_key, current_market_lot_if_known=None):
            if combo_key not in position_layers and combo_key not in open_positions:
                return

            long_layers = position_layers[combo_key]["long"]
            short_layers = position_layers[combo_key]["short"]
            
            total_long_qty = sum(qty for _, qty in long_layers)
            total_short_qty = sum(qty for _, qty in short_layers)
            
            net_qty = total_long_qty - total_short_qty
            open_positions[combo_key]["net_lots"] = net_qty
            
            if current_market_lot_if_known is not None and current_market_lot_if_known != 0:
                open_positions[combo_key]["market_lot"] = current_market_lot_if_known

            if net_qty == 0:
                open_positions[combo_key]["avg_entry_price"] = 0.0
            elif net_qty > 0:  # Net long
                if total_long_qty > 0:
                    weighted_sum_price = sum(price * qty for price, qty in long_layers)
                    open_positions[combo_key]["avg_entry_price"] = weighted_sum_price / total_long_qty
                else:
                    open_positions[combo_key]["avg_entry_price"] = 0.0
            else:  # Net short
                if total_short_qty > 0:
                    weighted_sum_price = sum(price * qty for price, qty in short_layers)
                    open_positions[combo_key]["avg_entry_price"] = weighted_sum_price / total_short_qty
                else:
                    open_positions[combo_key]["avg_entry_price"] = 0.0
            
            logger.debug(f"    _update_open_position_summary for {combo_key}: NetLots: {open_positions[combo_key]['net_lots']}, AvgEP: {open_positions[combo_key]['avg_entry_price']:.2f}, MktLot: {open_positions[combo_key]['market_lot']}")

        # Simulate each day of the month
        while current_calc_date <= latest_processing_date:
            
            # Determine if we are processing a transaction day or a gap day
            next_txn_date = positions[position_idx]["trade_date"] if position_idx < len(positions) else None

            # --- Gap Filling Logic ---
            is_gap_fill_day = not next_txn_date or current_calc_date < next_txn_date
            
            if is_gap_fill_day:
                date_str = current_calc_date.strftime("%d-%b-%Y")
                logger.debug(f"GAP FILL Day: {date_str}")
                
                # Special handling for the last day of the month
                is_last_day_of_month = current_calc_date == end_date
                
                for combo, pos_details in open_positions.items():
                    symbol, opt_type, strike, expiry = combo
                    
                    if pos_details["net_lots"] == 0 or current_calc_date > expiry:
                        if pos_details["net_lots"] != 0 and current_calc_date > expiry:
                            # Realize expiring positions
                            unrealised_map[date_str][combo] = {
                                "pnl": 0.0, "lots": 0, "closing_price": 0.0,
                                "avg_entry_price": pos_details["avg_entry_price"],
                                "market_lot": pos_details["market_lot"],
                                "position_type": "LONG" if pos_details["net_lots"] > 0 else "SHORT",
                                "daily_action": "EXPIRED"
                            }
                        continue

                    market_lot_size = pos_details["market_lot"]
                    if market_lot_size == 0:
                        logger.warning(f"Market lot size is 0 for {combo} on {date_str}. Skipping unrealised PnL.")
                        continue
                    
                    closing_price = await get_closing_price(symbol, current_calc_date, expiry, opt_type, strike)
                    
                    if closing_price is not None:
                        unp = 0.0
                        position_type = "FLAT"
                        if pos_details["net_lots"] > 0:  # LONG
                            unp = (closing_price - pos_details["avg_entry_price"]) * pos_details["net_lots"] * market_lot_size
                            position_type = "LONG"
                        elif pos_details["net_lots"] < 0:  # SHORT
                            unp = (pos_details["avg_entry_price"] - closing_price) * abs(pos_details["net_lots"]) * market_lot_size
                            position_type = "SHORT"
                        
                        # Record unrealized PnL
                        unrealised_map[date_str][combo] = {
                            "pnl": unp,
                            "lots": abs(pos_details["net_lots"]),
                            "closing_price": closing_price,
                            "avg_entry_price": pos_details["avg_entry_price"],
                            "market_lot": market_lot_size,
                            "position_type": position_type,
                        }
                        
                        # On the last day of the month, realize all open positions
                        if is_last_day_of_month:
                            realised_map[date_str][combo].append({
                                "pnl_leg": unp,
                                "lots_leg": abs(pos_details["net_lots"]),
                                "exit_price": closing_price,
                                "entry_price_closed_portion": pos_details["avg_entry_price"],
                                "market_lot": market_lot_size,
                                "closed_position_type": position_type,
                                "reason": "MONTH_END_REALIZATION"
                            })
                            
                            # Update unrealized entry to show it was realized
                            unrealised_map[date_str][combo]["daily_action"] = "REALIZED_AT_MONTH_END"
                            
                            logger.info(f"    MONTH_END_REALIZED for {combo} {position_type}: PnL {unp:.2f} for {abs(pos_details['net_lots'])} lots @ {closing_price}")
                            
                            # Clear the position after realization
                            if position_type == "LONG":
                                position_layers[combo]["long"] = deque()
                            else:
                                position_layers[combo]["short"] = deque()
                            
                            open_positions[combo]["net_lots"] = 0
                            open_positions[combo]["avg_entry_price"] = 0.0
            
            else:
                # --- Transaction Processing Logic ---
                current_calc_date = next_txn_date
                date_str = current_calc_date.strftime("%d-%b-%Y")
                logger.debug(f"TRANSACTION Day: {date_str}")

                # Store net_lots from open_positions at the start of the transaction day
                net_lots_summary_at_start_of_day = {c: summary["net_lots"] for c, summary in open_positions.items()}
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
                    combos_transacted_today.add(contract_combo)
                    
                    # Set market lot in open_positions
                    open_positions[contract_combo]["market_lot"] = txn["market_lot"]
                    
                    txn_lots_signed = txn["lots"]
                    txn_price = txn["entry_price"]
                    market_lot = txn["market_lot"]
                    
                    logger.debug(f"  Processing TXN: {contract_combo}, TxnLots: {txn_lots_signed}, TxnPrice: {txn_price:.2f}")

                    if txn_lots_signed > 0:  # BUY Transaction
                        buy_lots_to_process = txn_lots_signed
                        
                        # Try to close/reduce existing short layers
                        short_layers_q = position_layers[contract_combo]["short"]
                        while short_layers_q and buy_lots_to_process > 0:
                            short_layer_price, short_layer_qty = short_layers_q[0]
                            lots_to_cover_from_layer = min(buy_lots_to_process, short_layer_qty)
                            
                            real_pnl = (short_layer_price - txn_price) * lots_to_cover_from_layer * market_lot
                            realised_map[date_str][contract_combo].append({
                                "pnl_leg": real_pnl, "lots_leg": lots_to_cover_from_layer, "exit_price": txn_price,
                                "entry_price_closed_portion": short_layer_price, "market_lot": market_lot,
                                "closed_position_type": "SHORT"
                            })
                            logger.info(f"    TXN_REALIZED (Cover Short): {contract_combo} Covered {lots_to_cover_from_layer} lots @ {txn_price:.2f} against short entry @ {short_layer_price:.2f}. PnL: {real_pnl:.2f}")

                            buy_lots_to_cover_from_layer -= lots_to_cover_from_layer
                            if lots_to_cover_from_layer == short_layer_qty:
                                short_layers_q.popleft()
                            else:
                                short_layers_q[0] = (short_layer_price, short_layer_qty - lots_to_cover_from_layer)
                    
                    elif txn_lots_signed < 0:  # SELL Transaction
                        sell_lots_to_process_abs = abs(txn_lots_signed)
                        
                        # Try to close/reduce existing LONG layers
                        long_layers_q = position_layers[contract_combo]["long"]
                        while long_layers_q and sell_lots_to_process_abs > 0:
                            long_layer_price, long_layer_qty = long_layers_q[0]
                            lots_to_close_from_layer = min(sell_lots_to_process_abs, long_layer_qty)

                            real_pnl = (txn_price - long_layer_price) * lots_to_close_from_layer * market_lot
                            realised_map[date_str][contract_combo].append({
                                "pnl_leg": real_pnl, "lots_leg": lots_to_close_from_layer, "exit_price": txn_price,
                                "entry_price_closed_portion": long_layer_price, "market_lot": market_lot,
                                "closed_position_type": "LONG"
                            })
                            logger.info(f"    TXN_REALIZED (Close Long): {contract_combo} Closed {lots_to_close_from_layer} LONG lots @ {txn_price:.2f} against entry @ {long_layer_price:.2f}. PnL: {real_pnl:.2f}")
                        
                        # If SELL lots still remain (abs), add to SHORT layers
                        if sell_lots_to_process_abs > 0:
                            position_layers[contract_combo]["short"].append((txn_price, sell_lots_to_process_abs))
                            logger.info(f"    TXN_OPEN/ADD_SHORT: {contract_combo} Added {sell_lots_to_process_abs} SHORT lots @ {txn_price:.2f}")
                
                # Update the summary
                _update_open_position_summary(contract_combo, market_lot)
            
            # --- Post-Transaction/Daily Unrealised PnL Update for current_calc_date ---
            logger.debug(f"  POST_TXN_UNR_PnL_UPDATE Start for Date: {date_str}")
            
            # Special handling for the last day of the month
            is_last_day_of_month = current_calc_date == end_date
            
            all_relevant_combos = set(open_positions.keys()) | set(position_layers.keys())
            
            for combo in all_relevant_combos:
                _update_open_position_summary(combo)
                pos_summary = open_positions[combo]
                symbol, opt_type, strike, expiry = combo
                
                current_pos_net_lots = pos_summary["net_lots"]
                lots_before_today = net_lots_summary_at_start_of_day.get(combo, 0)
                
                # Determine daily action
                daily_action_str = "NO_CHANGE"
                if combo in combos_transacted_today or lots_before_today != current_pos_net_lots:
                    if lots_before_today == 0 and current_pos_net_lots != 0:
                        daily_action_str = "NEW_SHORT" if current_pos_net_lots < 0 else "NEW_LONG"
                    elif current_pos_net_lots > lots_before_today and lots_before_today >= 0:
                        daily_action_str = "ADDED_TO_LONG" if lots_before_today > 0 else ("FLIPPED_TO_LONG" if lots_before_today < 0 else "NEW_LONG")
                    elif current_pos_net_lots < lots_before_today and lots_before_today <= 0:
                        daily_action_str = "ADDED_TO_SHORT" if lots_before_today < 0 else ("FLIPPED_TO_SHORT" if lots_before_today > 0 else "NEW_SHORT")
                    elif abs(current_pos_net_lots) < abs(lots_before_today):
                        if current_pos_net_lots == 0:
                            daily_action_str = "CLOSED_SHORT" if lots_before_today < 0 else "CLOSED_LONG"
                        else: # Reduced
                            daily_action_str = "REDUCED_SHORT" if current_pos_net_lots < 0 else "REDUCED_LONG"
                    elif current_pos_net_lots == lots_before_today and current_pos_net_lots != 0 and combo in combos_transacted_today:
                        daily_action_str = "MODIFIED_NO_NET_LOT_CHANGE"
                
                position_type_str = "FLAT"
                if current_pos_net_lots > 0: position_type_str = "LONG"
                elif current_pos_net_lots < 0: position_type_str = "SHORT"

                # Handle expiry
                if current_calc_date > expiry and current_pos_net_lots != 0:
                    expiry_pnl = 0
                    if current_pos_net_lots > 0:  # Expired Long
                        expiry_pnl = (0 - pos_summary["avg_entry_price"]) * current_pos_net_lots * pos_summary["market_lot"]
                    elif current_pos_net_lots < 0:  # Expired Short
                        expiry_pnl = (pos_summary["avg_entry_price"] - 0) * abs(current_pos_net_lots) * pos_summary["market_lot"]
                    
                    realised_map[date_str][combo].append({
                        "pnl_leg": expiry_pnl,
                        "lots_leg": abs(current_pos_net_lots),
                        "exit_price": 0,
                        "entry_price_closed_portion": pos_summary["avg_entry_price"],
                        "market_lot": pos_summary["market_lot"],
                        "closed_position_type": "LONG" if current_pos_net_lots > 0 else "SHORT",
                        "reason": "EXPIRY"
                    })
                    
                    open_positions[combo]["net_lots"] = 0
                    open_positions[combo]["avg_entry_price"] = 0.0
                    
                    unrealised_map[date_str][combo] = {
                        "pnl": 0.0,
                        "lots": 0,
                        "closing_price": 0.0,
                        "avg_entry_price": 0.0,
                        "market_lot": pos_summary["market_lot"],
                        "position_type": position_type_str,
                        "daily_action": "EXPIRED"
                    }
                    continue

                # Skip if no position
                if current_pos_net_lots == 0:
                    if combo in combos_transacted_today:
                        unrealised_map[date_str][combo] = {
                            "pnl": 0.0,
                            "lots": 0,
                            "closing_price": None,
                            "avg_entry_price": 0.0,
                            "market_lot": pos_summary.get("market_lot", 0),
                            "position_type": "FLAT",
                            "daily_action": daily_action_str
                        }
                    continue

                # Get closing price and calculate unrealized PnL
                market_lot_size = pos_summary["market_lot"]
                closing_price = await get_closing_price(symbol, current_calc_date, expiry, opt_type, strike)

                if closing_price is not None:
                    unp = 0.0
                    if current_pos_net_lots > 0:  # LONG
                        unp = (closing_price - pos_summary["avg_entry_price"]) * current_pos_net_lots * market_lot_size
                    elif current_pos_net_lots < 0:  # SHORT
                        unp = (pos_summary["avg_entry_price"] - closing_price) * abs(current_pos_net_lots) * market_lot_size
                    
                    # Record unrealized PnL
                    unrealised_map[date_str][combo] = {
                        "pnl": unp,
                        "lots": abs(current_pos_net_lots),
                        "closing_price": closing_price,
                        "avg_entry_price": pos_summary["avg_entry_price"],
                        "market_lot": market_lot_size,
                        "position_type": position_type_str,
                        "daily_action": daily_action_str
                    }
                    
                    # On the last day of the month, realize all open positions
                    if is_last_day_of_month:
                        realised_map[date_str][combo].append({
                            "pnl_leg": unp,
                            "lots_leg": abs(current_pos_net_lots),
                            "exit_price": closing_price,
                            "entry_price_closed_portion": pos_summary["avg_entry_price"],
                            "market_lot": market_lot_size,
                            "closed_position_type": position_type_str,
                            "reason": "MONTH_END_REALIZATION"
                        })
                        
                        # Update unrealized entry to show it was realized
                        unrealised_map[date_str][combo]["daily_action"] = "REALIZED_AT_MONTH_END"
                        
                        logger.info(f"    MONTH_END_REALIZED for {combo} {position_type_str}: PnL {unp:.2f} for {abs(current_pos_net_lots)} lots @ {closing_price}")
                        
                        # Clear the position after realization
                        if position_type_str == "LONG":
                            position_layers[combo]["long"] = deque()
                        else:
                            position_layers[combo]["short"] = deque()
                        
                        open_positions[combo]["net_lots"] = 0
                        open_positions[combo]["avg_entry_price"] = 0.0

            # Move to the next day
            current_calc_date += timedelta(days=1)

        # Build response
        out = []
        all_pnl_dates_str = sorted(
            set(list(unrealised_map.keys()) + list(realised_map.keys())),
            key=lambda d_str: datetime.strptime(d_str, "%d-%b-%Y").date()
        )
        
        cumulative_realized_pnl = 0.0

        # Only include dates within our target month
        month_dates_str = [d for d in all_pnl_dates_str if 
                        start_date <= datetime.strptime(d, "%d-%b-%Y").date() <= end_date]

        for d_str in month_dates_str:
            daily_unrealised_pnl_sum = sum(data.get("pnl", 0) for data in unrealised_map[d_str].values() 
                                       if data.get("closing_price") is not None or data.get("daily_action") == "EXPIRED")
            
            # Sum PnL from all realization events for the day
            daily_realised_pnl_sum = sum(event["pnl_leg"] for events_list in realised_map[d_str].values() for event in events_list)
            
            cumulative_realized_pnl += daily_realised_pnl_sum
            
            response_unrealised_list = []
            for c, p_data in unrealised_map[d_str].items():
                # Only include if PnL was calculated or significant action
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
                        "pnl": round(p_data.get("pnl", 0), 2)
                    })

            response_realised_list = []
            for c, events_list in realised_map[d_str].items():
                for event_data in events_list:
                    if event_data.get("lots_leg", 0) > 0:
                        closed_type = event_data.get("closed_position_type", "UNKNOWN")
                        contract_display_list = list(c) + [f"CLOSED_{closed_type}"]

                        ep_closed = event_data.get('entry_price_closed_portion')
                        exit_p = event_data.get('exit_price')
                        ev_lots = event_data.get('lots_leg')
                        ev_ml = event_data.get('market_lot')
                        pnl_calc_str_realised = "N/A"

                        if closed_type == "LONG": # Realized from selling a long
                            pnl_calc_str_realised = f"({exit_p:.2f} - {ep_closed:.2f}) * {ev_lots} * {ev_ml}"
                        elif closed_type == "SHORT": # Realized from buying back a short
                            pnl_calc_str_realised = f"({ep_closed:.2f} - {exit_p:.2f}) * {ev_lots} * {ev_ml}"

                        response_realised_list.append({
                            "contract": contract_display_list,
                            "lots": event_data["lots_leg"],
                            "pnl": round(event_data["pnl_leg"], 2),
                            "debug_info": {
                                "entry_price_closed": round(ep_closed, 2) if ep_closed is not None else None,
                                "exit_price": round(exit_p, 2) if exit_p is not None else None,
                                "market_lot": ev_ml,
                                "pnl_calculation": pnl_calc_str_realised
                            }
                        })

            out.append({
                "date": d_str,
                "unrealised": response_unrealised_list,
                "realised": response_realised_list,
                "total_unrealised_pnl": round(daily_unrealised_pnl_sum, 2),
                "total_realized_pnl": round(daily_realised_pnl_sum, 2),
                "cumulative_total_realized_pnl": round(cumulative_realized_pnl, 2)
            })
        
        # Add month summary
        month_total_realized = sum(day["total_realized_pnl"] for day in out)
        month_unrealized_at_end = out[-1]["total_unrealised_pnl"] if out else 0
        
        final_summary = {
            "month": f"{year}-{month}",
            "month_name": date(year_int, month_int, 1).strftime("%B %Y"),
            "month_total_realized_pnl": round(month_total_realized, 2),
            "unrealized_at_month_end": month_unrealized_at_end,
            "positions_at_month_end": 0,  # All positions are realized at month end
            "days_with_activity": len(out),
            "data": out
        }
        
        logger.info(f"Successfully completed monthly simulation for {month}/{year}, user {request_user_id}")
        return {"status": "success", "summary": final_summary}
        
    except Exception as e:
        logger.exception(f"Error in monthly_strategy_simulation for month {month}/{year}, user {request_user_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/api/v1_0/strategy/monthly_volatility_simulation/{month}/{year}", status_code=status.HTTP_200_OK)
async def monthly_volatility_simulation(
    month: str,
    year: str,
    request: Request,
    response: Response,
    request_user_id: str = Header(None)
):
    """
    Simulates PnL for the four volatility-based positions of a specific month.
    
    This API finds the four strikes (two spot-based, two volatility-based) created by 
    the volatility_of_month API for the specified month and year, then simulates 
    the daily P&L from the first trading day to the last trading day of the month.
    All positions are realized on the last trading day.
    
    Args:
        month: Month in "MM" format (e.g., "01" for January)
        year: Year in "YY" format (e.g., "24" for 2024)
        
    Returns:
        Daily P&L breakdown and total realized P&L at month-end
    """
    try:
        logger.info(f"Starting monthly volatility simulation for {month}/{year}, user {request_user_id}")
        
        # Validate month and year format
        if len(month) != 2 or not month.isdigit() or int(month) < 1 or int(month) > 12:
            raise HTTPException(status_code=400, detail="Month must be in MM format (e.g., '01') and between 01-12")
            
        if not year.isdigit() or (len(year) != 2 and len(year) != 4):
            raise HTTPException(status_code=400, detail="Year must be in YY format (e.g., '24') or YYYY format (e.g., '2024')")
        
        # Convert to proper format
        full_year = year if len(year) == 4 else f"20{year}"
        month_int = int(month)
        year_int = int(full_year)
        
        # Calculate target month dates
        start_date = date(year_int, month_int, 1)
        if month_int == 12:
            next_month_start = date(year_int + 1, 1, 1)
        else:
            next_month_start = date(year_int, month_int + 1, 1)
        end_date = next_month_start - timedelta(days=1)
        
        logger.info(f"Target month: {start_date} to {end_date}")
        
        # Step 1: Find the four specific volatility-based options for this month
        # These were created by the volatility_of_month API
        volatility_positions = await execute_native_query(
            """
            SELECT * FROM user_transactions 
            WHERE user_id = %s 
              AND YEAR(trade_date) = %s 
              AND MONTH(trade_date) = %s
              AND status='active'
              AND instrument='OPTIDX'
            ORDER BY transaction_time
            LIMIT 4
            """,
            [request_user_id, year_int, month_int]
        )
        
        if not volatility_positions or len(volatility_positions) < 4:
            logger.warning(f"Found fewer than 4 volatility positions: {len(volatility_positions) if volatility_positions else 0}")
            # Try a more lenient query if exact 4 positions aren't found
            volatility_positions = await execute_native_query(
                """
                SELECT * FROM user_transactions 
                WHERE user_id = %s 
                  AND trade_date >= %s
                  AND trade_date <= %s
                  AND status='active'
                  AND instrument='OPTIDX'
                ORDER BY trade_date, transaction_time
                """,
                [request_user_id, start_date, end_date]
            )
        
        if not volatility_positions:
            return {
                "status": "error", 
                "message": f"No volatility positions found for {month}/{year}",
                "data": []
            }
        
        logger.info(f"Found {len(volatility_positions)} volatility positions for month {month}/{year}")
        
        # Step 2: Format the position data for processing
        positions = []
        
        for txn_raw in volatility_positions:
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
                    "lots": int(txn_raw["lots"]),
                    "entry_price": float(txn_raw["entry_price"]),
                    "market_lot": int(txn_raw["market_lot"]),
                })
            except Exception as e:
                logger.error(f"Error processing transaction: {txn_raw}. Error: {e}")
                continue
        
        # Log the positions we'll be simulating
        for pos in positions:
            logger.info(f"Position: {pos['symbol']} {pos['strike_price']} {pos['option_type']} x {pos['lots']} lots")
        
        # Get the first and last trading day of the month from the positions
        position_trade_dates = [p["trade_date"] for p in positions]
        first_trade_date = min(position_trade_dates) if position_trade_dates else start_date
        
        # Step 3: Find all trading days in the month for simulation
        # Get calendar days from first trade date to end of month
        current_date = first_trade_date
        calendar_days = []
        while current_date <= end_date:
            calendar_days.append(current_date)
            current_date += timedelta(days=1)
        
        # Step 4: Set up data structures for the simulation
        position_layers = defaultdict(lambda: {"long": deque(), "short": deque()})
        open_positions = defaultdict(lambda: {"net_lots": 0, "avg_entry_price": 0.0, "market_lot": 0})
        daily_pnl = {}
        
        # Helper function to update open position summary
        def update_open_position_summary(combo_key, position_layers, open_positions):
            if combo_key not in position_layers:
                return
            
            long_layers = position_layers[combo_key]["long"]
            short_layers = position_layers[combo_key]["short"]
            
            total_long_qty = sum(qty for _, qty in long_layers)
            total_short_qty = sum(qty for _, qty in short_layers)
            
            net_qty = total_long_qty - total_short_qty
            open_positions[combo_key]["net_lots"] = net_qty
            
            if net_qty == 0:
                open_positions[combo_key]["avg_entry_price"] = 0.0
            elif net_qty > 0:  # Net long
                if total_long_qty > 0:
                    weighted_sum_price = sum(price * qty for price, qty in long_layers)
                    open_positions[combo_key]["avg_entry_price"] = weighted_sum_price / total_long_qty
                else:
                    open_positions[combo_key]["avg_entry_price"] = 0.0
            else:  # Net short
                if total_short_qty > 0:
                    weighted_sum_price = sum(price * qty for price, qty in short_layers)
                    open_positions[combo_key]["avg_entry_price"] = weighted_sum_price / total_short_qty
                else:
                    open_positions[combo_key]["avg_entry_price"] = 0.0
        
        # Initialize position layers from the volatility positions
        for pos in positions:
            combo_key = (pos["symbol"], pos["option_type"], pos["strike_price"], pos["expiry_date"])
            
            # Set market lot
            open_positions[combo_key]["market_lot"] = pos["market_lot"]
            
            # Add to appropriate layer based on long/short
            if pos["lots"] > 0:  # Long position
                position_layers[combo_key]["long"].append((pos["entry_price"], pos["lots"]))
            elif pos["lots"] < 0:  # Short position
                position_layers[combo_key]["short"].append((pos["entry_price"], abs(pos["lots"])))
            
            # Update open position summary
            update_open_position_summary(combo_key, position_layers, open_positions)
        
        # Step 5: Simulate each day's PnL
        cumulative_realized_pnl = 0.0
        
        for sim_date in calendar_days:
            date_str = sim_date.strftime("%d-%b-%Y")
            logger.debug(f"Simulating day: {date_str}")
            
            # Check if this is the last trading day of the month
            is_last_day = sim_date == end_date
            
            # Track daily unrealized and realized PnL
            unrealised_pnl_entries = {}
            realised_pnl_entries = defaultdict(list)
            
            # Process each position
            for combo, pos_details in open_positions.items():
                symbol, opt_type, strike, expiry = combo
                
                # Skip if position is flat or expired
                if pos_details["net_lots"] == 0 or sim_date > expiry:
                    if pos_details["net_lots"] != 0 and sim_date > expiry:
                        # Handle expiry (position expires worthless)
                        logger.info(f"Position expired: {symbol} {strike} {opt_type}")
                        
                        # Record realized PnL at expiration (all premium is kept/lost)
                        expiry_pnl = 0
                        if pos_details["net_lots"] > 0:  # Long expired worthless
                            expiry_pnl = (0 - pos_details["avg_entry_price"]) * pos_details["net_lots"] * pos_details["market_lot"]
                        else:  # Short expired worthless
                            expiry_pnl = (pos_details["avg_entry_price"] - 0) * abs(pos_details["net_lots"]) * pos_details["market_lot"]
                        
                        realised_pnl_entries[combo].append({
                            "pnl": expiry_pnl,
                            "lots": abs(pos_details["net_lots"]),
                            "exit_price": 0,
                            "entry_price": pos_details["avg_entry_price"],
                            "reason": "EXPIRY"
                        })
                        
                        cumulative_realized_pnl += expiry_pnl
                        
                        # Clear position
                        position_layers[combo] = {"long": deque(), "short": deque()}
                        open_positions[combo]["net_lots"] = 0
                        open_positions[combo]["avg_entry_price"] = 0.0
                    
                    continue
                
                # Get option closing price for this date
                closing_price = await get_closing_price(symbol, sim_date, expiry, opt_type, strike)
                
                if closing_price is not None:
                    # Calculate unrealized PnL
                    unp = 0.0
                    position_type = "FLAT"
                    
                    if pos_details["net_lots"] > 0:  # LONG
                        unp = (closing_price - pos_details["avg_entry_price"]) * pos_details["net_lots"] * pos_details["market_lot"]
                        position_type = "LONG"
                    elif pos_details["net_lots"] < 0:  # SHORT
                        unp = (pos_details["avg_entry_price"] - closing_price) * abs(pos_details["net_lots"]) * pos_details["market_lot"]
                        position_type = "SHORT"
                    
                    # Record unrealized PnL
                    unrealised_pnl_entries[combo] = {
                        "pnl": unp,
                        "lots": abs(pos_details["net_lots"]),
                        "closing_price": closing_price,
                        "avg_entry_price": pos_details["avg_entry_price"],
                        "market_lot": pos_details["market_lot"],
                        "position_type": position_type
                    }
                    
                    # If last day of month, realize the position
                    if is_last_day:
                        logger.info(f"Realizing position at month-end: {symbol} {strike} {opt_type}")
                        
                        # Record realized PnL
                        realised_pnl_entries[combo].append({
                            "pnl": unp,
                            "lots": abs(pos_details["net_lots"]),
                            "exit_price": closing_price,
                            "entry_price": pos_details["avg_entry_price"],
                            "reason": "MONTH_END_REALIZATION"
                        })
                        
                        cumulative_realized_pnl += unp
                        
                        # Update unrealized entry to show realization
                        unrealised_pnl_entries[combo]["realized_at_month_end"] = True
                        
                        # Clear position layers
                        position_layers[combo] = {"long": deque(), "short": deque()}
                        open_positions[combo]["net_lots"] = 0
                        open_positions[combo]["avg_entry_price"] = 0.0
            
            # Calculate daily totals
            daily_unrealized_pnl = sum(entry["pnl"] for entry in unrealised_pnl_entries.values() if "closing_price" in entry)
            daily_realized_pnl = sum(entry["pnl"] for entries in realised_pnl_entries.values() for entry in entries)
            
            # Store daily PnL information
            daily_pnl[date_str] = {
                "date": date_str,
                "unrealised": [
                    {
                        "contract": [
                            symbol,
                            opt_type,
                            strike,
                            expiry.strftime("%Y-%m-%d"),
                            position_type
                        ],
                        "lots": data["lots"],
                        "daily_action": None,  # We don't track daily actions here, but matching format
                        "debug_info": {
                            "entry_price": round(data["avg_entry_price"], 2),
                            "closing_price": data["closing_price"],
                            "market_lot": data["market_lot"],
                            "pnl_calculation": (
                                f"({data['closing_price']} - {round(data['avg_entry_price'], 2)}) * {data['lots']} * {data['market_lot']}" 
                                if data["position_type"] == "LONG" else 
                                f"({round(data['avg_entry_price'], 2)} - {data['closing_price']}) * {data['lots']} * {data['market_lot']}"
                            )
                        },
                        "pnl": round(data["pnl"], 2)
                    }
                    for combo, data in unrealised_pnl_entries.items()
                    if "closing_price" in data
                    for symbol, opt_type, strike, expiry in [combo]
                    for position_type in [data["position_type"]]
                ],
                "realised": [
                    {
                        "contract": [
                            symbol,
                            opt_type,
                            strike,
                            expiry.strftime("%Y-%m-%d"),
                            f"CLOSED_{position_type}" 
                        ],
                        "lots": entry["lots"],
                        "pnl": round(entry["pnl"], 2),
                        "debug_info": {
                            "entry_price_closed": round(entry["entry_price"], 2),
                            "exit_price": round(entry["exit_price"], 2) if entry["exit_price"] is not None else None,
                            "market_lot": pos_details["market_lot"],
                            "pnl_calculation": (
                                f"({round(entry['exit_price'], 2)} - {round(entry['entry_price'], 2)}) * {entry['lots']} * {pos_details['market_lot']}"
                                if position_type == "LONG" else
                                f"({round(entry['entry_price'], 2)} - {round(entry['exit_price'], 2)}) * {entry['lots']} * {pos_details['market_lot']}"
                            )
                        }
                    }
                    for combo, entries in realised_pnl_entries.items()
                    for symbol, opt_type, strike, expiry in [combo]
                    for entry in entries
                    for pos_details in [open_positions[combo]]
                    for position_type in ["LONG" if entry.get("reason") == "EXPIRY" and entry["pnl"] < 0 else
                                       "SHORT" if entry.get("reason") == "EXPIRY" and entry["pnl"] >= 0 else
                                       entry.get("closed_position_type", "UNKNOWN")]
                ],
                "total_unrealised_pnl": round(daily_unrealized_pnl, 2),
                "total_realized_pnl": round(daily_realized_pnl, 2),
                "cumulative_total_realized_pnl": round(cumulative_realized_pnl, 2)
            }
        
        # Step 6: Build the final response
        # Sort dates for consistent ordering
        sorted_dates = sorted(daily_pnl.keys(), key=lambda d_str: datetime.strptime(d_str, "%d-%b-%Y").date())
        
        out = []
        for date_str in sorted_dates:
            out.append(daily_pnl[date_str])
        
        # Create month summary
        month_name = start_date.strftime("%B %Y")
        month_total_realized = sum(day["total_realized_pnl"] for day in out)
        
        summary = {
            "month": f"{year_int}-{month_int:02d}",
            "month_name": month_name,
            "strategy_type": "Monthly Volatility",
            "num_positions": len(positions),
            "total_realized_pnl": round(month_total_realized, 2),
            "first_trading_day": first_trade_date.strftime("%Y-%m-%d"),
            "last_trading_day": end_date.strftime("%Y-%m-%d"),
            "positions": [
                {
                    "symbol": pos["symbol"],
                    "strike": pos["strike_price"],
                    "option_type": pos["option_type"],
                    "lots": pos["lots"],
                    "entry_price": pos["entry_price"],
                    "trade_date": pos["trade_date"].strftime("%Y-%m-%d"),
                    "expiry_date": pos["expiry_date"].strftime("%Y-%m-%d")
                } for pos in positions
            ],
            "daily_pnl": out
        }
        
        logger.info(f"Completed monthly volatility simulation for {month}/{year}. Total realized PnL: {month_total_realized:.2f}")
        return {"status": "success", "data": summary}
        
    except Exception as e:
        logger.exception(f"Error in monthly_volatility_simulation: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
