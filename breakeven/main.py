import os
from fastapi import FastAPI
from tortoise.contrib.fastapi import register_tortoise
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()  # Load environment variables *before* anything else

# from routers import nse
# from routers import users
# from routers import test
# from routers import test2
# from routers import option_performance

from routers import break_even
from routers import implied_volatility
# from routers import safestrike

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only. Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    register_tortoise(
        app,
        db_url=os.environ.get('DB_CONFIG'),
        modules={'models': ['db.models.break_even']},
        generate_schemas=True,
        add_exception_handlers=True,
    )
except Exception as e:
    print(f"Failed to connect to the database: {e}")

# app.include_router(nse.router)
# app.include_router(users.router)
# app.include_router(test.router)
# app.include_router(test2.router)
# app.include_router(option_performance.router)

app.include_router(break_even.router)
app.include_router(implied_volatility.router)
# app.include_router(safestrike.router)