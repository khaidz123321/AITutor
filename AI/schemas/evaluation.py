from pydantic import BaseModel, Field
from enum import Enum

# NHẬN THỨC VÀ HÀNH VI
class CognitiveState(str, Enum):
    # nhóm 1: thành công
    STEP_CORRECT = "STEP_CORRECT"           # Đúng 1 bước trung gian (Để Backend tăng current_step)
    PROBLEM_COMPLETED = "PROBLEM_COMPLETED" # Giải xong bài toán (Để Backend update is_completed = True)

    # nhóm 2: mắc lỗi
    INCOMPLETE = "INCOMPLETE"               # Đúng hướng nhưng chưa xong, thiếu ý/thiếu điều kiện
    CALCULATION_ERROR = "CALCULATION_ERROR" # Nhầm dấu, sai tính toán, sai số học 
    CONCEPTUAL_ERROR = "CONCEPTUAL_ERROR"   # Sai bản chất, mất gốc kiến thức, dùng sai công thức 
    VAGUE_OR_OFFTOPIC = "VAGUE_OR_OFFTOPIC" # Trả lời lan man, không rõ ràng, lạc đề 

    # nhóm 3: tương tác
    REQUEST_HINT = "REQUEST_HINT"           # Xin gợi ý, xin giải hộ (Từ case g, i của StratL)
    REQUEST_THEORY = "REQUEST_THEORY"       # Hỏi lại lý thuyết/định nghĩa (Từ case h của StratL)

# CẢM XÚC (bổ sung theo case l, m của StratL)
class EmotionState(str, Enum):
    NEUTRAL = "NEUTRAL"                     # Bình thường, tập trung
    FRUSTRATED = "FRUSTRATED"               # Bực dọc, mất kiên nhẫn, thiếu động lực
    LACK_CONFIDENCE = "LACK_CONFIDENCE"     # Thiếu tự tin, tự ti ("Em kém quá", "Chắc lại sai")

# CHẨN ĐOÁN TỔNG QUAN
class StudentEvaluation(BaseModel):
    cognitive_state: CognitiveState = Field(
        ..., 
        description="Analyze the student's message and categorize their cognitive state or specific request."
    )
    emotion_state: EmotionState = Field(
        ..., 
        description="Assess the student's emotional tone from their phrasing. Default to NEUTRAL if unclear."
    )
    response: str = Field(
        ...,
        description="The actual response/message to the student in natural, fluent Vietnamese. Maximum 5 sentences."
    )
    next_step: int = Field(
        ...,
        description="The current step number the student should focus on next (integer). If they complete the current step, increment this by 1. If they fail, keep it the same."
    )