# generate api for authenticating softwares downloaded from the web

# -*- coding: utf-8 -*-
import uuid
from fastapi import APIRouter, Depends
from app.core.deps import get_db,CurrentUser, get_apikey_crud
from sqlalchemy.ext.asyncio import AsyncSession
from app.features.user.model.user_model import User
from app.core.deps import get_apikey_crud, get_current_user
from app.features.biz.apikey.apikey_crud import CRUDApiKey
 
router = APIRouter(prefix="/apikey", tags=["apikey"])


@router.post("/create")
async def create_key_api(api_key: dict, user: CurrentUser, crud:CRUDApiKey= Depends(get_apikey_crud), db: AsyncSession = Depends(get_db)):
    role = user.role
    api_key = await crud.generate_api_key(db, user.id, api_key.get("name"),tier=role)

    return {"api_key": api_key}


@router.get("/")
async def get_user_apikeys(
    user: CurrentUser,
    crud:CRUDApiKey=Depends(get_apikey_crud), db: AsyncSession = Depends(get_db)
):
    return await crud.get_keys(db=db, user_id=getattr(user, "id"))


@router.delete("/delete/{key_id}")
async def delete_apikey(
    key_id: str,
    user: CurrentUser,
    crud:CRUDApiKey=Depends(get_apikey_crud), db: AsyncSession = Depends(get_db)
):
    await crud.delete_key(db=db, key_id=key_id, user_id=getattr(user, "id"))
    return {"detail": "API key deleted successfully"}