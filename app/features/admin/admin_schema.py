
# !/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional
from pydantic import BaseModel, field_serializer,EmailStr
 

class AdminConsoleData(BaseModel):
    total_countries: int
    total_users: int
    stats: list[dict]
    role_vip_count: int
    role_user_count: int
    

class AdminUserUpdate(BaseModel):   
    is_active: Optional[bool] = None
    role: Optional[str] = None

class AdminUserOut(BaseModel):  
    id: int
    model_config = {"from_attributes": True}