from tortoise import Tortoise 
from app.config import DATABASES


async def init_db():
    await Tortoise.init(config=DATABASES)
    # Generate the schema
    await Tortoise.generate_schemas()
    print("Database initialized")


async def close_db():
    await Tortoise.close_connections()