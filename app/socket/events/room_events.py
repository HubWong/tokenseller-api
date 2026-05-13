from app.socket.socket_server import sio
from app.socket.manager import manager
from app.features.socket.socket_models import room_manager
from app.features.socket.schema import SocketMessageOut, JoinRoomModel ,SocketMsgType,RoomMsgType
from app.socket.emitter import ChatSvc
from app.core.database import AsyncSessionLocal
from app.back_jobs.db_tasks import get_user_by_id
from app.core.config import settings

rooms_count_user = settings.MAX_ROOM_PER_USER
rooms_count_user_vip = settings.MAX_ROOM_PER_VIP_USER

@sio.event
async def left_pubroom(sid,data):
    room_manager.leave_room(data,sid)
    await sio.leave_room(sid,data)
    await sio.emit('user_left','',room=data)
    
async def _join_room(sid, room_name):  
    # temper room 通用加入流程
    await sio.enter_room(sid, room_name)
    room_manager.join_room(room_name, sid)
    participants = room_manager.get_room_participants(room_name)
    sus = await manager.get_user_by_sids(participants)
    so = SocketMessageOut(from_sid=sid, to_room=room_name, data={"participants": sus},to_pc_id='')
    await ChatSvc.broadcast_room('joined', data=so,skip_sid=False)
    

@sio.event
async def join_user_room(sid,data): #loged in user joining room.
    to_room = data.get("to_room")
    uid = data.get("uid")
    from_pc_id = data.get("from_pcId")  
    if not uid or not to_room:
        await ChatSvc.send_error("uid is required", toSid=sid)
        return
    
    await sio.enter_room(sid, to_room)
    async with AsyncSessionLocal() as db:
        su = await get_user_by_id(db,int(uid))
        other_participants = room_manager.get_room_participants(to_room)
        others = []
        for p in other_participants:
            if p != sid:
                _,other_su = await manager.get_user_by_sid(p)
                if other_su:
                    others.append(other_su)
        others.append(su)  #把自己也加到列表里，方便前端显示
        if not su:
            await ChatSvc.send_error("用户不存在", toSid=sid)
            return
    room_manager.join_room(to_room, sid)
    so = SocketMessageOut(from_sid=sid, to_room=to_room, data={"participants": others},to_pc_id=from_pc_id)
    await ChatSvc.broadcast_room('joined', data=so,skip_sid=False)


@sio.event
async def join_p2p(sid, data):          
    jrModel = JoinRoomModel(**data)
    room_name = jrModel.room_name
    if room_name.startswith(('private_', 'mbr_')):
        maker = jrModel.maker 
        if room_name.startswith('private_') and not room_manager.create_room(room_name, maker):
            await ChatSvc.send_error(f"临时用户{maker} 已创建 {rooms_count_user} 个房间，无法继续创建", toSid=sid)            
            return           
                   
    await _join_room(sid, room_name)
    
#----------private room -----------


@sio.event
async def request_join_room(sid, data): #join room with password or by invite
    room_name = data.get("room_name")
    maker_id = data.get("maker_id")
    from_user = data.get("from_user")
    from_pc_id = data.get("from_pc_id")

    if not room_manager.room_exists(room_name):
        await ChatSvc.send_error("房间不存在", toSid=sid)
        return

    so = SocketMessageOut(
        from_sid=sid,
        from_user=from_user,
        from_pc_id=from_pc_id,
        to_room=room_name,
        to_pc_id='',
        msg_type=SocketMsgType.request_join.value,
        data={"room_name": room_name, "from_user": from_user, "from_pc_id": from_pc_id}
    )
    # 发送给房主
    maker_su = manager.get_by_pc_id(pcId=str(maker_id))
    if maker_su:
        so.to_sid = maker_su.sid
        await ChatSvc.emit_event_notify(data=so, except_sid=False)
    else:
        await ChatSvc.send_error("房主不在线", toSid=sid)

#----------pub room -----------

@sio.event
async def get_pubroom_users(sid, name):
    users = []
    room = f"{name}"
    for _, rooms in sio.manager.rooms.items():
        if room in rooms:
            sids = rooms[room]
            # 通过 sid 找对应的业务对象
            for s in sids:
                u = next((u for u in manager.user_sessions.values() if u.sid == s), None)
                if u:
                    users.append(u.dict())
    await sio.emit('pubroom-users', users, to=sid)

def get_sid_by_pc_id(pcId:str):
    su = manager.get_by_pc_id(pcid=pcId)
    if su:
        return su
    return None 


@sio.event
async def leave(sid, data):
    room = data["room"]       
    mkr = room_manager.get_maker_id_by_room(room)
    if not mkr:        
        return        
    room_manager.leave_room(room_name=room,sid=sid)
    #if maker's sid, delete room
    if mkr and mkr==sid:
        room_manager._delete_room(room_name=room,maker=mkr)
    await sio.leave_room(sid, room)
    so = SocketMessageOut(from_sid=sid,msg_type=SocketMsgType.left_room.value,from_user="sys",
                          to_room= room,data={"left_sid": sid,'rmt': RoomMsgType.leave.value},to_pc_id='')
    await ChatSvc.broadcast_room('user_left',data=so)    
    pass


@sio.event
async def leave_pubroom(sid, data):
    room = data["room"]       
    room_manager.leave_room(room_name=room,sid=sid)    
    await sio.leave_room(sid, room)
    so = SocketMessageOut(from_sid=sid,msg_type=SocketMsgType.left_room.value,from_user="sys",
                          to_room= room,data={"left_sid": sid,'rmt': RoomMsgType.leave.value},to_pc_id='')
    await ChatSvc.broadcast_room('user_left',data=so)


@sio.event
async def kick_user(sid, data):
    room = data["room"]
    target_sid = data["target_sid"]
    mkr = room_manager.get_maker_id_by_room(room)
    if not mkr:
        await ChatSvc.send_error("房间不存在", toSid=sid)
        return
    if mkr != sid:
        await ChatSvc.send_error("只有房主可以踢人", toSid=sid)
        return
    room_manager.leave_room(room_name=room, sid=target_sid)
    await sio.leave_room(target_sid, room)
    so = SocketMessageOut(from_sid=sid, msg_type=SocketMsgType.kick.value, from_user="sys",
                          to_room=room, data={"kicked_sid": target_sid,'rmt': RoomMsgType.kick.value},to_pc_id='')
    await ChatSvc.broadcast_room('user_kicked', data=so)
    

@sio.event
async def invite_chat(sid, data):    
    to_pc = data.get("to")
    from_user = data.get("from")
    from_pc = data.get('from_pc_id',None)
    room = data.get("room", None)
    if to_pc:
        su = get_sid_by_pc_id(to_pc)
        if su:
            so = SocketMessageOut(from_sid=sid, from_user=from_user,to_pc_id=su.pc_id,
                                  to_room=room, to_sid=su.sid,
                                  msg_type=SocketMsgType.notify.value,
                                  data={"from": from_user, "from_pc_id": from_pc})
            await ChatSvc.emit_event_notify(data=so,except_sid=True)
        else:
            await ChatSvc.send_error("用户不在线", toSid=sid)
    else:
        await ChatSvc.send_error("目标 pc_id is required", toSid=sid)
       
        
@sio.event
async def send_room_msg(sid,data):  
    room = data.get("to_room")
    ty = data.get("msg_type","chat")    
    from_pc_id= data.get('from_pc_id') 
    su = get_sid_by_pc_id(pcId=from_pc_id)
    cnt = data.get('data',{})
    if not su:
        await ChatSvc.send_error('no user find by pc id',toSid=sid)
        return
    t = SocketMsgType[ty] if ty in SocketMsgType.__members__ else SocketMsgType.chat    
    print('sending type:',t)         
    so = SocketMessageOut(from_user= data.get('from_user','') or f'{from_pc_id}',
                          from_sid=sid ,
                          from_pc_id = from_pc_id,
                          data={'content':cnt.get('content'),"rmt": cnt.get('rmt','')}, #rom msg type
                          id=data.get('msg_id',''),
                          to_room=room,                         
                          msg_type=t.value)
    await ChatSvc.broadcast_room("text-message",data=so)

@sio.event
async def send_msg(sid,data):  
    room = data.get("to_room")
    ty = data.get("msg_type","chat")
    data1 = data.get("data",{})
    to_pc= data.get('to_pc_id')
    from_pc_id= data.get('from_pc_id')
    
    # to_sid = data.get('to_sid')
    su = get_sid_by_pc_id(pcId=to_pc)
    if not su:
        await ChatSvc.send_error('no user find by pc id',toSid=sid)
        return
    
    t = SocketMsgType[ty] if ty in SocketMsgType.__members__ else SocketMsgType.chat    
    print('sending type:',t)         
    so = SocketMessageOut(from_user=data.get('from_user',''),
                          from_sid=sid, to_sid = su.sid,
                          from_pc_id = from_pc_id,
                          data={'content':data1.get('content',''),"rmt": data1.get('rmt','')},
                          id=data.get('msg_id',''),
                          to_room=room,
                          to_pc_id=to_pc,
                          msg_type=t.value)
    
    if t == SocketMsgType.notify:
        await ChatSvc.emit_msg_sid(event='notify', data=so,except_sid=True)  
    else:
        await ChatSvc.broadcast_room("text-message",data=so)
    
        
 