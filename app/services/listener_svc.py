import json
from app.services.redis_svc import get_redis
from app.core.config import settings
from app.features.biz.order.order_schema import OrderInDBBase
 

webhook_url = settings.FRONTEND_URL
payoneer_webhook_url = settings.PAYONEER_WEBHOOK_URL
payoneer_status_url = settings.PAYONEER_WEBHOOK_URL.replace('/status', '')

# Redis key prefixes
ORDER_POOL_KEY = "order_pool:orders"       # Hash: order_id -> order_json
ADDRESS_MAP_KEY = "order_pool:addresses"   # Hash: to_address -> order_id
PAYMENT_CHANNEL = "payment_notifications"  # Pub/Sub channel


class OrderPool:
    """Redis-backed order pool, shared across FastAPI and Listener processes"""
    def __init__(self, redis=None) -> None:
        self._redis = redis
        # Local cache for fast lookup in listener process
        self._address_cache = dict()  # to_address -> order_id
        self.order_repo = None

    async def init_redis(self):
        """Initialize redis connection, call during app/listener startup"""
        if self._redis is None:
            self._redis = await get_redis()

    async def add_order(self, order:OrderInDBBase):
        order_id = getattr(order, 'id', None)
        if not order_id:
            return

        if hasattr(order, 'model_dump'):
            order_data = order.model_dump(mode='json')
        elif hasattr(order, '__dict__'):
            order_data = {k: v for k, v in order.__dict__.items() if not k.startswith('_')}
        else:
            order_data = dict(order)

        order_json = json.dumps(order_data)

        pipe = self._redis.pipeline()
        pipe.hset(ORDER_POOL_KEY, str(order_id), order_json)

        to_address = getattr(order, 'to_address', None)
        if to_address:
            pipe.hset(ADDRESS_MAP_KEY, to_address, str(order_id))
            self._address_cache[to_address] = order_id

        await pipe.execute()

    async def get_order(self, order_id: int):
        order_json = await self._redis.hget(ORDER_POOL_KEY, str(order_id))
        if order_json:
            return json.loads(order_json)
        return None

    async def get_order_id_by_address(self, to_address: str):
        """Get order_id by to_address, used by TronListener"""
        # Check local cache first
        if to_address in self._address_cache:
            return self._address_cache[to_address]
        # Fallback to Redis
        order_id = await self._redis.hget(ADDRESS_MAP_KEY, to_address)
        if order_id:
            self._address_cache[to_address] = int(order_id)
            return int(order_id)
        return None

    async def remove_order(self, order_id: int):
        order_json = await self._redis.hget(ORDER_POOL_KEY, str(order_id))
        if order_json:
            order_data = json.loads(order_json)
            to_address = order_data.get('to_address')
            pipe = self._redis.pipeline()
            pipe.hdel(ORDER_POOL_KEY, str(order_id))
            if to_address:
                pipe.hdel(ADDRESS_MAP_KEY, to_address)
                self._address_cache.pop(to_address, None)
            await pipe.execute()

    async def clear_order_pool(self):
        """Remove all cached orders from Redis and clear local address cache."""
        await self._redis.delete(ORDER_POOL_KEY, ADDRESS_MAP_KEY)
        self._address_cache.clear()

    async def load_pending_orders(self, order_repo):
        """Load all pending orders from DB into Redis pool (call on startup)."""
      
        await self.init_redis()
        await self.clear_order_pool()

        orders = await order_repo.get_unfinished_orders()
        for order in orders:
            await self.add_order(order)
        print(f'Order pool initialized with {len(orders)} orders')

    async def publish_payment(self, order_id: int, payment_data: dict):
        """Publish payment notification via Redis Pub/Sub"""
        msg = json.dumps({
            'order_id': order_id,
            **payment_data
        })
        await self._redis.publish(PAYMENT_CHANNEL, msg)

    async def update_confirmed_order(self,payment_data:dict):
        """update order in order_repo"""
        order_id = payment_data['order_id']
        ...
        # TODO: Implement order update logic

    async def has_orders(self) -> bool:
        """Check if there are any orders in the pool"""
        count = await self._redis.hlen(ADDRESS_MAP_KEY)
        return count > 0

    async def subscribe_payments(self):
        """Subscribe to payment notifications (used by FastAPI process)"""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(PAYMENT_CHANNEL)
        return pubsub

order_pool = OrderPool()
 
       

