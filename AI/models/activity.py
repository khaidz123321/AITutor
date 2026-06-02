from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func 
from models.base import Base
class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True, index=True)
    # Khóa ngoại liên kết tới id user
    # ondelete="CASCADE": nếu tài khoản User bị xóa, toàn bộ lịch sử hoạt động của người đó cũng bị xóa theo.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # Phân loại hành động (vd: 'login', 'start_chat', 'submit_exercise')
    action_type = Column(String(255), nullable=False)
    # mô tả chi tiết hành động 
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())