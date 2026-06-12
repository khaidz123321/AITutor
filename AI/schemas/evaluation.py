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
    REVEAL_ANSWER = "REVEAL_ANSWER"

# CẢM XÚC (bổ sung theo case l, m của StratL)
class EmotionState(str, Enum):
    NEUTRAL = "NEUTRAL"                     # Bình thường, tập trung
    FRUSTRATED = "FRUSTRATED"               # Bực dọc, mất kiên nhẫn, thiếu động lực
    LACK_CONFIDENCE = "LACK_CONFIDENCE"     # Thiếu tự tin, tự ti ("Em kém quá", "Chắc lại sai")

# KẾT QUẢ CHẨN ĐOÁN (Dành cho AI 1)
class DiagnoseResult(BaseModel):
    cognitive_state: CognitiveState = Field(
        ..., 
        description="The student's current cognitive state. STRICT RULE: Output 'VAGUE_OR_OFFTOPIC' if the input is unrelated to the current subject/problem (e.g., hacking, chit-chat, writing code). Output 'REQUEST_THEORY' if they ask for a definition related to the subject. Output 'PROBLEM_COMPLETED' if they explicitly ask to skip or move to the next problem."
    )
    emotion_state: EmotionState = Field(
        ..., 
        description="Assess the student's emotional tone from their phrasing. Default to NEUTRAL if unclear."
    )
    rag_search_query: str = Field(
        default="", 
        description="If cognitive_state is REQUEST_THEORY, CONCEPTUAL_ERROR, or INCOMPLETE, generate a concise academic search query (max 6 words) based on the problem context to query the vector DB. Otherwise, return an empty string."
    )

# KẾT QUẢ SINH VĂN BẢN (Dành cho AI 2)
class GenerateResult(BaseModel):
    response: str = Field(
        ...,
        description="The actual response/message to the student in natural, fluent Vietnamese. MUST use LaTeX formatting."
    )
    source_citation: str = Field(
        default="",
        description="If you explain theory based on RAG_CONTEXT, extract the source from [Nguồn: ...] and format it as a hierarchical list using \\n."
    )