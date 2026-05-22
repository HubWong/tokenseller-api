from typing import Optional, Sequence, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from app.features.biz.user_balance.models import Transaction,TransactionType
from app.core.config import settings
from app.services.token_money_svc import TokenCostCalculator
import logging

logger = logging.getLogger(__name__)


# ================= 业务路由逻辑 =================
class TransactionRepo:
    def __init__(self,db:AsyncSession) :
        self.db = db         

    async def create_transaction(self, session: AsyncSession, 
                                 maker_id: int, 
                                 amount: float, 
                                 transaction_type: TransactionType) -> Transaction:
        return await self.consume_session(session, maker_id, amount, transaction_type)
    
    async def query_transaction_sum(self, session: AsyncSession, maker_id: int) -> float:
        try:
            
            stmt = select(func.sum(Transaction.amount)).where(
                Transaction.maker_id == maker_id                             
            )
            result = await session.execute(stmt)    
            total_amount = result.scalar() or 0.0
            return total_amount
        except Exception as e:
            logger.error(f"Error querying transaction sum: {str(e)}")
            return 0.0

    async def consume_session(
        self,
        session: AsyncSession,
        maker_id: int,
        amount: float,
        transaction_type: TransactionType,
        meta: Optional[Dict[str, str]] = None
    ):
        try:
            order_id = meta.get("id", None) if meta else None
            from_uid = meta.get('user_id',None) if meta else None

            if transaction_type != TransactionType.RECHARGE_FREE:             
                mm=f'from {from_uid}'
            else:
                mm=f'from {from_uid}'
            balance_after = await self.query_transaction_sum(session, maker_id) 
            balance_after += float(amount)
            data = Transaction(
                maker_id=maker_id,
                amount=amount,
                type=transaction_type.value,
                memo=mm,
                ref_id = str(order_id),
                balance_after=float(balance_after)
            )
            session.add(data)
            
            return data
        except Exception as e:
            await session.rollback()
            logger.error(f"Error adding transaction: {str(e)}")
            return None           
               
    
    async def get_month_trans(self,user_id:int,type_str:str, db: AsyncSession)->tuple[Sequence[Transaction], float]:
        from datetime import datetime
        from sqlalchemy import func

        try:
            # Convert type_str to TransactionType enum
            trans_type = TransactionType(type_str)

            # Query transactions for current month
            stmt = (
                select(Transaction)
                .where(
                    Transaction.maker_id == user_id,
                    Transaction.type == trans_type.value,
                    func.extract('year', Transaction.created_at) == datetime.now().year,
                    func.extract('month', Transaction.created_at) == datetime.now().month
                )
                .order_by(Transaction.created_at.desc())
            )

            result = await db.execute(stmt)
            transactions = result.scalars().all()

            # Calculate total amount (absolute values)
            total_amount = sum(t.amount for t in transactions) if transactions else 0.0

            return transactions, total_amount
        except Exception as e:
            print(f"Error in get_month_trans: {e}")
            return [], 0.0


    async def get_recent_logs(self, db: AsyncSession,
                                           user_id: int, 
                                           days: int = 30,
                                           typstr:Optional[str] = None
                                           ) -> Sequence[Transaction]:
        """Get user transaction logs for the last 30 days by user_id, optionally filtered by type"""
        try:
            from datetime import datetime, timedelta

            # Calculate the date 30 days ago
            thirty_days_ago = datetime.now() - timedelta(days=days)

            if typstr:
                # Filter by transaction type
                trans_type = TransactionType(typstr)
                stmt = (
                    select(Transaction)
                    .where(
                        Transaction.maker_id == user_id,
                        Transaction.type == trans_type.value,
                        Transaction.created_at >= thirty_days_ago)
                    .order_by(Transaction.created_at.desc())
                )
            else:
                # Query all transactions for the last 30 days
                stmt = (
                    select(Transaction)
                    .where(
                        Transaction.maker_id == user_id,
                        Transaction.created_at >= thirty_days_ago)
                    .order_by(Transaction.created_at.desc())
                )

            result = await db.execute(stmt)
            transactions = result.scalars().all()           
           
            return transactions
        except Exception as e:
            print(f"Error in get_recent_logs: {e}")
            return []        

    
    async def get_paged_logs(
        self,
        db: AsyncSession,
        user_id: int,
        typstr: Optional[str] = None,
        page: int = 1,
        limit: int = 10
    ) -> tuple[Sequence[Transaction], int, float]:
        """        
        返回：(当前页交易列表, 总条数, 总金额)
        """
        try:
            # 1. 构建基础查询条件（合并 where，更简洁）
            query_conditions = [Transaction.maker_id == user_id]
            
            if typstr:
                trans_type = TransactionType(typstr)
                query_conditions.append(Transaction.type == trans_type.value)

            # 2. 分页偏移量计算
            offset = (page - 1) * limit

            # 3. 查询当前页数据（只查这一页，性能极高）
            stmt = (
                select(Transaction)
                .where(*query_conditions)
                .order_by(Transaction.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await db.execute(stmt)
            transactions = result.scalars().all()

            # 4. 查询符合条件的【总条数】（用于前端分页）
            count_stmt = select(func.count()).where(*query_conditions)
            total_count = await db.scalar(count_stmt) or 0

            # 5. 查询【数据库级总金额】（不是内存求和，性能提升巨大）
            amount_stmt = (
                select(func.sum(Transaction.amount))
                .where(*query_conditions)
            )
            total_amount = await db.scalar(amount_stmt) or 0.0

            return transactions, total_count, total_amount

        except Exception as e:
            print(f"Error in get_paged_logs: {e}")
            return [], 0, 0.0   
        

    async def get_tokens_by_money(self,token_cal_svc:TokenCostCalculator,
                                  model_str:str='default',
                                  money_list:list=settings.BILL_PRICE_SET)->dict:
        if not money_list:
            money_list = [25 * (2 ** n) for n in range(10) if 25 * (2 ** n) < 500]
        
        #result = {x:await token_cal_svc.money_to_tokens(amount=x,model=model_str) for x in money_list}
        return money_list

   
    async def get_bill_datas(self, db: AsyncSession, *, user_id: int) -> Optional[Dict]:
        """Get user bill data by user_id"""
        
        data = await self.get_recent_logs(db=db,typstr="",days=30,user_id=user_id)
        records,_, balance = await self.get_paged_logs(db=db,user_id=user_id)
        # Get monthly consume transactions and total amount
        _, monthly_trans = await self.get_month_trans(user_id, 'consume', db)
        money_tokens = settings.BILL_PRICE_SET
        total_recharged = sum(t.amount for t in records if t.type == TransactionType.RECHARGE.value)
        return {  
            'balance':balance,
            'monthly_trans':monthly_trans,
            'trans_logs':data, #最近30天的交易记录
            'total_recharge':total_recharged,
            'money_tokens':money_tokens
        }



