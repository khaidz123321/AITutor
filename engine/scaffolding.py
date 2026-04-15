"""
Bộ quản lý tiến trình học tập: Điều phối lộ trình học tập từng bước,
so sánh lời giải của sinh viên với đáp án mẫu và cập nhật trạng thái học tập.
"""

import json 
from sqlalchemy.orm import Session
from models.chat_history import ChatHistory

class LearningScaffold:
    def __init__(self, db: Session):
        self.db = db
    
    def validate_step(self, user_id: int, subject: str, chapter: str, student_input:str, current_step: int, question_data: str):
        """
        Kiểm tra lời giải của user dựa trên dữ liệu sẵn
        """
        # tìm dữ liệu của bước hiện tại trong JSON 
        data = json.loads(question_data) 
        steps = data.get("steps", [])
        target_step = next((s for s in steps if s["step"] == current_step), None)

        if not target_step:
            return current_step, "Hệ thống không tìm thấy dữ liệu"
        
        # so sánh, kiểm tra lời giải sinh viên có chứa keyword hay ko
        keywords = target_step.get("key_keywords", [])
        is_correct = any(word.lower() in student_input.lower() for word in keywords)

        # 2. Quyết định cập nhật lộ trình
        if is_correct:
            new_step = current_step + 1
            instruction_to_ai = f"Sinh viên đã hoàn thành đúng Bước {current_step}. Hãy khen ngợi và hướng dẫn họ sang Bước {new_step}."
        else:
            new_step = current_step
            instruction_to_ai = f"Sinh viên giải sai hoặc chưa đủ ý cho Bước {current_step}. Tuyệt đối không cho đáp án, hãy gợi ý về: {target_step.get('hint')}"

        return new_step, instruction_to_ai