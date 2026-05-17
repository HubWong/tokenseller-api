from apscheduler.schedulers.background import BackgroundScheduler
from app.back_jobs.jobs import job_clean_expired_files, job_gen_reports
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI
import asyncio
from app.services.file_svc import create_upload_dir
from concurrent.futures import ThreadPoolExecutor
from app.services.oneapi_svc import OneAPISvc
from app.services.listener_svc import order_pool
from app.core.config import settings
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
    create_upload_dir()
    app.state.oneapi_svc = OneAPISvc()

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