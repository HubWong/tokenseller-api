# generate api for authenticating softwares downloaded from the web

# -*- coding: utf-8 -*-
import uuid
from fastapi import APIRouter, Depends
from app.core.deps import DbSessionDeps, get_apikey_crud
from app.core.deps_auth import DepUser
from app.core.deps import get_apikey_crud
from app.features.biz.apikey.apikey_crud import CRUDApiKey
 
router = APIRouter(prefix="/apikey", tags=["apikey"])


@router.post("/create")
async def create_key_api(api_key: dict[str,str], user: DepUser, db: DbSessionDeps, crud:CRUDApiKey= Depends(get_apikey_crud)):
    role = user.role
    t = api_key.get('name')
    k = await crud.generate_api_key(db=db, user_id=int(getattr(user,'id')), key_title=str(t),tier=str(role))
    return {"api_key": k}


@router.get("/")
async def get_user_apikeys(
    user: DepUser, db: DbSessionDeps,
    crud:CRUDApiKey=Depends(get_apikey_crud)
):
    return await crud.get_keys(db=db, user_id=getattr(user, "id"))


@router.delete("/delete/{key_id}")
async def delete_apikey(
    key_id: str,
    user: DepUser, db: DbSessionDeps,
    crud:CRUDApiKey=Depends(get_apikey_crud)
):
    await crud.delete_key(db=db, key_id=key_id, user_id=getattr(user, "id"))
    return {"detail": "API key deleted successfully"}