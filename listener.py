from app.core.abc.abc_biz import BaseService, BuyService, logger
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.features.biz.user_balance.transaction_reop import TransactionRepo
from app.services.token_money_svc import TokenCostCalculator
from app.services.tron_svc import TronListener
from app.services.listener_svc import order_pool
from app.core.database import AsyncSessionLocal
from app.features.biz.order.order_repo import OrderRepo
import asyncio

async def main():
    # Initialize Redis connection for order_pool
    await order_pool.init_redis()

    # Configure TRON RPC endpoints (use Trongrid or private nodes)
    rpc_pool = [
        "https://api.trongrid.io",
        "https://api.trongrid.org"
    ]

    async with AsyncSessionLocal() as session:
        transaction_repo = TransactionRepo(db=session)
        base_service = BaseService(db=session, redis_client=order_pool._redis)
        order_repo = OrderRepo(db=session)
        token_repo = TokenUsageRepo(db=session)
        token_cal_svc = TokenCostCalculator(price_db=session)

        buy_service = BuyService(
            base=base_service,
            order_repo=order_repo,
            token_repo=token_repo,
            token_cal_svc=token_cal_svc,
        )

        # Load pending orders from DB into Redis pool
        await order_pool.load_pending_orders(order_repo)

        # TRON listener for payment detection
        tron_listener = TronListener(rpc_pool=rpc_pool, order_pool=order_pool)

        async def callback(data, type='tron'):
            if type != 'tron':
                raise ValueError('not supported type')

            order_id = data.get('order_id')
            if not order_id:
                logger.warning('Missing order_id in TRON callback event: %s', data)
                return

            try:
                paid = await buy_service.pay_order(order_id)
                if not paid:
                    logger.warning('Payment processing failed or order not found: %s', order_id)
                    return

                try:
                    await order_pool.remove_order(order_id)
                except Exception:
                    logger.exception('Failed to remove order %s from Redis pool', order_id)

                try:
                    await order_pool.publish_payment(order_id, {
                        'status': 'confirmed',
                        'tx_hash': data.get('tx_hash'),
                        'value': data.get('value'),
                    })
                except Exception:
                    logger.exception('Failed to publish payment notification for order %s', order_id)

            except Exception:
                logger.exception('Error handling TRON callback for order %s', order_id)
                raise

        # Start all listeners
        await tron_listener.start(callback)

if __name__ == "__main__":
    asyncio.run(main())


