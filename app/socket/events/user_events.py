from app.socket.socket_server import sio
from app.socket.manager import manager
from app.features.user.user_crud import user_crud
from app.features.user.schemas.user_schema import SocketUser
from app.features.socket.schema import SocketMsgType, SocketMessageOut, JoinRoomModel, LeaveMsgIn, UserIsViewingModel
from app.socket.emitter import ChatSvc

def get_sid_by_pc_id(pcId:str):
    su = manager.get_by_pc_id(pcid=pcId)
    if su:
        return su
    return None

@sio.event #only update temper user info
async def update_info(sid, data):
    """
    Update temper user information
    Required data:
    - username,sid,pc_id
    - country: The country of the user
    - user_id: The unique identifier for the user
    上线
    """
    key, user = await manager.get_user_by_sid(sid)
    dictData ={**data,'sid':sid}
    newData = SocketUser(**dictData)   
  
    if not key: 
        manager.user_sessions[str(newData.id)] = newData        
        return
    newData.sid = sid
    manager.user_sessions[key] = newData 
        
    so = SocketMessageOut(from_sid=sid,to_pc_id=newData.pc_id,data={'user':newData})
    await ChatSvc.broadcast('temper_user_on',data=so,except_sid=True)

  
#also check details of user and userlist in users api
@sio.event
async def req_users(sid):
    socketUser = []
    _,from_su =await manager.get_user_by_sid(sid)
    if not from_su:
        return    
    for user in manager.user_sessions.values():
        #if user.ip_country and user.ip_country == from_su.ip_country:
            socketUser.append(user.dict())
    print('sending user list to',from_su.pc_id)
    so = SocketMessageOut(from_sid=sid,to_sid=sid,to_pc_id=from_su.pc_id,data=socketUser)
    await ChatSvc.emit_msg_sid('req_users_resp',data=so)
    

@sio.event
async def req_sid_by_id(sid, data):
    """
    Request user information by user ID
    data: { user_id: int }
    """
    user_id = data.get("user_id")
    if not user_id:
        await ChatSvc.send_error("user_id is required", toSid=sid)
        return
    async with get_db() as db:        
        user = await user_crud.get_by_id(db=db,id=int(user_id))
        if not user:
            await ChatSvc.send_error("用户不在线", toSid=sid)
            return
    so = SocketMessageOut(from_sid=sid,to_pc_id=user_id, to_sid=sid,data={"userSid": user.sid})
    await ChatSvc.emit_msg_sid('user_sid',data=so)
    

'''
video chat
'''
@sio.event
async def call_request(sid, data):
    # data = { to: str, from: user }
    # 这里的 to 是接收方的 socket id
    to_pc = data.get("to")
    from_user = data.get("from")
    room = data.get("room", None)
    
    participants = sio.manager.rooms["/"].get(room, set())
    if len(participants) == 0 or sid not in participants:
        await ChatSvc.send_error('房间不存在或你不在房间内', toSid=sid)
        return
    print('participants:',len(participants),participants)
    
    if to_pc:
        su = get_sid_by_pc_id(to_pc)
        if not su:
            await ChatSvc.send_error("用户不在线", toSid=sid)
            return
        # 只通知目标用户，不再广播给整个房间 from_user is username
        so = SocketMessageOut(from_sid=sid, from_user=from_user,to_sid=su.sid, to_pc_id=to_pc,
                              data={"from": from_user,"room":room,"initiator":True,'msg_type':SocketMsgType.calling.value, "caller_sid": sid})
        await ChatSvc.emit_msg_sid('rtc_action',data=so)
        #await sio.emit("call_request", {"from": from_user,"initiator":True,"caller_sid": sid}, to=to_sid)


@sio.event
async def call_response(sid, data):
    # data = { accept: bool, toSid: str,room: str }
    to_sid = data.get("toSid") #caller sid
    to_pc = data.get("to_pc")
    room = data.get("room", None)
    if not to_sid:
        return
    accepted = data.get("accept", False)
    
    if accepted:     
        so= SocketMessageOut(data={"initiator": False, "peer": sid,'msg_type':SocketMsgType.call_accepted.value},to_pc_id = to_pc,from_sid=sid,to_sid=to_sid)
        await ChatSvc.emit_msg_sid('rtc_action',data=so)
    else:
        # 拒绝通话 -> 通知发起方
        so= SocketMessageOut(from_sid=sid,to_sid=to_sid,to_pc_id=to_pc,data={"by": sid,'msg_type':SocketMsgType.call_rejected.value})
        await ChatSvc.emit_msg_sid('rtc_action',data=so)

@sio.event
async def video_signal(sid, data):
    toSid = data.get("to", None)
    if(not toSid):
        print("no target sid found")
        return
    signal = data['signal']
    fromSid = sid
    so = SocketMessageOut(from_sid=sid,to_pc_id='',to_sid=toSid,data={'signal':signal,'from':fromSid,'msg_type':SocketMsgType.video_signal.value})
    await ChatSvc.emit_msg_sid('rtc_action',data=so,except_sid=True)
    #await sio.emit('video_signal', {'from': fromSid, 'signal': signal}, room=room, skip_sid=sid)
    


@sio.event
async def end_call(sid, data):     
    toSid = data.get("toSid")
    so = SocketMessageOut(from_sid=sid,to_pc_id='',data={'by':sid,'msg_type':SocketMsgType.hangup.value},to_sid=toSid)
    await ChatSvc.emit_msg_sid('rtc_action',data=so)