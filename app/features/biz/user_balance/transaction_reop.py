from ast import Dict
from datetime import datetime
from typing import Optional, List, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.features.biz.user_balance.models import Transaction,TransactionType

import logging
from app.core.config import settings

from app.services.token_money_svc import TokenCostCalculator

logger = logging.getLogger(__name__)

mastkey = settings.ONE_API_MASTERKEY

REFERRAL_REWARD_LEVELS: dict[int, float] = {1: 0.10, 2: 0.05, 3: 0.02}


# ================= 业务路由逻辑 =================
class TransactionRepo:
    def __init__(self,db:AsyncSession) :
        self.db = db         

    async def create_transaction(self, session: AsyncSession, 
                                 maker_id: int, 
                                 amount: float, 
                                 transaction_type: TransactionType) -> Transaction:
        return await self.consume_session(session, maker_id, amount, transaction_type)
    
    async def consume_session(
        self,
        session: AsyncSession,
        maker_id: int,
        amount: float,
        transaction_type: TransactionType,
        meta: dict = None
    ):
        try:
            order_id = meta.get("id", None) if meta else None
            from_uid = meta.get('user_id',None) if meta else None
            if transaction_type != TransactionType.RECHARGE_FREE:             
                mm=f'from {from_uid}'
            else:
                mm=f'from {from_uid}'

            data = Transaction(
                maker_id=maker_id,
                amount=amount,
                type=transaction_type.value,
                memo=mm,
                ref_id = str(order_id)
            )
            session.add(data)
            
            return data
        except Exception as e:
            await session.rollback()
            logger.error(f"Error adding transaction: {str(e)}")
            raise           
   
            
    async def get_by_user(self, db: AsyncSession, *, user_id: int) -> Optional[Transaction]:
        """Get user balance by user_id"""
        result = await db.execute(
            select(Transaction).where(Transaction.maker_id == user_id)
        )
        return result.scalars().first()
    
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
                    Transaction.type == trans_type,
                    func.extract('year', Transaction.created_at) == datetime.now().year,
                    func.extract('month', Transaction.created_at) == datetime.now().month
                )
                .order_by(Transaction.created_at.desc())
            )

            result = await db.execute(stmt)
            transactions = result.scalars().all()

            # Calculate total amount (absolute values)
            total_amount = sum(abs(t.amount) for t in transactions) if transactions else 0.0

            return transactions, total_amount
        except Exception as e:
            print(f"Error in get_month_trans: {e}")
            return [], 0.0


    async def get_transaction_logs(self, db: AsyncSession, typstr:str = None, *, user_id: int,page:int=1,limit:int =10) -> tuple[Sequence[Transaction], float]:
        """Get user transaction logs by user_id, optionally filtered by type"""
        try:
            if typstr:
                # Filter by transaction type
                trans_type = TransactionType(typstr)
                stmt = (
                    select(Transaction)
                    .where(
                        Transaction.maker_id == user_id,
                        Transaction.type == trans_type
                    )
                    .order_by(Transaction.created_at.desc())
                )
            else:
                # Query all transactions
                stmt = (
                    select(Transaction)
                    .where(Transaction.maker_id == user_id)
                    .order_by(Transaction.created_at.desc())
                )

            result = await db.execute(stmt)
            transactions = result.scalars().all()

            # Calculate total amount (absolute values)
            total_amount = sum(abs(t.amount) for t in transactions) if transactions else 0.0

            return transactions, total_amount
        except Exception as e:
            print(f"Error in get_transaction_logs: {e}")
            return [], 0.0
        

    async def get_tokens_by_money(self,token_cal_svc:TokenCostCalculator,model_str:str='default',money_list:list=settings.BILL_PRICE_SET)->dict:
        if not money_list:
            money_list = [25 * (2 ** n) for n in range(10) if 25 * (2 ** n) < 500]
        
        #result = {x:await token_cal_svc.money_to_tokens(amount=x,model=model_str) for x in money_list}
        return money_list

    async def get_bill_datas(self, db: AsyncSession,token_cal_svc:TokenCostCalculator, user_id: int) -> Optional[Dict]:
        """Get user bill data by user_id"""
        
        data, total_left = await self.get_transaction_logs(db=db,typstr="",user_id=user_id)
        _, total_recharged = await self.get_transaction_logs(db=db,typstr="recharge",user_id=user_id)
        # Get monthly consume transactions and total amount
        _, monthly_trans = await self.get_month_trans(user_id, 'consume', db)
        money_tokens = settings.BILL_PRICE_SET
        return {  
            'balance':total_left,
            'monthly_trans':monthly_trans,
            'trans_logs':data, 
            'total_recharge':total_recharged,
            'money_tokens':money_tokens
        }



