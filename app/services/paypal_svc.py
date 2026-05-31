from app.core.abc.abc_biz import logger
import httpx
from app.core.config import settings

PAYPAL_TOKEN_URL = "/v1/oauth2/token"
PAYPAL_ORDER_URL = "/v2/checkout/orders"

paypal_id = 'AZvY9fTp4E1CjI-xAoRq-5CVaK2MkF6U7WzBCBB7E3Km4Tb3ie5Qw9FPigVzdgtVzeTsekSdzGLLO9Bm'
sct = 'EGnatGlEaKxU_44kSmCI3OnJDzQ0ZCT4K2LDVHjnxdiNVaVsEcUr8GHxNRHBn9GM3pOYqOq_ZJ'
class PayPalSvc:
    def __init__(self):
        if paypal_id is None or sct is None:
            raise ValueError("PayPal client ID or secret is not set")
        self.client_id = paypal_id
        self.client_secret = sct
        self.base_url = settings.PAYPAL_BASE_URL

    async def _get_token(self) -> str:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}{PAYPAL_TOKEN_URL}",
                    data={"grant_type": "client_credentials"},
                    auth=(self.client_id, self.client_secret),
                    headers={"Accept": "application/json"},
                )
                resp.raise_for_status()
                return resp.json()["access_token"]
        except Exception as e:
            logger.error("Failed to get PayPal token",str(e))
            raise RuntimeError("PayPal authentication failed") from e
            pass
        

    async def create_paypal_order(self, amount_usd: float, order_id: int, return_url: str, cancel_url: str) -> dict:
        token = await self._get_token()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {
                    "currency_code": "USD",
                    "value": f"{amount_usd:.2f}",
                },
                "custom_id": str(order_id),
            }],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}{PAYPAL_ORDER_URL}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def get_order(self, paypal_order_id: str) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}{PAYPAL_ORDER_URL}/{paypal_order_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def capture_order(self, paypal_order_id: str) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}{PAYPAL_ORDER_URL}/{paypal_order_id}/capture",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()
