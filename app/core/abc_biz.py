import logging
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from decimal import Decimal
from app.core.abc import BuyServiceABC, CommissionServiceABC, ConsumeServiceABC, BaseServiceABC
from app.core.database import get_db, to_dict, get_db_manual
from app.features.biz.order.order_repo import OrderRepo
from app.features.biz.order.order_schema import PurchaseRequest, OrderStatus
from app.features.biz.user_balance.models import Transaction, TransactionType
from app.features.biz.usage.model import TokenUsageLog
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.features.user.model.user_model import User
from app.features.biz.apikey.apikey_schema import ApiKeyResp
from app.services.token_money_svc import TokenCostCalculator

logger = logging.getLogger(__name__)

class BaseService(BaseServiceABC):
    def __init__(self, transc_rep, redis_client: redis.Redis):
        self.transaction = transc_rep
        self.redis_client = redis_client

    async def add_transaction(self, db: AsyncSession, memo: str, user_id: int, amount: float, transaction_type: TransactionType):
        trans = Transaction(user_id=user_id, amount=amount, transaction_type=transaction_type.value, memo=memo)
        db.add(trans)
        await db.commit()
        await db.refresh(trans)
        return trans

    async def update_user(self, user_id: int, amount: float, db: AsyncSession = None):
        stmt = update(User).where(User.id == user_id).values(balance=User.balance + amount)
        await db.execute(stmt)
        await db.commit()


class BuyService(BaseService, BuyServiceABC):
    def __init__(self, base: BaseService, 
            order_repo: OrderRepo, 
            token_repo: TokenUsageRepo, 
            token_cal_svc: TokenCostCalculator):
        super().__init__(base.transaction, base.redis_client)
        self.order_repo = order_repo
        self.token_cal_svc = token_cal_svc
        self.token_usage_repo = token_repo

    async def create_order(self, purchase: PurchaseRequest, user_id: int):
        return await self.order_repo.create(user_id=user_id, purchase=purchase)

    async def pay_order(self, order_id, order_data):
        async for session in get_db_manual():
            try:
                order = await self.order_repo.pay_order(order_id=order_id, session=session, status=OrderStatus.SUCCESS)
                if not order: return False

                meta = to_dict(order)
                await self.transaction.consume_session(session=session, maker_id=0, amount=order.amount, transaction_type=TransactionType.SYSINCOME, meta=meta)
                await self.transaction.consume_session(session=session, maker_id=order.user_id, amount=order.amount, transaction_type=TransactionType.RECHARGE, meta=meta)

                #token_count = await self.token_cal_svc.money_to_tokens(order.amount)
                #await self.token_usage_repo.recharge_tokens(session=session, user_id=order.user_id, provider='vip', amount=token_count, cost=order.amount, type='recharge')

                await session.commit()
                return True
            except Exception:
                await session.rollback()
                raise

    async def refund(self, user_id: int, amount: float, reason: str): ...


class ConsumeService(BaseService, ConsumeServiceABC):
    def __init__(self, base: BaseService, CommissionService, PriceCal: TokenCostCalculator):
        super().__init__(base.transaction, base.redis_client)
        self.commission = CommissionService
        self.calcu = PriceCal

    async def charge(self, user_data: ApiKeyResp, usage: dict, token_usage: TokenUsageLog, request_model: str, session: AsyncSession):
        inp_tk = usage.get('prompt_tokens', 0)
        outp_tk = usage.get('completion_tokens', 0)
       
        model_price = await self.calcu.query_price_table (request_model)
        if model_price is None:
            logger.warning(f"Model {request_model} not found in price table, using default price")
            raise Exception("Model not found in price table")
        
        cost = self.calcu.tokens_to_cost(input_tokens=inp_tk, output_tokens=outp_tk, model_price=model_price)
        sale_price = self.calcu.tokens_to_revenue(input_tokens=inp_tk,
                                                  output_tokens=outp_tk, 
                                                  model_price=model_price,
                                                  user_tier=user_data.tier 
                                                )
        token_usage.status = 'completed'
        token_usage.updated_at = datetime.now()
        token_usage.memo = f'api request:{str(usage)},user type: {user_data.tier}'
        token_usage.input_tokens = inp_tk
        token_usage.output_tokens = outp_tk
        token_usage.amount = inp_tk + outp_tk
        token_usage.provider_cost = cost
        token_usage.sale_price = sale_price # 如果有加价策略，可以在这里修改
        token_usage.profit = Decimal(sale_price) - Decimal(cost)


        if cost > 0:
            meta = {"model": request_model, "usage": usage}
            await self.transaction.consume_session(session=session, maker_id=user_id, amount=-sale_price, transaction_type=TransactionType.CONSUME, meta=meta)
            await self.transaction.consume_session(session=session, maker_id=0, amount=sale_price, transaction_type=TransactionType.SYSINCOME, meta=meta)

        # 必须在 commit 前执行，确保与消费在同一事务
        await self.commission.distribute(from_user=user_id, amount=cost, usage_id=token_usage.id, session=session)
        await session.commit()
        return cost

    async def refund(self, db: AsyncSession, user_id: int, amount: float, reason: str):
        await self.add_transaction(db=db, user_id=user_id, amount=-amount, transaction_type=TransactionType.REFUND, memo=reason)


class CommissionService(BaseService, CommissionServiceABC):
    def __init__(self, user_repo, base: BaseService):
        super().__init__(base.transaction, base.redis_client)
        self.user_repo = user_repo

    async def distribute(self, from_user: int, amount: float, usage_id=None, session: AsyncSession = None):
        is_new = session is None
        if is_new:
            session = await get_db().__anext__()
            try:
                await self._run(from_user, amount, usage_id, session)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        else:
            await self._run(from_user, amount, usage_id, session)

    async def _run(self, from_user: int, amount: float, usage_id, session: AsyncSession):
        current_user = from_user
        level = 0
        while True:
            parent = await self.user_repo.get_parent(db=session, user_id=current_user)
            if not parent: break
            level += 1
            commission = amount * self._get_rate(level)
            if commission <= 0: break

            session.add(Transaction(
                user_id=parent.user_id,
                amount=commission,
                transaction_type=TransactionType('commission'),
                memo=f"commission from {current_user}" + (f" (usage_id: {usage_id})" if usage_id else "")
            ))
            current_user = parent.user_id

    def _get_rate(self, level: int):
        return {1: 0.10, 2: 0.03, 3: 0.01}.get(level, 0)