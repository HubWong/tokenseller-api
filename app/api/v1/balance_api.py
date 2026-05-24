from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.features.db_base import ApiResp
from app.features.biz.user_balance import transaction_reop
from app.features.biz.user_balance.schemas import UserBalanceCreate
from app.core.deps import get_token_cal_svc, get_transaction_rep, get_current_user,get_token_usage_rep
from app.features.user.model.user_model import User
from app.features.biz.usage.model import TokenUsageLog
from app.services.token_money_svc import TokenCostCalculator

router = APIRouter(prefix="/balance", tags=["balance"])


@router.get("/key/{api_key}")
async def get_balance(api_key: str, db: AsyncSession = Depends(get_db)):
    """  
    
    Returns:
        - api_key: API Key
        - balances: 各提供商余额
        - total_tokens: 总余额
    """
    try:
        # Query user by api_key using SQLAlchemy
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.api_key == api_key)
        )
        user = result.scalars().first()
        
        if not user:
            raise HTTPException(status_code=404, detail="Invalid API key")
        
        # TODO: Implement actual token balance query
        token_balance = {}
        
        return {
            "api_key": api_key,
            "balances": token_balance,
            "total_tokens": sum(token_balance.values())
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/billData")
async def get_bill_data( db:AsyncSession=Depends(get_db),
                        token_cal_svc :TokenCostCalculator = Depends(get_token_cal_svc),
                        trans_rep :transaction_reop.TransactionRepo = Depends(get_transaction_rep),  
                        cur_user:User=Depends(get_current_user)):
    """Get user bill data."""
    user_id = cur_user.id
    return await trans_rep.get_bill_datas(db=db,user_id=user_id)
