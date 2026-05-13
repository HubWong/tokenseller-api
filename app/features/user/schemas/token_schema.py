from typing import Optional
from pydantic import BaseModel, EmailStr
from app.features.user.schemas.user_schema import UserLoginResp

class TokenSchema(BaseModel):
    token: str
    refresh_token: str
    token_type: str
     

class TokenSchemaUser(TokenSchema):
    user: Optional[UserLoginResp] = None
    

class TokenPayload(BaseModel):
    sub: Optional[int] = None

# UserCreate schema moved to schemas.user

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class LostPasswordReset(BaseModel):
    token:str
    confirmPassword:str
    newPassword:str
    
class PasswordResetRequest(BaseModel):
    email: EmailStr