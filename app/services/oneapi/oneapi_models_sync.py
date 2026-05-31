import json
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.features.biz.order.order_model import ModelPricing
from app.services.tools_svc import check_api_reachable
from app.services.oneapi_svc import OneApiSvc

class ModelPricingSyncService:

    @staticmethod
    async def sync_from_channels(
        db: AsyncSession,
    ):
        if not check_api_reachable(host='https://one-api-production-dd42.up.railway.app', timeout=2): 
            return
        print("[*] ModelPricingSyncService.sync_from_channels start...")
        channels =await OneApiSvc.channels()

        all_models = {}

        for ch in channels:

            models_raw = ch.get("models", "")

            model_list = [
                x.strip()
                for x in models_raw.split(",")
                if x.strip()
            ]

            mapping_raw = ch.get("model_mapping")

            try:
                mappings = json.loads(mapping_raw) \
                    if mapping_raw else {}
            except:
                mappings = {}

            # 原始模型
            for model_name in model_list:

                if model_name not in all_models:

                    all_models[model_name] = {
                        "provider_type": ch.get("type"),
                        "provider_name": ch.get("name"),
                        "group_name": ch.get("group"),

                        "priority": ch.get("priority", 0),
                        "weight": ch.get("weight", 0),

                        "channel_status": ch.get("status", 1),
                    }

            # 映射模型
            for alias_name in mappings.keys():

                if alias_name not in all_models:

                    all_models[alias_name] = {
                        "provider_type": ch.get("type"),
                        "provider_name": ch.get("name"),
                        "group_name": ch.get("group"),

                        "priority": ch.get("priority", 0),
                        "weight": ch.get("weight", 0),

                        "channel_status": ch.get("status", 1),
                    }

        # sync db
        for model_name, data in all_models.items():

            stmt = select(ModelPricing).where(
                ModelPricing.model_name == model_name
            )

            result = await db.execute(stmt)

            db_model = result.scalar_one_or_none()

            if db_model:

                db_model.provider_type = data["provider_type"]
                db_model.provider_name = data["provider_name"]

                db_model.group_name = data["group_name"]

                db_model.priority = data["priority"]
                db_model.weight = data["weight"]

                db_model.channel_status = data["channel_status"]

            else:

                db_model = ModelPricing(
                    model_name=model_name,

                    provider_type=data["provider_type"],
                    provider_name=data["provider_name"],

                    group_name=data["group_name"],

                    priority=data["priority"],
                    weight=data["weight"],

                    channel_status=data["channel_status"],

                    input_price=0,
                    output_price=0,
                )

                db.add(db_model)

        await db.commit()