"""
Quản lý Phiên làm việc: 
- Xử lý việc lưu trữ và truy xuất lịch sử trò chuyện
- Duy trì ngữ cảnh trong suốt quá trình tương tác giữa AI và user.
"""

from typing import List
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from models.chat_history import ChatHistory

class SessionManager:
    """
    Lớp điều phối dữ liệu hội thoại, kết nối giữa cơ sở dữ liệu PostgreSQL và định dạng tin nhắn của LangChain.
    """

    def __init__ (self, db: Session):
        self.db = db 
    
    def get_chat_history(self, user_id: int, subject: str, chapter: str) -> List[BaseMessage]:
        # Truy vấn các bản ghi cũ từ cơ sở dữ liệu
        history_records = self.db.query(ChatHistory).filter(
            ChatHistory.user_id == user_id,
            ChatHistory.subject == subject,
            ChatHistory.chapter == chapter
        ).order_by(ChatHistory.created_at.asc()).all()

        # Chuyển đổi bản ghi từ dtb sang định dạng mà LangChain hiểu được
        formatted_messages = []
        for record in history_records:
            if record.role == 'user':
                formatted_messages.append(HumanMessage(content = record.content))
            elif record.role == 'ai':
                formatted_messages.append(AIMessage(content = record.content))

        return formatted_messages 
    
    def save_message(self, user_id: int, subject: str, chapter: str, role: str, content: str):
        """
        Lưu một tin nhắn đơn lẻ (từ user or ai) vào cơ sở dữ liệu để làm trí nhớ dài hạn
        """
        try:
            new_msg = ChatHistory(
                user_id=user_id,
                subject=subject,
                chapter=chapter,
                role=role,
                content=content
            )
            self.db.add(new_msg)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Lỗi khi lưu tin nhắn hội thoại: {str(e)}")
            raise e