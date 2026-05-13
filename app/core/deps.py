from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from httpx import get
from jose import JWTError
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.core.security import verify_token,get_subject_from_token
from app.core.config import settings
from app.core.database import get_db, get_db_manual
from app.features.user.model.user_model import User, UserRole
from app.features.user.user_crud import user_crud
from app.features.user.schemas.user_schema import UserInDbWithPwd,UserLoginResp
import logging
from app.features.biz.data_func import DataCollector
from fastapi import Request, HTTPException
from app.services.oneapi_svc import OneAPISvc
from app.features.message.message_repo import MessageRepo
from app.features.biz.order.order_repo import OrderRepo
from app.features.biz.order.order_schema import OrderCreateOut
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.features.biz.user_balance.transaction_reop import TransactionRepo
from app.features.biz.apikey.apikey_crud import apikey_crud
from app.core.abc_biz import ConsumeService, CommissionService, BuyService, BaseService
from app.features.biz.order.price_repo import PriceRepo
from app.services.token_money_svc import TokenCostCalculator
from app.features.tron_address.address_repo import AddressSvc
from app.services.redis_svc import get_redis

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

async def get_user_crud():
    return user_crud

async def get_msg_repo(db:AsyncSession = Depends(get_db)):
    return MessageRepo(db=db)

async def get_address_pool_repo(db:AsyncSession =Depends(get_db),redis:Redis = Depends(get_redis)):
    return AddressSvc(db=db,redis=redis)

async def get_price_repo(db:AsyncSession=Depends(get_db)):
    return PriceRepo(db=db)

async def get_token_cal_svc(price_db:PriceRepo=Depends(get_price_repo)):
    return TokenCostCalculator(price_db=price_db)

async def get_order_rep(db:AsyncSession= Depends(get_db_manual),
            addressRepo:AddressSvc = Depends(get_address_pool_repo)):
    return OrderRepo(db=db,address_pool_svc=addressRepo)

async def get_token_usage_rep(db:AsyncSession= Depends(get_db_manual)):
    return TokenUsageRepo(db=db)

async def get_transaction_rep(db:AsyncSession= Depends(get_db_manual)):
    return TransactionRepo(db=db)
 
async def get_oneapi_svc(request: Request) -> OneAPISvc:
    svc = getattr(request.app.state, "oneapi_svc", None)
    if svc is None:
        raise HTTPException(status_code=500, detail="OneAPISvc 未初始化，请检查 lifespan 配置")
    return svc


async def get_base_svc(transc_rep:TransactionRepo = Depends(get_transaction_rep)) -> BaseService:  
    return BaseService(transc_rep=transc_rep, redis_client=None)


async def get_buy_svc(base:BaseService=Depends(get_base_svc),
    token_repo:TokenUsageRepo = Depends(get_token_usage_rep),
    order_repo:OrderRepo=Depends(get_order_rep),
    token_cal:TokenCostCalculator = Depends(get_token_cal_svc)) -> BuyService:
    return BuyService(base, order_repo=order_repo,
        token_repo= token_repo,
        token_cal_svc=token_cal
                )


async def get_commission_svc(
    user_crud_svc=Depends(get_user_crud),
    base:BaseService=Depends(get_base_svc)) -> CommissionService:
    return CommissionService(user_repo=user_crud_svc,base=base)


async def get_consume_svc(base:BaseService=Depends(get_base_svc), 
    commission_svc:CommissionService=Depends(get_commission_svc),
    price_cal_svc:TokenCostCalculator=Depends(get_token_cal_svc)) -> ConsumeService:
    return ConsumeService(base, CommissionService=commission_svc, PriceCal=price_cal_svc)


async def get_apikey_crud():
    return apikey_crud


async def get_data_collector(db:AsyncSession= Depends(get_db)):
    return DataCollector(db=db)

# ✅ 1. 修复：get_user_by_token —— 改为异步查询 + await
async def get_user_by_token(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
    ) -> Optional[User]:
    try:
        user_id = verify_token(token)
        if not user_id:
            return None

        result = await db.execute(select(User).where(User.id == int(user_id)))
        user = result.scalars().first()
        return user
    except Exception as e:
        logger.warning(f"Error in get_user_by_token: {e}")
        return None


# ✅ 3. get_current_user_with_pwd —— 已基本正确，但补充 error logging（可选）
async def get_current_user_with_pwd(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> UserInDbWithPwd:
    try:
        user_id = get_subject_from_token(token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await user_crud.get_by_id(db, id=int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        return UserInDbWithPwd.model_validate(user)

    except (JWTError, ValidationError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ✅ 4. get_current_user —— 关键修复：commit/refresh 加 await；查询用 select；avatar 预加载？
async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> UserLoginResp:
    try:
        user_id = get_subject_from_token(token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # 假设 user_crud.get_by_id 是异步的（你已用 await，说明它已是 async）
        user = await user_crud.get_by_id(db, id=int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        # ✅ 修复：invite_code 生成 & 异步提交
        if user.invite_code is None:
            from app.core.security import generate_invite_code
            inv = generate_invite_code(int(str(user.id)))
            user.invite_code = inv  # 直接赋值（SQLAlchemy 2.0+ 支持）
            await db.commit()
            await db.refresh(user)  # 重新加载，确保 invite_code 生效

       
       

        return UserLoginResp.model_validate(user)

    except (JWTError, ValidationError) as e:
        logger.warning(f"Token validation failed in get_current_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ✅ 5. admin_required —— 必须改为 async 依赖！
#    否则 Depends(get_current_user) 会报错：can't await in sync function
async def admin_required(
    current_user: UserLoginResp = Depends(get_current_user)
) -> UserLoginResp:
    # 特殊超级管理员邮箱白名单（注意：应避免硬编码！建议用配置或 DB 角色）
    if current_user.email == "wyb6688@hotmail.com":
        return current_user

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user

import qrcode
import io
import base64
import json

def gen_qr_code(data: str) -> str:
    qr = qrcode.make(data)
    buf = io.BytesIO()
    qr.save(buf)
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return qr_b64

def gen_qr_code_dic(data:OrderCreateOut) -> str:
    data_str = json.dumps({'token':data.token, 'amount': data.amount,'pay_address': data.to_address}, ensure_ascii=False)
 
    qr = qrcode.QRCode(
        version=1,  # 控制二维码大小，1~40
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=16,  # 每个格子的像素大小
        border=4,     # 边框格子宽度
        )
    qr.add_data(data_str)
    qr.make(fit=True)     
    img = qr.make_image(fill_color="black", back_color="white")    
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode("utf-8")
    return img_base64