import jwt

from datetime import datetime, timedelta

from conf import settings
from exceptions import AuthTokenMissing, AuthTokenExpired, AuthTokenCorrupted


SECRET_KEY = 'e0e5f53b239df3dc39517c34ae0a1c09d1f5d181dfac1578d379a4a5ee3e0ef5'
ALGORITHM = 'HS256'


def generate_access_token(
        data: dict,
        expires_delta: timedelta = timedelta(
            minutes=settings.ACCESS_TOKEN_DEFAULT_EXPIRES_MINUTES
        )
):

    # Get the current time and add the expiration time to it
    expire = datetime.utcnow() + expires_delta
    # Create a dictionary with the user's id, user type, and expiration time
    token_data = {
        'id': data['user_id'],
        'user_type': data['user_type'],
        'exp': expire,
    }

    # Encode the dictionary into a JWT token using the secret key and algorithm
    encoded_jwt = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    # Return the encoded JWT token
    return encoded_jwt

# def generate_access_token_for_consultant(data: dict,
#         expires_delta: timedelta = timedelta(
#             minutes=settings.ACCESS_TOKEN_DEFAULT_EXPIRE_MINUTES
#         )):
#     expire = datetime.utcnow() + expires_delta
#     token_data = {
#         'id': data['con_id'],
#         'user_type': data['type'],
#         'exp': expire,
#     }

#     encoded_jwt = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt
    

def decode_access_token(authorization: str = None):
    if not authorization:
        raise AuthTokenMissing('Auth token is missing in headers.')
    token = authorization.replace('Bearer ', '')
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        return payload
    except jwt.exceptions.ExpiredSignatureError:
        raise AuthTokenExpired('Auth token is expired.')
    except jwt.exceptions.DecodeError:
        raise AuthTokenCorrupted('Auth token is corrupted.')


def generate_request_header(token_payload):
    return {'request-user-id': str(token_payload['id'])}

# def generate_request_header_consultant(token_payload):
#     print("generate_request_header_consultant: +++++++++++")
#     print(str(token_payload['id']))
#     return {'request-consultant-id': str(token_payload['id'])}

def is_admin_user(token_payload):
    return token_payload['user_type'] == 'admin'


def is_default_user(token_payload):
    return token_payload['user_type'] in ['default', 'admin']

# def is_admin_consultant(token_payload):
#     #return token_payload['consultant_type'] == 'admin_consultant'
#     return token_payload['user_type'] == 'con_admin'


# def is_default_consultant(token_payload):
#     return token_payload['user_type'] in ['con_default', 'con_admin']