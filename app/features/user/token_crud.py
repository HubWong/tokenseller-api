from datetime import timezone, datetime, timedelta
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete,func
from app.features.crud_base import CRUDBase
from app.features.db_base import ApiResp
from app.features.user.model.token_model import RefreshToken
from app.features.user.schemas.token_schema import TokenSchema



class CRUDToken(CRUDBase[RefreshToken, RefreshToken, TokenSchema]):
    def __init__(self, model):
        super().__init__(model)

    async def create_token(
        self, db: AsyncSession, *, user_id: int, token: str, expire_at: datetime
    ) -> RefreshToken:
        """Create a new token for a user."""
        # ✅ 建议：确保 expire_at 是带时区的（UTC），避免歧义
        if expire_at.tzinfo is None:
            expire_at = expire_at.replace(tzinfo=timezone.utc)

        db_obj = self.model(user_id=user_id, refresh_token=token, expires_at=expire_at)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_user_tokens(self, db: AsyncSession, *, user_id: int) -> List[RefreshToken]:
        """Get all tokens for a specific user."""
        result = await db.execute(select(self.model).where(self.model.user_id == user_id))
        return list(result.scalars().all())

    async def get_refresh_token(self, db: AsyncSession, ref_token: str) -> Optional[RefreshToken]:
        """Get a token by refresh_token string."""
        result = await db.execute(
            select(self.model).where(self.model.refresh_token == ref_token)
        )
        return result.scalars().first()

    async def delete_token(self, db: AsyncSession, *, token_id: int) -> bool:
        """Delete a token by its ID."""
        # ❗ 原 self.get 是同步的且未 await；应改用异步查询
        result = await db.execute(select(self.model).where(self.model.id == token_id))
        db_obj = result.scalars().first()
        if db_obj:
            await db.delete(db_obj)
            await db.commit()
            return True
        return False
    from sqlalchemy import delete, select, func

    async def logout_delete_token(self, db: AsyncSession, uid) -> ApiResp:
        # 🔍 诊断：先查数量
        count_stmt = select(func.count()).select_from(self.model).where(self.model.user_id == uid)
        count_result = await db.execute(count_stmt)
        expected_count = count_result.scalar()
        print(f"[DEBUG] Expected to delete: {expected_count} rows for user_id={uid} (type: {type(uid)})")

        # 🧹 执行删除
        delete_stmt = delete(self.model).where(self.model.user_id == uid)
        result = await db.execute(delete_stmt)
        await db.commit()

        actual_deleted = result.rowcount
        print(f"[DEBUG] rowcount returned: {actual_deleted}")

        # ⚠️ 某些 DB（如 SQLite）rowcount 可能不准，fallback 到再查一次
        if actual_deleted <= 0 and expected_count > 0:
            # 二次确认
            count_after = (await db.execute(
                select(func.count()).select_from(self.model).where(self.model.user_id == uid)
            )).scalar()
            actual_deleted = expected_count - count_after
            print(f"[DEBUG] Fallback count: now {count_after} left, so deleted {actual_deleted}")

        if actual_deleted == 0:
            return ApiResp(success=False, message="No tokens found for this user")

        return ApiResp(
            success=True,
            message=f"All {actual_deleted} token(s) for user {uid} successfully deleted",
        )

    

token_crud = CRUDToken(RefreshToken)