import httpx
from app.core.config import settings

PAYPAL_TOKEN_URL = "/v1/oauth2/token"
PAYPAL_ORDER_URL = "/v2/checkout/orders"


class PayPalSvc:
    def __init__(self):
        self.client_id = settings.PAYPAL_CLIENT_ID
        self.client_secret = settings.PAYPAL_CLIENT_SECRET
        self.base_url = settings.PAYPAL_BASE_URL

    async def _get_token(self) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}{PAYPAL_TOKEN_URL}",
                data={"grant_type": "client_credentials"},
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    async def create_order(self, amount_usd: float, order_id: int, return_url: str, cancel_url: str) -> dict:
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
