from fastapi import HTTPException
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.features.biz.user_balance.schemas import DashboardStatsResponse, UsageStatsResponse

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
    
    async def get_daily(self, token_repo: TokenUsageRepo, uid: int, days: int = 7) -> list[UsageStatsResponse]:
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days - 1)

            data = await token_repo.get_token_usage_by_day(start_date, end_date, uid)

            # 建立日期 -> 数据 映射
            data_map = {}
            for item in data:
                date_str = item['date'].strftime("%Y-%m-%d") if isinstance(item['date'], datetime) else str(item['date'])
                data_map[date_str] = item

            # 填充所有日期，无数据的天显示零值
            usage_data = []
            for i in range(days):
                d = start_date + timedelta(days=i)
                date_str = d.strftime("%Y-%m-%d")
                if date_str in data_map:
                    item = data_map[date_str]
                    usage_data.append(UsageStatsResponse(
                        date=date_str,
                        tokens_used=float(item['tokens_used']),
                        cost_usd=float(item['cost_usd']),
                        api_calls=int(item['api_calls'])
                    ))
                else:
                    usage_data.append(UsageStatsResponse(
                        date=date_str,
                        tokens_used=0.0,
                        cost_usd=0.0,
                        api_calls=0
                    ))

            return usage_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
  
 
if __name__ =='__main__':
    pass

                


