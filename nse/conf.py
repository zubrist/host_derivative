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
    NSE_SERVICE_URL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
