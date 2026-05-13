from typing import Optional, List, Dict
from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.features.user.schemas.photo_schema import PhotoInDB


class UserCreate(BaseModel):
    email: EmailStr
      
    pc_id: Optional[str] = None
    password: str
    confirmPassword: Optional[str] = None
    invite_code:Optional[str] =None
    
class UpdateUsername(BaseModel):
    username: str

class UserCvUpdate(BaseModel):
    username: Optional[str] = None
    birth_year: Optional[int] = None
    gender:Optional[int] = 0
    bio: Optional[str] = None   
    marital_status:int = 0  
    pc_id: Optional[str] = None
    email: Optional[EmailStr] = None
    ip_country_city: Optional[str] = None     
   
   
    on_show: Optional[bool] = False
    
    class Config:
        from_attributes = True
    

class UserInDBBase(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    city: Optional[str] = None   
    is_active: Optional[bool] = True
    id: int   
    avatar: Optional[str] = None

    class Config:
        from_attributes = True


class BaseUser(BaseModel):
    id: Optional[str|int] = None  
    username: Optional[str] = None
   
    gender: Optional[int] = None
    birth_year: Optional[int] = None     
    
    
    
    class Config:
        from_attributes = True
    
class SocketUser(BaseUser):   
    avatar:Optional[str]=None
    online_time: str = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    last_active: str = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))     
   
    class Config:
        json_encoders = {datetime: lambda dt: dt.isoformat()}

class UserAvatarOut(BaseModel): #for admin use  
    avatar: Optional[str] = None
    
class UserLoginResp(BaseModel):
    id: Optional[str|int] 
    role: Optional[str] = "USER"
    email:Optional[str]=None
    username:Optional[str] =None
    is_active:Optional[bool] =None
    invite_code:Optional[str] =None
    pc_id: Optional[str] = None
    
    class Config:
        from_attributes = True

        

class UserInDB(BaseUser):  
    email:Optional[EmailStr] = None
    on_show:Optional[bool] = False
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None   
  

class UserWithAvatarOut(BaseUser):
    avatar: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
        
class UserInDbWithPwd(UserInDB):
    hashed_password: str
        
class UserInDbPhotos(BaseUser): 
    marital_status: Optional[int] = 0
    photos:Optional[List[PhotoInDB]] = None

class UserList(BaseModel):
    users: List[UserWithAvatarOut]
    total: int


class ResetPwd(BaseModel):
    token: str
    new_password: str


# ============== Token & Auth Schemas (from main.py) ==============

class TokenSchema(BaseModel):
    """JWT Token Schema"""
    token: str  # access token
    refresh_token: str
    token_type: str = "bearer"


class TokenSchemaUser(TokenSchema):
    """JWT Token Schema with user info"""
    user: Optional[Dict] = None


class TokenPayload(BaseModel):
    """Token payload for verification"""
    sub: Optional[str] = None  # subject (user_id)
    exp: Optional[datetime] = None
    type: Optional[str] = None  # "access" or "refresh"


# ============== Response Schemas (from main.py) ==============


class LoginResponse(BaseModel):
    """Legacy login response (for backward compatibility)"""
    success: bool
    message: str
    email: Optional[str] = None
    api_key: Optional[str] = None


class TokenLoginResponse(BaseModel):
    """OAuth2 style login response with JWT"""
    success: bool
    message: str
    data: Optional[TokenSchemaUser] = None


class OAuthResponse(BaseModel):
    """OAuth authentication response"""
    success: bool
    message: str
    email: Optional[str] = None
    api_key: Optional[str] = None
    provider: Optional[str] = None


class UserTokenBalanceResponse(BaseModel):
    """User with token balance (from main.py UserResponse)"""
    email: str   
    token_balance: Dict