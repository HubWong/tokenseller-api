from pydantic import BaseModel
from typing import List, Optional,Generic,TypeVar,Any
from datetime import datetime
from app.features.user.schemas.user_schema import SocketUser
from enum import Enum
import uuid

class SocketMsgType(str,Enum):  
    send_request ='send_request'
    UserConnect = "user_connect"
    UserDisconnect = "user_disconnect"
    chat = "chat"
    left_room = "left_room"     
    video_signal = "video_signal"
    chat_image = "chat_image"
    SYSTEM = "system"    
    notify = "notify"
    calling = "calling"
    call_accepted = "call_accepted"
    call_rejected = "call_rejected"
    hangup = "hangup"
    ERROR = "error"
    PRESENCE = "presence"

class RoomMsgType(str,Enum):
    join = "join"
    leave = "leave"
    message = "message"
    img_msg = "img_msg"

class BaseMsg(BaseModel):
    data: Any
    ts: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  

class SocketMessageOut(BaseMsg):
    from_sid: str
    from_pc_id:Optional[str] =None
    to_pc_id:Optional[str] = None
    from_uid: Optional[str|int]=None
    from_user: Optional[str] = None
    msg_type: str = SocketMsgType.chat.value
    id: Optional[str] = str(uuid.uuid4().hex)    
    to_sid: Optional[str] = None
    to_user: Optional[int] = None
    to_sids: Optional[List[str]] = None
    to_room:Optional[str] = None
   
    
    class Config:
        from_attributes =True
   
    

class LeaveMsgIn(BaseMsg):
    fromId: Optional[str|int]
    toId: Optional[str|int]
    convId:str
    isIn:Optional[bool]
    fromUser:Optional[str] #from username
    targetType: Optional[SocketMsgType] = SocketMsgType.chat

 
class JoinRoomModel(BaseModel):
    room_name:str   
    maker:Optional[str] = None
    maker_id: Optional[int] = None
    user:Optional[str] = None

class JoinUserRoomModel(BaseModel):
    room_name:str 
    room_pwd: Optional[str] = None
    user:Optional[str] = None


T = TypeVar('T')

class SocketMessageModel(BaseModel, Generic[T]):
    code: int = 200
    timestamp: int = int(datetime.now().timestamp())
    payload: T
           
class UserIsViewingModel(SocketUser):
    to_user_id:int

    
class PagedSocketUserByCountry(BaseModel):
    page: int = 1
    page_size: int = 10
    ip_country: Optional[str] = None  # 新增国家过滤字段