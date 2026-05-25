from datetime import datetime
from app.core.database import AsyncSessionLocal
from app.back_jobs.db_tasks import clean_expired_files_db
from app.features.biz.order.price_repo import PriceRepo
from app.core.deps import get_price_repo
import asyncio

async def run_clean():
    async with AsyncSessionLocal() as session:
        await clean_expired_files_db(session)

def job_clean_expired_files():    
    asyncio.run(run_clean())
    pass


def job_gen_reports():
    print("job_gen_reports running...",datetime.now())
    pass

async def get_model_pricing_cache():
    """从数据库加载模型定价数据到内存缓存"""
    # 这里应该有实际的数据库查询逻辑，示例中用静态数据代替
    async with AsyncSessionLocal() as session:
        price_repo = PriceRepo(session)
        pricing_data = await price_repo.get_all_db_models(active_only=True)
        # 将数据转换为字典格式，方便快速访问
        
        return pricing_data
   