from redis.asyncio import Redis
from app.core.abc import AddressPoolABC
from sqlalchemy.ext.asyncio import AsyncSession
from bip_utils import Bip44Coins,Bip84Coins,Bip84,Bip44Changes,Bip44

from app.core.config import settings

xpub_tron = settings.XPUB_tron
tron_key = 'tron:path_index'




class AddressSvc(AddressPoolABC):
    def __init__(self, db: AsyncSession,redis:Redis) -> None:
        super().__init__()       
        self.redis_client = redis
   
    def derive_addr(self, xpub: str, index: int, coin: Bip44Coins|Bip84Coins) -> str:
        if coin== Bip84Coins.BITCOIN:
            bip = Bip84.FromExtendedKey(xpub, Bip84Coins.BITCOIN)
            return (
                bip.Change(Bip44Changes.CHAIN_EXT)
                .AddressIndex(index)
                .PublicKey()
                .ToAddress()
            )
            
            
        bip = Bip44.FromExtendedKey(xpub, coin_type=coin)
        addr = bip.Change(Bip44Changes.CHAIN_EXT).AddressIndex(index).PublicKey().ToAddress()
        return addr

    async def get_address_by_redis(self):
        path_index = await self.redis_client.incr(tron_key)
        address = self.derive_addr(xpub=xpub_tron,index= path_index, coin = Bip44Coins.TRON)
        return address, path_index

 


