from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func 
from models.base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    # Mật khẩu (Bắt buộc phải băm/mã hóa trước khi lưu, không lưu chữ thô)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100))
    # Trạng thái tài khoản (True = Đang hoạt động, False = Bị khóa)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())