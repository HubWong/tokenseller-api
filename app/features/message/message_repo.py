from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, case, func, select, update,text
from app.features.db_base import ApiResp,PagedResp
from collections.abc import Sequence
from app.features.user.model.user_model import User
from app.features.message.model import Message
from app.features.message.schema import MessageCreate,MessageOut


class MessageRepo:
    def __init__(self,db:AsyncSession) -> None:
        self.db = db

    async def create_msg(self, msg_data: MessageCreate, to_user: int) -> MessageOut:
        new_msg = Message(
            title=msg_data.title,
            to_user=to_user,
            msg_pwd=msg_data.msg_pwd,
            memo=msg_data.memo,
            max_man = msg_data.max_man )
        self.db.add(new_msg)
        await db.commit()
        await db.refresh(new_msg)
        return new_msg
            
         
    async def get_msgs(self, to_user: int, pg: int, limit: int) ->tuple[Sequence[MessageOut], int]:
        offset = max(0, (pg - 1)) * limit
        result = await db.execute(select(Message).where(Message.to_user == to_user).order_by(Message.last_active_at.desc()).offset(offset).limit(limit))
        msgs = result.scalars().all()
        count = await db.scalar(select(func.count(Message.id)).where(Message.to_user == to_user))
        return [MessageOut.model_validate(msg) for msg in msgs], count
    

    async def get_all_msgs(self, msg_id: int)->Any:
        stmt = select(Message, User).join(User, Message.to_user == User.id).where(Message.id == msg_id)
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            return ApiResp(data=None, message="msg or maker not found", success=False)
        msg, maker = row
        return msg, maker
    
    async def get(self, msg_id: int,isForUpdate=False) -> ApiResp[Any]:  
        result = await db.execute(select(Message).where(Message.id == msg_id))
        msg = result.scalars().first()
        if not msg:
            return ApiResp(data=None, message="msg not found",success=False)
        if isForUpdate:
            msg_out = MessageOut.model_validate(msg)   
            return ApiResp(data=msg_out,success = True, message="msg retrieved successfully")
        else:
            msg_out = MessageOutWithMakerData.model_validate(msg)
            msg_out.has_pwd = bool(msg.msg_pwd)
            msg_out.maker_data = {"id": msg.to_user}  # 这里可以根据需要添加更多房主信息
            return ApiResp(data=msg_out,success = True, message="msg retrieved successfully")
    
    async def delete_msg(self, msg_id: int, to_user: int) -> bool:
        result = await db.execute(select(Message).where(Message.id == msg_id))
        msg = result.scalars().first()
        if not msg or msg.to_user != to_user:
            return False  # 房间不存在或当前用户不是房主
        await db.delete(msg)
        await db.commit()
        return True
        
    
     
if __name__ =='__main__':
    pass

                


