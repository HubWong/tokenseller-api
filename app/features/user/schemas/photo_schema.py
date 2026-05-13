from typing import Optional
from pydantic import BaseModel
from datetime import datetime


class PhotoUploadResp(BaseModel):    
    url: Optional[str] = None
    public_id: Optional[str] = None
    secure_url: Optional[str] = None
  
class PhotoBase(BaseModel):
    url: str
    description: Optional[str] = None
    user_id: int 

class PhotoCreate(PhotoBase):
    cloudinary_pub_id: Optional[str] = None

class UserPhoto(PhotoBase):
    id:int
    class Config:
        from_attributes = True
        
class PhotoInDB(PhotoBase):
    id: int
    created_at: datetime
    updated_at: datetime     
    
    class Config:
        from_attributes = True
