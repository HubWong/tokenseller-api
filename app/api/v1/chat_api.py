"""
Token Purchase API - Integrated from main.py MVP features
提供 AI Token 购买、余额查询等功能
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.oneapi_svc import OneAPISvc
from app.core.deps import get_oneapi_svc,get_consume_svc, get_token_usage_rep
from app.core.abc_biz import ConsumeService
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.services.tools_svc import check_port_open
from app.core.config import settings

router = APIRouter(prefix="/chat", tags=["AI chat gateway"])


@router.post("/completions")
async def chat_endpoint(
    request: Request, 
    oneSvc: OneAPISvc = Depends(get_oneapi_svc),  
    db:AsyncSession = Depends(get_db)  ,
    consume_svc: ConsumeService = Depends(get_consume_svc),
    token_repo:TokenUsageRepo = Depends(get_token_usage_rep),
    stream: bool = False  
):
    is_open = check_port_open(settings.ONEAPI_URL,8080,6)
    if not is_open:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail = 'api can not be reached')
    return await oneSvc.chat_llm(db=db,
                                token_repo = token_repo, request=request,
                                consume_svc=consume_svc, stream=stream)
    
   

