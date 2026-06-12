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
from schemas.evaluation import DiagnoseResult, GenerateResult
import os 
import json
import time

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
    mapped_subj, mapped_chap = get_mapped_paths(subject, chapter)
    
    try:
        # Thay thế toàn bộ bằng mapped_subj và mapped_chap
        progress = session_manager.get_user_progress(current_user_id, mapped_subj, mapped_chap)
        
        if progress:
            current_question_id = progress.get("question_id")
        else:
            current_question_id = ai_tutor.get_first_question_id(mapped_subj, mapped_chap)
            session_manager.update_progress(current_user_id, mapped_subj, mapped_chap, current_question_id, step=1)
        
        history_records = db.query(ChatHistory).filter(
            ChatHistory.user_id == current_user_id,
            ChatHistory.subject == mapped_subj,
            ChatHistory.chapter == mapped_chap
        ).order_by(ChatHistory.created_at.asc()).all()
        
        formatted_history = [
            {"role": record.role, "content": record.content} 
            for record in history_records
        ]

        if not formatted_history:
            welcome_message = ai_tutor.get_initial_question(mapped_subj, mapped_chap, current_question_id)
            session_manager.save_message(current_user_id, mapped_subj, mapped_chap, "ai", welcome_message)
            
            return {
                "reply": welcome_message, 
                "history": [], 
                "question_id": current_question_id,
                "status": "success"
            }

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
    mapped_subj, mapped_chap = get_mapped_paths(request.subject, request.chapter)
    current_user_id = 1 # TODO: Sau này lấy từ Token đăng nhập
    session_manager = SessionManager(db)
    
    try:
        # Sử dụng mapped_subj và mapped_chap
        progress = session_manager.get_user_progress(current_user_id, mapped_subj, mapped_chap)
        original_question_id = progress.get("question_id") if progress else None    
        
        if not progress:
            current_question_id = ai_tutor.get_first_question_id(mapped_subj, mapped_chap)
            current_step = 1
        else:
            current_question_id = progress.get("question_id")
            current_step = progress.get("step", 1)
        
        question_data = ai_tutor.load_question_data(mapped_subj, mapped_chap, current_question_id)

        chat_history = session_manager.get_chat_history(
            user_id=current_user_id,
            subject=mapped_subj,
            chapter=mapped_chap
        )

        try:
            q_data = json.loads(question_data) if isinstance(question_data, str) else {}
            current_step_obj = next(
                (s for s in q_data.get("scaffolding_steps", [])
                if s.get("step_number") == current_step), {}
            )
            diagnose_context = json.dumps({
                "question_text": q_data.get("question_text", ""),
                "topic": q_data.get("topic", ""),
                "current_step": current_step,
                "step_detail": current_step_obj.get("step_detail", ""),
                "total_steps": len(q_data.get("scaffolding_steps", []))
            }, ensure_ascii=False)
        except Exception:
            diagnose_context = question_data  # fallback nếu parse lỗi

        # Bắt đầu tính giờ Diagnose
        start_diagnose_time = time.time()
        diagnose_result = ai_tutor.diagnose(
            user_message=request.message,
            chat_history=chat_history,
            json_context=diagnose_context
        )
        end_diagnose_time = time.time()
        print(f"[Log] Thời gian chẩn đoán (Groq/Llama): {end_diagnose_time - start_diagnose_time:.2f} giây - Trạng thái: {diagnose_result.cognitive_state}")

        # Lazy-loading RAG: Kích hoạt khi sinh viên có lỗi nhận thức, hỏi lý thuyết, hoặc cần lộ đáp án
        rag_context = ""
        if diagnose_result.cognitive_state in ["CONCEPTUAL_ERROR", "REQUEST_THEORY", "INCOMPLETE", "REVEAL_ANSWER"]:
            # Llama (Agentic RAG) đã sinh sẵn câu truy vấn tối ưu
            rag_query = getattr(diagnose_result, "rag_search_query", "").strip()
            
            # Lấy lesson/topic context từ question_data để enrich query
            chapter_context = ""
            try:
                question_json = json.loads(question_data) if isinstance(question_data, str) else {}
                lesson_name = question_json.get("lesson_name", "")
                topic = question_json.get("topic", "")
                chapter_context = f"{lesson_name} {topic}".strip()
            except Exception:
                pass

            # Fallback nếu Llama không sinh được query
            if not rag_query:
                rag_query = chapter_context or request.message

            # Enrich query: ghép lesson/topic context vào để embedding tìm đúng nội dung hơn
            if chapter_context and chapter_context.lower() not in rag_query.lower():
                rag_query = f"{chapter_context} {rag_query}"

            print(f"[Agentic RAG] Llama generated query: '{rag_query}'")
            rag_context = rag_service.query_context(
                subject=mapped_subj,
                query=rag_query,
                display_subject=request.subject
            )
        
        # --- FIX LOGIC NHẢY BƯỚC / NHẢY BÀI ---
        # Lấy tổng số bước của bài toán hiện tại (TRƯỚC KHI gọi Generate)
        try:
            q_json = json.loads(question_data)
            total_steps = len(q_json.get("scaffolding_steps", []))
        except:
            total_steps = 999

        # [Bug #1 Fix] Hard-check: Nếu current_step đã vượt quá tổng số bước
        # (sinh viên đang ở trạng thái "đã xong bài"), ép state thành PROBLEM_COMPLETED
        # TRƯỚC KHI gọi Gemini để Gemini sinh đúng ngữ cảnh ngay từ đầu
        if current_step > total_steps:
            diagnose_result.cognitive_state = "PROBLEM_COMPLETED"

        scaffold_manager = LearningScaffold(db)
        scaffold_instruction = scaffold_manager.get_current_instruction(
            current_step=current_step, 
            question_data=question_data
        )

        # Bắt đầu tính giờ Generate
        start_generate_time = time.time()
        persona_text = ai_tutor.load_persona(mapped_subj)
        
        generate_result = ai_tutor.generate(
            cognitive_state=diagnose_result.cognitive_state.value if hasattr(diagnose_result.cognitive_state, 'value') else diagnose_result.cognitive_state,
            emotion_state=diagnose_result.emotion_state.value if hasattr(diagnose_result.emotion_state, 'value') else diagnose_result.emotion_state,
            user_message=request.message,
            chat_history=chat_history,
            persona_text=persona_text,
            json_context=question_data,
            rag_context=rag_context,
            scaffold_instruction=scaffold_instruction
        )
        end_generate_time = time.time()
        print(f"[Log] Thời gian sinh văn bản (Gemini): {end_generate_time - start_generate_time:.2f} giây")
        print(f"[Log] TỔNG THỜI GIAN PHẢN HỒI: {end_generate_time - start_diagnose_time:.2f} giây")

        # Bóc tách dữ liệu an toàn (Tránh crash nếu AI API trả về None)
        if generate_result:
            ai_reply = generate_result.response
            if getattr(generate_result, "source_citation", ""):
                citation_text = generate_result.source_citation.strip()
                ai_reply += f"\n\n**Nguồn tài liệu:**\n{citation_text}"
            
            print(f"[AI Đánh giá Trạng thái]: {diagnose_result.cognitive_state}")

            # --- XỬ LÝ CHUYỂN BƯỚC / CHUYỂN BÀI ---

            if diagnose_result.cognitive_state == "STEP_CORRECT":
                new_step = current_step + 1

            # [Bug #2 Fix] REVEAL_ANSWER: Tăng bước lên 1.
            # Nếu bước mới vượt quá total_steps → luồng chat tiếp theo sẽ tự động
            # kích hoạt PROBLEM_COMPLETED (nhờ hard-check ở đầu) rất gọn gàng.
            elif diagnose_result.cognitive_state == "REVEAL_ANSWER":
                new_step = current_step + 1

            # NẾU XONG BÀI TOÁN -> CHỦ ĐỘNG BỐC ĐỀ MỚI
            elif diagnose_result.cognitive_state == "PROBLEM_COMPLETED":
                next_question_id = ai_tutor.get_next_question_id(mapped_subj, mapped_chap, current_question_id)
                
                if next_question_id:
                    new_question_text = ai_tutor.get_initial_question(mapped_subj, mapped_chap, next_question_id, is_first=False)
                    ai_reply = f"{ai_reply}\n\n**Bài tập tiếp theo dành cho bạn:**\n{new_question_text}"
                    new_step = 1
                    current_question_id = next_question_id
                else:
                    # [Bug #3 Fix] Hết chương: Giữ nguyên step = total_steps (không để vượt)
                    # để tránh bị kẹt vòng lặp PROBLEM_COMPLETED vô tận ở các chat tiếp theo
                    ai_reply = f"{ai_reply}\n\nChúc mừng! Bạn đã hoàn thành toàn bộ bài tập của chương này rồi!"
                    new_step = total_steps
            else:
                new_step = current_step
        else:
            ai_reply = "Xin lỗi, hệ thống AI đang gặp sự cố kết nối. Bạn vui lòng thử lại nhé!"
            new_step = current_step

        # 5. Lưu toàn bộ xuống Database
        # Lưu tin nhắn User
        session_manager.save_message(
            user_id=current_user_id, 
            subject=mapped_subj, 
            chapter=mapped_chap, 
            role="user", 
            content=request.message 
        )
        
        # Lưu phản hồi AI
        session_manager.save_message(
            user_id=current_user_id, 
            subject=mapped_subj, 
            chapter=mapped_chap, 
            role="ai", 
            content=ai_reply
        )

        # Nếu AI quyết định cho sinh viên sang bước tiếp theo, cập nhật bảng Activity
        if new_step != current_step or current_question_id != original_question_id:
            session_manager.update_progress(
                user_id=current_user_id, 
                subject=mapped_subj, 
                chapter=mapped_chap, 
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
