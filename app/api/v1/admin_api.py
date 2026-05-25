
from app.features.user.schemas.photo_schema import  PhotoInDB
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.deps import AdminUser, get_db,DepUser, admin_required
from app.features.user.user_crud import get_console_datas, user_crud
from app.features.user.photo_crud import photo_crud
from app.features.db_base import ApiResp, PagedResp
from app.features.biz.order.order_schema import OrderStatus
from app.features.user.model.user_model import User
from app.features.admin.admin_schema import AdminUserUpdate
from app.features.user.schemas.user_schema import UserInDB, UserForAdmin


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard", response_model=ApiResp)
async def get_dashboard_stats(
    *,
    db: AsyncSession = Depends(get_db),
    _: AdminUser
):
    """获取仪表盘用户统计数据"""
    user_count_by_country = await get_console_datas(db)
    return user_count_by_country


# # 用户管理

@router.get("/users/{page}", response_model=PagedResp[List[UserForAdmin]])
async def read_users(
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    size: int = 10,
    sort_by: str = Query("id", pattern="^(id|name|created_at)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
):
    data,total  = await user_crud.user_list(
        db,
        page=page,
        size=size,
        sort_by=sort_by,
        sort_order=sort_order
    )

    return PagedResp(
        success=True,
        data=data,
        total=int(total),
        page=page,
        size=size
    )


@router.put("/user/{user_id}/deactive", response_model=ApiResp[UserForAdmin])
async def update_user(
    *,
    db: AsyncSession = Depends(get_db),
    _: AdminUser,
    user_id: int,    
):
    """更新用户信息"""
    user =await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user = await user_crud.admin_update_user(db, db_obj=user, obj_in=user_in)

    return ApiResp(success=True, data=UserInDB.model_validate(user))


@router.delete("/users/{user_id}", response_model=ApiResp)
async def delete_user(
    *,
    _: DepUser,
    db: AsyncSession = Depends(get_db),
    user_id: int
):
    """删除用户"""
    user = user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await user_crud.delete(db, id=user_id)
    return ApiResp(success=True, message="User deleted successfully")

# 支付管理

@router.put("/payments/{payment_id}/status", response_model=ApiResp)
async def update_payment_status(
    *,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_required),
    payment_id: int,
    status: OrderStatus
):
    """更新支付状态"""
    Order = await payment_crud.get(db, id=payment_id)
    if not Order:
        raise HTTPException(status_code=404, detail="Order not found")

    Order = await payment_crud.update(db, db_obj=Order, obj_in={"status": status})
    return ApiResp(success=True, data=Order)

# 照片管理


@router.get("/photos/{pg}", response_model=ApiResp[Optional[List[PhotoInDB]]])
async def get_photos(
    *,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_required),
    pg: int = 1,

):
    limit: int = 50
    """获取所有用户上传的照片"""
    photos = await photo_crud.get_all_photos(db, skip=(pg-1)*limit, limit=limit)
    if not photos:
        return ApiResp(success=True, data=[], message="No photos found")

    return ApiResp(success=True, data=photos, message="Photos retrieved successfully")


@router.delete("/photos/{photo_id}", response_model=ApiResp)
async def delete_photo(
    *,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(admin_required),
    photo_id: int
):
    """删除照片"""
    # 首先从Cloudinary删除文件
    deleted_photo = await photo_crud.delete_by_admin(db, photo_id=photo_id)
    return deleted_photo


