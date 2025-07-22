from fastapi import FastAPI, status, Request, Response
from typing import List
from conf import settings
from core import route 
from fastapi.middleware.cors import CORSMiddleware
from auth import *

'''
import from datastructures
'''

from datastructures.nse  import *
from datastructures.users import *
from datastructures.break_even import *
from datastructures.volatility import *
from datastructures.implied_volatility import *


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"], #["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@route(
    request_method=app.get,
    path='/api/v1_0/index',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=False,
    response_model=None
)
async def index(request: Request, response: Response):
    pass




'''
o   o  o-o  o--o 
|\  | |     |    
| \ |  o-o  O-o  
|  \|     | |    
o   o o--o  o--o

'''
# @route(
#     request_method=app.post,
#     path='/api/v1_0/fetch_data_from_nse',
#     status_code=status.HTTP_200_OK,
#     payload_key="payload",
#     service_url=settings.NSE_SERVICE_URL,
#     authentication_required=False,
#     response_model=None
# )
# async def fetch_data(payload: FetchDataPayload, request: Request, response: Response):
#     pass




@route(
    request_method=app.get,
    path='/api/v1_0/search-data/{from_date}/{to_date}/{instrument_type}/{symbol}/{year}/{expiry_date}/{option_type}/{strike_price}',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=False,
    response_model=None
)
async def search_data(from_date: str, to_date: str, instrument_type: str, symbol: str, 
    year: int, expiry_date: str, option_type: str, strike_price: float,
    request: Request,response: Response):
    pass


# @route(
#     request_method=app.post,
#     path='/api/v1_0/option-strategy-builder/{view_type}',
#     status_code=status.HTTP_200_OK,
#     payload_key="strategy",
#     service_url=settings.NSE_SERVICE_URL,
#     authentication_required=False,
#     response_model=None
# )
# async def calculate_option_strategy(view_type: str,strategy: OptionStrategy,
#                                      request: Request,response: Response):
#     pass



# @route(
#     request_method=app.post,
#     path='/api/v1_0/option-strategy-table/{view_type}',
#     status_code=status.HTTP_200_OK,
#     payload_key="strategy",
#     service_url=settings.NSE_SERVICE_URL,
#     authentication_required=False,
#     response_model=None
# )
# async def format_option_strategy_table(view_type: str,strategy: OptionStrategy,
#                                      request: Request,response: Response):
#     pass


# @route(
#     request_method=app.get,
#     path= '/api/v1_0/option-strategy/performance',
#     status_code=status.HTTP_201_CREATED,
#     payload_key=None,
#     service_url=settings.NSE_SERVICE_URL,
#     authentication_required=True,
#     post_processing_func=None,
#     authentication_token_decoder='auth.decode_access_token',
#     service_authorization_checker='auth.is_default_user',
#     service_header_generator='auth.generate_request_header',
#     response_model=None
#     )
# async def  calculate_option_performance(request: Request, response: Response):
#     pass



# @route(
#     request_method=app.get,
#     path= '/api/v1_0/option-strategy/performance_queue',
#     status_code=status.HTTP_201_CREATED,
#     payload_key=None,
#     service_url=settings.NSE_SERVICE_URL,
#     authentication_required=True,
#     post_processing_func=None,
#     authentication_token_decoder='auth.decode_access_token',
#     service_authorization_checker='auth.is_default_user',
#     service_header_generator='auth.generate_request_header',
#     response_model=None
#     )
# async def  calculate_option_performance_queue(request: Request, response: Response):
#     pass


# @route(
#     request_method=app.get,
#     path= '/api/v1_0/option-strategy/performance_queue_2',
#     status_code=status.HTTP_201_CREATED,
#     payload_key=None,
#     service_url=settings.NSE_SERVICE_URL,
#     authentication_required=True,
#     post_processing_func=None,
#     authentication_token_decoder='auth.decode_access_token',
#     service_authorization_checker='auth.is_default_user',
#     service_header_generator='auth.generate_request_header',
#     response_model=None
#     )
# async def  calculate_option_performance_queue_2(request: Request, response: Response):
#     pass



@route(
    request_method=app.get,
    path= '/api/v1_0/strategy/simulation',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def strategy_simulation(request: Request, response: Response):
    pass


@route(
    request_method=app.get,
    path= '/api/v1_0/strategy/simulation/monthly/{month}/{year}',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def monthly_strategy_simulation(
    month: str,
    year: str,
    request: Request, response: Response):
    pass


@route(
    request_method=app.get,
    path= '/api/v1_0/strategy/monthly_volatility_simulation/{month}/{year}',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def monthly_volatility_simulation(
    month: str,
    year: str,
    request: Request, response: Response):
    pass



'''
                                           
O       o .oOOOo.  o.OOoOoo `OooOOo.  .oOOOo.  
o       O o     o   O        o     `o o     o  
O       o O.        o        O      O O.       
o       o  `OOoo.   ooOO     o     .O  `OOoo.  
o       O       `O  O        OOooOO'        `O 
O       O        o  o        o    o          o 
`o     Oo O.    .O  O        O     O  O.    .O 
 `OoooO'O  `oooO'  ooOooOoO  O      o  `oooO'
'''


@route(
    request_method=app.post,
    path='/api/v1_0/register_user',
    status_code=status.HTTP_201_CREATED,
    payload_key="user",
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=False, 
    response_model=None
)
async def register_user(user: UserCreate, request:Request, response: Response):
    pass


@route(
    request_method=app.post,
    path= '/api/v1_0/user_login',
    status_code=status.HTTP_201_CREATED,
    payload_key='login_payload',
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=False,
    post_processing_func='post_processing.access_token_generate_handler',
    response_model=None
    )
async def  user_login(login_payload: UserLogin, request: Request, response: Response):
    pass


@route(
    request_method=app.post,
    path= '/api/v1_0/create_transection',
    status_code=status.HTTP_201_CREATED,
    payload_key='trans_payload',
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def  create_transection(trans_payload: TransactionCreate, request: Request, response: Response):
    pass



@route(
    request_method=app.delete,
    path= '/api/v1_0/delete_user_transactions',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def  delete_user_transactions(request: Request, response: Response):
    pass


@route(
    request_method=app.delete,
    path= '/api/v1_0/delete_transaction/{transaction_id}',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def  delete_specific_transaction(transaction_id: int,request: Request, response: Response):
    pass




@route(
    request_method=app.get,
    path= '/api/v1_0/get_active_transactions',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def  get_active_transactions(request: Request, response: Response):
    pass

'''
.______   .______       _______     ___       __  ___     ___________    ____  _______ .__   __. 
|   _  \  |   _  \     |   ____|   /   \     |  |/  /    |   ____\   \  /   / |   ____||  \ |  | 
|  |_)  | |  |_)  |    |  |__     /  ^  \    |  '  /     |  |__   \   \/   /  |  |__   |   \|  | 
|   _  <  |      /     |   __|   /  /_\  \   |    <      |   __|   \      /   |   __|  |  . `  | 
|  |_)  | |  |\  \----.|  |____ /  _____  \  |  .  \     |  |____   \    /    |  |____ |  |\   | 
|______/  | _| `._____||_______/__/     \__\ |__|\__\    |_______|   \__/     |_______||__| \__|

'''


@route(
    request_method=app.get,
    path='/api/v1_0/break_even_calculator',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.BREAKEVEN_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def break_even_calculation(request: Request, response: Response):
    pass



@route(
    request_method=app.post,
    path='/api/v1_0/breakeven_profit',
    status_code=status.HTTP_200_OK,
    payload_key='strategy_request',
    service_url=settings.BREAKEVEN_SERVICE_URL,
    authentication_required=False,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
)
async def analyze_options_strategy(strategy_request: StrategyRequest, request: Request, response: Response):
     pass





@route(
    request_method=app.post,
    path='/api/v1_0/analyze_custom_strategy',
    status_code=status.HTTP_200_OK,
    payload_key='strategy_request',
    service_url=settings.BREAKEVEN_SERVICE_URL,
    authentication_required=False,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
)
async def analyze_custom_strategy(strategy_request: StrategyRequest, request: Request, response: Response):
     pass

'''
 ___________    ____ .______       _______     _______.
|   ____\   \  /   / |   _  \     |   ____|   /       |
|  |__   \   \/   /  |  |_)  |    |  |__     |   (----`
|   __|   \_    _/   |      /     |   __|     \   \    
|  |        |  |     |  |\  \----.|  |____.----)   |   
|__|        |__|     | _| `._____||_______|_______/

'''


@route(
    request_method=app.get,
    path='/api/v1_0/fyres/access_token',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=False,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def access_token(request: Request, response: Response):
    pass


@route(
    request_method=app.post,
    path='/api/v1_0/fyres/volatility',
    status_code=status.HTTP_200_OK,
    payload_key='payload',
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def calculate_volatility_api(payload:VolatilityRequest, request: Request, response: Response):
    pass


@route(
    request_method=app.get,
    path='/api/v1_0/fyres/volatility_of_month/{month}/{year}/{symbol}',
    status_code=status.HTTP_200_OK,
    payload_key=None,
    service_url=settings.NSE_SERVICE_URL,
    authentication_required=True,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
    )
async def volatility_of_month(
    month: str,
    year: str,
    symbol: str ,
    request: Request, 
    response: Response):
    pass




'''
$$$$$$\ $$\    $$\ 
\_$$  _|$$ |   $$ |
  $$ |  $$ |   $$ |
  $$ |  \$$\  $$  |
  $$ |   \$$\$$  / 
  $$ |    \$$$  /  
$$$$$$\    \$  /   
\______|    \_/

'''
@route(
    request_method=app.post,
    path='/api/v1_0/implied_volatility',
    status_code=status.HTTP_200_OK,
    payload_key='payload',
    service_url=settings.BREAKEVEN_SERVICE_URL,
    authentication_required=False,
    post_processing_func=None,
    authentication_token_decoder='auth.decode_access_token',
    service_authorization_checker='auth.is_default_user',
    service_header_generator='auth.generate_request_header',
    response_model=None
)
async def calculate_implied_volatility(payload: ImpliedVolatilityRequest, request: Request, response: Response):
    pass