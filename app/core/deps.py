from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession 
from typing import Annotated
from app.core.database import  get_db_manual,get_db
from app.features.biz.data_func import DataCollector
from app.features.message.message_repo import MessageRepo
from app.features.biz.order.order_repo import OrderRepo
from app.features.biz.order.order_schema import OrderCreateOut
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.features.biz.user_balance.transaction_reop import TransactionRepo
from app.features.biz.apikey.apikey_crud import apikey_crud
from app.features.biz.order.price_repo import PriceRepo
from app.features.tron_address.address_repo import AddressSvc
from app.services.redis_svc import get_redis
from app.features.user.user_crud import UserRepo
import logging
import qrcode
import io
import base64
import json

logger = logging.getLogger(__name__)


DbSessionDeps = Annotated[AsyncSession, Depends(get_db)]

async def get_msg_repo(db:DbSessionDeps):
    return MessageRepo(db=db)

async def get_address_pool_repo(db:DbSessionDeps,redis:Redis = Depends(get_redis)):
    return AddressSvc(db=db,redis=redis)

async def get_price_repo(db:DbSessionDeps):
    return PriceRepo(db=db)

PriceRepoDeps= Annotated[PriceRepo, Depends(get_price_repo)]


async def get_order_rep(db:AsyncSession= Depends(get_db_manual),
            addressRepo:AddressSvc = Depends(get_address_pool_repo)):
    return OrderRepo(db=db,address_pool_svc=addressRepo)

OrderRepoDeps = Annotated[OrderRepo, Depends(get_order_rep)]

async def get_token_usage_rep(db:AsyncSession= Depends(get_db_manual)):
    return TokenUsageRepo(db=db)

TokenUsageDeps = Annotated[TokenUsageRepo, Depends(get_token_usage_rep)]
async def get_transaction_rep(db:AsyncSession= Depends(get_db_manual)):
    return TransactionRepo(db=db)
 
TransRepoDeps = Annotated[TransactionRepo, Depends(get_transaction_rep)]

async def get_apikey_crud():
    return apikey_crud

async def get_user_repo(db:AsyncSession= Depends(get_db_manual)):
    return UserRepo()

UserRepoDeps = Annotated[UserRepo, Depends(get_user_repo)]

async def get_data_collector(db:AsyncSession= Depends(get_db)):
    return DataCollector(db=db)


def gen_qr_code(data: str) -> str:
    qr = qrcode.make(data)
    buf = io.BytesIO()
    qr.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return qr_b64
 

