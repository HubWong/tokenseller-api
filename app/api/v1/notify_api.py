from typing import Any, List,Dict, Union,Optional
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from fastapi.responses import StreamingResponse


from app.core.security import verify_token
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.core.deps import get_msg_repo
import asyncio
import json
from collections import deque

from app.features.message.message_repo import MessageRepo
from app.services.listener_svc import order_pool

router = APIRouter(prefix="/notify", tags=["notify"])

# 全局通知队列，用于存储待发送的通知
notification_queue = deque()
active_connections = set()



class ScheduledNotification(BaseModel):
    user_id: Optional[int] = None  # 如果为 None，则广播给所有用户
    message: str
    delay_seconds: int = 0  # 延迟多少秒后发送
    send_at: Optional[datetime] = None  # 或者指定具体时间发送


async def send_notification(user_id: Optional[int], message: str):
    """
    发送通知到客户端（添加到队列供 SSE 推送）
    """
    notification_data = {
        "type": "notification",
        "user_id": user_id,
        "message": message,
        "timestamp": datetime.now().isoformat(),
        'from':'host'
    }
    
    # 添加到通知队列
    notification_queue.append(notification_data)
    
    print(f"Notification queued: {message} for user {user_id}")

@router.get('/stream')
async def notification_stream(token: Optional[str] = Query(None),
                                msg_repo : MessageRepo = Depends(get_msg_repo)):
    """
    SSE 端点：客户端连接后持续接收通知
    
    支持通过 query param 传递 token（EventSource 不支持自定义 Header）
    客户端使用 EventSource API 连接此端点
    """
    # 从 query param 中解析用户信息
    user_id = None
    if token:
        try:
            payload = verify_token(token)
            if payload:
                user_id = payload.get("sub")
        except Exception:
            pass  # token 无效/过期时仍允许连接，只是无法定向推送

    async def event_generator():
        connection_id = id(event_generator)
        active_connections.add(connection_id)
        pubsub = None

        try:
            # Subscribe to Redis payment notifications
            if order_pool._redis:
                pubsub = await order_pool.subscribe_payments()

            # 发送连接成功消息
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to notification stream'})}\n\n"

            while True:
                # 检查内存队列中是否有新通知
                if notification_queue:
                    notification = notification_queue.popleft()

                    # 广播消息或发送给特定用户
                    if notification['user_id'] is None or str(notification['user_id']) == str(user_id):
                        yield f"data: {json.dumps(notification)}\n\n"

                # Check Redis Pub/Sub for payment notifications
                if pubsub:
                    try:
                        msg = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=0.1)
                        if msg and msg.get('type') == 'message':
                            payment_data = json.loads(msg['data'])
                            # Push payment notification to SSE
                            yield f"data: {json.dumps({'type': 'payment', **payment_data})}\n\n"
                    except asyncio.TimeoutError:
                        pass

                # 发送心跳保持连接
                yield f" \n heartbeat-{len(active_connections)}"

                # 等待一段时间再检查
                await asyncio.sleep(3)

        except asyncio.CancelledError:
            print(f"Client {connection_id} disconnected")
        finally:
            if pubsub:
                await pubsub.unsubscribe()
                await pubsub.close()
            active_connections.discard(connection_id)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@router.post('/schedule')
async def schedule_notification(
    notification: ScheduledNotification,
    background_tasks: BackgroundTasks
):
    """
    定时发送通知到客户端
    
    参数:
    - user_id: 目标用户ID，如果为None则广播给所有用户
    - message: 消息内容
    - delay_seconds: 延迟秒数
    - send_at: 指定发送时间（可选，优先级高于delay_seconds）
    """
    # 计算发送时间
    if notification.send_at:
        delay = (notification.send_at - datetime.now()).total_seconds()
        if delay < 0:
            return {"success": False, "message": "Send time must be in the future"}
    else:
        delay = notification.delay_seconds
    
    if delay <= 0:
        # 立即发送
        await send_notification(notification.user_id, notification.message)
        return {"success": True, "message": "Notification sent immediately"}
    
    # 添加后台任务
    background_tasks.add_task(
        asyncio.sleep,
        delay
    )
    background_tasks.add_task(
        send_notification,
        notification.user_id,
        notification.message
    )
    
    return {
        "success": True,
        "message": f"Notification scheduled to be sent in {delay} seconds",
        "scheduled_time": (datetime.now() + timedelta(seconds=delay)).isoformat()
    }

