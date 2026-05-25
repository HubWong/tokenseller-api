from typing import List, Optional, Tuple, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select, func
from app.features.biz.order.order_model import Order
from app.features.biz.order.order_schema import PurchaseRequest, OrderCreateIn,OrderStatus,OrderInDBBase
from datetime import  datetime, timedelta
from app.features.tron_address.address_repo import AddressSvc
from app.features.db_base import ApiResp
from app.services.listener_svc import order_pool
'''
order is temporary use only,transaction is final record
'''

class OrderRepo():
    def __init__(self, db:AsyncSession, address_pool_svc:AddressSvc = None) :
        self.db = db
        self.address_svc = address_pool_svc
    
    async def get_unfinished_orders(self)-> Sequence[OrderInDBBase]:
        try:
            stmt = select(Order).where(Order.order_status == 'pending', Order.expired_at > datetime.now())
            result = await self.db.execute(stmt)
            db_objs = result.scalars().all()
            return [OrderInDBBase.model_validate(obj) for obj in db_objs]
        except Exception as e:
            print(f"❌ 获取未完成订单失败: {e}")
            return []

    async def remove_expired_orders(self) -> int:
        try:
            stmt = select(Order).where(Order.order_status == 'pending', Order.expired_at <= datetime.now())
            result = await self.db.execute(stmt)
            expired_orders = result.scalars().all()
            count = len(expired_orders)
            for order in expired_orders:
                await self.db.delete(order)
            await self.db.commit()
            print(f"✅ 已删除 {count} 个过期订单")
            return count
        except Exception as e:
            await self.db.rollback()
            print(f"❌ 删除过期订单失败: {e}")
            return 0

    # user recharge/buy token 
    async def pay_order(self, order_id: int, session: AsyncSession,
        status:Optional[OrderStatus]):
        try:
            order = select(Order).where(Order.id == order_id)
            result = await session.execute(order)
            order = result.scalar_one_or_none()
            if not order or order.order_status == OrderStatus.SUCCESS.value:
                return None
            
            order.order_status = status.value            
            order.notify_count += 1             
            return order
             
        except Exception as e:
            
            print(f"❌ 更新订单失败: {e}")
            return None

    async def cancel_order(self, order_id: int,uid:int,username:str) -> bool:
        try:        
           
            stmt = select(Order).where(Order.id == order_id)
            result = await self.db.execute(stmt)
            db_obj = result.scalar_one_or_none()
            
            if db_obj:
                db_obj.order_status = OrderStatus.CANCELLED.value
                db_obj.updated_at = datetime.now()
                db_obj.memo = f'test cancel order by {uid}'
                await self.db.commit()
                return True
            return False
        except Exception as e:
            await self.db.rollback()
            print(f"❌ 取消订单失败: {e}")
            return False

    async def list_orders(self,user_id:int=None, page:int=1,limit:int=10):
        skip = (page - 1) * limit
        
        # Get total count
        if user_id:
            count_stmt = select(func.count(Order.id)).where(Order.user_id == user_id)
            stmt = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc()).offset(skip).limit(limit)
        else:
            count_stmt = select(func.count(Order.id))
            stmt = select(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit)
        
        # Execute count query
        count_result = await self.db.execute(count_stmt)
        total = count_result.scalar()
        
        # Execute paginated query
        result = await self.db.execute(stmt)
        db_objs = result.scalars().all()
        
        return [OrderInDBBase.model_validate(obj) for obj in db_objs], total
    
   

    async def get_by_id(self,  order_id: int) -> Optional[OrderCreateIn]:
        stmt = select(Order).where(Order.id == order_id)
        result = await self.db.execute(stmt)
        db_obj = result.scalar_one_or_none()
        return OrderCreateIn.model_validate(db_obj) if db_obj else None

    async def get_by_user_id(self, user_id: int) -> List[OrderCreateIn]:
        stmt = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
        result = await self.db.execute(stmt)
        db_objs = result.scalars().all()
        return [OrderCreateIn.model_validate(obj) for obj in db_objs]

    async def get_pending_order(
            self,     
            user_id: int, 
            item_id: int, 
            amount:float,
            expired_at: datetime = None
        ) -> Optional[OrderInDBBase]:
            
            conditions = [
                Order.user_id == user_id,
                Order.pay_way == item_id,
                Order.amount == amount,
                Order.order_status == OrderStatus.PENDING.value,
                Order.expired_at > datetime.now()  
            ]
            
            # 动态追加时间条件
            if expired_at is not None:
                conditions.append(Order.expired_at <= expired_at)

            stmt = select(Order).where(and_(*conditions)).order_by(Order.expired_at.desc())
            
            result = await self.db.execute(stmt)
            db_obj = result.scalar_one_or_none()
            
            if db_obj:          
                return OrderInDBBase.model_validate(db_obj)
            return None
            
            
    async def create(self,  purchase:PurchaseRequest, user_id:int) -> ApiResp:
        obj_in = OrderCreateIn(**purchase.model_dump())
        obj_in.user_id = user_id
        old_order =await self.get_pending_order(user_id= obj_in.user_id,
                                                amount= obj_in.amount,
                                                item_id= obj_in.pay_way)
        if old_order:
            await order_pool.add_order(old_order)
            return ApiResp(success=True,data= old_order)
        try:
            if purchase.pay_way == 1:
                # PayPal: 不需要区块链地址
                obj_in.to_address = 'paypal'
                obj_in.path_index = 0
                obj_in.contract = ''
                obj_in.currency = 'usd'
                obj_in.chain = 'paypal'
                obj_in.pay_way = 1
                
            else:
                # TRON: 分配 HD 钱包地址
                new_address, idx = await self.address_svc.get_address_by_redis()
                print(f"🔑 获取新地址: {new_address}, idx: {idx}")
                obj_in.to_address = new_address
                obj_in.path_index = idx
                obj_in.contract = ''
                obj_in.currency = 'usdt'
                obj_in.chain = 'tron'
                obj_in.pay_way = 2
            obj_in.expired_at = datetime.now() + timedelta(minutes=20)
            obj_data = obj_in.model_dump(exclude_unset=True)
            db_obj = Order(**obj_data)

            self.db.add(db_obj)

            await self.db.commit()
            await self.db.refresh(db_obj)
            OrderOut = OrderInDBBase.model_validate(db_obj)
            if purchase.pay_way == 2:
                await order_pool.add_order(OrderOut)

            return ApiResp(success=True, message="创建订单成功", data=OrderOut)

        except Exception as e:
            print(f"❌ 创建订单失败: {e}")

            await self.db.rollback()
            return ApiResp(success=False, message=f"创建订单失败: {str(e)}")
       


