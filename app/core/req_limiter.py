from fastapi import Request, HTTPException, status
from slowapi import Limiter
from app.core.config import settings
from app.core.security import verify_token
from slowapi.util import get_remote_address
import redis.asyncio as redis
from app.services.redis_svc import get_redis
from app.features.user.schemas.user_role import UserRole
from typing import Optional

def _get_user_context(request: Request) -> dict:
    if hasattr(request.state, "_user_ctx"):
        return request.state._user_ctx

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header else ""
    
    ctx = {"is_authenticated": False, "user_id": None, "role": "normal"}
    if token:
        try:
            payload = verify_token(token)
            if payload:
                ctx.update({
                    "is_authenticated": True,
                    "user_id": payload.get("sub"),
                    "role": payload.get("role", "normal")
                })
        except Exception:
            pass  # Token 无效/过期时降级处理
    
    request.state._user_ctx = ctx
    return ctx

# 1. 自定义限流 Key：按 user_id 隔离，未登录则按 IP
def get_rate_limit_key(request: Request) -> str:
    ctx = _get_user_context(request)
    if ctx["is_authenticated"] and ctx["user_id"]:
        return f"user:{ctx['user_id']}"
    return f"ip:{get_remote_address(request)}"

# 2. 动态限流阈值生成器
def dynamic_rate_limit(request: Request) -> str:
    ctx = _get_user_context(request)
    role = ctx["role"]
    
    # 只限制 free 角色的用户，VIP 和 Admin 不受限
    if role == UserRole.USER.value:
        return "50/minute; 500/hour"    # User 角色限流
    return None  # 其他角色不限流

# 3. 初始化 Limiter（生产环境务必使用 Redis）
limiter = Limiter(
    key_func=get_rate_limit_key,
    storage_uri=settings.REDIS_URL,
    default_limits=["100/minute"],  # 兜底策略
    headers_enabled=True            # 自动返回 X-RateLimit-* 响应头
)

# 4. Redis 客户端用于并发限制
redis_client: Optional[redis.Redis] = None

# async def get_redis_client() -> redis.Redis:
#     """获取 Redis 客户端单例"""
#     global redis_client
#     if redis_client is None:
#         redis_client = await redis.from_url(
#             settings.REDIS_URL,
#             encoding="utf-8",
#             decode_responses=True
#         )
#     return redis_client

# 5. 并发限制配置
CONCURRENCY_LIMITS = {
    "User": 5,        # User 角色最多 5 个并发请求
    "VIP": None,      # VIP 不限制
    "Admin": None,    # Admin 不限制
    None: None        # 未认证不限制
}

async def check_concurrency_limit(request: Request) -> bool:
    """
    检查并发限制
    
    使用 Redis 计数器跟踪每个用户的并发请求数
    请求开始时计数+1，结束时计数-1
    """
    ctx = _get_user_context(request)
    role = ctx.get("role")
    
    # 获取该角色的并发限制
    limit = CONCURRENCY_LIMITS.get(role)
    if limit is None:
        return True  # 不限制
    
    user_id = ctx.get("user_id")
    if not user_id:
        return True  # 未登录用户不限制
    
    try:
        client = await get_redis()
        
        # Redis key: concurrency:{user_id}
        key = f"concurrency:{user_id}"
        
        # 获取当前并发数
        current = await client.incr(key)
        
        # 设置过期时间（5分钟，防止僵尸计数）
        await client.expire(key, 300)
        
        if current > limit:
            # 超过限制，回滚计数
            await client.decr(key)
            return False
        
        # 将计数信息存入 request.state，以便请求结束时清理
        request.state._concurrency_key = key
        return True
        
    except Exception as e:
        # Redis 出错时不限制，避免影响正常服务
        print(f"Redis concurrency check failed: {e}")
        return True

async def release_concurrency_limit(request: Request):
    """释放并发计数"""
    if hasattr(request.state, "_concurrency_key"):
        try:
            client = redis_client or await get_redis()
            await client.decr(request.state._concurrency_key)
        except Exception as e:
            print(f"Redis concurrency release failed: {e}")

# 6. 限流中间件
async def rate_limit_middleware(request: Request, call_next):
    """
    综合限流中间件
    
    1. 检查并发限制（只对 free 角色生效）
    2. 调用 slowapi 的请求速率限制
    3. 请求结束后释放并发计数
    """
    # 跳过 SSE 长连接路径，避免限流影响推送
    if request.url.path == "/notify/stream":
        return await call_next(request)
    
    ctx = _get_user_context(request)
    role = ctx.get("role")
    
    # 只对 free 角色进行并发限制
    if role == UserRole.USER.value:
        if not await check_concurrency_limit(request):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many concurrent requests. Please wait and try again."
            )
    
    try:
        response = await call_next(request)
        return response
    finally:
        # 释放并发计数
        if role == UserRole.USER.value:
            await release_concurrency_limit(request)