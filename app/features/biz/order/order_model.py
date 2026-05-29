from sqlalchemy import func, Column, Integer, Float, String, DECIMAL, ForeignKey, DateTime, Integer, String, ForeignKey, Enum, Text, Float
from sqlalchemy.types import Numeric
from app.features.biz.order.order_schema import OrderStatus as Ord
from app.features.db_base import TimestampMixin
from app.core.database import Base
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column

#每笔订单 order_id | chain | to_address | path_index | amount | status
'''
  
'''

class Order(Base, TimestampMixin): # record all the orders for paying for vip and items
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    notify_count =Column(Integer,default=0)
    
    amount = Column(DECIMAL(18, 6), nullable=False, comment="应收金额")
    received_amount = Column(DECIMAL(18, 6), default=0, comment="实际到账金额")
    currency = Column(String(20), nullable=False, comment="USDT, TRX")
    chain = Column(String(20), nullable=False, comment="TRON, ETH 等")

    # 📍 地址与合约
    to_address = Column(String(100), nullable=False, comment="收款地址(Base58格式)")
    from_address = Column(String(100),nullable=True, comment="付款人地址(Base58格式)")
    path_index = Column(Integer, comment="HD钱包派生索引")
    contract = Column(String(100), comment="TRC20代币合约地址，原生TRX为空")

    # 🔗 链上交易凭证
    tx_hash = Column(String(128), index=True, nullable=True, comment="TRON交易哈希(TXID)")
    confirmations = Column(Integer, default=0, comment="当前确认数")
    required_confirmations = Column(Integer, default=19, comment="TRON建议19+确认")

    # 📦 业务字段
    order_status = Column(String(20), default="pending", comment="pending/detected/confirming/success/expired/failed")
    order_for = Column(String(50), comment="vip, chat, item")
    pay_way = Column(Integer, nullable=False) #1 paypal 2 tron
    expired_at = Column(DateTime, nullable=False)
    payment_channel = Column(String(30),nullable = True)
    callback_payload =Column(String(200),nullable=True)



'''
记录“谁给谁贡献了佣金”
和 transactions 分离（便于审计）
可以关联 transaction（推荐）
'''
class CommissionLog(Base, TimestampMixin):
    __tablename__ = "commission_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    from_user: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id"), 
        nullable=False,
        index=True
    )
    # 产生消费的用户（下级）

    to_user: Mapped[int] = mapped_column(
        Integer,        
        nullable=False,
        index=True
    )
    # 获得佣金的用户（上级）

    amount: Mapped[float] = mapped_column(
        Float, 
        nullable=False
    )

    # 推荐：关联到交易表（更完整账务链路）
    transaction_id: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

class ModelPricing(Base, TimestampMixin):

    __tablename__ = "model_pricing"

    id: Mapped[int] = mapped_column(primary_key=True)

    # oneapi模型名
    model_name: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        index=True
    )

    # oneapi渠道信息
    provider_type: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    provider_name: Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )

    group_name: Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    weight: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    # 成本
    input_cost: Mapped[float] = mapped_column(
        Numeric(10, 6),
        nullable=True
    )

    output_cost: Mapped[float] = mapped_column(
        Numeric(10, 6),
        nullable=True
    )

    # 售价
    input_price: Mapped[float] = mapped_column(
        Numeric(10, 6),
        default=0
    )

    output_price: Mapped[float] = mapped_column(
        Numeric(10, 6),
        default=0
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="USD"
    )

    # oneapi渠道状态
    channel_status: Mapped[int] = mapped_column(
        Integer,
        default=1
    )

    # fastapi内部状态
    is_active: Mapped[bool] = mapped_column(
        Integer,
        default=1
    )

    level: Mapped[int] = mapped_column(
        Integer,
        default=3
    )

# class ModelPricing(Base, TimestampMixin):
#     """Model pricing configuration table"""
#     __tablename__ = "model_pricing"

#     id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
#     model_name: Mapped[str] = mapped_column(
#         String(100),
#         unique=True,
#         index=True,
#         nullable=False
#     )

#     input_cost: Mapped[float] = mapped_column(
#         Numeric(10, 6),
#         nullable=True
#     )
#     output_cost: Mapped[float] = mapped_column(
#         Numeric(10, 6),
#         nullable=True
#     )

#     input_price: Mapped[float] = mapped_column(
#         Numeric(10, 6),
#         nullable=False
#     )
#     output_price: Mapped[float] = mapped_column(
#         Numeric(10, 6),
#         nullable=False
#     )
#     currency: Mapped[str] = mapped_column(
#         String(10),
#         default="USD"
#     )
#     is_active: Mapped[bool] = mapped_column(
#         Integer,
#         default=1
#     )

#     level: Mapped[int] = mapped_column(Integer,default=3)
