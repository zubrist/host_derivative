from fastapi import HTTPException, status, Request, Response, Header
from db.models.users import Users, UserTransactions
from services.nse_service import get_option_data_with_cache
from datetime import datetime
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class TransactionCreate:
    def __init__(self, symbol, strike_price, option_type, lots, trade_date, expiry_date, instrument):
        self.symbol = symbol
        self.strike_price = strike_price
        self.option_type = option_type
        self.lots = lots
        self.trade_date = trade_date
        self.expiry_date = expiry_date
        self.instrument = instrument

async def create_single_transaction_with_cache(
    trans_payload: TransactionCreate,
    request_user_id: str
) -> Dict[str, Any]:
    """
    Create a single transaction using cache-first approach for data fetching
    """
    try:
        # Validate user
        if not request_user_id:
            return {
                "status": "failed",
                "strike": trans_payload.strike_price,
                "type": trans_payload.option_type,
                "lots": trans_payload.lots,
                "error": "request-user-id header is required"
            }

        user_id = int(request_user_id)
        user = await Users.get_or_none(user_id=user_id)
        if not user:
            return {
                "status": "failed",
                "strike": trans_payload.strike_price,
                "type": trans_payload.option_type,
                "lots": trans_payload.lots,
                "error": "User not found"
            }
        
        # Date Conversion
        try:
            trade_date_obj = datetime.strptime(trans_payload.trade_date, '%Y-%m-%d').date()
            expiry_date_obj = datetime.strptime(trans_payload.expiry_date, '%Y-%m-%d').date()
        except ValueError as e:
            return {
                "status": "failed",
                "strike": trans_payload.strike_price,
                "type": trans_payload.option_type,
                "lots": trans_payload.lots,
                "error": f"Invalid date format: {str(e)}"
            }
        
        # Use cache-first approach to fetch entry price
        logger.info(f"Fetching data for {trans_payload.symbol} {trans_payload.strike_price} {trans_payload.option_type}")
        
        nse_data = await get_option_data_with_cache(
            symbol=trans_payload.symbol,
            from_date=trade_date_obj,
            to_date=expiry_date_obj,
            expiry_date=expiry_date_obj,
            option_type=trans_payload.option_type,
            strike_price=trans_payload.strike_price
        )
        
        if not nse_data or not isinstance(nse_data, list):
            return {
                "status": "failed",
                "strike": trans_payload.strike_price,
                "type": trans_payload.option_type,
                "lots": trans_payload.lots,
                "error": f"Could not fetch data from cache or NSE"
            }

        # Find the record for the trade date
        entry_price = None
        market_lot = None
        for record in nse_data:
            if 'FH_TIMESTAMP' in record:
                try:
                    record_date = datetime.strptime(record['FH_TIMESTAMP'], '%d-%b-%Y').date()
                except Exception:
                    continue
                if record_date == trade_date_obj:
                    entry_price = float(record.get('FH_CLOSING_PRICE', 0))
                    market_lot = record.get('FH_MARKET_LOT', 75)  # Default to 75
                    break
                    
        if entry_price is None or entry_price == 0:
            return {
                "status": "failed",
                "strike": trans_payload.strike_price,
                "type": trans_payload.option_type,
                "lots": trans_payload.lots,
                "error": f"No FH_CLOSING_PRICE found for trade date {trade_date_obj}"
            }

        # Insert into user_transactions
        txn = await UserTransactions.create(
            user=user,
            symbol=trans_payload.symbol,
            instrument=trans_payload.instrument,
            strike_price=trans_payload.strike_price,
            option_type=trans_payload.option_type,
            lots=trans_payload.lots,
            trade_date=trade_date_obj,
            expiry_date=expiry_date_obj,
            entry_price=entry_price,
            market_lot=market_lot,
            status='active'
        )

        logger.info(f"Successfully created transaction for {trans_payload.symbol} {trans_payload.strike_price} {trans_payload.option_type}")
        
        return {
            "status": "success",
            "transaction_id": txn.transaction_id,
            "entry_price": entry_price,
            "strike": trans_payload.strike_price,
            "type": trans_payload.option_type,
            "lots": trans_payload.lots
        }

    except Exception as e:
        logger.error(f"Error creating transaction for {trans_payload.strike_price} {trans_payload.option_type}: {str(e)}", exc_info=True)
        return {
            "status": "failed",
            "strike": trans_payload.strike_price,
            "type": trans_payload.option_type,
            "lots": trans_payload.lots,
            "error": str(e)
        }

async def create_transactions_batch_concurrent(
    option_payloads: List[Dict[str, Any]], 
    request_user_id: str, 
    batch_size: int = 5  # Reduced batch size for first run
) -> List[Dict[str, Any]]:
    """
    Create multiple transactions concurrently in batches
    """
    all_results = []
    
    logger.info(f"Starting batch transaction creation for {len(option_payloads)} transactions")
    
    # Process in smaller batches for first run (when cache is empty)
    for i in range(0, len(option_payloads), batch_size):
        batch = option_payloads[i:i + batch_size]
        batch_num = i // batch_size + 1
        
        logger.info(f"Processing batch {batch_num}: {len(batch)} transactions")
        
        # Create TransactionCreate objects for this batch
        transaction_payloads = []
        for option in batch:
            trans_payload = TransactionCreate(
                symbol=option["symbol"],
                strike_price=option["strike_price"],
                option_type=option["option_type"],
                lots=option["lots"],
                trade_date=option["trade_date"],
                expiry_date=option["expiry_date"],
                instrument=option["instrument"]
            )
            transaction_payloads.append(trans_payload)
        
        # Create tasks for concurrent execution
        tasks = [
            create_single_transaction_with_cache(trans_payload, request_user_id)
            for trans_payload in transaction_payloads
        ]
        
        # Execute batch concurrently with longer timeout for first run
        try:
            batch_results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=300  # 5 minutes timeout per batch (increased for first run)
            )
            
            # Process results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Exception in batch {batch_num}, item {j}: {result}")
                    all_results.append({
                        "status": "failed",
                        "strike": batch[j]["strike_price"],
                        "type": batch[j]["option_type"],
                        "lots": batch[j]["lots"],
                        "error": str(result)
                    })
                else:
                    all_results.append(result)
                    
        except asyncio.TimeoutError:
            logger.error(f"Batch {batch_num} timed out after 5 minutes")
            # Add failed entries for the batch
            for option in batch:
                all_results.append({
                    "status": "failed",
                    "strike": option["strike_price"],
                    "type": option["option_type"],
                    "lots": option["lots"],
                    "error": f"Batch {batch_num} timeout (5 minutes)"
                })
        
        # Longer delay between batches for first run
        if i + batch_size < len(option_payloads):
            await asyncio.sleep(5)  # 5 second delay between batches
    
    # Log summary
    successful_count = len([r for r in all_results if r.get("status") == "success"])
    failed_count = len([r for r in all_results if r.get("status") == "failed"])
    logger.info(f"Transaction creation completed - Success: {successful_count}, Failed: {failed_count}")
    
    return all_results