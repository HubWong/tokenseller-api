from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
 
from app.features.biz.user_balance import transaction_reop
from app.core.deps import  get_transaction_rep
from app.core.deps_auth import DepUser
from app.features.user.model.user_model import User
from app.core.deps import DbSessionDeps

router = APIRouter(prefix="/balance", tags=["balance"])


@router.get("/key/{api_key}")
async def get_balance(api_key: str, db: DbSessionDeps):
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
async def get_bill_data( cur_user: DepUser,
                        db:DbSessionDeps,
                        trans_rep :transaction_reop.TransactionRepo = Depends(get_transaction_rep),  
                         ):
    """Get user bill data."""
    user_id = cur_user.id
    return await trans_rep.get_bill_datas(db=db,user_id=user_id)
