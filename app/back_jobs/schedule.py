from apscheduler.schedulers.background import BackgroundScheduler
from app.back_jobs.jobs import job_clean_expired_files,job_remove_expired_orders, job_gen_reports,get_model_pricing_cache
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI
import asyncio
from app.services.file_svc import create_upload_dir
from concurrent.futures import ThreadPoolExecutor
from app.services.oneapi_svc import OneAPISvc
from app.services.listener_svc import order_pool
from app.core.config import settings
from app.core.database import Base, async_engine, sync_columns
from sqlalchemy import text
from listener import main as run_listener
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

scheduler: BackgroundScheduler | None = None
executor = ThreadPoolExecutor(max_workers=1)

def start_scheduler():    
    global scheduler
    if scheduler:
        return scheduler  

    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        job_clean_expired_files,
        "interval",
        minutes=10,
        id="clean_files",
        replace_existing=True
    )

    scheduler.add_job(
        job_remove_expired_orders,
        "interval",
        minutes=30,
        id="remove_expired_orders",
        replace_existing=True
    )

    scheduler.add_job(
        job_gen_reports,
        "interval",
        weeks=1,
        id="gen_reports",
        replace_existing=True
    )

    scheduler.start()
    print('Scheduler started.')
    return scheduler



def stop_scheduler():
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        print("Scheduler stopped.")
        
 
async def init_db():
    """根据模型定义自动创建不存在的表"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_pricing_data():
    """插入默认模型定价数据（如已存在则更新）"""
    sql = text("""
        INSERT INTO model_pricing
        (model_name, input_cost, output_cost, input_price, output_price, currency, is_active, level, created_at)
        VALUES
        ('DeepSeek-V4 Flash', 0.0028, 0.28, 0.00448, 0.448, 'USD', 1, 3, NOW()),
        ('Qwen3.6 Flash (通义)', 0.0056, 0.028, 0.00896, 0.0448, 'USD', 1, 3, NOW()),
        ('文心4.0 Turbo', 0.021, 0.084, 0.0336, 0.1344, 'USD', 1, 3, NOW()),
        ('GLM-4 Air (智谱)', 0.042, 0.14, 0.0672, 0.224, 'USD', 1, 3, NOW()),
        ('讯飞星火4.0', 0.07, 0.28, 0.112, 0.448, 'USD', 1, 3, NOW()),
        ('Qwen3.6 Plus (通义)', 0.28, 1.68, 0.448, 2.688, 'USD', 1, 3, NOW()),
        ('DeepSeek-V4 Pro', 0.42, 0.84, 0.672, 1.344, 'USD', 1, 3, NOW())
        ON CONFLICT (model_name) DO UPDATE SET
            input_cost = EXCLUDED.input_cost,
            output_cost = EXCLUDED.output_cost,
            input_price = EXCLUDED.input_price,
            output_price = EXCLUDED.output_price,
            currency = EXCLUDED.currency,
            is_active = EXCLUDED.is_active,
            level = EXCLUDED.level
    """)
    async with async_engine.begin() as conn:
        await conn.execute(sql)
    logger.info("Seed pricing data checked.")


def login_info(message: str):
    logger.info('environment: %s | %s', settings.APP_ENV, message)
    logger.info('database: %s', settings.SQL_DB_URL.split("://")[0] if settings.SQL_DB_URL else "unknown")
   

'''
Singleton services:
   - RedisBalanceService
   - BillingEngine
   - CommissionService
   ↓
Request scoped:
   - DB Session
   - LedgerService
'''
@asynccontextmanager
async def lifespanJob(app: FastAPI):
    login_info("Starting up application...")
    await init_db()
    await sync_columns()
    await seed_pricing_data()
    create_upload_dir()
    app.state.oneapi_svc = OneAPISvc()
    app.state.model_price_cache = await get_model_pricing_cache() # 用于缓存模型定价数据，减少数据库查询
    # Initialize Redis connection for order_pool (shared with listener process)
    await order_pool.init_redis()

    async def _listener_background():
        try:
            await run_listener()
        except asyncio.CancelledError:
            logger.info("Tron listener task cancelled")
            raise
        except Exception:
            logger.exception("Tron listener task crashed")

    app.state.tron_listener_task = asyncio.create_task(_listener_background())

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(executor, start_scheduler)
    try:
        yield
    finally:
        if getattr(app.state, "tron_listener_task", None):
            app.state.tron_listener_task.cancel()
            with suppress(asyncio.CancelledError):
                await app.state.tron_listener_task

        await app.state.oneapi_svc.aclose()
        await loop.run_in_executor(executor, stop_scheduler)