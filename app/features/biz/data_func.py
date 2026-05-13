from typing import Any, Dict, Optional
from fastapi import HTTPException
from datetime import datetime,timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from collections.abc import Sequence
from app.features.user.model.user_model import User
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.features.biz.user_balance.schemas import DashboardStatsResponse,UsageStatsResponse

class DataCollector:
    def __init__(self, db:AsyncSession):
        self.db = db        

    async def get_token_datas(self,token_repo:TokenUsageRepo,  uid: int) ->DashboardStatsResponse:
        """
        Get dashboard overview statistics
        - Account Balance (USD)
        - Today's Token Usage
        - Total API Calls
        """
        try:
            # Warning if balance < $10
            return await  token_repo.get_token_datas(user_id=uid)
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))    
    
    async def get_daily(self,token_repo:TokenUsageRepo, uid:int, days:int =7)->Any:
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            data = await token_repo.get_token_usage_by_day(start_date, end_date, uid)

            # Convert to response format
            usage_data = []
            for item in data:
                usage_data.append({
                    "date": item['date'].strftime("%Y-%m-%d") if isinstance(item['date'], datetime) else str(item['date']),
                    "tokens_used": item['tokens_used'],
                    "cost_usd": item['cost_usd'],
                    "api_calls": item['api_calls']
                })

            return [UsageStatsResponse(**item) for item in usage_data]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
  
 
if __name__ =='__main__':
    pass

                


