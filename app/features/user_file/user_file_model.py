# models.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from app.core.database import Base
from app.features.db_base import TimestampMixin
import enum


class AuthenGroups(enum.Enum):
    Payed = 1
    Friends = 2
    LikeMe = 3
    OnlyMe = 4


class UploadedFile(Base, TimestampMixin):
    __tablename__ = "user_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)          # 原始文件名
    filepath = Column(String, unique=True)         # 服务器上保存的路径（或 URL）
    file_size = Column(Integer)                    # 文件大小（字节）
    already_used = Column(Integer, default=0)      # 已使用次数
    authend_groups=Column(String, default="")  # 授权的用户组，逗号分隔 1,3,4
    
    # 外键：关联到 users 表的 id
    user_id = Column(Integer, ForeignKey("users.id"))

    # 正向关系：指向所属用户
    owner = relationship("User", back_populates="uploaded_files")