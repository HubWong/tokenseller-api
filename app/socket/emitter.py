from app.features.socket.schema import SocketMessageOut

# Lazy import to avoid circular import
def get_sio():
    from app.socket.socket_server import sio
    return sio

class ChatSvc:   
    @staticmethod
    async def send_error(msg:str, toSid):   
        sio = get_sio()
        data = SocketMessageOut(data=msg,from_sid=toSid,to_sid=toSid)
        await sio.emit('error_msg',data= data.model_dump(), to=toSid)
        
    @staticmethod
    async def emit_msg_sid(event: str, data: SocketMessageOut,except_sid:bool = False):
        sio = get_sio()
        if except_sid:
            await sio.emit(event, data.model_dump(), to=data.to_sid,skip_sid=data.from_sid)
            return
        await sio.emit(event, data.model_dump(), to=data.to_sid)
    
    @staticmethod
    async def emit_event_msg(data:SocketMessageOut,except_sid:bool= False):
        '''
        p2p / p2room message
        '''
        return await ChatSvc.emit_msg_sid("message",data=data,except_sid=except_sid)
    
    @staticmethod
    async def emit_event_notify(data:SocketMessageOut,except_sid:bool= False):
        return await ChatSvc.emit_msg_sid("notify",data=data,except_sid=except_sid)
    
    @staticmethod 
    async def broadcast_sids(event: str, data: SocketMessageOut):        
        sio = get_sio()     
        for sid in data.to_sids:
            await sio.emit(event, data.model_dump(), to=sid)
            
    @staticmethod 
    async def broadcast_room(event: str, data: SocketMessageOut,skip_sid:bool=True):        
        sio = get_sio()     
        if not data.to_room:
            print('no room data found.')
            return        
        if skip_sid:            
            await sio.emit(event, data.model_dump(), room=data.to_room,skip_sid=data.from_sid)
            return
        await sio.emit(event, data.model_dump(), room=data.to_room)
           
           
    @staticmethod
    async def broadcast(event: str, data: SocketMessageOut,except_sid:bool=False):
        sio = get_sio()
        if except_sid:
            await sio.emit(event, data.model_dump(), skip_sid=data.from_sid)  
            return
        await sio.emit(event, data.model_dump())                
       
   