from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.features.user.schemas.user_schema import SocketUser
from app.core.deps import UserRepoDeps
from typing import Optional


async def clean_expired_files_db():
    print("[*] clean_expired_files_db executed at", datetime.now())
    pass


async def get_user_by_id(session: AsyncSession,user_crud: UserRepoDeps, user_id: int) -> Optional[SocketUser]:
    user = await user_crud.get_by_id(db=session, id=user_id)
    su = SocketUser.model_validate(user) if user else None
    return su


