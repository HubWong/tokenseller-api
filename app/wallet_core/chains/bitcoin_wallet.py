import httpx
from bitcoinlib.wallets import HDWallet
from app.wallet_core.base import BaseWallet
from app.core.config import settings

 
btc_xpub= settings.XPRV_bit

class BitcoinWallet(BaseWallet):

    def __init__(self):
        self.xpub = btc_xpub
        self.wallet = HDWallet.create(
            name='btc_watch',
            keys=self.xpub,
            network='bitcoin',
            witness_type='segwit',
            db_uri=None
        )

    def derive_address(self, index: int):
        key = self.wallet.get_key(account_id=0, change=0, number=index)
        return {
            "address": key.address,
            "index": index
        }

    async def check_payment(self, address: str, amount: float):
        url = f"https://blockstream.info/api/address/{address}/utxo"
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            utxos = r.json()

            total = sum([u["value"] for u in utxos]) / 100000000

            if total >= amount:
                return {"confirmed": True}
        return {"confirmed": False}

    async def sweep(self, from_index: int, to_address: str, amount: float):
        # 实际生产需签名服务器处理
        raise NotImplementedError("BTC sweep must be signed offline")

    async def get_balance(self, address: str):
        url = f"https://blockstream.info/api/address/{address}"
        async with httpx.AsyncClient() as client:
            r = await client.get(url)
            data = r.json()
            return data["chain_stats"]["funded_txo_sum"] / 100000000