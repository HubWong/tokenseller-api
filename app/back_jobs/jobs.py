from datetime import datetime

import httpx
from app.core.database import AsyncSessionLocal
from app.back_jobs.db_tasks import clean_expired_files_db
from app.services.oneapi.oneapi_models_sync import ModelPricingSyncService
from app.services.oneapi_svc import OneApiSvc
from app.features.biz.order.price_repo import PriceRepo
from app.features.biz.order.order_repo import OrderRepo
from app.core.config import settings
from app.services.tools_svc import check_api_reachable

oneapi_url = 'https://one-api-production-dd42.up.railway.app'
import asyncio
# 顶层统一运行异步任务的工具函数
def run_async_task(coro):
    """安全运行异步协程"""
    try:
        # 获取当前事件循环（如果存在）
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # 没有则创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # 运行协程直到完成
    return loop.run_until_complete(coro)

async def run_clean():
    async with AsyncSessionLocal() as session:
        await clean_expired_files_db()

async def run_remove_expired_orders():
    async with AsyncSessionLocal() as session:
        order_repo = OrderRepo(session)
        await order_repo.remove_expired_orders()

async def run_sync_chanels():
    async with AsyncSessionLocal() as session:
        await ModelPricingSyncService.sync_from_channels(db=session)

def job_clean_expired_files():    
    run_async_task(run_clean())
    

def job_remove_expired_orders():
    run_async_task(run_remove_expired_orders())
    

def job_sync_db_onapi_channels():
    run_async_task(run_sync_chanels())
    print("\n [==>]job_sync_db_onapi_channels running...",datetime.now())


def job_gen_reports():
    print("job_gen_reports running...",datetime.now())
    


async def get_model_pricing_cache():
    """从数据库加载模型定价数据到内存缓存"""
    # 这里应该有实际的数据库查询逻辑，示例中用静态数据代替
    async with AsyncSessionLocal() as session:
        price_repo = PriceRepo(session)
        pricing_data = await price_repo.get_all_db_models(active_only=True)
        # 将数据转换为字典格式，方便快速访问
        
        return pricing_data
   