"""
Quản lý Phiên làm việc: 
- Xử lý việc lưu trữ và truy xuất lịch sử trò chuyện
- Duy trì ngữ cảnh trong suốt quá trình tương tác giữa AI và user.
"""

import json
from typing import List
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from models.chat_history import ChatHistory
from models.activity import Activity

class SessionManager:
    """
    Lớp điều phối dữ liệu hội thoại, kết nối giữa cơ sở dữ liệu PostgreSQL và định dạng tin nhắn của LangChain.
    """

    def __init__ (self, db: Session):
        self.db = db 

    # ==========================================
    # 1. QUẢN LÝ LỊCH SỬ CHAT 
    # ==========================================
    def get_chat_history(self, user_id: int, subject: str, chapter: str) -> List[BaseMessage]:
        # Truy vấn các bản ghi cũ từ cơ sở dữ liệu
        history_records = self.db.query(ChatHistory).filter(
            ChatHistory.user_id == user_id,
            ChatHistory.subject == subject,
            ChatHistory.chapter == chapter
        ).order_by(ChatHistory.created_at.asc()).all()

        # Chuyển đổi bản ghi từ dtb sang định dạng LangChain hiểu được
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
    
    # ==========================================
    # 2. QUẢN LÝ TIẾN ĐỘ HỌC 
    # ==========================================
    def get_user_progress(self, user_id: int, subject: str, chapter: str):
        """
        Lấy tiến độ mới nhất từ bảng activities.
        Trả về dict: {"question_id": "...", "step": int} hoặc None nếu chưa học.
        """
        action_key = f"progress_{subject}_{chapter}"
        
        # Tìm hành động cập nhật tiến độ mới nhất
        latest_activity = self.db.query(Activity).filter(
            Activity.user_id == user_id,
            Activity.action_type == action_key
        ).order_by(Activity.created_at.desc()).first()

        if latest_activity and latest_activity.description:
            # Giải mã chuỗi JSON từ cột description
            return json.loads(latest_activity.description) 
        return None

    def update_progress(self, user_id: int, subject: str, chapter: str, question_id: str, step: int):
        """
        Lưu tiến độ mới vào bảng activities dưới dạng chuỗi JSON.
        """
        try:
            action_key = f"progress_{subject}_{chapter}"
            desc_data = json.dumps({"question_id": question_id, "step": step})
            
            new_progress = Activity(
                user_id=user_id,
                action_type=action_key,
                description=desc_data
            )
            self.db.add(new_progress)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            print(f"Lỗi khi lưu tiến độ học tập: {str(e)}")
            raise e