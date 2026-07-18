"""
Quản lý Phiên làm việc:
- Truy xuất lịch sử hội thoại từ bảng chat_sessions + chat_messages (Spring Boot)
- Duy trì ngữ cảnh cho AI Engine trong suốt quá trình tương tác.
- Quản lý tiến độ học tập qua bảng activities (Python sở hữu).

THAY ĐỔI KIẾN TRÚC:
  Trước: Python tự lưu lịch sử vào bảng chat_histories riêng.
  Sau  : Python CHỈ ĐỌC lịch sử từ bảng của Spring Boot (chat_sessions + chat_messages).
         Việc GHI lịch sử do Spring Boot đảm nhiệm sau khi nhận reply từ Python.
"""

import json
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from models.activity import Activity

class SessionManager:
    """
    Lớp điều phối dữ liệu hội thoại, kết nối giữa database PostgreSQL
    và định dạng tin nhắn của LangChain.
    """

    def __init__(self, db: Session):
        self.db = db

    # ==========================================
    # 1. LỊCH SỬ CHAT (ĐỌC TỪ BẢNG SPRING BOOT)
    # ==========================================
    def get_chat_history(self, user_id: int, chapter_id: int) -> List[BaseMessage]:
        """
        Đọc lịch sử hội thoại từ bảng chat_sessions + chat_messages của Spring Boot.
        Trả về danh sách LangChain messages để AI Engine dùng làm ngữ cảnh.

        Args:
            user_id   : ID người dùng (lấy từ header X-User-Id do Spring Boot gửi)
            chapter_id: ID chương học (lấy từ header X-Chapter-Id do Spring Boot gửi)
        """
        rows = self.db.execute(
            text("""
                SELECT cm.role, cm.content
                FROM chat_messages cm
                JOIN chat_sessions cs ON cm.session_id = cs.id
                WHERE cs.user_id   = :uid
                  AND cs.chapter_id = :cid
                ORDER BY cm.created_at ASC
            """),
            {"uid": user_id, "cid": chapter_id}
        ).fetchall()

        formatted: List[BaseMessage] = []
        for row in rows:
            # Map role: Spring Boot dùng USER/ASSISTANT, LangChain dùng Human/AI
            if row.role in ("user", "USER"):
                formatted.append(HumanMessage(content=row.content))
            elif row.role in ("ai", "ASSISTANT"):
                formatted.append(AIMessage(content=row.content))
        return formatted

    def get_raw_history(self, user_id: int, chapter_id: int) -> List[dict]:
        """
        Đọc lịch sử dạng dict thô (dành cho endpoint /chat/init trả về cho frontend).
        """
        rows = self.db.execute(
            text("""
                SELECT cm.role, cm.content
                FROM chat_messages cm
                JOIN chat_sessions cs ON cm.session_id = cs.id
                WHERE cs.user_id   = :uid
                  AND cs.chapter_id = :cid
                ORDER BY cm.created_at ASC
            """),
            {"uid": user_id, "cid": chapter_id}
        ).fetchall()

        result = []
        for row in rows:
            role_mapped = "user" if row.role in ("user", "USER") else "ai"
            result.append({"role": role_mapped, "content": row.content})
        return result

    # LƯU Ý: save_message() đã bị XÓA.
    # Việc lưu tin nhắn vào chat_messages là trách nhiệm của Spring Boot.
    
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
        Lưu tiến độ vào bảng activities dưới dạng chuỗi JSON.
        UPSERT: cập nhật bản ghi cũ nếu đã tồn tại, insert mới nếu chưa có.
        Tránh bảng activities phình to vô hạn sau nhiều lần học.
        """
        try:
            action_key = f"progress_{subject}_{chapter}"
            desc_data = json.dumps({"question_id": question_id, "step": step})

            # Tìm bản ghi tiến độ hiện có (nếu có)
            existing = self.db.query(Activity).filter(
                Activity.user_id == user_id,
                Activity.action_type == action_key
            ).first()

            if existing:
                # UPDATE bản ghi cũ thay vì tạo mới
                existing.description = desc_data
            else:
                # INSERT lần đầu tiên học môn/chương này
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
        