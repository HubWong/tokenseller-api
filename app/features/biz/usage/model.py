from sqlalchemy import Boolean, Integer, String, Column, DateTime, Text
from sqlalchemy.types import Float,Numeric
from app.features.db_base import TimestampMixin
from app.core.database import Base


    
    

class TokenUsageLog(Base, TimestampMixin):
    __tablename__ = "token_usage_log"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    provider = Column(String(50), index=True, nullable=True)  # openai/openrouter
    request_data = Column(Text,nullable=True)    
   
    # 防重复（建议保留）
    request_id = Column(String(128), unique=True, index=True, nullable=True)

    # 统一扩展字段
    memo = Column(Text, nullable=True)    
    # 是否流式
    is_stream = Column(Boolean, default=False)
    
  
    model = Column(String(100))

    input_tokens = Column(Float, default=0)
    output_tokens = Column(Float, default=0)
     # 核心计费字段
    amount = Column(Float, nullable=True) #input_tokens + output_tokens 

    provider_cost = Column(Numeric(10, 6), default=0)
    sale_price = Column(Numeric(10, 6), default=0)
    profit = Column(Numeric(10, 6), default=0)

    status = Column(String(20))        # success/error
