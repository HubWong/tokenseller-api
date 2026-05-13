from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.features.crud_base import CRUDBase
from app.features.user_file.user_file_model import UploadedFile
from app.features.user_file.user_file_schema import UploadFileSchema


class CRUDUserFile(CRUDBase[UploadedFile, UploadedFile, UploadFileSchema]):
    async def create_file_upload(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        filename: str,
        filepath: str,
        size: int
    ) -> UploadedFile:
        """Create a new file record for a user."""
        db_obj = self.model(
            user_id=user_id,
            filename=filename,
            filepath=filepath,
            file_size=size
        )
        db.add(db_obj)
        await db.commit()      # ← await
        await db.refresh(db_obj)  # ← await
        return db_obj

    async def get_user_files(self, db: AsyncSession, *, user_id: int) -> list[UploadedFile]:
        """Get all files for a specific user."""
        stmt = select(self.model).where(self.model.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_file_by_id(self, db: AsyncSession, id: int) -> Optional[UploadedFile]:
        stmt = select(self.model).where(self.model.id == id)
        result = await db.execute(stmt)
        return result.scalars().first()

    # ❗ 重要：这里必须确保父类 CRUDBase.update 是 async 的！
    # 如果父类仍是同步 update，下面直接 await super().update(...) 会报错。
    # 建议：要么重构父类，要么在此重写异步 update（推荐临时方案）：
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: UploadedFile,
        obj_in: UploadFileSchema | Dict[str, Any]
    ) -> UploadedFile:
        # 兼容 Pydantic 模型或 dict
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete_file_by_id(self, db: AsyncSession, *, file_id: int) -> bool:
        """Delete a file by its ID."""
        db_obj = await self.get(db, id=file_id)  # ← 假设 self.get 已异步化；见下方说明
        if db_obj:
            await db.delete(db_obj)  # AsyncSession.delete 是 awaitable（实际可不 await，但推荐 await 以统一风格）
            await db.commit()
            return True
        return False


user_file_crud = CRUDUserFile(UploadedFile)