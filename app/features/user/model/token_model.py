
from sqlalchemy import Boolean, Column, String, Integer, ForeignKey, Text, Enum,DateTime, func
from app.features.db_base import TimestampMixin
from datetime import datetime, timezone
from app.core.database import Base






class RefreshToken(Base, TimestampMixin):
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)    
    refresh_token = Column(String(200), unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)  

    def is_expired(self):
        return datetime.now(timezone.utc) > self.expires_at