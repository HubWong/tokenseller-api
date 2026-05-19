from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta,date
from collections.abc import Sequence
from sqlalchemy import func, select, desc
from typing import Optional, Any,Dict
from app.features.biz.usage.model import TokenUsageLog
from app.features.biz.usage.schema import TokenUsageRecord
from app.features.biz.user_balance.schemas import DashboardStatsResponse
from app.core.config import settings

class TokenUsageRepo:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def recharge_tokens(
        self,
        session: AsyncSession,
        user_id: int,
        provider: str,
        amount: float,
        cost: float = 0,
        type: str = 'recharge'
    ):
        try:
            newData = TokenUsageLog(
                user_id=user_id,
                memo=type,
                amount=amount,
                cost=cost,
                provider=provider
            )
            session.add(newData)
            
            return newData
        except Exception as e:
            await session.rollback()
            print(f"Error updating tokens: {e}")
            return None
        
    async def add_token_log(self,db:AsyncSession,resp_data:str, uid :int,json_data:Dict):
        new_log = TokenUsageLog(
            user_id=uid,
            request_data=str(json_data),
            is_stream = json_data.get('stream',False),
            memo= resp_data or '',
            provider='deepseek',
            model = json_data.get('model','unknown'),
            amount =0
        )
        try:
            db.add(new_log)
            await db.commit()
            await db.refresh(new_log)
        except Exception as ex:
            await db.rollback()
            print("error:", str(ex))
            return None
        return new_log
 
        
    async def get_usage_log_by_id(self,db:AsyncSession,logid:int) -> Optional[TokenUsageRecord]:
        result = await db.execute(
            select(TokenUsageLog).where(TokenUsageLog.id == logid)
        )
        log = result.scalars().first()
        if log:
            return TokenUsageRecord.model_validate(log)
        return None

    async def get_monthly_usage(self, user_id: int) -> float:
        """
        Get total token usage for current month
        """
        try:
            stmt = (
                select(func.sum(TokenUsageLog.amount))
                .where(
                    TokenUsageLog.user_id == user_id,
                    func.extract('year', TokenUsageLog.created_at) == datetime.now().year,
                    func.extract('month', TokenUsageLog.created_at) == datetime.now().month
                )
            )

            result = await self.db.execute(stmt)
            total = result.scalar()

            return float(total) if total else 0.0
        except Exception as e:
            print(f"Error getting monthly usage: {e}")
            return 0.0

    async def recharge_token(self, log:TokenUsageLog):
        try:
            self.db.add(log)
            await self.db.commit()
            await self.db.refresh(log)
            return log
        except Exception as ex:
            await self.db.rollback()

   
    
    '''
    get request count, data and sum the tokens(left)
    '''
    async def get_request_log(self, uid: int, page: int = 1, limit: int = 10):
        try:
            base_query = select(TokenUsageLog).where(TokenUsageLog.user_id == uid)

            # 1. 统计记录数 (仅 api 请求)
            count_query = select(func.count()).select_from(TokenUsageLog)\
                .where(TokenUsageLog.user_id == uid, TokenUsageLog.memo.startswith('api'))
            total_result = await self.db.execute(count_query)
            total_records = total_result.scalar()

            # 2. 合并查询使用量: 条件聚合一次性获取使用量(非充值)和充值量
            stats_query = select(
                func.sum(TokenUsageLog.amount).filter(TokenUsageLog.memo != 'recharge').label('used'),
                func.sum(TokenUsageLog.amount).filter(TokenUsageLog.memo == 'recharge').label('recharged')
            ).where(TokenUsageLog.user_id == uid)

            stats_result = await self.db.execute(stats_query)
            row = stats_result.first()
            token_used = row.used or 0
            recharged = row.recharged or 0

            left_token = settings.FREE_TOKENS - token_used + recharged

            # 3. 获取当前页数据
            data_query = base_query.offset((page - 1) * limit).limit(limit)
            data_result = await self.db.execute(data_query)
            data = data_result.scalars().all()

            return total_records, data, token_used, left_token
        except Exception as ex:
            print('error', str(ex))
      
     
    async def get_token_datas(self,  user_id: int ,days:int = 7):
         
        total_rqst, _,token_used,_ = await self.get_request_log(uid=user_id)
        # Get last 5 days usage
        from_day = datetime.now() - timedelta(days=days)
        to_day = datetime.now()
        recent_usage = await self.get_token_usage_by_day(from_day=from_day,
                                to_day=to_day,
                                user_id=user_id)

        # Calculate today's tokens from recent usage
        # Calculate today's tokens from recent usage
        today_str = date.today().strftime("%Y-%m-%d")
        today_tokens_used = next(
            (item['tokens_used'] for item in recent_usage if str(item['date']) == today_str),
            0
        )
        # TODO: Implement total API calls from request logs     

        return DashboardStatsResponse(   
                token_used=token_used,             
                today_tokens_used=today_tokens_used or 0.0,
                total_api_calls=total_rqst or 0,
                low_balance_warning=True,
                dailyUsage = []
            )

    async def get_token_usage_by_day(
        self,
        from_day: datetime,
        to_day: datetime,
        user_id: int        
    ) -> Sequence[Any]:
        """
        Get token usage grouped by day for a user within a date range
        """
        try:
            # Query to group usage by date
            stmt = (
                select(
                    func.date(TokenUsageLog.created_at).label('date'),
                    func.sum(TokenUsageLog.amount).label('tokens_used'),
                    func.sum(TokenUsageLog.sale_price).label('cost_usd'),
                    func.count(TokenUsageLog.id).label('api_calls')
                )
                .where(
                    TokenUsageLog.user_id == user_id,
                    TokenUsageLog.created_at >= from_day,
                    TokenUsageLog.created_at <= to_day,
                    TokenUsageLog.amount < 0
                )
                .group_by(func.date(TokenUsageLog.created_at))
                .order_by(desc(func.date(TokenUsageLog.created_at)))
            )

            result = await self.db.execute(stmt)
            rows = result.all()

            # Convert to list of objects with date attribute
            usage_data = []
            for row in rows:
                usage_data.append({
                    'date': row.date,
                    'tokens_used': abs(float(row.tokens_used)) if row.tokens_used else 0.0,
                    'cost_usd': float(row.cost_usd) if row.cost_usd else 0.0,
                    'api_calls': int(row.api_calls) if row.api_calls else 0
                })

            return usage_data

        except Exception as e:
            print(f"Error in get_token_usage_by_day: {e}")
            return []