import socketio
import redis.asyncio as redis
from app.core.config import settings


# Redis manager
mgr = socketio.AsyncRedisManager(
    settings.REDIS_URL
)

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins="*",
    client_manager=mgr,
    max_http_buffer_size=10 * 1024 * 1024
)

 
from app.socket.events import init_events,room_events,user_events
# Connect to Redis
redis_client = redis.from_url(settings.REDIS_URL)

