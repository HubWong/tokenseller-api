
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from datetime import datetime


class TokenUsageRecord(BaseModel):
    id: Optional[int] = None
    user_id: int
    request_model: str
    input_tokens: int
    output_tokens: int
    amount: int
    provider_cost: Decimal
    sale_price: Decimal
    profit: Decimal
    memo: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True