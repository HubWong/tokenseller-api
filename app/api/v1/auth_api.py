from datetime import datetime,timezone
from typing import Any,Optional
from fastapi import APIRouter, Body, Depends,  status
from sqlalchemy.ext.asyncio import AsyncSession
from app.socket.manager import manager
from app.features.db_base import ApiResp
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,    
    get_subject_from_token
)
from app.core.database import get_db
from app.features.user.user_crud import user_crud
from app.core.database import get_db
from app.features.user.model.user_model import User
from app.core.deps import get_current_user, get_current_user_with_pwd, get_oneapi_svc, get_transaction_rep
from app.features.user.photo_crud import photo_crud
from app.features.user.schemas.token_schema import (
    PasswordResetRequest,
    TokenSchema,  
    TokenSchemaUser, 
    PasswordChange,
    LostPasswordReset
)
from app.features.user.schemas.user_schema import UserLoginResp,UpdateUsername, UserCreate, UserInDB,UserCvUpdate,UserAvatarOut
from app.core.security import CustomOAuth2Form
from app.features.user.token_crud import token_crud
from app.features.biz.usage.token_usage_repo import TokenUsageRepo
from app.features.biz.user_balance.transaction_reop import TransactionRepo
from app.services.oneapi_svc import OneAPISvc

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register")
async def register(
    *,
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),    
    one_api_svc:OneAPISvc= Depends(get_oneapi_svc),
    transaction_repo :TransactionRepo= Depends(get_transaction_rep)
) :
    """
    Register new user.
    """
    resp=await user_crud.create(db=db,one_api_svc=one_api_svc,transaction_repo=transaction_repo, obj_in=user_in)   
    
    return resp


@router.post("/login", response_model=ApiResp[Optional[TokenSchemaUser]])
async def login(
    db: AsyncSession = Depends(get_db),
    form_data: CustomOAuth2Form = Depends()
) -> ApiResp[Optional[TokenSchemaUser]]:
    """
    OAuth2 compatible token login.
    """   
    tknSu = await user_crud.login_user(db=db, 
                                       emailOrTel=form_data.username,
                                       password=form_data.password,
                                       pc_id=form_data.pc_id)  
    if not tknSu.success:
        return ApiResp(success=False,message=tknSu.message,data=None)   
    return tknSu
    

@router.post("/refresh-token", response_model=ApiResp[Optional[TokenSchema]])
async def refresh_token(
    db: AsyncSession = Depends(get_db),
    refresh_token: str = Body(...),
):
    """
    Refresh access token.
    """
    user_id = get_subject_from_token(refresh_token)
    if not user_id:
        return ApiResp(success=False,message="Invalid refresh token",data=None)
    
    user =await user_crud.get(db, id=int(user_id))
    if not user:
        return ApiResp(success=False,message="User not found",data=None)
    elif not getattr(user, "is_active", True):
        return ApiResp(success=False,message="Inactive user",data=None)

    uid = getattr(user, "id")
    tknSchm = TokenSchema(
        token= create_access_token(uid),
        refresh_token=create_refresh_token(uid)[1],
        token_type="bearer"
    )
    return ApiResp(success=True,data=tknSchm,message="")

@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    req: PasswordResetRequest, db: AsyncSession = Depends(get_db)
) -> ApiResp:
    """
    请求密码重置 ,by send email

    Args:
        req: 密码重置请求
        db: 数据库会话

    Returns:
        API响应
    """
    return await user_crud.request_reset_pwd(req.email, db=db)


@router.post("/newpwd",response_model=ApiResp)
async def change_password(password_data: PasswordChange,    
                          db: AsyncSession = Depends(get_db),
                          current_user = Depends(get_current_user_with_pwd)): 
    if not verify_password(password_data.old_password, str(current_user.hashed_password)):
        return ApiResp(success=False,message="旧密码不正确",data=None)    
    await user_crud.update_password(db, db_obj=current_user, new_password=password_data.new_password)    
    return ApiResp(success=True,message="",data=None)


@router.post("/pwd_lost_reset")
async def pwd_lost_reset(
    *,
    db: AsyncSession = Depends(get_db),    
    lostPwdReset: LostPasswordReset,
) -> Any:
    """
    Change password.
    """
    if not lostPwdReset.token:
        return ApiResp(success=False,message="not validated.")
    res = await user_crud.lost_pwd_reset(newPwdModel=lostPwdReset,db=db)  
    return res

@router.post('/logout', response_model=ApiResp[Optional[bool]])
async def logout(
    db: AsyncSession = Depends(get_db),
    current_user: UserLoginResp = Depends(get_current_user)
) -> ApiResp[Optional[bool]]:
    """
    Logout user by deleting the refresh token.
    """    
    userId = current_user.id
    await manager.logout_user(uid=int(str(userId)))                       
    return await token_crud.logout_delete_token(db, uid=userId)

@router.get("/me")
def get_my_profile(
    current_user: UserInDB = Depends(get_current_user),
) -> ApiResp[Optional[UserInDB]]:
    """
    Get current user information.
    """   
    res = ApiResp(success=True, data=current_user, message="User fetched successfully")
    return res


@router.put('/update_username/{id}')
async def update_user(id:int,username:UpdateUsername,db:AsyncSession=Depends(get_db)):
    return await user_crud.update_username(db=db,uid=id, username=username.username)

@router.get("/my_avatar")
async def get_current_user_avatar(
    *,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
) -> ApiResp[Optional[str]]:
    return await photo_crud.get_avatar_base64(db=db, user=current_user)

@router.put('/me_avatar') #update user avatar only
async def update_current_user_avatar(
    *,
    db: AsyncSession = Depends(get_db),
    avatar_url: str = Body(..., embed=True),
    current_user = Depends(get_current_user),
) -> ApiResp[Any]:
    """
    Update current user's avatar.
    """   
    res = await photo_crud.update_avatar(db=db, user=current_user, avatar_url=avatar_url)                                                            
    if not res:
        return ApiResp(success=False, message="Failed to update avatar", data=None)                             
    return ApiResp(success=True, data=res, message="Avatar updated successfully")


@router.put("/me") #update user without avatar ,avatar moves to another api of photo 
async def update_profile(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCvUpdate,    
    current_user :User = Depends(get_current_user),
) -> ApiResp[Optional[UserLoginResp]]:
    """
    Update current user information.
    """   
    if not current_user:
        return ApiResp(success=False, message="User not found", data=None)
    current_user.updated_at = datetime.now(timezone.utc)
    #res = await user_crud.update(db=db, db_obj= current_user, obj_in=user_in)   
    res = await user_crud.update_cv(db=db, db_obj=current_user, obj_in=user_in) #更新简历信息                                                         
    if not res:
        return ApiResp(success=False, message="Failed to update profile", data=None)  
    result = UserLoginResp.model_validate(res)                         
    return ApiResp(success=True, data=result, message="Profile updated successfully")