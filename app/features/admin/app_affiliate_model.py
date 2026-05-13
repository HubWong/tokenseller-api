from sqlalchemy import Boolean, Column, String, Integer, ForeignKey, Text, Enum,DateTime, func

from app.features.db_base import TimestampMixin
from app.core.database import Base

'''
user_id
parent_id
rate          # 一级分佣比例
level 
'''
class AppAffiliate(Base, TimestampMixin):
    __tablename__ = "app_affiliate"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    rate = Column(Float, nullable=False)
    level = Column(Integer, nullable=False)

class AffiliateRepo:
    def __init__(self,db:AsyncSession) -> None:
        self.db = db

     
    

