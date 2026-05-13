from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple

from app.features.db_base import ApiResp

class BaseServiceABC(ABC):
    """基础服务抽象类
   
    """
    @abstractmethod
    async def add_transaction(self, user_id: int, amount: float, transaction_type: str):
        """更新交易记录"""
        pass

    @abstractmethod
    async def update_user(self, user_id: int, amount: float):
        """更新用户余额"""
        pass


class BuyServiceABC(BaseServiceABC):
    """
    负责：充值 / 买 token
    Order(PAID)
            ↓
    Transaction(+100, type=recharge)
            ↓
    UserBalance(+100)
    """

    @abstractmethod
    async def create_order(self, model: str,user_id:int) -> Dict[str, Any]:
        """创建充值订单
      
        """
        pass

    @abstractmethod
    async def pay_order(self, order_id: int, order_data: Dict):
        """支付订单"""
        pass

    @abstractmethod
    async def refund(self, user_id: int, amount: float, reason: str):
        """退款 / 回滚"""
        pass

class ConsumeServiceABC(BaseServiceABC):
    '''#消费 token
    ApiKey
        ↓
    TokenUsageLog
        ↓
    Transaction(-1, type=consume)
        ↓
    UserBalance(-1)
    '''
    @abstractmethod
    async def charge(self,charge_type:str, user_id: int, model: str, usage: dict, meta: dict = None):
        pass
 
class CommissionServiceABC(BaseServiceABC):
    ''' #分销佣金
    
        子用户消费
        ↓
        Transaction(-1, type=consume)
            ↓
        Transaction(+0.1, type=commission)
            ↓
        UserBalance(+0.1)
            ↓
        CommissionLog
    '''
    @abstractmethod
    async def distribute(self, order_id: int, from_uid: int, amount: float):
        pass
    

class RedisListenerABC(ABC):
    @abstractmethod
    async def start():
        ...

    @abstractmethod
    async def stop():
        ...
    
    @abstractmethod
    async def callback(data:dict):
        pass

class AddressPoolABC(ABC):

    @abstractmethod
    def derive_addr(xpub,index,coin)->str:
        ...

    @abstractmethod
    async def get_address_by_redis(self, index: int)->Tuple[str,int]:
        pass


class BaseChainListener(ABC):

    def __init__(self, rpc_pool: str):
        self.rpc_pool = rpc_pool #rpc pool ,防止单个rpc url失效
        self.last_block = None

    @abstractmethod
    async def get_latest_block(self):
        pass

    @abstractmethod
    async def get_block_transactions(self, block_number):
        pass

    @abstractmethod
    async def start(self, callback):
        """
        callback(tx)
        """
        pass
 