import os
import sys
from logging.config import fileConfig

# 添加 backend 目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.database import Base  # 导入 Base
from app.core.config import settings  # 导入配置
from app.features.biz.apikey.apikey_model import ApiKey
from app.features.user.model.token_model import RefreshToken
from app.features.user.model.user_model import User
from app.features.user.model.user_photo import Photo
from app.features.biz.usage.model import TokenUsageLog
from app.features.biz.order.order_model import Order,ModelPricing
from app.features.biz.user_balance.models import Transaction
from app.features.message.model import Message


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 使用与应用程序相同的数据库路径
 
db_path =  "postgresql://postgres:wyb@localhost/token_seller"
config.set_main_option("sqlalchemy.url", f"{db_path}")
 

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()



# migrations/env.py （临时加在最后）

# === DEBUG: 检查 metadata 内容 ===
print("\n🔍 DEBUG: Tables in target_metadata:")
for table_name in sorted(target_metadata.tables.keys()):
    print(f"  - {table_name}")

print(f"🔍 Total tables: {len(target_metadata.tables)}")
print(f"🔍 'users' in tables? {'users' in target_metadata.tables}")
print(f"🔍 'coopers' in tables? {'coopers' in target_metadata.tables}")
# =================================