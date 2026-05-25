from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Update, select, update, delete
from typing import Any, Optional, List
from app.features.biz.order.order_model import ModelPricing
from decimal import Decimal
import httpx
from app.core.config import settings
from app.services.tools_svc import check_api_reachable



class PriceRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_model(
        self,
        model_name: str,
        input_cost: float,
        output_cost: float,
        level: Optional[int] = 1,
        input_price: Optional[float] = None,
        output_price: Optional[float] = None,
        currency: str = "USD",
        is_active: bool = True
    ) -> Optional[ModelPricing]:
        """Create a new model pricing record"""
        if input_price is None:
            input_price = round(input_cost * 1.5, 6)
        if output_price is None:
            output_price = round(output_cost * 1.5, 6)
        try:            
            pricing = ModelPricing(
                model_name=model_name,
                input_cost=input_cost,
                output_cost=output_cost,
                input_price=input_price,
                output_price=output_price,
                currency=currency,
                level=level,
                is_active=1 if is_active else 0
            )

            self.db.add(pricing)
            await self.db.commit()
            await self.db.refresh(pricing)
            if check_api_reachable(settings.ONEAPI_URL,3):
               from app.core.application import fapp
               await fapp.state.oneapi_svc.create_model(model_name, input_cost, output_cost)
            return pricing
        except Exception as e:
            await self.db.rollback()
            return None

    async def get_pricing_by_model(self, model_name: str) -> Optional[ModelPricing]:
        """Get pricing by model name"""
        result = await self.db.execute(
            select(ModelPricing).where(ModelPricing.model_name == model_name)
        )
        return result.scalars().first()

    async def get_oneapi_models(self):
        url = f'{settings.ONEAPI_URL}/v1/models'
        token = settings.ONE_API_MASTERKEY
        try:                
            async with httpx.AsyncClient() as client:
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                if response.status_code == 200:
                    data = response.json()
                    return data.get('data', [])
                return []
        except Exception as ex:
            print('error rqst:',str(ex))
            return []

    async def get_all_db_models(self, active_only: bool = True):
        """Get all pricing records"""
        query = select(ModelPricing)
        if active_only:
            query = query.where(ModelPricing.is_active == 1)
        query = query.order_by(ModelPricing.model_name, ModelPricing.level.desc(),ModelPricing.created_at.desc())
        result = await self.db.execute(query)
        data = result.scalars().all()
        if not data:
           return []
        result =[]
        for item in data:
            if item.model_name == 'default':
                continue
            result.append({
                "name": item.model_name,
                'id':item.id,
                'input_cost':getattr(item,'input_cost',0),
                'output_cost':getattr(item,'output_cost',0),
                "input_price": getattr(item,'input_price',0),
                "output_price": getattr(item,'output_price',0),
                "currency": item.currency,
                "level": item.level,
                'is_active':item.is_active
            })
        return result

    async def update_pricing(
        self,
        model_name: str,
        input_cost: Optional[float] = None,
        output_cost: Optional[float] = None,
        input_price: Optional[float] = None,
        output_price: Optional[float] = None,
        currency: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Optional[ModelPricing]:
        """Update pricing by model name"""
        pricing = await self.get_pricing_by_model(model_name)
        if not pricing:
            return None

        update_data = {}
        if input_cost is not None:
            update_data['input_cost'] = input_cost
        if output_cost is not None:
            update_data['output_cost'] = output_cost
        if input_price is not None:
            update_data['input_price'] = input_price
        elif input_cost is not None:
            update_data['input_price'] = round(input_cost * 1.5, 6)
        if output_price is not None:
            update_data['output_price'] = output_price
        elif output_cost is not None:
            update_data['output_price'] = round(output_cost * 1.5, 6)
        if currency is not None:
            update_data['currency'] = currency
        if is_active is not None:
            update_data['is_active'] = 1 if is_active else 0

        if update_data:
            stmt = (
                update(ModelPricing)
                .where(ModelPricing.model_name == model_name)
                .values(**update_data)
            )
            await self.db.execute(stmt)
            await self.db.commit()
            await self.db.refresh(pricing)

        return pricing

    async def delete_pricing(self, model_name: str) -> bool:
        """Delete pricing by model name"""
        stmt = (
            Update(ModelPricing)
            .where(ModelPricing.model_name == model_name)
            .values(is_active=0)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0
 

    async def seed_pricing(self) -> int:
        """Seed initial pricing data into the database"""
        prices = {
            # --- OpenAI 主力模型 ---
            "gpt-4o": {
                "input": Decimal("0.0025"),
                "output": Decimal("0.010")
            },
            "gpt-4o-mini": {
                "input": Decimal("0.00015"),
                "output": Decimal("0.0006")
            },
            "gpt-4.1": {
                "input": Decimal("0.002"),
                "output": Decimal("0.008")
            },
            "gpt-4.1-mini": {
                "input": Decimal("0.0004"),
                "output": Decimal("0.0016")
            },
            "gpt-4.1-nano": {
                "input": Decimal("0.00005"),
                "output": Decimal("0.0004")
            },
            "gpt-4-turbo": {
                "input": Decimal("0.01"),
                "output": Decimal("0.03")
            },
            "gpt-3.5-turbo": {
                "input": Decimal("0.0005"),
                "output": Decimal("0.0015")
            },
            "o3": {
                "input": Decimal("0.002"),
                "output": Decimal("0.008")
            },
            "o4-mini": {
                "input": Decimal("0.0011"),
                "output": Decimal("0.0044")
            },

            # --- Anthropic 模型 ---
            "claude-opus-4": {
                "input": Decimal("0.015"),
                "output": Decimal("0.075")
            },
            "claude-sonnet-4": {
                "input": Decimal("0.003"),
                "output": Decimal("0.015")
            },
            "claude-3.5-sonnet": {
                "input": Decimal("0.003"),
                "output": Decimal("0.015")
            },
            "claude-3.5-haiku": {
                "input": Decimal("0.0008"),
                "output": Decimal("0.004")
            },

            # --- Google Gemini 模型 ---
            "gemini-2.5-pro": {
                "input": Decimal("0.00125"),
                "output": Decimal("0.010")
            },
            "gemini-2.5-flash": {
                "input": Decimal("0.0003"),
                "output": Decimal("0.0025")
            },

            # --- 其他高性价比模型 ---
            "deepseek-chat": {
                "input": Decimal("0.00027"),
                "output": Decimal("0.0011")
            },

            # --- 默认兜底 ---
            "default": {
                "input": Decimal("0.001"),
                "output": Decimal("0.002")
            }
        }

        created_count = 0
        for model_name, price_data in prices.items():
            existing = await self.get_pricing_by_model(model_name)
            if not existing:
                await self.create_model(
                    model_name=model_name,
                    input_price=float(price_data["input"]),
                    output_price=float(price_data["output"]),
                    currency="USD",
                    is_active=True
                )
                created_count += 1

        return created_count
