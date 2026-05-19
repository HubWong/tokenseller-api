# -*- coding: utf-8 -*-
import decimal
from typing import Any, List,Optional, Tuple
from fastapi import APIRouter, Depends
from app.core.deps import admin_required, get_buy_svc, get_current_user, get_order_rep
from app.features.biz.order.order_schema import PurchaseRequest
from app.features.user.model.user_model import User
from app.features.db_base import ApiResp, PagedResp
from app.features.biz.order.order_repo import OrderRepo
from app.features.biz.order.order_schema import  OrderInDBBase
from app.core.abc_biz import BuyService
from app.features.user.schemas.user_role import UserRole

router = APIRouter(prefix="/orders", tags=["orders"])



@router.post("/")
async def create_order(
    order: PurchaseRequest,
    user: User = Depends(get_current_user),
    buy_svc:BuyService=Depends(get_buy_svc)
    ):  
    if order.pay_way!=2:
        return ApiResp(message='paypal not aviable right now.',data=None, success=False)
    return await  buy_svc.create_order(user_id=getattr(user,'id'), purchase=order)

    
@router.delete("/{order_id}") 
async def delete_order(order_id: int, user:User= Depends(admin_required),  order_repo: OrderRepo = Depends(get_order_rep)) -> ApiResp[Any]:
    r = await order_repo.cancel_order(order_id,uid=user.id, username=user.username)
    return ApiResp(success=r, message="Order cancelled" if r else "Order not found")


@router.get('/{order_id}', response_model=ApiResp)
async def get_order(order_id: int, order_repo: OrderRepo = Depends(get_order_rep)) -> ApiResp:
    order = await order_repo.get_by_id(order_id)
    if not order:
        return ApiResp(success=False, message="Order not found")
    return ApiResp(success=True, data=order)


@router.get('/list/{pg}/{pg_size}', response_model=PagedResp[List[OrderInDBBase]])
async def list_orders(
    pg: int ,
    pg_size: int ,
    order_repo: OrderRepo = Depends(get_order_rep),
    cur_user:User = Depends(get_current_user)
) -> PagedResp[List[OrderInDBBase]]:
    if cur_user.role == UserRole.USER and cur_user.email !='wyb6688@hotmail.com':
        return PagedResp(success=False,message="user is not a seller")
    orders, total = await order_repo.list_orders(page=pg, limit=pg_size)
    return PagedResp(success=True, data=orders, message=f"Total orders: {total}", total=total, page=pg, page_size=pg_size)