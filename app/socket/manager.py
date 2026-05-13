from app.features.user.schemas.user_schema import UserInDB, UserInDbPhotos,SocketUser
from typing import Dict, Any,  Optional, List
from app.features.socket.socket_models import room_manager


class ConnManager():
    def __init__(self):
        self.user_sessions: Dict[str, SocketUser] = {}  # user_id -> list of sid

    async def connect(self, id: str, su: SocketUser):
        userItem = self.get_by_pc_id(pcid=su.pc_id)
        if userItem and userItem.sid != su.sid:
            # 如果 pc_id 已存在且 sid 不同，说明是重复连接，拒绝新的连接
            userItem.sid = su.sid  # 更新为新的 sid  
            print(f"reconnected****Updated existing user with pc_id {su.pc_id} to new sid {su.sid}")
            return
        self.user_sessions[str(id)] = su

    def get_by_pc_id(self, pcid: str) -> Optional[SocketUser]:
        for id, user in self.user_sessions.items():
            if user.pc_id == pcid:
                return user
        return None
    
    async def disconnect(self, sid: str):
        id,su =await self.get_user_by_sid(sid=sid)
        if id:
            del self.user_sessions[str(id)]
            print('user disconnected,',id, sid)

    
    async def get_user_by_sids(self,sids:List[str]):
        sus=[]
        for sid in sids:
            _,su = await self.get_user_by_sid(sid)
            sus.append(su)
        return sus
            
    async def get_user_by_sid(self, sid: str) -> (tuple[str, SocketUser] | tuple[None, None]):
        for id, user in self.user_sessions.items():
            if user.sid == sid:
                return id, user
        return None, None
    
    
    async def get_mbrs_detail_by_room(self, room,exceptId):
        sids = room_manager.get_room_participants(room_name=room)
        sids.remove(exceptId)
        if len(sids)>0:
            mbrs = await self.get_user_by_sids(sids)
            return mbrs
        return None  
            
            
    async def attach_user_sid(self,user: UserInDbPhotos) :
        if user and user.id:
            for k,u in self.user_sessions.items():
                if u.id == user.id:
                    user.sid = u.sid
                    break
                
    async def reconnect(self, user_id: str, old_sid: str, new_sid: str):
        if user_id in self.user_sessions:
            if old_sid in self.user_sessions.values():
                self.user_sessions[user_id].remove(old_sid)
            self.user_sessions[user_id].append(new_sid)
        else:
            self.user_sessions[user_id] = [new_sid]
            
    def is_user_online(self, user_id: str) -> bool:
        return user_id in self.user_sessions and len(self.user_sessions[user_id]) > 0
    

    def check_isOnline_by_id(self,userid: int) -> Optional[str]:
        for _,u in self.user_sessions.items():
            if u.id == userid:
                return u.sid
        return None
    
    async def check_users_online(self,users: List[UserInDB]) -> List[UserInDB]:
        """
        Check if users are online based on their pc_id
        """
        
        for user in users:
            if user.id in self.user_sessions:
                print('Checking user online status for:', user.username,True)            
                user.sid = self.user_sessions[user.id].sid
            else:
                print('Checking user not online status for:', user.username)            
                user.sid = None
        return users
    
manager = ConnManager()