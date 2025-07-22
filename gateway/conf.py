import os

from pydantic import BaseSettings

class Settings(BaseSettings):
    AUTH0_DOMAIN: str = os.getenv("AUTH0_DOMAIN")   
    ACCESS_TOKEN_DEFAULT_EXPIRES_MINUTES: int = 360
    NSE_SERVICE_URL : str = os.getenv("NSE_SERVICE_URL")
    #NSE_SERVICE_URL: str = os.environ.get("NSE_SERVICE_URL") # if above doesnot work use this
    USER_SERVICE_URL : str = os.getenv("USER_SERVICE_URL")
    BREAKEVEN_SERVICE_URL : str = os.getenv("BREAKEVEN_SERVICE_URL")
    GATEWAY_TIMEOUT: int = 120


settings = Settings()    