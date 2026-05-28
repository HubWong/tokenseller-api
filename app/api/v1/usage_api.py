from fastapi import APIRouter, Depends,  Query
from app.core.deps import  TokenUsageDeps
from app.features.biz.user_balance.schemas import DashboardStatsResponse,UsageStatsResponse
from app.core.deps import get_token_usage_rep,  get_data_collector
from app.core.deps_auth import DepUser
from app.features.biz.data_func import DataCollector
from app.features.biz.usage.token_usage_repo import TokenUsageRepo


router = APIRouter(prefix="/usage", tags=["usage"])



@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats( 
    current_user: DepUser,
    token_repo :TokenUsageRepo = Depends(get_token_usage_rep),
    data_collector: DataCollector = Depends(get_data_collector)
):
    return await data_collector.get_token_datas(token_repo=token_repo,uid=getattr(current_user, "id"))


@router.get("/daily", response_model=list[UsageStatsResponse])
async def get_daily_usage(
    current_user: DepUser,
    token_repo :TokenUsageDeps,
    days: int = Query(7, ge=1, le=30, description="Number of days (1-30)"),
    data_collector:DataCollector = Depends(get_data_collector),
):
    """
    Get daily token usage statistics
    - Line chart data for 7 or 30 days
    """
    return await data_collector.get_daily(token_repo=token_repo,days=days, uid=getattr(current_user, "id"))


# @router.get("/token_log", response_model=List[RecentRequestResponse])
# async def get_token_log(
#     current_user: DepUser,
#     db:DbSessionDeps,
#     limit: int = Query(10, ge=1, le=50, description="Number of recent requests"),
#     data_collector: DataCollector = Depends(get_data_collector),
# ):
#     return await data_collector.get_token_datas(db=db,maker_id=current_user.id)
