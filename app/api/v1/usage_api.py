from fastapi import APIRouter, Depends,  Query
from typing import  List

from sqlalchemy.ext.asyncio import AsyncSession
from app.features.biz.user_balance.schemas import RecentRequestResponse, DashboardStatsResponse,UsageStatsResponse
from app.core.deps import get_token_usage_rep, DepUser, get_data_collector
from app.features.user.model.user_model import User
from app.features.biz.data_func import DataCollector
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.core.deps import get_db
from app.features.biz.apikey.apikey_crud import CRUDApiKey


router = APIRouter(prefix="/usage", tags=["usage"])



@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats( 
    current_user: DepUser,
    token_repo :TokenUsageRepo = Depends(get_token_usage_rep),
    data_collector: DataCollector = Depends(get_data_collector)
):
    return await data_collector.get_token_datas(token_repo=token_repo,uid=current_user.id)


@router.get("/daily", response_model=list[UsageStatsResponse])
async def get_daily_usage(
    current_user: DepUser,
    days: int = Query(7, ge=1, le=30, description="Number of days (1-30)"),
    data_collector:DataCollector = Depends(get_data_collector),
    token_repo :TokenUsageRepo = Depends(get_token_usage_rep)
):
    """
    Get daily token usage statistics
    - Line chart data for 7 or 30 days
    """
    return await data_collector.get_daily(token_repo=token_repo,days=days, uid=current_user.id)


@router.get("/token_log", response_model=List[RecentRequestResponse])
async def get_token_log(
    current_user: DepUser,
    limit: int = Query(10, ge=1, le=50, description="Number of recent requests"),
    data_collector: DataCollector = Depends(get_data_collector),
    db:AsyncSession = Depends(get_db)
):
    return await data_collector.get_order_list(db=db,maker_id=current_user.id)
