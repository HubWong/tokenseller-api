
from typing import List, Dict, Any
from fastapi import HTTPException
from app.features.biz.order.price_repo import PriceRepo
from app.features.biz.order.order_model import ModelPricing
import json
import random

SAAS_TIERS = {
    "free": {"rpm": 5, "discount": 1.0},
    "vip": {"rpm": 20, "discount": 1.4},
    "pro":  { "rpm": 30, "discount": 0.85},
    "ent":  {"rpm": 200, "discount": 0.70}
}

def build_cost_map(model_costs: List[ModelPricing]) -> Dict[str, Dict]:
    cost_map = {}
    for item in model_costs:
        cost_map[item["name"]] = {
            "input_cost": float(item["input_cost"]),
            "output_cost": float(item["output_cost"]),
            "sell_input": float(item["input_price"]),
            "sell_output": float(item["output_price"]),
        }
    return cost_map

def get_limit(tier: str, key: str, default: int) -> int:
    return SAAS_TIERS.get(tier, {}).get(key, default)

def weighted_choice(channels):
    total = sum(c.get('weight', 1) or 1 for c in channels)
    r = random.uniform(0, total)
    upto = 0
    for c in channels:
        w = c.get('weight', 1) or 1
        if upto + w >= r:
            return c
        upto += w


def calc_profit(model: str, cost_cfg: dict) -> float:
    cfg = cost_cfg.get(model)
    if not cfg:
        return -1

    input_profit = cfg["sell_input"] - cfg["input_cost"]
    output_profit = cfg["sell_output"] - cfg["output_cost"]

    return input_profit * 0.4 + output_profit * 0.6



async def get_models_avialable(tier, channels,
                               body: dict,
                               price_repo: PriceRepo)-> tuple[str, ModelPricing]:

    model_prices = await price_repo.get_all_modelpricings(active_only=True)
    if not model_prices:
        raise HTTPException(status_code=401, detail="没有可用模型")
    lmt_cfg = get_limit(tier=tier, key="rpm", default=0)
    assigned = assign_models(
        user_tier=tier,
        channels=channels,
        limit_cfg=lmt_cfg,
        model_costs=model_prices,
    )
    if "error" in assigned:
        raise HTTPException(status_code=401, detail=assigned["error"])

    default_model = assigned["default_model"]
    optional = assigned.get("optional_models", [])
    allowed = {default_model, *optional} if default_model else set(optional)
    if not allowed:
        raise HTTPException(status_code=401, detail=f"等级 {tier} 没有可用模型")

    requested_model = body.get("model")
    selected_model = (
        requested_model if requested_model and requested_model in allowed
        else default_model or next(iter(allowed))
    )
    return selected_model, model_prices[0]

def assign_models(
    user_tier: str,
    channels: List[Dict],    
    limit_cfg: int,
    model_costs: List[ModelPricing]   # ← 改这里
) -> Dict[str, Any]:    

    # ✅ 新增：构建 cost_map
    cost_map = build_cost_map(model_costs)

    target_group = 'vip' if user_tier == 'vip' else 'default'

    groups = (target_group,) if target_group == "vip" else ("default",)

    candidates = [
        c for c in channels
        if c['status'] == 1
        and c['group'] in groups
    ]

    if not candidates:
        return {"error": "No available channel"}

    min_p = min(c['priority'] for c in candidates)
    same_level = [c for c in candidates if c['priority'] == min_p]

    best_channel = weighted_choice(same_level)
    if best_channel is None:
        return {"error": "No available channel"}
    raw_models = [m.strip() for m in best_channel['models'].split(',') if m.strip()]
    if not raw_models:
        return {"error": "Empty model list"}

    # ✅ 利润排序（用 cost_map）
    model_profits = []
    for m in raw_models:
        profit = calc_profit(m, cost_map)
        if profit > 0:
            model_profits.append((m, profit))

    if model_profits:
        model_profits.sort(key=lambda x: x[1], reverse=True)
        default_model = model_profits[0][0]
        optional_models = [m for m, _ in model_profits[1:]]
    else:
        default_model = raw_models[0]
        optional_models = raw_models[1:]
    mapping_str = best_channel.get("model_mapping") or "{}"
    return {
        "channel_id": best_channel['id'],
        "channel_name": best_channel['name'],
        "default_model": default_model,
        "optional_models": optional_models,
        "model_mapping": json.loads(mapping_str),
        "applied_rate_limit": limit_cfg
    }
