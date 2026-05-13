from tronpy import Tron
from tronpy.keys import PrivateKey
from app.wallet_core.base import BaseWallet, derive_addr, Bip44Coins
from app.core.config import settings


tron_xpub = settings.XPUB_tron

class TronWallet(BaseWallet):

    def __init__(self):
        self.client = Tron()
        self.xpub = tron_xpub

    def derive_address(self, index: int):
        address = derive_addr(self.xpub, index, Bip44Coins.TRON)
        return {
            "address": address,
            "index": index
        }

    async def check_payment(self, address: str, amount: float):
        balance = self.client.get_account_balance(address)
        if balance >= amount:
            return {"confirmed": True}
        return {"confirmed": False}

    async def sweep(self, from_index: int, to_address: str, amount: float):
        raise NotImplementedError

    async def get_balance(self, address: str):
        return self.client.get_account_balance(address)