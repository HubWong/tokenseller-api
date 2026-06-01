from datetime import date, datetime, timezone
from typing import Optional,Tuple,Any
from sqlalchemy import or_, case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from collections.abc import Sequence
from app.features.biz.user_balance.models import TransactionType
from app.features.db_base import ApiResp
from app.core.config import settings
from app.features.user.model.user_model import User,UserRole
from app.features.user.token_crud import token_crud
from app.features.admin.admin_schema import AdminUserUpdate, AdminConsoleData
from app.features.user.schemas.token_schema import LostPasswordReset, TokenSchemaUser
from app.features.user.schemas.user_schema import UserLoginResp, UserCreate, UserInDB, UserCvUpdate, UserInDbPhotos,UserForAdmin
from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_invite_code,
    get_password_hash,    
    verify_password    
)
from app.services.tools_svc import check_api_reachable
from app.features.biz.apikey.apikey_crud import apikey_crud
from app.services.email_svc import smtp
from app.services.oneapi_svc import OneApiSvc

import logging
from datetime import datetime, timezone
from typing import Optional, Sequence, Tuple
from sqlalchemy import select, update, func, or_
from sqlalchemy.exc import IntegrityError
# 其他依赖请按需保留

class UserRepo: 
    async def update_username(self, uid:int, username:str,db:AsyncSession):
        user = await self.get_by_id(db=db,id=uid)
        if user:
            setattr(user, 'username', username)
            await db.commit()
            await db.refresh(user)
            return True
        return False

  
    async def get_by_email(self, db: AsyncSession, *, emailOrTel: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == emailOrTel))
        return result.scalars().first()
        
    async def get_by_username(self, db: AsyncSession, *, username: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalars().first()

    async def get_invite_userId(self, db: AsyncSession, *, invite: str) -> Optional[int]:
        result = await db.execute(select(User.id).where(User.invite_code == invite))
        return result.scalar_one_or_none()  # ✅ 防无结果/多结果报错

    async def get_parent(self, db: AsyncSession, user_id: int) -> Optional[int]:
        result = await db.execute(select(User.parent_id).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, db: AsyncSession, id: int) -> Optional[User]:
        result = await db.execute(select(User).where(User.id == id))
        return result.scalars().first()      

    async def create(self, one_api_svc: OneApiSvc, transaction_repo: Any, db: AsyncSession, *, obj_in: UserCreate) -> ApiResp[dict|bool]:
        try:
            if len(obj_in.password) < 8:
                return ApiResp(success=False, data=False, message="Password must be at least 8 characters long")
            
            if await self.get_by_email(db, emailOrTel=obj_in.email):
                return ApiResp(success=False, data=False, message="Email already registered")

            db_obj = User(
                email=obj_in.email,
                hashed_password=get_password_hash(obj_in.password),
                pc_id=obj_in.pc_id,
                memo='test',
                username=obj_in.email.split('@')[0]
            )
            if obj_in.invite_code:
                inviter_id = await self.get_invite_userId(db=db, invite=obj_in.invite_code)
                if inviter_id:  
                    setattr(db_obj, 'parent_id', inviter_id)                 
                    
            db.add(db_obj)
            await db.flush()  # ✅ 使用 flush 获取 id，避免重复 commit
            await transaction_repo.create_transaction(
                session=db, maker_id=db_obj.id, amount=settings.FREE_AMOUNT, transaction_type=TransactionType.RECHARGE_FREE
            )
            await db.flush()
            uid = setattr(db_obj, 'id', db_obj.id)
            await apikey_crud.generate_api_key(db=db, user_id=int(uid))
            
            if check_api_reachable(settings.ONEAPI_URL, 3):
                await one_api_svc.create_oneapi_user(username=db_obj.username, pwd=obj_in.password, access_token=settings.ONEAPI_ACCESS_TOKEN)
                
            await db.commit()
            await db.refresh(db_obj) 
            return ApiResp(success=True, data=True, message='')

        except IntegrityError as e:
            await db.rollback()
            logging.error(f"User creation IntegrityError: {e}")
            return ApiResp(success=False, data=False, message="Email already registered (concurrent request)")
        except Exception as e:
            await db.rollback()
            logging.error(f"User creation failed: {e}", exc_info=True)
            return ApiResp(success=False, data=False, message="Failed to create user. Please try again.")

    async def update_password(self, db: AsyncSession, *, db_obj: User, new_password: str) -> User:
        if len(new_password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        stmt = update(User).where(User.id == db_obj.id).values(
            hashed_password=get_password_hash(new_password), updated_at=datetime.now(timezone.utc)
        )
        await db.execute(stmt)
        await db.commit()
        return await self.get(db, id=db_obj.id)  # 假设基类已实现 get

    async def _update_user_session(self, user: User, pc_id: str):
        user.pc_id = pc_id
        logging.info(f"Updating user session for user_id: {user.id}, pc_id: {pc_id}")
        
    

    async def login_user(self, db: AsyncSession, *, emailOrTel: str, password: str, pc_id: str) -> ApiResp[Optional[TokenSchemaUser]]:
        user = await self.authenticate(db, email=emailOrTel, password=password, pc_id=pc_id)
        if not user: return ApiResp(success=False, message="Invalid credentials", data=None)
        if not user.is_active: return ApiResp(success=False, message="User is inactive", data=None)
        
        exp, refresh_token = create_refresh_token(user.id)        
        await token_crud.create_token(db, user_id=user.id, token=refresh_token, expire_at=exp)
        
        tknSchUser = TokenSchemaUser(
            token=create_access_token(user.id, getattr(user, 'role', UserRole.USER.value)),
            refresh_token=refresh_token,
            user=UserLoginResp.model_validate(user),
            token_type="bearer",
        )
        return ApiResp(success=True, message=str(user.id), data=tknSchUser)

    async def authenticate(self, db: AsyncSession, *, email: str, password: str, pc_id: str) -> Optional[User]:
        try:
            user = await self.get_by_email(db, emailOrTel=email)
            if not user: return None
            
            hashed = getattr(user, "hashed_password", None)            
            if not hashed or not verify_password(password, hashed): return None

            updated = False
            if user.invite_code is None:
                user.invite_code = generate_invite_code(user.id)
                updated = True
            if user.pc_id != pc_id:  # ✅ 修复：值比较用 !=
                user.pc_id = pc_id
                updated = True
                
            if updated:
                user.updated_at = datetime.now(timezone.utc) 
                await db.commit()
                await db.refresh(user)
            return user
        except Exception as e:
            logging.error(f"Auth error: {e}")
            return None

    async def user_list(self, db: AsyncSession, *, size: int = 10, for_admin: bool = False, page: int = 1, sort_by: str = "id", sort_order: str = "asc") -> Tuple[Sequence[UserForAdmin], int]:
        page = max(page, 1)
        size = max(min(size, 100), 1)
        valid_sort_fields = {"id": User.id, "name": User.username, "created_at": User.created_at}
        sort_column = valid_sort_fields.get(sort_by, User.id)
        sort_expr = sort_column.asc() if sort_order == "asc" else sort_column.desc()

        base_q = select(User).where(User.is_active.is_(True))
        if not for_admin: base_q = base_q.where(User.role == UserRole.USER.value)
        
        # ✅ 修复：安全计数查询
        total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar_one() or 0
        if total == 0: return [], 0

        result = await db.execute(base_q.order_by(sort_expr).offset((page - 1) * size).limit(size))
        return [UserForAdmin.model_validate(u) for u in result.scalars().all()], total

    async def search_users(self, db: AsyncSession, *, area: str, keyword: str, gender: int = -1, min_age: Optional[int] = None, max_age: Optional[int] = None, page: int = 1, limit: int = 10) -> Tuple[int, Sequence[UserInDB]]:
        q = select(User).where(User.on_show.is_(True))
        if gender != -1: q = q.where(User.gender == gender)
        today = datetime.now(timezone.utc).date()
        if min_age is not None: q = q.where(User.birth_year <= today.year - min_age)
        if max_age is not None: q = q.where(User.birth_year > today.year - max_age - 1)
        if area: q = q.where(User.living_city == area)
        if keyword:
            k = f"%{keyword}%"
            q = q.where(or_(User.username.ilike(k), User.bio.ilike(k), User.living_city.ilike(k), User.dowry.ilike(k)))

        total = await db.scalar(select(func.count()).select_from(q.subquery())) or 0
        if not total: return 0, []
        
        result = await db.execute(q.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit))
        return total, [UserInDB.model_validate(u) for u in result.scalars().all()]

    async def request_reset_pwd(self, email: str, db: AsyncSession) -> ApiResp:
        user = await self.get_by_email(db, emailOrTel=email)  
        if not user: return ApiResp(success=False, message="User not found")
        try:
            user.reset_pwd_token = smtp.create_reset_token(email)
            user.updated_at = datetime.now(timezone.utc)
            await db.commit()
            return await smtp.send_email_async(to=email, token=user.reset_pwd_token)
        except Exception as e:
            await db.rollback()
            return ApiResp(success=False, message=str(e))

    async def get_by_pc_Id(self, db: AsyncSession, pcId: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.pc_id == pcId))
        return result.scalars().first()

    async def down_cv(self, db: AsyncSession, uid: int) -> bool:
        user = await self.get_by_id(db, id=uid)
        if user:
            user.on_show = False
            user.updated_at = datetime.now(timezone.utc)
            await db.commit()
            return True
        return False

    async def lost_pwd_reset(self, newPwdModel: LostPasswordReset, db: AsyncSession):
        email = smtp.get_mail_exp(token=newPwdModel.token)
        if not email: return ApiResp(success=False, message="Token invalid or expired")

        user = await self.get_by_email(db, emailOrTel=email)
        if not user or user.reset_pwd_token != newPwdModel.token:  # ✅ 修复：先判空再取值
            return ApiResp(success=False, message="Invalid token")
            
        user.hashed_password = get_password_hash(newPwdModel.newPassword)
        user.reset_pwd_token = None
        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return ApiResp(success=True, message="Password reset successfully")

    async def admin_update_user(self, db: AsyncSession, *, db_obj: User, obj_in: AdminUserUpdate) -> User:
        updated = False
        if obj_in.role is not None and db_obj.role != obj_in.role:  # ✅ 修复：值比较
            db_obj.role = obj_in.role; updated = True
        if obj_in.is_active is not None and db_obj.is_active != obj_in.is_active:  # ✅ 修复：值比较
            db_obj.is_active = obj_in.is_active; updated = True
            
        if updated:
            db_obj.updated_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(db_obj)
        return db_obj



# ✅ 异步版 get_user_count_by_country
async def get_user_count_by_country(db: AsyncSession):
    stmt = (
        select(User.ip_country, func.count(User.id).label("user_count"))
        .where(User.ip_country.isnot(None))
        .group_by(User.ip_country)
    )
    result = await db.execute(stmt)
    rows = result.all()

    stats = [
        {"id": idx + 1, "ip_country": r.ip_country, "user_count": r.user_count}
        for idx, r in enumerate(rows)
    ]
    total_countries = len(rows)
    total_users = sum(r.user_count for r in rows)
    return {
        "stats": stats,
        "total_countries": total_countries,
        "total_users": total_users,
    }


# ✅ get_role_user_data（已修正）
async def _get_role_user_data(db: AsyncSession) -> Tuple[int, int]:
    stmt = select(
        func.coalesce(func.sum(case((User.role == UserRole.VIP, 1), else_=0)), 0).label("vip_count"),
        func.coalesce(func.sum(case((User.role == UserRole.USER, 1), else_=0)), 0).label("user_count"),
    )
    result = await db.execute(stmt)
    row = result.first()
     # ✅ 安全处理：即使 row 为 None，也返回 (0, 0)
    if row is None:
        return 0, 0
    return int(row.vip_count), int(row.user_count)


# ✅ admin get_console_datas（全面异步）
async def get_console_datas(db: AsyncSession) -> ApiResp[AdminConsoleData]:
    try:
        # ✅ 全部 await
        user_stats = await get_user_count_by_country(db)
        vip_sum, user_sum = await _get_role_user_data(db)

        console_data = AdminConsoleData(
            total_countries=user_stats["total_countries"],
            total_users=user_stats["total_users"],
            stats=user_stats["stats"],
            role_vip_count=int(str(vip_sum)),
            role_user_count=int(str(user_sum)),
        )
        return ApiResp(success=True, data=console_data)
    except Exception as e:
        return ApiResp(success=False, message=f"Console data error: {str(e)}")