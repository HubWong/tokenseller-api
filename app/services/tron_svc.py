
from app.core.abc.abc import BaseChainListener
from dotenv import load_dotenv
from sqlmodel import SQLModel
from typing import Optional, Dict
from tronpy import AsyncTron, Tron, Contract
from tronpy.providers import HTTPProvider
from app.core.config import settings
import aiohttp
import asyncio
import base58
import logging
 
load_dotenv()

logger = logging.getLogger(__name__)
TRON_TIMEOUT = aiohttp.ClientTimeout(total=30)


class ChinTx(SQLModel):
    chain: str          # 链名称，例如 "BTC"
    to: str             # 接收地址
    value: float        # 金额
    tx_hash: str        # 交易哈希
    vout_index: Optional[int] =None     # 输出索引（BTC 特有，ETH/TRON可用0）
    from_addr: str = "" # 发送地址，可选
    token: str = "BTC"  # 代币类型 交易的资产类型（链上资产/代币）
    block:Optional[str|int]=None
    
    '''
    链 (chain)	资产 (token)	说明
    BTC	         BTC	    BTC 链上的原生比特币
    ETH 	    ETH	        ETH 链上的原生以太币
    ETH	        USDT	    ERC20 USDT，仍在 ETH 链上
    TRON	    TRX	        TRON 链上的原生 TRX
    TRON	    USDT	    TRC20 USDT，TRON 链上
    '''
TRON_API_KEY ='a42e537c-417a-42a7-b253-298c8b2f171f'
TRON_API = "https://api.trongrid.io" 
TRON_HEADERS = {"TRON-PRO-API-KEY": TRON_API_KEY} if TRON_API_KEY else {}


TRC20_TRANSFER_TOPIC = "a9059cbb"  # transfer(address,uint256)



def tron_addr_normalize(addr: str):
    """
    tron 地址统一转成 base58
    RPC 可能返回 hex 或 base58
    """

    if not addr:
        return None

    # 已经是 base58
    if addr.startswith("T"):
        return addr

    # hex 地址
    if addr.startswith("41"):
        try:
            addr_bytes = bytes.fromhex(addr)
            return base58.b58encode_check(addr_bytes).decode()
        except Exception:
            return None
    return None


class TronListener(BaseChainListener):
    REQUIRED_CONFIRMATIONS = 20  # TRON recommended: 19-20 blocks (~1 min)

    def __init__(self, rpc_pool, order_pool):
        super().__init__(rpc_pool)
        self.order_pool = order_pool
        self.client = None
        self.rpc_pool = [endpoint.rstrip('/') for endpoint in rpc_pool] if rpc_pool else [TRON_API]
        self.rpc_index = 0
        # tx_hash -> {order_id, block, confirmations, parsed}
        self.pending_confirmations: Dict[str, dict] = {}

    async def _rpc_request(self, path, json_body=None, method='post'):
        if not self.rpc_pool:
            self.rpc_pool = [TRON_API]

        errors = []
        for _ in range(len(self.rpc_pool)):
            endpoint = self.rpc_pool[self.rpc_index]
            url = f"{endpoint}{path}"
            try:
                if method.lower() == 'get':
                    async with self.client.get(url) as r:
                        if r.status != 200:
                            raise RuntimeError(f"HTTP {r.status}: {await r.text()}")
                        return await r.json()
                else:
                    async with self.client.post(url, json=json_body) as r:
                        if r.status != 200:
                            raise RuntimeError(f"HTTP {r.status}: {await r.text()}")
                        return await r.json()
            except Exception as exc:
                logger.warning('Tron RPC request failed on %s: %s', url, exc)
                errors.append(f"{url}: {exc}")
                self.rpc_index = (self.rpc_index + 1) % len(self.rpc_pool)
                await asyncio.sleep(0.2)

        raise RuntimeError('All Tron RPC endpoints failed: %s' % ' | '.join(errors))

    async def _get_block(self, num):
        return await self._rpc_request('/wallet/getblockbynum', json_body={"num": num, "visible": True}, method='post')

    async def get_latest_block(self):
        block_data = await self._rpc_request('/wallet/getnowblock', method='get')
        return block_data["block_header"]["raw_data"]["number"]

    async def get_block_transactions(self, block_number):
        block = await self._get_block(block_number)
        return block.get("transactions", [])

    def parse_trx_transfer(self, tx, contract, block):
        value = contract["parameter"]["value"]
        from_addr = tron_addr_normalize(value.get("owner_address"))
        to_addr = tron_addr_normalize(value.get("to_address"))

        obj = {
            "chain": "tron",
            "tx_hash": tx["txID"],
            "from_addr": from_addr,
            "to": to_addr,
            "value": value.get("amount", 0),
            "block": block
        }
        return ChinTx(**obj)

    def parse_trc20_transfer(self, tx, contract, block):
        data = contract["parameter"]["value"].get("data")
        if not data or not data.startswith(TRC20_TRANSFER_TOPIC):
            return None
        try:
            to_hex = data[32:72]
            amount_hex = data[72:]
            to_addr = tron_addr_normalize("41" + to_hex[-40:])
            amount = int(amount_hex, 16)
            from_hex = contract["parameter"]["value"]["owner_address"]
            from_addr = tron_addr_normalize(from_hex)

            ojb = {
                "chain": "tron",
                "tx_hash": tx["txID"],
                "from_addr": from_addr,
                "to": to_addr,
                "value": amount,
                "block": block,
                "token": "trc20"
            }
            return ChinTx(**ojb)

        except Exception:
            return None

    async def _dispatch_confirmed_transactions(self, latest, callback):
        confirmed_txs = []
        for tx_hash, info in list(self.pending_confirmations.items()):
            info['confirmations'] = latest - info['block']
            if info['confirmations'] >= self.REQUIRED_CONFIRMATIONS:
                confirmed_txs.append(tx_hash)

        for tx_hash in confirmed_txs:
            info = self.pending_confirmations.get(tx_hash)
            if not info:
                continue
            parsed = info['parsed']
            parsed['confirmations'] = info['confirmations']
            logger.info('[TX confirmed]: order_id=%s, tx=%s, confirmations=%s', info['order_id'], tx_hash, info['confirmations'])
            try:
                await callback(parsed)
                self.pending_confirmations.pop(tx_hash, None)
            except Exception as exc:
                logger.exception('Confirmed transaction callback failed for %s: %s', tx_hash, exc)

    async def start(self, callback):
        logger.info('[*] Tron listener started, waiting for orders...')

        while not await self.order_pool.has_orders():
            await asyncio.sleep(5)

        logger.info('[*] Orders detected, starting blockchain polling')

        async with aiohttp.ClientSession(headers=TRON_HEADERS, timeout=TRON_TIMEOUT) as session:
            self.client = session
            if self.last_block is None:
                self.last_block = await self.get_latest_block()
            while True:
                try:
                    latest = await self.get_latest_block()
                    if latest is None:
                        await asyncio.sleep(5)
                        continue

                    if self.last_block is None:
                        self.last_block = latest

                    if latest > self.last_block:
                        for block in range(self.last_block + 1, latest + 1):
                            txs = await self.get_block_transactions(block)
                            for tx in txs:
                                raw = tx.get("raw_data")
                                if not raw:
                                    continue

                                contracts = raw.get("contract")
                                if not contracts:
                                    continue

                                contract = contracts[0]
                                ctype = contract.get("type")
                                parsed = None

                                if ctype == "TransferContract":
                                    parsed = self.parse_trx_transfer(tx, contract, block)
                                elif ctype == "TriggerSmartContract":
                                    parsed = self.parse_trc20_transfer(tx, contract, block)

                                if not parsed:
                                    continue

                                order_id = await self.order_pool.get_order_id_by_address(parsed.to)
                                if order_id:
                                    parsed["order_id"] = order_id
                                    self.pending_confirmations[parsed.tx_hash] = {
                                        'order_id': order_id,
                                        'block': parsed.block,
                                        'confirmations': 0,
                                        'parsed': parsed,
                                    }
                                    logger.info('[TX detected]: order_id=%s, tx=%s, block=%s, waiting confirmations...', order_id, parsed.tx_hash, parsed.block)

                        self.last_block = latest

                    await self._dispatch_confirmed_transactions(latest, callback)
                    await asyncio.sleep(3)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.exception('tron listener error: %s', e)
                    await asyncio.sleep(5)
