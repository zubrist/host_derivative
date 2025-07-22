from tortoise import Tortoise 
from tortoise.transactions import in_transaction
import logging
from fastapi import HTTPException

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def execute_native_query(query: str , params: None):

    connection = Tortoise.get_connection('default')

    async with in_transaction():
        results = await connection.execute_query_dict(query, params)
    return results    




async def insert_into_table(table_name: str, data: list):
    """
    Inserts new data into the appropriate table.
    """
    try:
        connection = Tortoise.get_connection("default")
        async with in_transaction(connection):
            for row in data:
                columns = ", ".join(row.keys())
                placeholders = ", ".join(["%s"] * len(row))
                values = list(row.values())

                query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                logger.info(f"Inserting into {table_name}: {query} with values: {values}")
                await connection.execute_query(query, values)

        logger.info(f"✅ Successfully inserted data into {table_name}")
    except Exception as e:
        logger.exception(f"❌ Failed to insert data: {e}")
        raise HTTPException(status_code=500, detail="Database insert failed.")
    


class PositionQueue:
    def __init__(self):
        self.queue = []

    def add_buy(self, price, lots):
        self.queue.extend([price] * lots)

    def current_lots(self):
        return len(self.queue)

    def average_price(self):
        return round(sum(self.queue) / len(self.queue), 2) if self.queue else 0.0

    def unrealized_pnl(self, ltp, lot_size):
        avg_price = self.average_price()
        return round((ltp - avg_price) * self.current_lots() * lot_size, 2)
