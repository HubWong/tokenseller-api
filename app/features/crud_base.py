from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload  # 若需预加载关系可选
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder

from app.features.db_base import ApiResp
from app.features.user.schemas.user_schema import UserInDBBase

ModelType = TypeVar("ModelType", bound=Any)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)
UpdateSchemaType_co = TypeVar("UpdateSchemaType_co", bound=BaseModel, covariant=True)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        Async CRUD object with default methods to Create, Read, Update, Delete (CRUD).
        """
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.id == id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
    ) -> tuple[int, List[ModelType]]:
        # 构建 where 条件
        where_clauses = []
        if filters:
            where_clauses = [
                getattr(self.model, key) == value for key, value in filters.items()
            ]

        # 总数：count(*) 用 scalar + func.count()
        count_stmt = select(func.count()).select_from(self.model).where(*where_clauses)
        total = await db.scalar(count_stmt) or 0

        if total == 0:
            return 0, []

        # 数据查询
        stmt = select(self.model).where(*where_clauses).offset(skip).limit(limit)
        result = await db.execute(stmt)
        items = result.scalars().all()

        return total, list(items)

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        # 过滤掉 None（可选；按需调整）
        filtered_data = {k: v for k, v in obj_in_data.items() if v is not None}
        try:
            db_obj = self.model(**filtered_data)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except Exception as e:
            await db.rollback()
            print(f"Error creating {self.model.__name__}: {str(e)}")
            raise e
    async def update_username(self, uid:int, username:str,db:AsyncSession):
        user = await self.get(db=db,id=uid)
        if user:
            user.username = username
            await db.commit()
            await db.refresh(user)
            return ApiResp(success=True, data=UserInDBBase.model_validate(user))
        return ApiResp(success=False, message= 'no user found')

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
  
        try:
            for field in obj_data:
                if field in update_data:
                    new_value = update_data[field]
                    old_value = getattr(db_obj, field)
                    if new_value != old_value:  # 可选：避免无意义 setattr
                        setattr(db_obj, field, new_value)
            db.add(db_obj)
            await db.commit()
            await db.refresh(db_obj)
            return db_obj
        except Exception as e:
            await db.rollback()
            print(f"Error updating {self.model.__name__}: {str(e)}")
            raise e

    async def delete(self, db: AsyncSession, *, id: int) -> Optional[ModelType]:
        # 先查出对象（需返回被删对象）
        obj = await self.get(db, id)
        if obj:
            await db.delete(obj)
            await db.commit()
        return obj