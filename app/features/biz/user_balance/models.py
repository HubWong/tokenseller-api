from sqlalchemy import Column, Integer, String,  Enum, Float
from app.features.db_base import TimestampMixin
from app.core.database import Base
from datetime import datetime
from sqlalchemy.orm import  Mapped, mapped_column
from sqlalchemy import DateTime, func

import enum

''' 流程：
transactions:
  B: -10 (consume)

commission_log:
  from_user=B
  to_user=A
  amount=2

transactions:
  A: +2 (commission)
'''
class TransactionType(enum.Enum):
    CONSUME = "consume"        # 消费（扣费）
    RECHARGE = "recharge"      # 充值
    RECHARGE_FREE = 'sys-free'
    COMMISSION = "commission"  # 分佣收入
    SYSINCOME = "sysincome"   # 系统收入
    REFUND= "refund"

'''
所有资金变动统一记录（核心账本）
正负值表示收入/支出
type 控制业务类型
'''
class Transaction(Base,TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    maker_id: Mapped[int] = mapped_column(
        Integer,         
        nullable=False, 
        index=True
    )
    amount: Mapped[float] = mapped_column(
        Float, 
        nullable=False
    )
    # 建议规则：
    # 消费：负数
    # 充值/佣金：正数

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 可选：来源说明（例如：gpt-4o / usdt / stripe）
    source: Mapped[str] = mapped_column(String(100), nullable=True)
    # 可选：订单ID / 外部交易ID
    ref_id: Mapped[str] = mapped_column(String(100), nullable=True)
    balance_after: Mapped[float] = mapped_column(Float, nullable=True)  # 变动后的余额快照

    