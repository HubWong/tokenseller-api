
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime

class MessageCreate(BaseModel):
    title : str 
    maker_id : Optional[int] = None
    max_man : Optional[int] = Field(default=10, gt=1, lt=100)
    memo: Optional[str] = None
    living_city:Optional[str] = None
    room_pwd: Optional[str] = None
    class Config:
        from_attributes = True  

class MessageSearchModel(BaseModel):
    query: Optional[str] = None
    city: Optional[str] = None
    is_public: bool = True
    page: int = 1
    
    class Config:
        from_attributes = True

class MessageRequest(BaseModel):
    room_id: int
    from_sid: str


class MessageOut(BaseModel):
    id: int
    title : str      
    max_man : int
    memo: Optional[str] = None
    has_pwd: bool = False
    url:Optional[str] =None
    room_pic: Optional[str] =None
    created_at: datetime
    updated_at:datetime
    online_count: Optional[int] = 0
    
    class Config:
        from_attributes = True
         