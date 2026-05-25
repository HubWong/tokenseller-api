from typing import Optional,Dict
from pydantic import BaseModel
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel, Field

'''
PENDING (创建订单) 
   → DETECTED (链上发现交易，未确认) 
   → CONFIRMING (确认中 < required_confirmations) 
   → Success (确认数达标，发货/开通权益) 
   ↘ FAILED (金额不足/合约不匹配/链上回滚)
'''
class OrderStatus(str, Enum):   
    PENDING = "pending"
    SUCCESS = "success"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    FAILED = "failed"
    CONFIRMING ="confirming"
    

class OrderFor(str, Enum):
    VIP = "vip"
    ITEM = "item"
    CHAT = "chat"

class PurchaseRequest(BaseModel):
    amount:float
    pay_way: int
   




class ModelPricingUpdate(BaseModel):
    input_cost: Optional[float] = Field(None, gt=0, description="Input cost per 1K tokens")
    output_cost: Optional[float] = Field(None, gt=0, description="Output cost per 1K tokens")
    input_price: Optional[float] = Field(None)
    output_price: Optional[float] = Field(None)
    currency: Optional[str] = Field(None, description="Currency code")
    is_active: Optional[bool] = Field(None, description="Whether the model is active")
    level: Optional[int] = Field(None, description="Model level for tiered pricing")

# Request/Response Schemas
class ModelPricingCreate(ModelPricingUpdate):
    model_name: str = Field(..., description="Model name")   

class ModelPricingResponse(ModelPricingCreate):
    id: int   

    class Config:
        from_attributes = True

class TokenBalanceResponse(BaseModel):
    api_key: str
    balances: Dict[str, int]
    total_tokens: int


class ProviderInfo(BaseModel):
    name: str
    id: str
    price_per_1k: float
    capacity: str

class ProvidersResponse(BaseModel):
    providers: list[ProviderInfo]

        
class OrderBase(PurchaseRequest):   
    currency: Optional[str] = "usdt"  # usdt/usdc
    order_for: Optional[str] = None

class OrderCreateIn(OrderBase):
    to_address:Optional[str] = None
    chain:Optional[str] = 'tron'
    path_index :Optional[int]=None
    contract:Optional[str]=''
    order_status: Optional[OrderStatus|str] = OrderStatus.PENDING.value
    pay_way: Optional[int] = 2
    user_id: Optional[int] = None
    expired_at: Optional[datetime] = datetime.now()+ timedelta(minutes=20)
    
    class Config:
        from_attributes = True

class OrderCreateOut(OrderCreateIn):   
    token:Optional[str] = "usdt" # usdt/usdc (currency)


class OrderInDBBase(OrderCreateIn):
    id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True