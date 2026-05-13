from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
import time

scheduler = BackgroundScheduler()

def my_task():
    print("定时任务:运行时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    
def start_scheduler():
    scheduler.add_job(
        my_task,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        id="weekly_task",
        replace_existing=True,
    )
    scheduler.start()
    print("Scheduler started successfully.")

def stop_scheduler():
    scheduler.shutdown()
    print("Scheduler shutdown successfully.")
    

@asynccontextmanager
async def lifespanJob(app: FastAPI):
     # 在线程池中启动调度器（避免阻塞 async loop）
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, start_scheduler)

    yield

    # 在线程池中关闭调度器
    with ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, stop_scheduler)