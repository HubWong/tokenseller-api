from typing import Dict, Any,  Optional, List
from urllib.parse import urlparse, parse_qs
from app.features.user.schemas.user_schema import SocketUser
import json


user_sessions: Dict[str, SocketUser] = {}   

async def query_data_on_connect(environ: Dict[str, Any]) -> Any:
    """
    Extract user ID from query parameters

    Args:
        environ: The WSGI environment dictionary

    Returns:
        dict of user
    """
    query_params = environ["QUERY_STRING"]
    parsed_url = urlparse(query_params)
    query_params = parse_qs(parsed_url.path)
    ruser = query_params.get('data',[None])[0]
    
    user =json.loads(ruser)   
    return user
   
   
   
# used in auth_api.py
