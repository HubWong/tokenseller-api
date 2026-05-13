from app.features.user.schemas.user_schema import SocketUser
from app.features.user.user_crud import user_crud
from app.features.socket.schema import SocketMsgType, SocketMessageOut, LeaveMsgIn
from app.features.db_base import Notification
from app.socket.manager import manager 
from app.features.socket.socket_models import room_manager
from app.socket.emitter import ChatSvc
from app.core.database import AsyncSessionLocal
from app.socket.socket_utils import query_data_on_connect   
from app.socket.socket_server import sio


async def join_country_room(sid:str, room_name:str):
    if room_name:
        await sio.enter_room(sid, room=room_name)    

async def send_notification(notify: Notification, target_ids: list[int] = []):
    """
    Send a notification to a specific user identified by their socket ID.
    """
    from_pid = notify.from_pc_id
    su = manager.user_sessions.get(str(from_pid), None)
    if not su:
        print(f"Sender with pc_id {from_pid} not found in user_sessions")
        return

    target_sids = [sid for t in target_ids if (sid := manager.check_isOnline_by_id(t)) is not None]
    for target in target_sids:
        print(f"Sending notification to target SID: {target}")
        so = SocketMessageOut(from_sid=sid,to_sids=target_sids,data=notify.data,to_pc_id='')
        await ChatSvc.broadcast_sids('notify',data=so)
            

@sio.event
async def connect(sid, environ): 
    user = await query_data_on_connect(environ)     
        # --- 校验 pc_id ---
    if not user or not user['pc_id']:
        await ChatSvc.send_error("pc_id is required", toSid=sid)
        return False        
    
    guest_user = SocketUser(**user)
    if(not guest_user.id):
        await ChatSvc.send_error("user id is required", toSid=sid)
        return False   
    guest_user.sid = sid
    await manager.connect(id=str(guest_user.id), su=guest_user)
    # --- 根据 ip_country 加入公共房间 ---
    if guest_user.ip_country:
        room = guest_user.ip_country
        await join_country_room(sid, room)  
    print(f"Sid {sid} connected, total users ({len(manager.user_sessions)})")
    so = SocketMessageOut(data= guest_user,from_sid=sid,to_pc_id=guest_user.pc_id, msg_type = SocketMsgType.UserConnect.value)
    # 通知其他已连接用户（排除自己）
    await ChatSvc.broadcast('notify',data=so,except_sid=True)
 

@sio.event
async def disconnect(sid):
    """
    Handle client disconnection
    """
    await sio.leave_room(sid,'/')  # Leave the country room if exists
    await manager.disconnect(sid=sid)
    room_manager.remove_sid_from_all_rooms(sid)  # Ensure the SID is removed from all rooms
    print(f"Sid {sid} disconnected, total users ({len(manager.user_sessions)})")
    so = SocketMessageOut(from_sid=sid,data={'user':sid},to_pc_id='',msg_type=SocketMsgType.UserDisconnect.value)
    await ChatSvc.emit_msg_sid('notify',data=so)
   
    
@sio.event
async def connect_error(sid, data):
    """
    Handle connection errors
    """
    print(f"Connection error for sid {sid}: {data}")
    # Optionally, you can clean up the session if needed    
    await manager.disconnect(sid=key)
       

@sio.event
async def leave_msg(sid, data): #when mbr is not online
    """summary
    data: { toId: str, fromId: str, msg: str, type: int  }
    """
    #if toId is online
    chtModel = LeaveMsgIn(**data)
    async with AsyncSessionLocal() as db:
        toUser = await user_crud.get_by_id(db=db,id=int(str(chtModel.toId)))
        if toUser:
            target_sid = toUser.sid  
            if not target_sid: 
                raise Exception('no target sid')
            await sio.emit('receive-message', 
                            {'from': 
                                {
                                    'id': str(chtModel.fromId),
                                    'name': f'用户{chtModel.fromUser}',
                                    'fromSid':sid
                                },
                            'msg': chtModel.content,
                            'type': chtModel.targetType
                            }, 
                            to=target_sid)
        else:
            async with AsyncSessionLocal() as session:
                 pass
            
        await ChatSvc.send_error('user not online',toSid=sid)
