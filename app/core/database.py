from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
from app.core.config import settings

async_db_url =settings.SQL_DB_URL
# --- 异步引擎 ---
# 关键：使用 asyncpg 驱动！
async_engine = create_async_engine(async_db_url, echo=True, future=True)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
)


def to_dict(model_instance):
    return {
        c.name: getattr(model_instance, c.name)
        for c in model_instance.__table__.columns
    }


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()  # 业务代码无异常则提交
        except Exception as ex:
            print('error in get db:',str(ex))
            await session.rollback()  # 发生异常则回滚
            raise
        finally:
            await session.close()

# 2. 显式事务依赖（交出控制权）
async def get_db_manual() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session  # 不自动提交，由路由/Service 决定

Base = declarative_base()

async def create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)