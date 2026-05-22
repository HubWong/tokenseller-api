from typing import Any, Optional
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from datetime import datetime




class UsageStatsResponse(BaseModel):
    """Usage statistics response"""
    date: str
    tokens_used: float = 0.0
    cost_usd: float = 0.0
    api_calls: int = 0


class RecentRequestResponse(BaseModel):
    """Recent API request response"""
    id: int
    model_name: str
    tokens_used: int
    cost_usd: float
    created_at: str


class DashboardStatsResponse(BaseModel):
    """Dashboard overview stats"""
    token_used: float
    today_tokens_used: Optional[float] =0
    total_api_calls: int
    low_balance_warning: bool
    dailyUsage:list[Any]

'''
    amount = Column(Numeric(10, 2), default=0.0)   
    # user acccount for receiving payments
    chain_type = Column(String(20))  # e.g., evm, tron
    wallet_chain = Column(String(20))  # e.g., eth, bsc, polygon, tron
    wallet_address = Column(String(128), nullable=False)
    accept_contract = Column(String(128), nullable=False)
    currency = Column(String(3), default="USDC")
'''
class UserBalanceBase(BaseModel):   
    amount: Decimal = Field(default=Decimal("0.0"), ge=0)
    expired_at: Optional[datetime] = None

class UserBalanceCreate(UserBalanceBase):
    chain_type: str
    wallet_chain: str
    wallet_address: str = "0x24dd415dc89c6c42a435be46768cce3e5e301ca1"
    accept_contract: str
    currency: str = "USDC"
    
    class Config:
        from_attributes = True
    
    
     

class UserBalanceUpdate(UserBalanceBase):
   pass

class UserBalanceInDBBaseOut(UserBalanceCreate):
    id: int
    user_id: int    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True
