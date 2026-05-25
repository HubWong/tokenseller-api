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
    """异步安全版：不访问 __table__，避免同步IO"""
    if not model_instance:
        return {}
    
    # 手动指定字段（最安全）
    fields = [
        "id", "user_id", "amount", "status",
        "created_at", "updated_at"  # 你有什么字段加什么
    ]
    
    result = {}
    for field in fields:
        try:
            result[field] = getattr(model_instance, field)
        except:
            pass
    return result


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


async def sync_columns():
    """同步模型列到数据库：检测并添加模型中定义但数据库缺失的列"""
    from sqlalchemy import inspect, text

    async with async_engine.begin() as conn:
        def _sync(sync_conn):
            inspector = inspect(sync_conn)
            existing_tables = inspector.get_table_names()

            for table_name, table in Base.metadata.tables.items():
                if table_name not in existing_tables:
                    continue
                existing_cols = {c['name'] for c in inspector.get_columns(table_name)}
                for col in table.columns:
                    if col.name in existing_cols:
                        continue
                    col_type = col.type.compile(sync_conn.dialect)
                    nullable = "NULL" if col.nullable else "NOT NULL"
                    sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col_type} {nullable}'
                    if col.default and col.default.arg is not None:
                        default_val = col.default.arg
                        if isinstance(default_val, str):
                            sql += f" DEFAULT '{default_val}'"
                        elif isinstance(default_val, bool):
                            sql += f" DEFAULT {'TRUE' if default_val else 'FALSE'}"
                        else:
                            sql += f" DEFAULT {default_val}"
                    sync_conn.execute(text(sql))
                    print(f'  [sync] Added column: {table_name}.{col.name}')

        await conn.run_sync(_sync)