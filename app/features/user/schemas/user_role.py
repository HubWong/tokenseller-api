from typing import Optional,List
from pydantic import BaseModel
from datetime import datetime
import enum

class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "free"
    VIP = "vip"

class UserRoleBase(BaseModel):
    name: str
    start_at: datetime
    end_at: Optional[datetime] = None
    