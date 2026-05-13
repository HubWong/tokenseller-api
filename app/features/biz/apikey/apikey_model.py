from app.features.db_base import TimestampMixin
from app.core.database import Base
from sqlalchemy import Column,Text, Integer, String, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.sql import func


class ApiKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    key = Column(String(128), unique=True, index=True, nullable=False)
    name = Column(String(128))
    tier = Column(String(20), default="free")
    rpm_limit = Column(Integer, default=60)
    status = Column(String(20), default="active")

