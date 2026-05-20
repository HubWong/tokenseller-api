from decimal import Decimal, ROUND_HALF_UP
from typing import  Optional
from decimal import ROUND_DOWN
from app.features.user.schemas.user_role import UserRole
from app.features.biz.order.order_schema import ModelPricingResponse


PRICE_UNIT = Decimal("1000000")
PRECISION = Decimal("0.000001")




user_multiplier = {
  "free"    : 1.5,
  "vip"     : 1.0,
  "reseller": 0.8,
  'admin'   : 1.0
}



def get_role_multiplier(role: UserRole) -> float:
    """
    根据用户角色枚举，返回对应的倍率
    
    Args:
        role: UserRole 枚举实例（如 UserRole.ADMIN）
    
    Returns:
        float: 对应角色的倍率
    """
    # 获取角色的字符串值
    role_value = role.value
    # 从字典中获取倍率，不存在则返回默认值 1.0
    return user_multiplier.get(role_value, 1.0)

class TokenCostCalculator:
    def __init__(self,price_db):       
        self.prices =price_db

    async def query_price_table(self, model:str) -> Optional[ModelPricingResponse]:
        """查询模型的单价"""
        result = await self.prices.get_pricing_by_model(model_name=model)
        if not result:
            return None
        return ModelPricingResponse.model_validate(result)
   

     
    def tokens_to_revenue(self, input_tokens: int, 
                          output_tokens: int,                        
                          model_price:ModelPricingResponse,
                          user_tier:UserRole) -> Decimal:
        """根据 token 数量和模型计算收入"""        

        input_price = model_price.input_price
        output_price = model_price.output_price
        if input_price is None or output_price is None:
            raise ValueError("Model price not found")

        revenue = Decimal(
            input_tokens * input_price +
            output_tokens * output_price
        ) / PRICE_UNIT

         
        revenue *=Decimal(get_role_multiplier(user_tier))
         # 其他用户正常收入
        return revenue.quantize(PRECISION, rounding=ROUND_HALF_UP)


    def tokens_to_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model_price:ModelPricingResponse,
    ) -> Decimal:       

        input_cost = model_price.input_cost
        output_cost = model_price.output_cost

        if input_cost is None or output_cost is None:
            raise ValueError("Model cost not found")

        cost = Decimal(
            (input_tokens * input_cost) +
            (output_tokens * output_cost)
        ) / PRICE_UNIT

       

        return cost.quantize(PRECISION, rounding=ROUND_HALF_UP)

    
    async def money_to_tokens(
        self,
        amount: Decimal,
        model: str = "default",
        token_type: str = "input"
    ) -> int:

        if amount <= 0:
            raise ValueError("invalid amount")

        price_config = await self.query_price_table(model)
        if not price_config:
            raise ValueError("Model price not found")

        input_price = price_config.input_price
        output_price = price_config.output_price

        price = (
            input_price
            if token_type == "input"
            else output_price
        )

        if price is None or price <= 0:
            raise ValueError("invalid token price")

        tokens = (amount * PRICE_UNIT) / Decimal(price)

        return int(
            tokens.to_integral_value(
                rounding=ROUND_DOWN
            )
        )
