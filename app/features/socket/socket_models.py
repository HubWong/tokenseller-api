from pydantic import BaseModel
from typing import Optional,Generic,TypeVar, Dict, Set,Any
from datetime import datetime
from app.core.config import settings
from enum import Enum
import uuid

max_room_vip = settings.MAX_ROOM_PER_VIP_USER
max_room_user = settings.MAX_ROOM_PER_USER

class ChatRoom:
    def __init__(self, maker: str,title: Optional[str] = None,city:Optional[str]=None,
                 has_pwd:Optional[bool] = None, memo: Optional[str] = None):
        self.maker = maker
        self.participants: set[str] = set()    
        
    def join(self, sid: str):
        self.participants.add(sid)

    def leave(self, sid: str):
        self.participants.discard(sid)

    def is_empty(self) -> bool:
        return len(self.participants) == 0

    def get_participants(self) -> list[str]:
        return list(self.participants)

    @property
    def user_count(self) -> int:
        return len(self.participants)


class ChatRoomManager:
    def __init__(self):
        self.chat_rooms: Dict[str, ChatRoom] = {}  # room_name -> ChatRoom
        self.maker_rooms: Dict[str, Set[str]] = {}  # maker -> set of room names

    def _can_create_room(self, maker: str, isVip:bool) -> bool:
        c =len(self.maker_rooms.get(maker, set()))
        if isVip:
            return  c< max_room_vip
        else:
            return c<max_room_user
        
    def create_room(self, room_name: str, maker: str,role:str='user') -> bool:
        if room_name in self.chat_rooms:
            return True  # already exists

        if not self._can_create_room(maker,role=='vip'):
            return False  # limit reached

        self.chat_rooms[room_name] = ChatRoom(maker)
        self.maker_rooms.setdefault(maker, set()).add(room_name)
        return True

    def join_room(self, room_name: str, sid: str):
        if room_name in self.chat_rooms:
            self.chat_rooms[room_name].join(sid)            
        else:          
            print('\t===> no room to enter ----------')
            if self.create_room(room_name, maker=sid):
                self.chat_rooms[room_name].join(sid)
            
    def remove_sid_from_all_rooms(self, sid: str):
        for room_name, room in list(self.chat_rooms.items()):
            if sid in room.participants:
                room.leave(sid)
                if room.is_empty():
                    self._delete_room(room_name, room.maker)

    def leave_room(self, room_name: str, sid: str):
        room = self.chat_rooms.get(room_name)
        if room:
            room.leave(sid)
            if room.is_empty():
                self._delete_room(room_name, room.maker)                
          
    def get_maker_id_by_room(self,room:str)->Optional[str|None]:
        if room in self.chat_rooms:        
            return self.chat_rooms[room].maker
        return None
    
    def count_online_users(self, room_name: str) -> int:
        room = self.chat_rooms.get(room_name)
        if room:
            return room.user_count if room else 0
        return 0
    
    def _delete_room(self, room_name: str, maker: str):
        self.chat_rooms.pop(room_name, None)
        self.maker_rooms.get(maker, set()).discard(room_name)
        if not self.maker_rooms.get(maker):
            self.maker_rooms.pop(maker, None)

    def get_room_participants(self, room_name: str) -> list[str]:
        room = self.chat_rooms.get(room_name)
        return room.get_participants() if room else []
    
    # async def get_mbrs_by_room(self,room, exceptId:int):
    #     userSids = self.get_room_participants(room)
    #     if len(userSids)>0:
    #         idList= 
    #     pass
    
    def find_user_room(self, sid: str) -> str | None:
        for room_name, room in self.chat_rooms.items():
            if sid in room.participants:
                return room_name
        return None
    
    def remove_all_rooms(self):
        self.chat_rooms.clear()
        self.maker_rooms.clear()
    
    def list_rooms_sorted(
        self,
        page: int = 1,
        page_size: int = 20,
        desc: bool = True
    ) -> dict[str, Any]:
        """
        按房间人数排序并分页
        """

        rooms = [
            {
                "room_name": room_name,
                "maker": room.maker,
                "user_count": room.user_count
            }
            for room_name, room in self.chat_rooms.items()
        ]

        # 按在线人数排序
        rooms.sort(key=lambda x: x["user_count"], reverse=desc)

        total = len(rooms)
        total_pages = ceil(total / page_size) if page_size else 1

        # 分页
        start = (page - 1) * page_size
        end = start + page_size
        page_items = rooms[start:end]

        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "items": page_items
        }

room_manager = ChatRoomManager()

    
