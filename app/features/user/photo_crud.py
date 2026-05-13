from typing import List, Optional
from datetime import datetime, timezone
from collections.abc import Sequence
from app.core.config import settings
from fastapi import UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from collections.abc import Sequence
from sqlalchemy.future import select
from sqlalchemy import and_, or_

from app.features.crud_base import CRUDBase
from app.features.db_base import ApiResp
from app.features.user.model.user_photo import Photo
from app.features.user.model.user_model import User
from app.features.user.user_crud import user_crud

from app.features.user.schemas.photo_schema import PhotoCreate, PhotoUploadResp, UserPhoto
from app.services.file_svc import upload_and_resize_image, delete_image_by_public_id
from urllib.parse import unquote


class CRUDphoto(CRUDBase[Photo, PhotoCreate, PhotoCreate]):
    
    async def get_by_id(self, db: AsyncSession, photo_id: int) -> Optional[Photo]:
        result = await db.execute(select(Photo).where(Photo.id == photo_id))
        return result.scalars().first()

    async def update_privacy(self, db: AsyncSession, photo_id: int, user_id: int) -> Optional[Photo]:
        result = await db.execute(
            select(self.model).where(
                (self.model.id == photo_id) &
                (self.model.user_id == user_id)
            )
        )
        photo: Optional[Photo] = result.scalars().first()
        if not photo:
            return None

        # 切换隐私状态
        photo.is_private = not photo.is_private
        db.add(photo)
        await db.commit()
        await db.refresh(photo)
        return photo

    async def get_user_photos(
        self,
        db: AsyncSession,
        *,
        user_id: int
    ) -> Optional[Sequence[UserPhoto]]:
        result = await db.execute(
            select(self.model).where(
            and_(
                self.model.user_id == user_id,
                 or_(
                self.model.description.is_(None),          # ← 匹配 NULL
                self.model.description != 'avatar'
            )
            ))
        )
        photos = result.scalars().all()
        if not photos:
            return None
        return [UserPhoto.model_validate(p) for p in photos]

    
    async def get_avatar_base64(self, db: AsyncSession, *, user: User) -> ApiResp[Optional[str]]:
        result = await db.execute(
            select(self.model).where(
                (self.model.user_id == int(str(user.id))) &
                (self.model.description == 'avatar')
            )
        )
        photo: Optional[Photo] = result.scalars().first()
        if not photo or not photo.url:
            return ApiResp(success=True, data=None, message="No avatar found")

        # 假设 url 存储的是 base64 编码的字符串
        return ApiResp(success=True, data=photo.url, message="Avatar fetched successfully")
    
    async def update_avatar(self, db: AsyncSession, *, user: User, avatar_url: str) -> Optional[UserPhoto]:
            # 更新或创建头像记录
            result = await db.execute(
                select(self.model).where(
                    (self.model.user_id == int(str(user.id))) &
                    (self.model.description == 'avatar')
                )
            )
            photo: Optional[Photo] = result.scalars().first()
    
            if photo:
                # 更新已有头像
                photo.url = avatar_url
                photo.updated_at = datetime.now(timezone.utc)
                db.add(photo)
                await db.commit()
                await db.refresh(photo)
            else:
                # 创建新头像记录
                photo_create = PhotoCreate(
                    url=avatar_url,
                    user_id=int(str(user.id)),
                    description='avatar'
                )
                photo = await self.create_with_user(db=db, obj_in=photo_create)
                if not photo:
                    return None
            photoOut = UserPhoto.model_validate(photo)
            return photoOut
    
    async def add_or_update_avatar(self, db: AsyncSession, file: UploadFile, user: User) -> ApiResp[str]:
        # 异步获取用户（user_crud 也需支持 async）
        db_user: Optional[User] = await user_crud.get_by_email(db=db, emailOrTel=str(user.email))
        print('prv_avatar:', db_user.avatar if db_user else "User not found")

        if not db_user:
            return ApiResp(success=False, data=None, message="用户不存在或已被删除")

        # 删除旧头像
        if db_user.avatar_cloudinary_pub_id:
            delete_image_by_public_id(str(db_user.avatar_cloudinary_pub_id))

        # 上传新头像
        upload_response: ApiResp[Optional[PhotoUploadResp]] = await upload_and_resize_image(
            file, folder=str(user.email), isThumbnail=True
        )
        if not upload_response.success or not upload_response.data:
            return ApiResp(success=False, data=None, message="上传失败")

        resp = upload_response.data
        imgUrl = unquote(resp.url.strip()) if resp.url else ""

        # 更新用户
        db_user.updated_at = datetime.now(timezone.utc)
        setattr(db_user, 'avatar', imgUrl)
        setattr(db_user, 'avatar_cloudinary_pub_id', str(resp.public_id))

        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)

        print('new_avatar:', db_user.avatar)
        return ApiResp(success=True, data=imgUrl, message="头像更新成功")

    async def create(
        self,
        db: AsyncSession,
        file: UploadFile,
        user: User
    ) -> ApiResp[UserPhoto]:
        uid = user.id

        # 检查配额
        countImages = await self.count_user_photos(db=db, user_id=int(str(uid)))
        if countImages >= settings.MAX_PHOTO_COUNT:
            return ApiResp(success=False, data=None, message="用户已达到上传图片数量上限")

        # 上传
        foldername = str(user.email)
        upload_response = await upload_and_resize_image(file, folder=foldername)
        if not upload_response.success or not upload_response.data:
            return ApiResp(success=False, data=None, message="上传失败")

        data = upload_response.data
        imgUrl = data.url.strip() if data.url else ""
        pubId = data.public_id.strip() if data.public_id else ""

        # 构造 create schema
        photo_create = PhotoCreate(
            url=imgUrl,
            user_id=int(str(uid)),
            cloudinary_pub_id=pubId,
        )

        # 创建 DB 记录（使用 async create_with_user）
        db_obj = await self.create_with_user(db=db, obj_in=photo_create)
        if not db_obj:
            return ApiResp(success=False, data=None, message="创建图片记录失败")

        return ApiResp(success=True, data=db_obj, message="图片上传成功")

    async def create_with_user(
        self,
        db: AsyncSession,
        *,
        obj_in: PhotoCreate
    ) -> Optional[UserPhoto]:
        try:
            obj_in_data = jsonable_encoder(obj_in)
            db_obj = self.model(**obj_in_data)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return UserPhoto.model_validate(db_obj)
        except Exception as e:
            print(f"Error creating photo: {e}")
            await db.rollback()
            return None

    async def get_all_photos(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> Sequence[Photo]:
        result = await db.execute(
            select(self.model)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def delete_by_admin(self, db: AsyncSession, *, photo_id: int) -> ApiResp[bool]:
        result = await db.execute(select(self.model).where(self.model.id == photo_id))
        photo: Optional[Photo] = result.scalars().first()
        if not photo:
            return ApiResp(success=True, data=True, message="Photo not found (treated as success)")

        photo.valid = False
        db.add(photo)
        await db.commit()
        await db.refresh(photo)

        # 异步删除云存储
        deletion_result = delete_image_by_public_id(str(photo.cloudinary_pub_id))
        return ApiResp[bool](success=True, data=bool(deletion_result.data), message="Photo invalidated and image deleted if possible")

    async def delete_photo(
        self,
        db: AsyncSession,
        *,
        photo_id: int
    ) -> tuple[bool, Optional[Photo]]:
        result = await db.execute(select(self.model).where(self.model.id == photo_id))
        photo: Optional[Photo] = result.scalars().first()
        if photo:
            await db.delete(photo)
            await db.commit()
            return photo.description=='avatar',photo
        return False,None

    async def count_user_photos(
        self,
        db: AsyncSession,
        *,
        user_id: int
    ) -> int:
        result = await db.execute(
            select(self.model)
            .where(
                (self.model.user_id == user_id) &
                (self.model.description != 'avatar')  # ⚠️ 注意：Photo 表是否有 `description` 字段？若无请修正条件
            )
        )
        return len(result.scalars().all())  # 或改用 .count()，但需注意 async count 写法（见下方备选）

   
photo_crud = CRUDphoto(Photo)