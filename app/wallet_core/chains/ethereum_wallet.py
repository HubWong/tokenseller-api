from web3 import Web3
from app.wallet_core.base import BaseWallet
from eth_account import Account
from app.core.config import settings


eth_xpub = settings.XPUB_eth

class EthereumWallet(BaseWallet):

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_KEY"))
        self.xpub = eth_xpub

    def derive_address(self, index: int):
        # ETH 常用 m/44'/60'/0'/0/index
        acct = Account.from_key("DERIVED_PRIVATE_KEY")  # 实际应签名服务生成
        return {
            "address": acct.address,
            "index": index
        }

    async def check_payment(self, address: str, amount: float):
        balance = self.w3.eth.get_balance(address)
        if self.w3.from_wei(balance, 'ether') >= amount:
            return {"confirmed": True}
        return {"confirmed": False}

    async def sweep(self, from_index: int, to_address: str, amount: float):
        # 实际需签名服务器
        raise NotImplementedError

    async def get_balance(self, address: str):
        balance = self.w3.eth.get_balance(address)
        return self.w3.from_wei(balance, 'ether')