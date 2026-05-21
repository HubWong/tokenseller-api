import redis.asyncio as redis
from app.core.config import settings

 

async def get_redis():   
    return await redis.from_url(
    settings.REDIS_URL,
    max_connections=settings.REDIS_POOL_SIZE,   
    db=0,
    decode_responses=True,  # 自动转字符串
)




async def close_redis():
    print('redis is closing...')
    redis_client = await get_redis()
    await redis_client.close()