from app.core.abc.abc_biz import ConsumeService, CommissionService, BuyService, BaseService
from app.core.deps import OrderRepoDeps, PriceRepoDeps, TokenUsageDeps,UserRepoDeps,DbSessionDeps
from fastapi import Depends,HTTPException,Request
from typing import Optional,Annotated
from app.services.oneapi_svc import OneApiSvc
from app.services.paypal_svc import PayPalSvc
from app.services.token_money_svc import TokenCostCalculator

async def get_paypal_svc():
    return PayPalSvc()

async def get_token_cal_svc(price_db:PriceRepoDeps):
    return TokenCostCalculator(price_db=price_db)


async def get_oneapi_svc(request: Request):
    svc = getattr(request.app.state, "oneapi_svc", None)
    if svc is None:
        raise HTTPException(status_code=500, detail="OneApiSvc 未初始化，请检查 lifespan 配置")
    return svc

OneApiDeps = Annotated[OneApiSvc, Depends(get_oneapi_svc)]


async def get_base_svc(db:DbSessionDeps) -> BaseService:  
    return BaseService( db=db,redis_client=None)
    
    
async def get_buy_svc(token_repo:TokenUsageDeps,
        order_repo:OrderRepoDeps,                      
        base:BaseService=Depends(get_base_svc),
        token_cal:TokenCostCalculator = Depends(get_token_cal_svc)) -> BuyService:
    return BuyService(base, order_repo=order_repo,
        token_repo= token_repo,
        token_cal_svc=token_cal
                )


async def get_commission_svc(
    user_crud_svc:UserRepoDeps,
    base:BaseService=Depends(get_base_svc)) -> CommissionService:
    return CommissionService(user_repo=user_crud_svc,base=base)


async def get_consume_svc(base:BaseService=Depends(get_base_svc), 
    commission_svc:CommissionService=Depends(get_commission_svc),
    price_cal_svc:TokenCostCalculator=Depends(get_token_cal_svc)) -> ConsumeService:
    return ConsumeService(base=base, commission_service=commission_svc, price_calc=price_cal_svc)

ConsumeDeps = Annotated[ConsumeService, Depends(get_consume_svc)]
