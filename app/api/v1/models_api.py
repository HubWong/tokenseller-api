# -*- coding: utf-8 -*-
from typing import List
from fastapi import APIRouter, Depends
from app.features.biz.order.order_schema import ModelPricingCreate, ModelPricingResponse, ModelPricingUpdate
from app.core.deps import get_price_repo
from app.core.deps_auth import admin_required
from app.features.biz.order.price_repo import PriceRepo
from app.features.db_base import ApiResp


router = APIRouter(prefix="/models", tags=["models"])





@router.get("/", response_model=ApiResp[List[dict]])
async def get_all_models(
    active_only: bool = True,
    price_repo: PriceRepo = Depends(get_price_repo)
):
    """Get all model pricing records"""
    try:
        models = await price_repo.get_all_db_models(active_only=active_only)
        return ApiResp(success=True, data=models)
    except Exception as e:
        return ApiResp(success=False, message=str(e))


@router.get("/{model_name}", response_model=ApiResp[ModelPricingResponse])
async def get_model(
    model_name: str,
    price_repo: PriceRepo = Depends(get_price_repo)
):
    """Get model pricing by model name"""
    model = await price_repo.get_pricing_by_model(model_name)
    if not model:
        return ApiResp(success=False, message=f"Model {model_name} not found")
    return ApiResp(success=True, data=ModelPricingResponse.model_validate(model))


@router.post("/", response_model=ApiResp[ModelPricingResponse])
async def create_model(
    model_data: ModelPricingCreate,
    user = Depends(admin_required),
    price_repo: PriceRepo = Depends(get_price_repo)
):
    """Create a new model pricing record (admin only)"""
    try:
        existing = await price_repo.get_pricing_by_model(model_data.model_name)
        if existing:
            return ApiResp(success=False, message=f"Model {model_data.model_name} already exists")

        model = await price_repo.create_model(
            input_cost=model_data.input_cost or 0.006,
            output_cost=model_data.output_cost or 0.012,
            model_name=model_data.model_name,
            input_price=model_data.input_price,
            output_price=model_data.output_price,
            currency=model_data.currency or 'USD',
            is_active=model_data.is_active or True,
            level=model_data.level
        )
       
        return ApiResp(success=True, data=ModelPricingResponse.model_validate(model))
    except Exception as e:
        return ApiResp(success=False, message=str(e))


@router.put("/{model_name}", response_model=ApiResp[ModelPricingResponse])
async def update_model(
    model_name: str,
    model_data: ModelPricingUpdate,
    user = Depends(admin_required),
    price_repo: PriceRepo = Depends(get_price_repo)
):
    """Update model pricing by model name (admin only)"""
    try:
        if model_name =='undefined':
            return ApiResp(success=False, message=f"Model {model_name} not defined") 
        model = await price_repo.update_pricing(
            model_name=model_name,
            input_cost=model_data.input_cost,
            output_cost=model_data.output_cost,
            input_price=model_data.input_price,
            output_price=model_data.output_price,
            currency=model_data.currency,
            level=model_data.level,
            is_active=model_data.is_active
        )
        if not model:
            return ApiResp(success=False, message=f"Model {model_name} not found")
        return ApiResp(success=True, data=ModelPricingResponse.model_validate(model))
    except Exception as e:
        return ApiResp(success=False, message=str(e))


@router.delete("/{model_name}", response_model=ApiResp)
async def delete_model(
    model_name: str,
    user = Depends(admin_required),
    price_repo: PriceRepo = Depends(get_price_repo)
):
    """Delete model pricing by model name (admin only)"""
    try:
        success = await price_repo.delete_pricing(model_name)
        if not success:
            return ApiResp(success=False, message=f"Model {model_name} not found")
        return ApiResp(success=True, message=f"Model {model_name} deleted successfully")
    except Exception as e:
        return ApiResp(success=False, message=str(e))