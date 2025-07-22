from auth import generate_access_token

def access_token_generate_handler(rdata):
    
    # if 'con_id' in  rdata['data'] :
    #     access_token = generate_access_token_for_consultant(rdata['data'])
    # else:   
    access_token = generate_access_token(rdata['data'])
        
    return {
        'success': rdata['success'],
        'access_token': access_token, 'token_type': 'bearer',
        'user_data':rdata['data'],
        'error':{}
    }

