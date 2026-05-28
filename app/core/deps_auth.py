from typing import Annotated,Optional
from app.core.deps import get_db,UserRepoDeps
from app.features.user.schemas.user_role import UserRole
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.features.user.model.user_model import User
from app.core.security import verify_token, get_subject_from_token
from app.features.user.schemas.user_schema import UserLoginResp
from app.features.user.schemas.user_schema import UserInDbWithPwd
from logging import getLogger

logger = getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"/auth/login"
)

async def get_user_by_token(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
    ) -> Optional[User]:
    try:
        user_id = verify_token(token)
        if not user_id:
            return None

        result = await db.execute(select(User).where(User.id == getattr(user_id, "id")))
        user = result.scalars().first()
        return user
    except Exception as e:
        logger.warning(f"Error in get_user_by_token: {e}")
        return None


# ✅ 3. get_current_user_with_pwd —— 已基本正确，但补充 error logging（可选）
async def get_current_user_with_pwd(
    user_crud:  UserRepoDeps,        
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> UserInDbWithPwd:
    try:
        user_id = get_subject_from_token(token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await user_crud.get_by_id(db, id=int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if getattr(user, "is_active", True) is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        return UserInDbWithPwd.model_validate(user)

    except (JWTError, ValidationError) as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ✅ 4. get_current_user —— 关键修复：commit/refresh 加 await；查询用 select；avatar 预加载？
async def get_current_user(
    user_crud:UserRepoDeps,
        
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> UserLoginResp:
    try:
        user_id = get_subject_from_token(token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await user_crud.get_by_id(db, id=int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user"
            )

        # ✅ 修复：invite_code 生成 & 异步提交
        if user.invite_code is None:
            from app.core.security import generate_invite_code
            inv = generate_invite_code(int(str(user.id)))
            setattr(user, "invite_code", inv) # 直接赋值（SQLAlchemy 2.0+ 支持）
            await db.commit()
            await db.refresh(user)  # 重新加载，确保 invite_code 生效

       
       

        return UserLoginResp.model_validate(user)

    except (JWTError, ValidationError) as e:
        logger.warning(f"Token validation failed in get_current_user: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ✅ 5. admin_required —— 必须改为 async 依赖！
#    否则 Depends(get_current_user) 会报错：can't await in sync function
async def admin_required(
    current_user: UserLoginResp = Depends(get_current_user)
) -> UserLoginResp:
    # 特殊超级管理员邮箱白名单（注意：应避免硬编码！建议用配置或 DB 角色）
    if current_user.email == "wyb6688@hotmail.com":
        return current_user

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user

TokenDep = Annotated[str, Depends(oauth2_scheme)]
DepUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(admin_required)]
