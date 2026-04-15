from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from models.base import Base 

class ChatHistory(Base):
    __tablename__ = "chat_histories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    # Ngữ cảnh cho biết user đang học môn nào chương nào <important>
    subject = Column(String(50), index=True, nullable=False)
    chapter = Column(String(50), index=True, nullable=False)
    # role + content biết thoại nào thuộc về role nào
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())