from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple
import tiktoken
from decimal import ROUND_DOWN
from app.features.biz.order.order_model import ModelPricing

PRICE_UNIT = Decimal("1000000")
PRECISION = Decimal("0.000001")
class TokenCostCalculator:
    def __init__(self,price_db):
        # 定义模型价格表 (每 1000 tokens 的价格，单位：元)
        # 实际使用时，请根据最新的官方定价修改这里
        self.prices =price_db

    def count_tokens(text: str, model: str = "gpt-4o") -> int:
        try:
            # 获取对应模型的编码器
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # 如果模型不支持，使用默认编码器 (cl100k_base 适用于大多数新模型)
            encoding = tiktoken.get_encoding("cl100k_base")
        
        # 计算长度
        return len(encoding.encode(text))

    async def query_price(self, model:str) -> ModelPricing:
        """查询模型的单价"""
        return await self.prices.get_pricing_by_model(model_name=model)

    async def _get_price(self, model: str) -> Tuple[Decimal, Decimal]:
        """获取模型的输入和输出单价"""
        # 使用 .get 防止模型不存在报错，回退到 default
        price_config = await self.query_price(model)
        if not price_config:
            return 0,0
        return price_config.input_price, price_config.output_price

     


    async def tokens_to_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str = "default",
        multiplier: Decimal = Decimal("1.0")
    ) -> Decimal:

        input_price, output_price = await self._get_price(model)

        if input_price is None or output_price is None:
            raise ValueError("Model price not found")

        cost = (
            (Decimal(input_tokens) * input_price) +
            (Decimal(output_tokens) * output_price)
        ) / PRICE_UNIT

        cost *= multiplier

        return cost.quantize(PRECISION, rounding=ROUND_HALF_UP)

    #????????? vip and common seperately.
    
    async def money_to_tokens(
        self,
        amount: Decimal,
        model: str = "default",
        token_type: str = "input"
    ) -> int:

        if amount <= 0:
            raise ValueError("invalid amount")

        input_price, output_price = await self._get_price(model)

        price = (
            input_price
            if token_type == "input"
            else output_price
        )

        if price is None or price <= 0:
            raise ValueError("invalid token price")

        tokens = (Decimal(str(amount)) * PRICE_UNIT) / price

        return int(
            tokens.to_integral_value(
                rounding=ROUND_DOWN
            )
        )

# --- 使用示例 ---

# calculator = TokenCostCalculator()

# # 场景 1: 计算金额 (Token -> Money)
# # 假设使用了 1000 个输入 token 和 500 个输出 token
# cost = calculator.calculate_cost(1000, 500, model="gpt-4o")
# print(f"消耗金额: {cost} 元") 

# # 场景 2: 计算 Token (Money -> Token)
# # 假设我有 10 元钱，想买 gpt-3.5-turbo 的输入额度
# tokens = calculator.money_to_tokens(10.0, model="gpt-3.5-turbo", token_type="input")
# print(f"10元可买 Token 数: {tokens}")