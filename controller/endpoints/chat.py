"""
Quản lí luồng chat trong thời gian thực
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.session import get_db
from schemas.chat import ChatRequest, ChatResponse
from models.chat_history import ChatHistory
from engine.ai_engine import AItutor 
from engine.session_manager import SessionManager
from engine.rag_service import RAGService
from engine.scaffolding import LearningScaffold

router = APIRouter()
ai_tutor = AItutor()
rag_service = RAGService()
scaffold = LearningScaffold(db=None)

@router.post("/", response_model=ChatResponse)
def chat_with_tutor(request: ChatRequest, db: Session = Depends(get_db)):
    current_user_id = 1 
    session_manager = SessionManager(db)
    try:
        # 1 Truy xuất lịch sử 
        chat_history = session_manager.get_chat_history(
            user_id=current_user_id,
            subject=request.subject,
            chapter=request.chapter
        )

        # Lấy dữ liệu bài tập mẫu (JSON)
        question_data = ai_tutor.load_question_data(request.subject, request.chapter)

        # 3. Kích hoạt kiểm tra lời giải sinh viên
        current_step = 1 
        new_step, scaffold_instruction = scaffold.validate_step(
            user_id=current_user_id,
            subject=request.subject,
            chapter=request.chapter,
            student_input=request.message,
            current_step=current_step,
            question_data=question_data
        )

        # 4. TRUY XUẤT KIẾN THỨC: Tìm đoạn văn liên quan trong PDF đã upload
        rag_context = rag_service.query_context(
            subject=request.subject, 
            query=request.message
        )

        # 2 Gọi aI, truyền đúng môn + chương để AI tìm file + xử lí
        ai_reply = ai_tutor.get_response(
            subject=request.subject,
            chapter=request.chapter,
            user_message=request.message,
            chat_history=chat_history,
            scaffold_instruction=scaffold_instruction,
            rag_context=rag_context
        )

        # 3 Lưu cả câu hỏi và câu trả lời vào Database thông qua SessionManager
        session_manager.save_message(
            user_id=current_user_id, 
            subject=request.subject, 
            chapter=request.chapter, 
            role="user", 
            content=request.message
        )
        session_manager.save_message(
            user_id=current_user_id, 
            subject=request.subject, 
            chapter=request.chapter, 
            role="ai", 
            content=ai_reply
        )

        # 4 Trả kết quả về cho Frontend
        return ChatResponse(reply=ai_reply, status="success")

    except Exception as e:
        db.rollback()
        print(f"Chat API Error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="The AI Tutor engine encountered an error. Please try again later."
        )