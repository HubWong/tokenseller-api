from sqlalchemy import Integer,String,Column,ForeignKey,DateTime,Boolean
from app.features.db_base import TimestampMixin
from app.core.database import Base


class Message(Base, TimestampMixin):
    __tablename__ = "app_messages"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)  # 房间标题
    to_user= Column(String(100),nullable=False)
    from_user = Column(String(100), nullable=True) 
    content =Column(String(500),nullable=True)
    message_type= Column(String(10),default='notification')
    is_read = Column(Boolean, default=False)
    level = Column(Integer,default = 0)
     
    