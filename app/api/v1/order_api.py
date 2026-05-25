# -*- coding: utf-8 -*-
import logging
from typing import Any, List, Optional, Tuple
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from app.core.deps import admin_required, get_buy_svc, DepUser, get_order_rep, get_paypal_svc
from app.features.biz.order.order_schema import PurchaseRequest
from app.features.user.model.user_model import User
from app.features.db_base import ApiResp, PagedResp
from app.features.biz.order.order_repo import OrderRepo
from app.features.biz.order.order_schema import OrderInDBBase
from app.core.abc_biz import BuyService
from app.features.user.schemas.user_role import UserRole
from app.services.paypal_svc import PayPalSvc
from app.services.listener_svc import order_pool
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/")
async def create_order(
    order: PurchaseRequest,
    user: DepUser,
    buy_svc: BuyService = Depends(get_buy_svc),
    paypal_svc: PayPalSvc = Depends(get_paypal_svc),
):
    result = await buy_svc.create_order(user_id=getattr(user, 'id'), purchase=order)

    if order.pay_way == 1 and result.success:
        db_order = result.data
        backend_url = settings.BACKEND_URL.rstrip("/")
        frontend_url = settings.FRONTEND_URL.rstrip("/")
        return_url = f"{backend_url}/orders/paypal/success"
        cancel_url = f"{frontend_url}/app/billing?payment=cancelled"

        paypal_order = await paypal_svc.create_paypal_order(
            amount_usd=order.amount,
            order_id=db_order.id,
            return_url=return_url,
            cancel_url=cancel_url,
        )
        approval_url = next(
            (link["href"] for link in paypal_order.get("links", []) if link["rel"] == "approve"),
            None,
        )
        return ApiResp(
            success=True,
            message="PayPal order created",
            data={"approval_url": approval_url, "order_id": db_order.id},
        )

    return result


@router.get("/paypal/success")
async def paypal_success(
    token: str = Query(..., description="PayPal order ID"),
    paypal_svc: PayPalSvc = Depends(get_paypal_svc),
    buy_svc: BuyService = Depends(get_buy_svc),
):
    """PayPal payment success callback: capture -> mark paid -> SSE -> redirect"""
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    try:
        paypal_order = await paypal_svc.get_order(token)
        custom_id = None
        for unit in paypal_order.get("purchase_units", []):
            custom_id = unit.get("custom_id")
            if custom_id:
                break

        if not custom_id:
            logger.error("PayPal order missing custom_id: %s", token)
            return RedirectResponse(url=f"{frontend_url}/app/billing?payment=error")

        order_id = int(custom_id)

        if paypal_order.get("status") == "APPROVED":
            capture_resp = await paypal_svc.capture_order(token)
            if capture_resp.get("status") != "COMPLETED":
                logger.error("PayPal capture not completed: %s", token)
                return RedirectResponse(url=f"{frontend_url}/app/billing?payment=error")
        elif paypal_order.get("status") == "COMPLETED":
            pass
        else:
            logger.warning("PayPal order unexpected status %s: %s", token, paypal_order.get("status"))
            return RedirectResponse(url=f"{frontend_url}/app/billing?payment=error")

        paid = await buy_svc.pay_order(order_id)
        if paid:
            await order_pool.remove_order(order_id)
            await order_pool.publish_payment(order_id, {
                "status": "confirmed",
                "paypal_order_id": token,
            })

        return RedirectResponse(url=f"{frontend_url}/app/billing?payment=success")
    except Exception:
        logger.exception("PayPal callback failed for token=%s", token)
        return RedirectResponse(url=f"{frontend_url}/app/billing?payment=error")


@router.get("/paypal/cancel")
async def paypal_cancel():
    """PayPal payment cancelled callback"""
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    return RedirectResponse(url=f"{frontend_url}/app/billing?payment=cancelled")


@router.delete("/{order_id}")
async def delete_order(order_id: int, user: User = Depends(admin_required), order_repo: OrderRepo = Depends(get_order_rep)) -> ApiResp[Any]:
    r = await order_repo.cancel_order(order_id, uid=user.id, username=user.username)
    return ApiResp(success=r, message="Order cancelled" if r else "Order not found")


@router.get('/{order_id}', response_model=ApiResp)
async def get_order(order_id: int, order_repo: OrderRepo = Depends(get_order_rep)) -> ApiResp:
    order = await order_repo.get_by_id(order_id)
    if not order:
        return ApiResp(success=False, message="Order not found")
    return ApiResp(success=True, data=order)


@router.get('/list/{pg}/{pg_size}', response_model=PagedResp[List[OrderInDBBase]])
async def list_orders(
    pg: int,
    pg_size: int,
    cur_user: DepUser,
    order_repo: OrderRepo = Depends(get_order_rep),

) -> PagedResp[List[OrderInDBBase]]:
    if cur_user.role == UserRole.USER and cur_user.email != 'wyb6688@hotmail.com':
        return PagedResp(success=False, message="user is not a seller")
    orders, total = await order_repo.list_orders(page=pg, limit=pg_size)
    return PagedResp(success=True, data=orders, message=f"Total orders: {total}", total=total, page=pg, page_size=pg_size)
