# model_choose.py


import json
import random
from typing import List, Dict, Any
from fastapi import HTTPException
from app.features.biz.order.price_repo import PriceRepo
from app.features.biz.order.order_model import ModelPricing
from app.features.biz.order.order_schema import ModelPricingResponse

SAAS_TIERS = {
    "free": {
        "rpm": 5,
        "discount": 1.0,
    },

    "vip": {
        "rpm": 20,
        "discount": 1.4,
    },

    "pro": {
        "rpm": 30,
        "discount": 0.85,
    },

    "ent": {
        "rpm": 200,
        "discount": 0.70,
    }
}


def build_cost_map(
        costs: List[ModelPricingResponse]
) -> Dict[str, Dict]:
    cost_map = {}

    for item in costs:

        cost_map[item.model_name] = {

            "input_cost": float(
                item.input_cost or 0
            ),

            "output_cost": float(
                item.output_cost or 0
            ),

            "sell_input": float(
                item.input_price or 0
            ),

            "sell_output": float(
                item.output_price or 0
            ),
        }

    return cost_map


def get_limit(
        tier: str,
        key: str,
        default: int
) -> int:

    return SAAS_TIERS.get(
        tier,
        {}
    ).get(key, default)


def weighted_choice(channels):

    total = sum(
        c.get("weight", 1) or 1
        for c in channels
    )

    r = random.uniform(0, total)

    upto = 0

    for c in channels:

        w = c.get("weight", 1) or 1

        if upto + w >= r:
            return c

        upto += w

    return None


def calc_profit(
        model: str,
        cost_cfg: dict
) -> float:

    cfg = cost_cfg.get(model)

    if not cfg:
        return -1

    input_profit = (
        cfg["sell_input"] -
        cfg["input_cost"]
    )

    output_profit = (
        cfg["sell_output"] -
        cfg["output_cost"]
    )

    return (
        input_profit * 0.4 +
        output_profit * 0.6
    )


def safe_json_loads(value):

    if not value:
        return {}

    try:
        return json.loads(value)
    except Exception:
        return {}


def get_allowed_groups(
        tier: str
) -> list[str]:

    groups = {

        "free": [
            "default"
        ],

        "vip": [
            "default",
            "vip"
        ],

        "pro": [
            "default",
            "vip",
            "pro"
        ],

        "ent": [
            "default",
            "vip",
            "pro",
            "ent"
        ],
    }

    return groups.get(
        tier,
        ["default"]
    )


async def get_models_avialable(
        tier,
        channels,
        body: dict,
        price_repo: PriceRepo
):

    # =====================================================
    # 1. 获取模型价格
    # =====================================================

    model_prices = (
        await price_repo.get_all_modelpricings(
            active_only=True
        )
    )

    if not model_prices:
        raise HTTPException(
            status_code=401,
            detail="没有可用模型"
        )
    model_prices_schemas = [
        ModelPricingResponse.model_validate(model)
        for model in model_prices
    ]
    # =====================================================
    # 2. assign
    # =====================================================

    assigned = assign_models(
        user_tier=tier,
        channels=channels,
        limit_cfg=get_limit(
            tier=tier,
            key="rpm",
            default=0
        ),
        model_costs=model_prices_schemas,
    )

    if "error" in assigned:
        raise HTTPException(
            status_code=401,
            detail=assigned["error"]
        )

    # =====================================================
    # 3. 允许模型
    # =====================================================

    default_model = assigned["default_model"]

    optional = assigned.get(
        "optional_models",
        []
    )

    allowed = (
        {default_model, *optional}
        if default_model
        else set(optional)
    )

    if not allowed:

        raise HTTPException(
            status_code=401,
            detail=f"等级 {tier} 没有可用模型"
        )

    # =====================================================
    # 4. 用户请求模型
    # =====================================================

    requested_model = body.get("model")

    selected_model = (

        requested_model

        if requested_model
        and requested_model in allowed

        else default_model
        or next(iter(allowed))
    )

    # =====================================================
    # 5. 模型映射
    # =====================================================

    mapping = assigned.get(
        "model_mapping",
        {}
    )

    target_model = mapping.get(
        selected_model,
        selected_model
    )

    # =====================================================
    # 6. model price
    # =====================================================

    model_price = next(

        (
            m for m in model_prices
            if m.model_name == selected_model
        ),

        None
    )

    if not model_price:

        raise HTTPException(
            status_code=404,
            detail=f"Model price not found: {selected_model}"
        )

    # =====================================================
    # 7. return
    # =====================================================

    return {

        "request_model": selected_model,

        "target_model": target_model,

        "model_price": model_price,

        "channel_id": assigned["channel_id"],

        "channel_name": assigned["channel_name"],

        "applied_rate_limit": assigned[
            "applied_rate_limit"
        ],
    }


def assign_models(
        user_tier: str,
        channels: List[Dict],
        limit_cfg: int,
        model_costs: List[ModelPricingResponse]
) -> Dict[str, Any]:

    # =====================================================
    # 1. cost map
    # =====================================================

    cost_map = build_cost_map(
        model_costs
    )

    # =====================================================
    # 2. group
    # =====================================================

    allowed_groups = get_allowed_groups(
        user_tier
    )

    candidates = [

        c for c in channels

        if c.get("status") == 1
        and c.get("group") in allowed_groups
    ]

    if not candidates:

        return {
            "error": "No available channel"
        }

    # =====================================================
    # 3. priority
    # =====================================================

    min_p = min(
        c["priority"]
        for c in candidates
    )

    same_level = [

        c for c in candidates
        if c["priority"] == min_p
    ]

    # =====================================================
    # 4. weighted
    # =====================================================

    best_channel = weighted_choice(
        same_level
    )

    if best_channel is None:

        return {
            "error": "No available channel"
        }

    # =====================================================
    # 5. models
    # =====================================================

    models_str = (
        best_channel.get("models")
        or ""
    )

    raw_models = [

        m.strip()

        for m in models_str.split(",")

        if m.strip()
    ]

    if not raw_models:

        return {
            "error": "Empty model list"
        }

    # =====================================================
    # 6. 利润排序
    # =====================================================

    model_profits = []

    for m in raw_models:

        profit = calc_profit(
            m,
            cost_map
        )

        if profit > 0:

            model_profits.append(
                (m, profit)
            )

    if model_profits:

        model_profits.sort(
            key=lambda x: x[1],
            reverse=True
        )

        default_model = (
            model_profits[0][0]
        )

        optional_models = [

            m for m, _
            in model_profits[1:]
        ]

    else:

        default_model = raw_models[0]

        optional_models = raw_models[1:]

    # =====================================================
    # 7. model mapping
    # =====================================================

    mapping_str = (
        best_channel.get("model_mapping")
        or "{}"
    )

    model_mapping = safe_json_loads(
        mapping_str
    )

    # =====================================================
    # 8. return
    # =====================================================

    return {

        "channel_id": best_channel["id"],

        "channel_name": best_channel["name"],

        "default_model": default_model,

        "optional_models": optional_models,

        "model_mapping": model_mapping,

        "applied_rate_limit": limit_cfg,
    }

