
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean,Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.features.db_base import TimestampMixin

class Photo(Base,TimestampMixin):
    __tablename__ = "user_photos"
    __table_args__ = {'extend_existing': True}  
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(Text)
    description = Column(String(200))
    is_private = Column(Boolean,default=False)  #if need to be payed
    user_id = Column(Integer, ForeignKey("users.id"))
    validated = Column(Boolean, default=True)  # 是否已审核
    cloudinary_pub_id =Column(String(100))
    