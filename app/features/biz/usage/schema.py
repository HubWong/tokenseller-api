
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from datetime import datetime

class UserRoomCreate(BaseModel):
    title : str 
    maker_id : Optional[int] = None
    max_man : Optional[int] = Field(default=10, gt=1, lt=100)
    memo: Optional[str] = None
    living_city:Optional[str] = None
    room_pwd: Optional[str] = None
    class Config:
        from_attributes = True  

class UserRoomSearchModel(BaseModel):
    query: Optional[str] = None
    city: Optional[str] = None
    is_public: bool = True
    page: int = 1
    
    class Config:
        from_attributes = True

class UserRoomRequest(BaseModel):
    room_id: int
    from_sid: str

class UserRoomUpdate(UserRoomCreate):
    pass


class UserRoomOut(BaseModel):
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
        
class UserRoomOutWithMakerData(UserRoomOut): 
    maker_id:Optional[int]
    living_city:Optional[str] =None
    maker_data: Optional[Dict[str, Any]] = None  # 可选的房主信息字段
    
    class Config:
        from_attributes = True