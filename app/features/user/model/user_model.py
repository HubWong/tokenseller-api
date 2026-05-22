from sqlalchemy import Boolean,Float, Column, String, Integer, ForeignKey, Text, Enum,DateTime, func
from app.features.user.schemas.user_role import UserRole
from app.features.db_base import TimestampMixin
from app.core.database import Base
import enum


class UserGender(enum.Enum):
    female=0
    male=1
    both =2
    other=3
    

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(50), default="",nullable=True)
    hashed_password = Column(String(255), nullable=True)       
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)    
    reset_pwd_token = Column(String(200), nullable=True)  # reset password token
    pc_id = Column(String(200), nullable=True,index=True)  # device pc id
    invite_code = Column(String(20), unique=True, nullable=True)  # 邀请码
    oauth_provider = Column(String(100), nullable=True)
    oauth_id = Column(String(100),nullable=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    balance = Column(Float, default=0.0)
    user_ip = Column(String(20), nullable=True)
    user_location = Column(String(100), nullable=True)
    
class UserSettings(Base,TimestampMixin):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    avatar_url =Column(String(500),nullable=True)    
    location = Column(String(200), nullable=True)  
    living_city = Column(String(100),nullable=True)
    birth_year = Column(Integer, nullable=True)   
    tel= Column(String(20), nullable=True, unique=True)

   