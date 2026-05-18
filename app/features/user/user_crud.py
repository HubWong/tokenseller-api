from datetime import date, datetime, timezone
from typing import Optional, List, Any, Tuple
from sqlalchemy import or_, case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload,selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from collections.abc import Sequence
from app.features.biz.user_balance.models import TransactionType
from app.features.crud_base import CRUDBase
from app.features.db_base import ApiResp
from app.core.config import settings
from app.features.user.model.user_model import User,UserRole
from app.features.user.model.user_photo import Photo
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
from app.services.tools_svc import check_port_open
from app.features.biz.apikey.apikey_crud import apikey_crud
from app.services.email_svc import smtp
from app.features.biz.user_balance.transaction_reop import TransactionRepo
from app.services.oneapi_svc import OneAPISvc


class CRUDUser(CRUDBase[User, UserCreate, UserCvUpdate]): 

    async def get_by_email(self, db: AsyncSession, *, emailOrTel: str) -> Optional[User]:
        stmt = select(User).where(User.email == emailOrTel)
        result = await db.execute(stmt)
        return result.scalars().first()
    

    async def get_by_username(self, db: AsyncSession, *, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        result = await db.execute(stmt)
        return result.scalars().first()


    async def get_invite_userId(self, db: AsyncSession, *, invite: str) -> Optional[int]:
        stmt = select(User.id).where(User.invite_code == invite)
        result = await db.execute(stmt)
        user_id = result.scalar()
        return user_id  

    async def get_parent(self,db:AsyncSession,user_id:int)->Optional[int]:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        return user.parent_id

    async def get_by_id(self, db: AsyncSession, id: int)->Optional[User]:
        stmt = select(User).where(User.id==id)
        result = await db.execute(stmt)
        return result.scalars().first()      
    

    async def get_user_details_photos(self, db: AsyncSession, uid: int) -> Optional[UserInDbPhotos]:
        '''
        query user with photos and avatars
        '''
        stmt = select(User).options(joinedload(User.photos)).where(User.id == uid)
        result = await db.execute(stmt)
        user = result.scalars().first()
        if not user:
            return None
        return UserInDbPhotos.model_validate(user)

    async def create(self,one_api_svc:OneAPISvc, transaction_repo:TransactionRepo, db: AsyncSession, *, obj_in: UserCreate) -> ApiResp[dict|bool]:
        try:
            if len(obj_in.password) < 8:
                return ApiResp(success=False, data=False, message="Password must be at least 6 characters long")
            
            existing_user = await self.get_by_email(db, emailOrTel=obj_in.email)
            if existing_user:
                return ApiResp(success=False, data=False, message="Email already registered")

            # ✅ 密码哈希
            hashed = get_password_hash(obj_in.password)        
            username = obj_in.email.split('@')[0]

            # ✅ 构建用户对象
            db_obj = User(
                email=obj_in.email,
                hashed_password=hashed,
                pc_id=obj_in.pc_id,
                memo='test',
                username = username      
            )
            # ✅ 处理邀请码
            if obj_in.invite_code:
                inviter_id = await self.get_invite_userId(db=db, invite=obj_in.invite_code)
                if inviter_id:                   
                    setattr(db_obj,'parent_id',inviter_id)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)  # ✅ 关键！确保 id 等 DB 生成字段已加载
            await transaction_repo.create_transaction(
                session=db,
                maker_id=int(getattr(db_obj,'id')),
                amount=settings.FREE_AMOUNT,
                transaction_type=TransactionType.RECHARGE_FREE
            )
            await db.commit()
            await apikey_crud.generate_api_key(db=db,user_id= int(getattr(db_obj,'id')))
            if check_port_open('localhost',3000,3):
                await one_api_svc.create_oneapi_user(username=username,pwd=obj_in.password)
            return ApiResp(success=True, data=True, message='')

        except IntegrityError as e:
            print('error:', e)
            # 可能因唯一约束（如 email 唯一）再次触发冲突（并发场景）
            await db.rollback()
            return ApiResp(success=False, data=False, message="Email already registered (concurrent request)")

        except Exception as e:
            print('error:', e)
            await db.rollback()
            # 🔒 安全建议：生产环境避免泄露具体错误，可记日志，前端返回通用消息
            import logging
            logging.error(f"User creation failed: {e}", exc_info=True)
            return ApiResp(success=False, data=False, message="Failed to create user. Please try again.")


    async def update_password(
        self, db: AsyncSession, *, db_obj: User, new_password: str
    ) -> User:
        if len(new_password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        hashed = get_password_hash(new_password)
        stmt = (
            update(User)
            .where(User.id == db_obj.id)
            .values(hashed_password=hashed, updated_at=datetime.now(timezone.utc))
        )
        await db.execute(stmt)
        await db.commit()
        return await self.get(db, id=db_obj.id)

    async def _update_user_session(self,user: User, pc_id: str):
        setattr(user, "pc_id", pc_id)
        userIndb = UserInDB.model_validate(user)
        print("\t [&*&] Updating user session for user_id:", user.id, "pc_id:", pc_id)
        
    
    
    async def update_cv(self, db: AsyncSession, *, db_obj: User, obj_in: UserCvUpdate) -> User:
        res = await super().update(db=db, db_obj=db_obj, obj_in=obj_in)
        if res:
            # 更新用户会话信息（如在 socket 连接中）           
            await self._update_user_session(res, pc_id=db_obj.pc_id)        
        return res

    async def login_user(
        self, db: AsyncSession, *, emailOrTel: str, password: str, pc_id: str
    ) -> ApiResp[Optional[TokenSchemaUser]]:
        user = await self.authenticate(db, email=emailOrTel, password=password, pc_id=pc_id)
        if not user:
            return ApiResp(success=False, message="Invalid credentials", data=None)
        if not user.is_active:
            return ApiResp(success=False, message="User is inactive", data=None)
        exp, refresh_token = create_refresh_token(user.id)        
        await token_crud.create_token(db, user_id=int(str(user.id)), token=refresh_token, expire_at=exp)
        loginResp = UserLoginResp.model_validate(user)
        user_role = getattr(user,'role',UserRole.USER).value
        tknSchUser = TokenSchemaUser(
            token= create_access_token(getattr(user,'id'),user_role),
            refresh_token=refresh_token,
            user=loginResp,
            token_type="bearer",
        )
        #await self._update_user_session(user, pc_id)        
        return ApiResp(success=True, message=str(user.id), data=tknSchUser)


    async def authenticate(
        self, db: AsyncSession, *, email: str, password: str, pc_id: str
    ) -> Optional[User]:
        try:
            user = await self.get_by_email(db, emailOrTel=email)
            if not user:
                return None
            hashed = getattr(user, "hashed_password", None)            
            if not hashed or not verify_password(password, hashed):
                return None

            updated = False
            if user.invite_code is None:
                d =  generate_invite_code(int(str(user.id)))
                setattr(user, "invite_code", d)
                updated = True
            if user.pc_id is not pc_id:
                setattr(user, "pc_id", pc_id)
                updated = True
            if updated:
                user.updated_at = datetime.now(timezone.utc) 
                db.add(user)
                await db.commit()
                await db.refresh(user)
            
            return user
        except Exception as e:
            print("Auth error:", e)
            return None


    async def user_list(
        self, db: AsyncSession, *, size: int = 10, forAdmin: bool = False,
        page: int = 1,       
        sort_by: str = "id",        # 支持排序字段：id, name, created_at
        sort_order: str = "asc",    # asc / desc
    ) -> Tuple[int, Sequence[UserForAdmin]]:
        
        """
        返回：(用户列表, 总记录数)
        """
        if page < 1:
            page = 1
        if size < 1:
            size = 10
        if size > 100:
            size = 100  # 防止滥用

        # ✅ 构造主查询（带左连接 avatar）
        # 注意：把 avatar 条件写进 JOIN ON，而非 WHERE，否则会过滤掉无 avatar 用户！
        stmt = (
            select(User, Photo)
            .join(
                Photo,
                (User.id == Photo.user_id) & (Photo.description == 'avatar'),
                isouter=True  # ← 关键！左连接
            )
        )

        # 🔁 排序
        sort_col = getattr(User, sort_by, User.id)
        if sort_order.lower() == "desc":
            stmt = stmt.order_by(sort_col.desc())
        else:
            stmt = stmt.order_by(sort_col.asc())

        # 🧮 分页：先查总数（独立 COUNT 查询，精确）
        count_stmt = select(func.count()).select_from(User)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        # 📄 分页数据：LIMIT + OFFSET
        stmt = stmt.offset((page - 1) * size).limit(size)

        # 🔍 执行查询
        result = await db.execute(stmt)
        rows = result.all()  # List[Tuple[User, Photo | None]]
        data =[]
        # 🧹 转为响应结构
        for u in rows:
            user_with_avatar = UserForAdmin.model_validate(u)            
            data.append(user_with_avatar)
        return data, total

    async def search_users(
        self,
        db: AsyncSession,
        *,
        area: str,
        keyword: str,
        gender: int = -1,
        min_age: Optional[int] = None,
        max_age: Optional[int] = None,
        page: int = 1,
        limit: int = 10,
    ) -> Tuple[int, Sequence[UserInDB]]:
        query = select(User).where(User.on_show == True)

        if gender != -1:
            query = query.where(User.gender == gender)

        today = date.today()
        if min_age is not None:
            max_birthYear = today.year - min_age
            query = query.where(User.birth_year <= max_birthYear)
        if max_age is not None:
            min_birthYear = today.year - max_age - 1
            query = query.where(User.birth_year > min_birthYear)
        if area:
            query = query.where(User.living_city == area)
            
        if keyword:
            k = f"%{keyword}%"
            query = query.where(
                or_(
                    User.username.ilike(k),
                    User.bio.ilike(k),
                    User.living_city.ilike(k),
                    User.dowry.ilike(k),
                )
            )

        # ✅ 异步总数 & 分页
        count_stmt = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_stmt) or 0
        if total>0:
            offset = (page - 1) * limit
            stmt = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
            result = await db.execute(stmt)
            users = result.scalars().all()

            return total, [UserInDB.model_validate(u) for u in users]
        return 0, []
 


    async def request_reset_pwd(self, email: str, db: AsyncSession) -> ApiResp:
        user = await self.get_by_email(db, emailOrTel=email)  
        if not user:
            return ApiResp(success=False, message="User not found")

        try:
            reset_token = smtp.create_reset_token(email)
            setattr(user, "reset_pwd_token", reset_token)
            setattr(user, "updated_at", datetime.now(timezone.utc))
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return await smtp.send_email_async(to=email, token=reset_token)
        except Exception as e:
            await db.rollback()
            return ApiResp(success=False, message=str(e))

    async def get_by_pc_Id(self, db: AsyncSession, pcId: str) -> Optional[User]:
        stmt = select(User).where(User.pc_id == pcId)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def down_cv(self, db: AsyncSession, uid: int) -> bool:
        user = await self.get(db, id=uid)
        if user:
            setattr(user,'on_show',False)
            user.updated_at = datetime.now(timezone.utc)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return True
        return False


    async def lost_pwd_reset(self, newPwdModel: LostPasswordReset, db: AsyncSession):
        token = newPwdModel.token
        new_pwd = newPwdModel.newPassword
        email = smtp.get_mail_exp(
            token=token
        )
        if not email:
            return ApiResp(success=False, message="Token invalid or expired")

        user = await self.get_by_email(db, emailOrTel=email)
        if not user or user.reset_pwd_token != token:
            return ApiResp(success=False, message="Invalid token")
        pwd = get_password_hash(new_pwd)
        setattr(user, "hashed_password", pwd)
        setattr(user, "reset_pwd_token", None)
        user.updated_at = datetime.now(timezone.utc)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return ApiResp(success=True, message="Password reset successfully")


    async def admin_update_user(
        self, db: AsyncSession, *, db_obj: User, obj_in: AdminUserUpdate
    ) -> User:
        updated = False
        if obj_in.role is not None and db_obj.role is not obj_in.role:
            setattr(db_obj, "role", obj_in.role)
            updated = True
        if obj_in.is_active is not None and db_obj.is_active is not obj_in.is_active:
            setattr(db_obj, "is_active", obj_in.is_active)  
            updated = True
        if updated:
            db_obj.updated_at = datetime.now(timezone.utc)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
        return db_obj


user_crud = CRUDUser(User)


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