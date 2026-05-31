from datetime import datetime

from app.core.database import AsyncSessionLocal
from app.back_jobs.db_tasks import clean_expired_files_db
from app.services.oneapi.oneapi_models_sync import ModelPricingSyncService
from app.features.biz.order.price_repo import PriceRepo
from app.features.biz.order.order_repo import OrderRepo
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
oneapi_url = settings.ONEAPI_URL


async def job_clean_expired_files():
    async with AsyncSessionLocal() as session:
        await clean_expired_files_db()


async def job_remove_expired_orders():
    async with AsyncSessionLocal() as session:
        order_repo = OrderRepo(session)
        await order_repo.remove_expired_orders()


async def job_sync_db_onapi_channels():
    async with AsyncSessionLocal() as session:
        await ModelPricingSyncService.sync_from_channels(db=session)
    logger.info("[==>] job_sync_db_onapi_channels running... %s", datetime.now())


async def job_gen_reports():
    logger.info("job_gen_reports running... %s", datetime.now())
    


async def get_model_pricing_cache():
    """从数据库加载模型定价数据到内存缓存"""
    # 这里应该有实际的数据库查询逻辑，示例中用静态数据代替
    async with AsyncSessionLocal() as session:
        price_repo = PriceRepo(session)
        pricing_data = await price_repo.get_all_db_models(active_only=True)
        # 将数据转换为字典格式，方便快速访问
        
        return pricing_data
   