from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_environment_file() -> str:
    """Load environment variables from base .env and environment-specific .env files."""
    base_env = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(base_env):
        load_dotenv(base_env, override=False)

    app_env = os.getenv("APP_ENV", os.getenv("PYTHON_ENV", "development")).lower()
    env_specific = os.path.join(PROJECT_ROOT, f".env.{app_env}")
    if os.path.exists(env_specific):
        load_dotenv(env_specific, override=True)

    return app_env

APP_ENV = load_environment_file()

class Settings(BaseSettings):   
    PROJECT_NAME: str = "token_seller"
    APP_ENV: str = APP_ENV
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    FREE_TOKENS: int = 100000
    FREE_AMOUNT: float = 10.0
    # 数据库创建在项目根目录（token seller 文件夹）
    
    PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR)))  # backend/app/core -> backend/app -> backend -> token seller
    ONE_API_MASTERKEY :str = os.getenv("ONE_API_MASTER_KEY","sk-LpE8Zq7xhrwF3yrYFeBd1c5a8eF3458f9a9b23C3123a2b9f")
    ONEAPI_URL:str =os.getenv('ONEAPI_BASE',"http://localhost:3000/v1")
    ONEAPI_ACCESS_TOKEN :str = '251b372a815a4393a2cdeaabe9b1d503'
    #room
    MAX_ROOM_PER_USER: int = 3
    MAX_ROOM_PER_VIP_USER: int = 10
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    SECRET_KEY_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 16  # 16 minutes
    REFRESH_TOKEN_EXPIRE_MINUTES:int = 60*24*7  
    EXPIRE_TOKEN_MINUTES_LOST_PWD: int = 10  # Token过期时间，单位为分钟


# 合理的设置
# ACCESS_TOKEN_EXPIRE_MINUTES: int = 60      # 1小时，适中
# REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # 7天，方便用户
    # Database
    SQL_DB_URL: str = os.getenv(
        "DATABASE_URL",  f"sqlite+aiosqlite:///{os.path.join(PROJECT_ROOT, 'tokens.db')}"
    )
    SQL_DB_URL_Sync:str = os.getenv(
        "SQL_DB_URL_Sync",  f"sqlite:///{os.path.join(PROJECT_ROOT, 'tokens.db')}"
    )
   
    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        "redis://default:HYWOrzxxIaMSwuymHbICKQbTnmovFTFF@shinkansen.proxy.rlwy.net:31115"
    )

    REDIS_POOL_SIZE: int = int(os.getenv("REDIS_POOL_SIZE", 20))
    # CORS
    FRONTEND_URL: str = os.getenv('FRONTEND_URL','')
    
    # Payment
    PAYPAL_CLIENT_ID: Optional[str] = os.getenv("PAYPAL_CLIENT_ID")
    PAYPAL_CLIENT_SECRET: Optional[str] = os.getenv("PAYPAL_CLIENT_SECRET")
    PAYPAL_MODE: str = os.getenv("PAYPAL_MODE", "sandbox")  # sandbox or live
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com" if PAYPAL_MODE == "sandbox" else "https://api-m.paypal.com"
    XPUB_tron:str = 'xpub6BsVPv5EsdwgcnkYP5DQ7xnY4tYn49ewY3aygAxpcYKRFa8JiGZpLNpm82pZXJUMJeddMQZXX4iYMjzoqyWSZvWrHBJmg7nPFXjQQ5xz6VL'
    PAYONEER_WEBHOOK_URL: str = os.getenv("PAYONEER_WEBHOOK_URL", "http://localhost:3001/api/payoneer/status")
    
    # Upload
    UPLOAD_DIR: str = "app/uploads"
    MAX_DIMENSION:int = 800     
    IMAGE_QUALITY:int = 85      
    KEEP_DAYS:int = 300      
    MAX_UPLOAD_SIZE: int = 3 * 1024 * 1024  # 1MB
    MAX_PHOTO_COUNT: int = 4  # Maximum number of photos per user
    ALLOWED_IMAGE_TYPES: list = ["image/jpeg", "image/png", "image/gif"]
    DEFAULT_AVATAR: str = "default_avatar.png"
    # Email
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.example.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_SENDER_EMAIL: str = os.getenv("SMTP_SENDER_EMAIL", "noreply@p2p_lover.com")
    SMTP_SENDER_PASSWORD: str = os.getenv("SMTP_SENDER_PASSWORD", "your-email-password-here")

    #cloudinary
        
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "dnnchlq3x")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "961581311975732")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "WSe7R-LouKH32ZJ3DyZjrB0St_k")
    
    # OAuth - GitHub
    GITHUB_CLIENT_ID: str = os.getenv("GITHUB_CLIENT_ID", "Ov23li9u2cmXZDU4QJR8")
    GITHUB_CLIENT_SECRET: str = os.getenv("GITHUB_CLIENT_SECRET", "")
    
    # OAuth - Google
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    # Frontend URL for OAuth callbacks
    # OAUTH_REDIRECT_URL: str = os.getenv("OAUTH_REDIRECT_URL", "https://tokenmaker.ccwu.cc")
    # Backend URL for OAuth provider redirect_uri (OAuth providers redirect back here)
    BACKEND_URL: str = os.getenv("BACKEND_URL", "https://tokenseller-api-production.up.railway.app")
    BILL_PRICE_SET :list[float] = [10,25,50,100,200,500]
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    
   
settings = Settings()




if __name__ == "__main__":
    pass
        