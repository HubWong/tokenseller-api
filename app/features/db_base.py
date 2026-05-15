from sqlalchemy import Column, Integer, DateTime, String,func
from datetime import datetime,timezone
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlmodel import SQLModel



class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), 
    default=lambda: datetime.now(timezone.utc), 
    nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        server_onupdate=func.now(),  # ⚠️ Important: works in PostgreSQL
        nullable=True)
    memo = Column(String, nullable=True)

from pydantic import BaseModel
from typing import Generic, TypeVar, Optional



T = TypeVar('T')

class ApiResp(BaseModel, Generic[T]):
    success: bool
    message: Optional[str] = None
    data: Optional[T] = None


class PagedResp(ApiResp[T]):
    total: int
    page: int
    size: int = 10
    data: Optional[T] = None


class Notification(BaseModel, Generic[T]):  
    
    data :T
    timestamp: float | None = None

class NotifOut(BaseModel, Generic[T]):   
    fromDevice: str | None = None
    data: T
    timestamp: float | None = None
    fromName: str | None = None
    fromSid: str | None = None

 