"""
Quản lý luồng chat theo kiến trúc Single-Agent AI Tutor
Tách biệt luồng Khởi tạo (Init) và luồng Hỏi đáp (Chat)
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.session import get_db
from schemas.chat import ChatRequest, ChatResponse
from engine.ai_engine import AItutor 
from engine.session_manager import SessionManager
from engine.rag_service import RAGService
from engine.scaffolding import LearningScaffold
from models.chat_history import ChatHistory
from core.mapping import get_mapped_paths
from core.config import settings
from schemas.evaluation import StudentEvaluation
import os 
import json

router = APIRouter()
ai_tutor = AItutor()
rag_service = RAGService()

# =================================================================
# ENDPOINT 1: KHỞI TẠO PHIÊN HỌC (AI CHỦ ĐỘNG GIAO BÀI)
# Gọi bằng phương thức GET khi frontend/HTML vừa load xong
# =================================================================
@router.get("/init")
def init_chat_session(subject: str, chapter: str, db: Session = Depends(get_db)):
    current_user_id = 1 # TODO: Sau này lấy từ Token đăng nhập (JWT)
    session_manager = SessionManager(db)
    
    try:
        progress = session_manager.get_user_progress(current_user_id, subject, chapter)
        
        if progress:
            current_question_id = progress.get("question_id")
        else:
            current_question_id = ai_tutor.get_first_question_id(subject, chapter)
            session_manager.update_progress(current_user_id, subject, chapter, current_question_id, step=1)
        
        # --- BẮT ĐẦU FIX: LẤY LỊCH SỬ CHAT TỪ DB ---
        # Truy vấn trực tiếp vào DB để lấy data format dễ đọc cho Frontend
        history_records = db.query(ChatHistory).filter(
            ChatHistory.user_id == current_user_id,
            ChatHistory.subject == subject,
            ChatHistory.chapter == chapter
        ).order_by(ChatHistory.created_at.asc()).all()
        
        # Biến đổi thành mảng JSON
        formatted_history = [
            {"role": record.role, "content": record.content} 
            for record in history_records
        ]

        # Nếu mảng trống -> Lần đầu tiên học -> Tạo câu chào
        if not formatted_history:
            welcome_message = ai_tutor.get_initial_question(subject, chapter, current_question_id)
            session_manager.save_message(current_user_id, subject, chapter, "ai", welcome_message)
            
            return {
                "reply": welcome_message, 
                "history": [], # Lịch sử trống
                "question_id": current_question_id,
                "status": "success"
            }

        # Nếu đã có lịch sử -> KHÔNG tạo câu chào mới, trả về lịch sử
        return {
            "reply": "", 
            "history": formatted_history, 
            "question_id": current_question_id,
            "status": "success"
        }

    except Exception as e:
        print(f"Init Session Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Không thể khởi tạo bài học. Vui lòng thử lại.")


# =================================================================
# ENDPOINT 2: XỬ LÝ CHAT (SINGLE-AGENT EVALUATION & RESPONSE)
# Gọi bằng phương thức POST mỗi khi sinh viên bấm gửi tin nhắn
# =================================================================
@router.post("/", response_model=ChatResponse)
def chat_with_tutor(request: ChatRequest, db: Session = Depends(get_db)):
    current_user_id = 1 # TODO: Sau này lấy từ Token đăng nhập
    session_manager = SessionManager(db)
    
    try:
        # 1. Xác định bài tập và bước hiện tại từ Database
        progress = session_manager.get_user_progress(current_user_id, request.subject, request.chapter)
        original_question_id = progress.get("question_id") if progress else None    
        
        if not progress:
            # Trường hợp dự phòng nếu Init thất bại
            current_question_id = ai_tutor.get_first_question_id(request.subject, request.chapter)
            current_step = 1
        else:
            current_question_id = progress.get("question_id")
            current_step = progress.get("step", 1)
        
        # Chỉ load đúng 1 bài tập đang làm (Tiết kiệm Token)
        question_data = ai_tutor.load_question_data(request.subject, request.chapter, current_question_id)

        # 2. Truy xuất lịch sử chat
        chat_history = session_manager.get_chat_history(
            user_id=current_user_id,
            subject=request.subject,
            chapter=request.chapter
        )

        # 3. RAG: Tìm ngữ cảnh từ PDF nếu có
        rag_context = rag_service.query_context(
            subject=request.subject, 
            query=request.message
        )
        
        scaffold_manager = LearningScaffold(db)
        scaffold_instruction = scaffold_manager.get_current_instruction(
            current_step=current_step, 
            question_data=question_data
        )

        # 4. Gọi Single-Agent AI (Vừa chấm lỗi, vừa sinh câu trả lời)
        # eval_result giờ đây là một object chứa: response, next_step, cognitive_state
        eval_result: StudentEvaluation = ai_tutor.get_response(
            subject=request.subject,
            chapter=request.chapter,
            user_message=request.message,
            question_id=current_question_id,
            chat_history=chat_history,
            scaffold_instruction=scaffold_instruction,
            rag_context=rag_context
        )

        # Bóc tách dữ liệu an toàn (Tránh crash nếu AI API trả về None)
        if eval_result:
            ai_reply = eval_result.response
            print(f"[AI Đánh giá Trạng thái]: {eval_result.cognitive_state}")
            
            # --- BẮT ĐẦU FIX LOGIC NHẢY BƯỚC / NHẢY BÀI ---
            
            if eval_result.cognitive_state == "STEP_CORRECT":
                new_step = current_step + 1
            
            # NẾU XONG BÀI TOÁN -> CHỦ ĐỘNG BỐC ĐỀ MỚI
            elif eval_result.cognitive_state == "PROBLEM_COMPLETED":
                # 1. Logic giả định: Khải cần viết 1 hàm lấy ID bài tiếp theo
                # Ví dụ: từ GT1_C1_001 -> GT1_C1_002
                next_question_id = ai_tutor.get_next_question_id(request.subject, request.chapter, current_question_id)
                
                if next_question_id:
                    # 2. Lấy đề bài mới
                    new_question_text = ai_tutor.get_initial_question(request.subject, request.chapter, next_question_id)
                    
                    # 3. Ghi đè câu "hứa lèo" của AI bằng đề bài thực tế
                    ai_reply = f"{ai_reply}\n\n**Bài toán tiếp theo dành cho bạn:**\n{new_question_text}"
                    
                    # 4. Reset step về 1 cho bài mới
                    new_step = 1
                    current_question_id = next_question_id # Cập nhật ID để lưu DB
                else:
                    ai_reply = f"{ai_reply}\n\nChúc mừng! Bạn đã hoàn thành toàn bộ bài tập của chương này rồi!"
                    new_step = current_step
            else:
                new_step = current_step
        else:
            ai_reply = "Xin lỗi, hệ thống AI đang gặp sự cố kết nối. Bạn vui lòng thử lại nhé!"
            new_step = current_step # Giữ nguyên tiến độ nếu lỗi

        # 5. Lưu toàn bộ xuống Database
        # Lưu tin nhắn User
        session_manager.save_message(
            user_id=current_user_id, 
            subject=request.subject, 
            chapter=request.chapter, 
            role="user", 
            content=request.message 
        )
        
        # Lưu phản hồi AI
        session_manager.save_message(
            user_id=current_user_id, 
            subject=request.subject, 
            chapter=request.chapter, 
            role="ai", 
            content=ai_reply
        )

        # Nếu AI quyết định cho sinh viên sang bước tiếp theo, cập nhật bảng Activity
        if new_step != current_step or current_question_id != original_question_id:
            session_manager.update_progress(
                user_id=current_user_id, 
                subject=request.subject, 
                chapter=request.chapter, 
                question_id=current_question_id, 
                step=new_step
            )

        # 6. Trả về cho giao diện (HTML/JS)
        return ChatResponse(reply=ai_reply, status="success")

    except Exception as e:
        db.rollback()
        print(f"Chat API Error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="The AI Tutor engine encountered an error. Please try again later."
        )
