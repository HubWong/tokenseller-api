from typing import Optional
from pydantic import BaseModel

"""
 "id": k.id,
                        "key": k.key,  # 如果你做了hash，这里不要返回原key
                        "status": k.status,
                        "quota": k.quota,
                        "used_tokens": k.used_tokens,
                        "tier": k.tier,
                        "created_at": k.created_at,
                        'key_title':k.key_title,
"""


class ApiKeyResp(BaseModel):
    id:int
    user_id:int
    key:str
    name:str
    tier:str
    status:str
    rpm_limit:int

    class Config:
        from_attributes = True
     
