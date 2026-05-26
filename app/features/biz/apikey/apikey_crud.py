from typing import Optional
from aiohttp import http_exceptions
from aiohttp.http_exceptions import HttpBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from collections.abc import Sequence
from fastapi import Request,HTTPException
from sqlalchemy import select
from app.features.crud_base import CRUDBase
from app.features.db_base import ApiResp
from app.features.biz.apikey.apikey_model import ApiKey
from app.features.biz.apikey.apikey_schema import ApiKeyResp
from app.core.security import gen_api_key
import json
from datetime import  datetime,timedelta

from app.features.biz.user_balance.transaction_reop import TransactionRepo



class CRUDApiKey(CRUDBase[ApiKey, ApiKeyResp, ApiKeyResp]):       
  

    async def generate_api_key(
        self, db: AsyncSession, user_id: int, key_title: str = "key1", 
        tier: str = "free"
        ) -> str:
       
        key = gen_api_key(user_id=user_id)
        api_key = ApiKey(
            user_id=user_id,
            key=key,
            status="active",           
            rpm_limit = 60,
            tier = tier,
            name=key_title,
        )
        try:
            db.add(api_key)
            await db.commit()
            await db.refresh(api_key)
        except Exception as ex:
            await db.rollback()
            print("error:", str(ex))
        return key   
     
    async def auth_user(self,db: AsyncSession, request: Request,balance_repo:TransactionRepo) -> ApiKey:
        auth = request.headers.get("Authorization")
        if not auth:
            raise HTTPException(401, "Missing API Key")
        key = auth.replace("Bearer ", "")
        # 假设 CRUDApiKey 已正确导入
        user = await self.get_user_from_key(db=db, key=key)
        uid = getattr(user, "id") if user else None
        if user is None or uid is None:
            raise HTTPException(403, "Invalid API Key")        
        
        #_,_,_,left = await token_respo.get_request_log(uid=int(uid))
        left = await balance_repo.query_transaction_sum(session=db, maker_id=uid)
        if left == 0:
            raise HTTPException(status_code=402,detail = "No token left")
        return user

    
    async def get_user_from_key(self,db:AsyncSession, key: str)->Optional[ApiKey]:
        # 1. 构建查询语句
        stmt = select(ApiKey).where(ApiKey.key == key)        
        # 2. 异步执行查询 (await)
        result = await db.execute(stmt)        
        # 3. 获取第一条结果
        api_key = result.scalar_one_or_none()
        
        return api_key
    
    async def delete_key(self, db: AsyncSession, key_id: str, user_id: int) -> None:
        stmt = select(ApiKey).where(ApiKey.key == key_id, ApiKey.user_id == user_id)
        result = await db.execute(stmt)
        api_key = result.scalar_one_or_none()
        if api_key:
            await db.delete(api_key)
            await db.commit()
        else:
            raise HTTPException(status_code=404, detail="Key not found")

    async def get_keys(self, db: AsyncSession, user_id: int) -> ApiResp:
        try:
            stmt = select(ApiKey).where(ApiKey.user_id == user_id)
            result = await db.execute(stmt)

            keys = result.scalars().all()

            data = []
            for k in keys:
                data.append(
                    {
                        "id": k.id,
                        "key": k.key,  # 如果你做了hash，这里不要返回原key
                        "status": k.status,                        
                        "used_tokens": 0,
                        "tier": k.tier,
                        "created_at": k.created_at,
                        'key_title':k.name,
                        
                    }
                )

            return ApiResp(success=True, message="ok", data=data)

        except Exception as e:
            return ApiResp(success=False, message=str(e), data=None)


apikey_crud = CRUDApiKey(ApiKey)
