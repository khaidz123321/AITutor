from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from models.base import Base 

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False) 
    # tên file gốc hiển thị -> Frontend
    filename = Column(String(255), nullable=False)
    # Phân loại tài liệu thuộc môn nào
    subject = Column(String(50), index=True, nullable=False)
    # Đường dẫn lưu tài liệu thực tế
    file_path = Column(String(500), nullable=False)
    # Các trạng thái xử lí của hệ thống bao gồm 'pending' (mới tải lên), 'processing' (AI đang đọc/băm nhỏ file), 'completed' (đã sẵn sàng)
    status = Column(String(20), default="pending")
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())