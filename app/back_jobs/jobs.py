from datetime import datetime
from app.core.database import AsyncSessionLocal
from app.back_jobs.db_tasks import clean_expired_files_db

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