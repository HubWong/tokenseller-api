# Database Configuration Guide

## 环境变量配置

### 1. 创建 .env 文件

复制 `.env.example` 到 `.env`：

```bash
cp .env.example .env
```

### 2. 配置数据库路径

编辑 `.env` 文件：

```env
# SQLite database URL
SQLITE_DB_URL=sqlite:///./tokens.db
```

支持的格式：
- **相对路径**: `sqlite:///./tokens.db` (当前目录)
- **绝对路径**: `sqlite:////full/path/to/tokens.db` (Linux/Mac)
- **Windows**: `sqlite:///C:/path/to/tokens.db` (注意正斜杠)

## 数据库迁移

### 方式一：使用 migrate.py (推荐)

```bash
# 初始化数据库（创建所有表）
python migrate.py init

# 运行 Alembic 迁移
python migrate.py upgrade

# 回滚上一次迁移
python migrate.py downgrade

# 重置数据库（删除并重建，会丢失数据！）
python migrate.py reset
```

### 方式二：使用 Alembic 命令

```bash
# 运行所有迁移
alembic upgrade head

# 回滚一次
alembic downgrade -1

# 回滚到初始状态
alembic downgrade base

# 创建新的迁移
alembic revision --autogenerate -m "add new table"

# 查看当前版本
alembic current

# 查看历史
alembic history
```

## 主要变更

### main.py
- ✅ 从 `.env` 读取 `SQLITE_DB_URL`
- ✅ 使用 `DB_PATH` 变量替代硬编码 `'tokens.db'`
- ✅ 启动时显示数据库路径

### migrations/env.py
- ✅ 从 `.env` 读取 `SQLITE_DB_URL`
- ✅ 支持 SQLite 数据库迁移

### 新增文件
- `.env.example` - 环境变量模板
- `migrate.py` - 数据库管理脚本
- `migrations/versions/001_init_token_tables.py` - 初始迁移

## 测试配置

```bash
# 1. 设置环境变量
set SQLITE_DB_URL=sqlite:///./tokens.db

# 2. 初始化数据库
python migrate.py init

# 3. 启动后端
python main.py

# 4. 检查输出
# 应显示: "📦 Database URL: sqlite:///./tokens.db"
```

## 常见问题

### Q: 数据库文件在哪里？
A: 默认在当前目录的 `tokens.db`。可以通过 `SQLITE_DB_URL` 更改位置。

### Q: 如何备份数据库？
A: 直接复制 `.db` 文件即可：
```bash
cp tokens.db tokens_backup.db
```

### Q: 如何切换到 PostgreSQL？
A: 修改 `.env`：
```env
SQLITE_DB_URL=postgresql://user:password@localhost/token_seller
```
并安装依赖：`pip install psycopg2-binary`
