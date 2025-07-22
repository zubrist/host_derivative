# import os
# from dotenv import load_dotenv
# from pydantic import BaseSettings

# # Load environment variables from .env file
# load_dotenv()

# class Settings(BaseSettings):
#     # Auth
#     #AUTH0_DOMAIN: str = os.getenv("AUTH0_DOMAIN")   
#     ACCESS_TOKEN_DEFAULT_EXPIRES_MINUTES: int = 360
#     NSE_SERVICE_URL : str = os.getenv("NSE_SERVICE_URL")
#     #NSE_SERVICE_URL: str = os.environ.get("NSE_SERVICE_URL") # if above doesnot work use this
#     GATEWAY_TIMEOUT: int = 59

# settings = Settings() 

from pydantic import BaseSettings

class Settings(BaseSettings):
    DB_CONFIG: str
    BREAKEVEN_SERVICE_URL: str

    class Config:
        # The environment file to load configuration from
        env_file = ".env"
        # The encoding of the environment file
        env_file_encoding = "utf-8"

settings = Settings()
