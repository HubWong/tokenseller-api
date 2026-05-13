from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
from jose import jwt,JWTError
import hashlib
import bcrypt
import ast
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Form
from app.core.config import settings
from datetime import time
import secrets

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.SECRET_KEY_ALGORITHM

async def validate_order(order_id: int):
    # TODO: validate order from payoneer callback
    # for now just return True
    return True

class CustomOAuth2Form(OAuth2PasswordRequestForm):
    def __init__(
        self,
        username: str = Form(...),
        password: str = Form(...),
        pc_id: str = Form(None)  # 自定义字段，可选
    ):
        super().__init__(username=username, password=password)
        self.pc_id = pc_id
        
def create_access_token(
    subject: Union[str, int],
    role:Optional[str] = '',
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None
) -> str:
    """Create JWT access token.
    
    Args:
        subject: User identifier (usually user_id)
        expires_delta: Optional custom expiration time
        extra_claims: Additional claims to include in token
    
    Returns:
        Encoded JWT string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    to_encode = {"exp": expire, "sub": str(subject),'role':role, "type": "access"}
    if extra_claims:
        to_encode.update(extra_claims)
    
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(
    subject: Union[str, int]
) -> tuple[datetime, str]:
    """Create JWT refresh token.
    
    Args:
        subject: User identifier (usually user_id)
    
    Returns:
        Tuple of (expiration_datetime, encoded_jwt)
    """
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    to_encode = {"exp": expire, "sub": str(subject), "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return expire, encoded_jwt

# Legacy SHA256 hash for backward compatibility with old passwords
# New passwords will use bcrypt via get_password_hash from security.py
def legacy_hash_password(password: str) -> str:
    """Legacy SHA256 password hashing - for backward compatibility only"""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash.
    
    Handles both raw bcrypt hashes and string representations that may
    have been stored with Python byte string notation.
    
    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hashed password
    
    Returns:
        True if password matches, False otherwise
    """
    try:
        # Handle Python byte string representation if stored that way
        if hashed_password.startswith("b'") or hashed_password.startswith('b"'):
            hashed_bytes = ast.literal_eval(hashed_password)
        else:
            # Normal str → bytes
            hashed_bytes = hashed_password.encode('utf-8')
        
        # Pre-hash password to match bcrypt's 72-byte limit
        pwd_bytes = hashlib.sha256(plain_password.encode('utf-8')).digest()
        
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False
 

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt with SHA256 pre-hashing.
    
    Pre-hashing with SHA256 allows passwords longer than bcrypt's
    72-byte limit while maintaining security.
    
    Args:
        password: Plain text password
    
    Returns:
        Bcrypt hash string
    """
    # Convert to bytes first
    pwd_bytes = password.encode('utf-8')
    
    # Pre-hash to fit bcrypt's limit safely
    pre_hashed = hashlib.sha256(pwd_bytes).digest()  # 32 bytes
    
    # Hash with bcrypt (12 rounds for security/performance balance)
    return bcrypt.hashpw(pre_hashed, bcrypt.gensalt(rounds=12)).decode()

def verify_token(token: str, token_type: Optional[str] = None) -> Optional[dict]:
    """Verify JWT token and return payload.
    
    Args:
        token: JWT token string
        token_type: Optional expected token type ("access" or "refresh")
    
    Returns:
        Token payload dict if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token, 
            SECRET_KEY, 
            algorithms=[ALGORITHM],
            options={"require": ["exp"]}
        )
        
        # Validate token type if specified
        if token_type and payload.get("type") != token_type:
            return None
            
        return payload
    except JWTError:
        return None

#get user id from the token
def get_subject_from_token(token: str) -> Optional[str]:
    """Extract subject from token without full validation.
    
    Args:
        token: JWT token string
    
    Returns:
        Subject identifier if token can be decoded, None otherwise
        refresh_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAi
    """
    if token.startswith("refresh_token="):
        token = token[14:]
    payload = verify_token(token)
    return payload.get("sub") if payload else None



def gen_api_key(user_id: int) -> str:
    raw = f"{user_id}-{time()}-{secrets.token_hex(16)}"
    return "sk-" + hashlib.sha256(raw.encode()).hexdigest()[:40]


def generate_invite_code(user_id: int) -> str:
    # Step 1: 哈希处理（SHA-256取前4字节）
    hash_bytes = hashlib.sha256(str(user_id).encode()).digest()[:4]
    hash_int = int.from_bytes(hash_bytes, byteorder='big')

    # Step 2: 转换为62进制（0-9A-Za-z共62字符）
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    code = []
    for _ in range(6):
        hash_int, remainder = divmod(hash_int, 62)
        code.append(chars[remainder])
    return ''.join(reversed(code))
