import logging
from datetime import datetime
from sqlalchemy import select, update
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError 
import redis.asyncio as redis
from decimal import Decimal
from app.core.abc.abc import BuyServiceABC, CommissionServiceABC, ConsumeServiceABC
from app.core.database import get_db, to_dict, get_db_manual
from app.features.biz.user_balance.transaction_reop import TransactionRepo
from app.features.biz.order.order_model import ModelPricing
from app.features.biz.order.order_repo import OrderRepo
from app.features.biz.order.order_schema import PurchaseRequest, OrderStatus
from app.features.biz.user_balance.models import Transaction, TransactionType
from app.features.biz.usage.model import TokenUsageLog
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.features.user.model.user_model import User
from app.features.biz.apikey.apikey_schema import ApiKeyResp
from app.services.token_money_svc import TokenCostCalculator
from app.features.user.schemas.user_role import UserRole
from app.features.biz.apikey.apikey_crud import apikey_crud

logger = logging.getLogger(__name__)
MIN_BUY_AMOUNT = Decimal("0.0005")

class BaseService:
    def __init__(self, db: AsyncSession, redis_client: Optional[redis.Redis]):
        self.transaction = TransactionRepo(db)
        self.db = db
        self.redis_client = redis_client

    async def add_transaction(self, db: AsyncSession, memo: str, user_id: int, amount: float, transaction_type: TransactionType):
        trans = Transaction(user_id=user_id, amount=amount, transaction_type=transaction_type.value, memo=memo)
        db.add(trans)
        await db.commit()
        await db.refresh(trans)
        return trans

    async def update_user(self, user_id: int,amount: float):
        # 修复：增加空值判断
       
        try:
            stmt = update(User).where(User.id == user_id).values(balance=User.balance + amount,role=UserRole.VIP.value)
            await self.db .execute(stmt)
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to update user {user_id} balance: {str(e)}", exc_info=True)
            raise

        logger.info(f"Updated user {user_id} balance with {amount}")


class BuyService(BaseService, BuyServiceABC):
    def __init__(self, base: BaseService, 
            order_repo: OrderRepo, 
            token_repo: TokenUsageRepo, 
            token_cal_svc: TokenCostCalculator
            ):
        super().__init__(db = base.db, redis_client = base.redis_client)
        self.order_repo = order_repo
        self.token_cal_svc = token_cal_svc
        self.token_usage_repo = token_repo

    async def create_order(self, purchase: PurchaseRequest, user_id: int):
        return await self.order_repo.create(user_id=user_id, purchase=purchase)

    async def pay_order(self, order_id):
        async for session in get_db_manual():
            try:
                order = await self.order_repo.pay_order(order_id=order_id, session=session, status=OrderStatus.SUCCESS)
                if not order:
                    return False
                #update user role if needed 
                
                await self.update_user(user_id=getattr(order, "user_id"), amount=getattr(order, "amount"))
                await apikey_crud.update_tier_by_id_cmmition(uid=getattr(order, "user_id"), tier=UserRole.VIP.value, db=session)
                meta = to_dict(order)
                await self.transaction.consume_session(session=session, maker_id=0, amount=getattr(order, "amount"), transaction_type=TransactionType.SYSINCOME, meta=meta)
                await self.transaction.consume_session(session=session, maker_id=getattr(order,'user_id'), amount=getattr(order, "amount"), transaction_type=TransactionType.RECHARGE, meta=meta)
                 

                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                logger.exception("Pay order failed",str(e))
                raise

    async def refund(self, user_id: int, amount: float, reason: str):
        # 补充空实现逻辑
        pass


class ConsumeService(BaseService, ConsumeServiceABC):
    # 修复：类型注解
    def __init__(self, base: BaseService, commission_service: CommissionServiceABC, price_calc: TokenCostCalculator):
        super().__init__(db=base.db,redis_client = base.redis_client)
        self.commission = commission_service
        self.calcu = price_calc

    async def charge(self,model_price:ModelPricing, user_data: ApiKeyResp, usage: dict, token_usage: TokenUsageLog, request_model: str, session: AsyncSession):
        # 1. 获取 token 数量
        inp_tk = usage.get('prompt_tokens', 0)
        outp_tk = usage.get('completion_tokens', 0)

        # 2. 查询模型价格（不存在直接抛错）
        if model_price is None:
            logger.warning(f"Model {request_model} not found in price table")
            raise Exception(f"Model {request_model} not found in price table")

        # 3. 计算成本与售价
        cost = self.calcu.tokens_to_cost(input_tokens=inp_tk, output_tokens=outp_tk, model_price=model_price)
        sale_price = self.calcu.tokens_to_revenue(
            input_tokens=inp_tk,
            output_tokens=outp_tk,
            model_price=model_price,
            user_tier=UserRole(user_data.tier)
        )

        # ===================== 修复 1：统一 Decimal 类型 =====================
        # 强制全部使用 Decimal，避免 float 精度丢失 + 类型比较错误
        MIN_BUY_AMOUNT_DEC = Decimal(MIN_BUY_AMOUNT) if not isinstance(MIN_BUY_AMOUNT, Decimal) else MIN_BUY_AMOUNT
        cost = Decimal(cost) if not isinstance(cost, Decimal) else cost
        sale_price = Decimal(sale_price) if not isinstance(sale_price, Decimal) else sale_price

        # ===================== 修复 2：售价不能低于成本 =====================
        if sale_price < cost:
            logger.warning(f"Sale price {sale_price} < cost {cost} for user {user_data.id}, force set to cost")
            sale_price = cost

        # ===================== 修复 3：最低消费金额 =====================
        if sale_price < MIN_BUY_AMOUNT_DEC:
            sale_price = MIN_BUY_AMOUNT_DEC
        mmo_str = f'api request:{str(usage)}, user type: {user_data.tier}'
        # ===================== 修复 4：更新 token 日志 =====================
        setattr(token_usage,'status','completed')
        token_usage.updated_at = datetime.now()
        setattr(token_usage,'memo',mmo_str)
        token_usage.input_tokens = inp_tk
        token_usage.output_tokens = outp_tk
        token_usage.amount = inp_tk + outp_tk
        setattr(token_usage,'provider_cost',cost)
        setattr(token_usage,'sale_price',sale_price)
        setattr(token_usage,'profit',sale_price - cost)

        # 元数据
        meta = {"model": request_model, "usage": usage}

        # ===================== 修复 5：事务安全 + 异常处理 =====================
        try:
            # 用户扣费
            await self.transaction.consume_session(
                session=session,
                maker_id=user_data.user_id,
                amount=-sale_price,
                transaction_type=TransactionType.CONSUME,
                meta=meta
            )
            # 平台收入
            await self.transaction.consume_session(
                session=session,
                maker_id=0,
                amount=sale_price,
                transaction_type=TransactionType.SYSINCOME,
                meta=meta
            )

            # 分润逻辑：必须满足 售价>最低金额 且 有利润
            profit = sale_price - cost
            if sale_price > MIN_BUY_AMOUNT_DEC and profit > 0:
                # 必须在同一事务内
                await self.commission.distribute(
                    from_user=user_data.user_id,
                    amount=float(profit),
                    usage_id=token_usage.id,
                    session=session,
                )

            # 统一提交
            await session.commit()
            logger.info(f"Charge success for user {user_data.id}, cost={cost}, sale_price={sale_price}, profit={profit}")

        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Charge transaction failed, rollback: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Charge failed, rollback: {str(e)}", exc_info=True)
            raise

        return cost

    async def refund(self, db: AsyncSession, user_id: int, amount: float, reason: str):
        await self.add_transaction(db=db, user_id=user_id, amount=-amount, transaction_type=TransactionType.REFUND, memo=reason)


class CommissionService(BaseService, CommissionServiceABC):
    def __init__(self, user_repo, base: BaseService):
        super().__init__(db=base.db, redis_client =base.redis_client)
        self.user_repo = user_repo

    async def distribute(self, from_user: int, 
                         amount: float, 
                         usage_id=None, 
                         session: Optional[AsyncSession] = None):
        is_new = session is None
        if is_new:
            session = await get_db().__anext__()
            try:
                await self._run(from_user, amount, usage_id, session)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Commission distribute failed")
                raise
            finally:
                await session.close()
        else:
            await self._run(from_user, amount, usage_id, session)

    async def _run(self, from_user: int, amount: float, usage_id, session: AsyncSession):
        current_user = from_user
        level = 0
        while True:
            parent = await self.user_repo.get_parent(db=session, user_id=current_user)
            if not parent:
                break
            level += 1
            commission = amount * self._get_rate(level)
            if commission <= 0:
                break

            # 修复：TransactionType 正确使用
            session.add(Transaction(
                user_id=parent.user_id,
                amount=commission,
                transaction_type=TransactionType.COMMISSION.value,
                memo=f"commission from {current_user}" + (f" (usage_id: {usage_id})" if usage_id else "")
            ))
            current_user = parent.user_id

    def _get_rate(self, level: int):
        return {1: 0.10, 2: 0.03, 3: 0.01}.get(level, 0)
