from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from enum import IntEnum

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
    status: str
    used_tokens:float
    tier:str
    created_at:str
    key: str
    key_title: str
    status: str
    quota: float
