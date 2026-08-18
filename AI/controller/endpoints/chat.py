"""
Quản lý luồng chat theo kiến trúc Single-Agent AI Tutor
Tách biệt luồng Khởi tạo (Init) và luồng Hỏi đáp (Chat)
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.session import get_db
from schemas.chat import ChatRequest, ChatResponse
from engine.ai_engine import AItutor
from engine.session_manager import SessionManager
from engine.rag_service import RAGService
from engine.scaffolding import LearningScaffold
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
def init_chat_session(
    subject: str,
    chapter: str,
    db: Session = Depends(get_db),
    x_user_id: int = Header(..., description="User ID từ Spring Boot JWT"),
    x_chapter_id: int = Header(..., description="Chapter ID từ Spring Boot")
):
    current_user_id = x_user_id
    session_manager = SessionManager(db)
    
    # Lookup course_id và order_index từ chapters table thay vì dùng subject string
    chapter_row = db.execute(
        text("SELECT course_id, order_index FROM chapters WHERE id = :cid"),
        {"cid": x_chapter_id}
    ).fetchone()
    
    if chapter_row and chapter_row[0]:
        mapped_subj = f"course_{chapter_row[0]}"
        mapped_chap = f"chuong_{chapter_row[1]}"
    else:
        mapped_subj, mapped_chap = get_mapped_paths(subject, chapter)
    
    print(f"[Chat Init] chapter_id={x_chapter_id} → mapped_subj='{mapped_subj}', mapped_chap='{mapped_chap}'")    
    try:
        progress = session_manager.get_user_progress(current_user_id, mapped_subj, mapped_chap)

        current_question_id = None
        if progress:
            current_question_id = progress.get("question_id")
            # Bỏ qua nếu là mã câu hỏi test cũ
            if current_question_id in ["COURSE_1_001", "1"]:
                current_question_id = None

        if not current_question_id:
            # 1. Thử lấy ID bài tập đầu tiên từ file JSON
            try:
                first_id = ai_tutor.get_first_question_id(mapped_subj, mapped_chap)
                if first_id and first_id not in ["COURSE_1_001", "1"]:
                    current_question_id = first_id
            except Exception:
                current_question_id = None

            # 2. Nếu file JSON chưa có hoặc chỉ là file test cũ, lấy trực tiếp từ bảng exercise_ai trong DB
            if not current_question_id:
                first_ex = db.execute(
                    text("SELECT exercise_code FROM exercise_ai WHERE chapter_id = :cid ORDER BY id ASC LIMIT 1"),
                    {"cid": x_chapter_id}
                ).fetchone()
                if first_ex and first_ex[0]:
                    current_question_id = str(first_ex[0])

            if current_question_id:
                session_manager.update_progress(current_user_id, mapped_subj, mapped_chap, current_question_id, step=1)

        # Đọc lịch sử từ bảng Spring Boot (chat_sessions + chat_messages)
        formatted_history = session_manager.get_raw_history(
            user_id=current_user_id,
            chapter_id=x_chapter_id
        )

        if not formatted_history:
            welcome_message = ""
            if current_question_id and current_question_id not in ["COURSE_1_001", "1"]:
                try:
                    loaded_msg = ai_tutor.get_initial_question(mapped_subj, mapped_chap, current_question_id)
                    if loaded_msg and "SYSTEM ERROR" not in loaded_msg and "bảo trì" not in loaded_msg and "1 + 1" not in loaded_msg:
                        welcome_message = loaded_msg
                except Exception:
                    welcome_message = ""

            # Nếu file chưa có kịch bản hoặc là câu test cũ, đọc đề bài từ bảng exercise_ai trong DB
            if not welcome_message:
                ex_row = db.execute(
                    text("SELECT question FROM exercise_ai WHERE chapter_id = :cid ORDER BY id ASC LIMIT 1"),
                    {"cid": x_chapter_id}
                ).fetchone()
                if ex_row and ex_row[0]:
                    welcome_message = (
                        f"Chào bạn! Chúng ta cùng bắt đầu bài tập này nhé:\n\n"
                        f"**Yêu cầu:** {ex_row[0]}\n\n"
                        f"Bạn đã có ý tưởng nào để bắt đầu chưa? Hãy cho tôi biết suy nghĩ của bạn nhé."
                    )
                else:
                    welcome_message = "Chào bạn! Tôi là Gia sư AI đồng hành cùng bạn trong bài học này. Hãy đặt bất kỳ câu hỏi nào về lý thuyết hoặc bài tập nhé!"

            return {
                "reply": welcome_message,
                "history": [],
                "question_id": current_question_id or "",
                "status": "success"
            }

        return {
            "reply": "",
            "history": formatted_history,
            "question_id": current_question_id or "",
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
def chat_with_tutor(
    request: ChatRequest,
    db: Session = Depends(get_db),
    x_user_id: int = Header(..., description="User ID từ Spring Boot JWT"),
    x_chapter_id: int = Header(..., description="Chapter ID từ Spring Boot")
):
    current_user_id = x_user_id
    session_manager = SessionManager(db)
    
    # Lookup course_id và order_index từ chapters table thay vì dùng subject string
    chapter_row = db.execute(
        text("SELECT course_id, order_index FROM chapters WHERE id = :cid"),
        {"cid": x_chapter_id}
    ).fetchone()
    
    if chapter_row and chapter_row[0]:
        mapped_subj = f"course_{chapter_row[0]}"
        mapped_chap = f"chuong_{chapter_row[1]}"
    else:
        mapped_subj, mapped_chap = get_mapped_paths(request.subject, request.chapter)
    
    print(f"[Chat] chapter_id={x_chapter_id} → mapped_subj='{mapped_subj}', mapped_chap='{mapped_chap}'")    
    try:
        progress = session_manager.get_user_progress(current_user_id, mapped_subj, mapped_chap)
        original_question_id = progress.get("question_id") if progress else None
        if original_question_id in ["COURSE_1_001", "1"]:
            original_question_id = None

        if not original_question_id:
            try:
                first_id = ai_tutor.get_first_question_id(mapped_subj, mapped_chap)
                if first_id and first_id not in ["COURSE_1_001", "1"]:
                    current_question_id = first_id
                else:
                    current_question_id = None
            except Exception:
                current_question_id = None
                
            if not current_question_id:
                first_ex = db.execute(
                    text("SELECT exercise_code FROM exercise_ai WHERE chapter_id = :cid ORDER BY id ASC LIMIT 1"),
                    {"cid": x_chapter_id}
                ).fetchone()
                if first_ex and first_ex[0]:
                    current_question_id = str(first_ex[0])
            current_step = 1
        else:
            current_question_id = original_question_id
            current_step = progress.get("step", 1)

        # 1. Load kịch bản từ file JSON (chỉ nhận nếu không phải file test cũ)
        question_data = ""
        if current_question_id and current_question_id not in ["COURSE_1_001", "1"]:
            try:
                loaded = ai_tutor.load_question_data(mapped_subj, mapped_chap, current_question_id)
                if loaded and "SYSTEM ERROR" not in loaded and "1 + 1" not in loaded:
                    question_data = loaded
            except Exception:
                question_data = ""

        # 2. Fallback: Nếu chưa có file JSON trên disk, nạp trực tiếp từ bảng exercise_ai do AI sinh ra trong DB!
        if not question_data:
            exercise_rows = db.execute(
                text("SELECT id, exercise_code, exercise_name, question, correct_answer, difficulty, bloom_level FROM exercise_ai WHERE chapter_id = :cid ORDER BY id ASC"),
                {"cid": x_chapter_id}
            ).fetchall()
            
            if exercise_rows:
                target_ex = None
                if current_question_id:
                    target_ex = next((ex for ex in exercise_rows if str(ex[1]) == str(current_question_id) or str(ex[0]) == str(current_question_id)), None)
                if not target_ex:
                    target_ex = exercise_rows[0]
                    current_question_id = str(target_ex[1])
                
                question_data = json.dumps({
                    "id": str(target_ex[1]),
                    "topic": target_ex[2] or "Bài tập AI",
                    "question_text": target_ex[3],
                    "full_answer": target_ex[4] or "",
                    "scaffolding_steps": [
                        {
                            "step_number": 1,
                            "step_detail": f"Phân tích đề bài và tìm hướng giải bài toán: {target_ex[3]}",
                            "hint": f"Gợi ý phương pháp giải quyết bám sát đáp án: {target_ex[4]}"
                        }
                    ]
                }, ensure_ascii=False)

        # Đọc lịch sử chat từ bảng Spring Boot
        chat_history = session_manager.get_chat_history(
            user_id=current_user_id,
            chapter_id=x_chapter_id
        )

        total_steps = 0
        current_step_obj = {}
        if question_data:
            try:
                q_data = json.loads(question_data)
                scaffold_steps = q_data.get("scaffolding_steps", [])
                total_steps = len(scaffold_steps)
                current_step_obj = next(
                    (s for s in scaffold_steps if s.get("step_number") == current_step), {}
                )
                diagnose_context = json.dumps({
                    "question_text": q_data.get("question_text", ""),
                    "topic": q_data.get("topic", ""),
                    "current_step": current_step,
                    "step_detail": current_step_obj.get("step_detail", ""),
                    "total_steps": total_steps
                }, ensure_ascii=False)
            except Exception:
                diagnose_context = json.dumps({
                    "subject": mapped_subj,
                    "chapter": mapped_chap,
                    "context": "General Course Chat & Q&A"
                }, ensure_ascii=False)
        else:
            diagnose_context = json.dumps({
                "subject": mapped_subj,
                "chapter": mapped_chap,
                "context": "Hỏi đáp lý thuyết và bài tập về chương học này"
            }, ensure_ascii=False)

        # Bắt đầu tính giờ Diagnose
        start_diagnose_time = time.time()
        subject_scope = ai_tutor.load_subject_scope(mapped_subj)
        diagnose_result = ai_tutor.diagnose(
            user_message=request.message,
            chat_history=chat_history,
            json_context=diagnose_context,
            subject_scope=subject_scope
        )
        end_diagnose_time = time.time()
        print(f"[Log] Thời gian chẩn đoán (Groq/Llama): {end_diagnose_time - start_diagnose_time:.2f} giây - Trạng thái: {diagnose_result.cognitive_state}")

        # Lazy-loading RAG: Kích hoạt khi sinh viên hỏi lý thuyết, lỗi nhận thức, hoặc hỏi bài khi chưa có question bank
        rag_context = ""
        needs_rag = (
            diagnose_result.cognitive_state in ["CONCEPTUAL_ERROR", "REQUEST_THEORY", "INCOMPLETE", "REVEAL_ANSWER", "REQUEST_HINT"]
            or (not question_data and diagnose_result.cognitive_state != "VAGUE_OR_OFFTOPIC")
        )

        if needs_rag:
            rag_query = getattr(diagnose_result, "rag_search_query", "").strip()
            
            chapter_context = ""
            if question_data:
                try:
                    question_json = json.loads(question_data)
                    lesson_name = question_json.get("lesson_name", "")
                    topic = question_json.get("topic", "")
                    chapter_context = f"{lesson_name} {topic}".strip()
                except Exception:
                    pass

            if not rag_query:
                rag_query = chapter_context or request.message

            if chapter_context and chapter_context.lower() not in rag_query.lower():
                rag_query = f"{chapter_context} {rag_query}"

            print(f"[Agentic RAG] Query: '{rag_query}'")
            rag_context = rag_service.query_context(
                subject=mapped_subj,
                query=rag_query,
                display_subject=request.subject
            )
        
        # Chỉ kiểm tra hoàn thành nếu bài tập có các bước scaffolding thực tế (> 0)
        if total_steps > 0 and current_step > total_steps:
            diagnose_result.cognitive_state = "PROBLEM_COMPLETED"

        scaffold_instruction = ""
        if question_data and total_steps > 0:
            scaffold_manager = LearningScaffold(db)
            scaffold_instruction = scaffold_manager.get_current_instruction(
                current_step=current_step, 
                question_data=question_data
            )
        else:
            scaffold_instruction = "Giải thích rõ ràng, chuẩn xác theo phương pháp sư phạm, giải đáp trọng tâm câu hỏi của sinh viên."

        # Bắt đầu tính giờ Generate
        start_generate_time = time.time()
        persona_text = ai_tutor.load_persona(mapped_subj, ai_persona_override=request.ai_persona)
        
        generate_result = ai_tutor.generate(
            cognitive_state=diagnose_result.cognitive_state.value if hasattr(diagnose_result.cognitive_state, 'value') else diagnose_result.cognitive_state,
            emotion_state=diagnose_result.emotion_state.value if hasattr(diagnose_result.emotion_state, 'value') else diagnose_result.emotion_state,
            user_message=request.message,
            chat_history=chat_history,
            persona_text=persona_text,
            json_context=question_data or diagnose_context,
            rag_context=rag_context,
            scaffold_instruction=scaffold_instruction
        )
        end_generate_time = time.time()
        print(f"[Log] Thời gian sinh văn bản (Gemini): {end_generate_time - start_generate_time:.2f} giây")
        print(f"[Log] TỔNG THỜI GIAN PHẢN HỒI: {end_generate_time - start_diagnose_time:.2f} giây")

        # Bóc tách dữ liệu an toàn
        if generate_result:
            ai_reply = generate_result.response
            if getattr(generate_result, "source_citation", ""):
                citation_text = generate_result.source_citation.strip()
                citation_text = citation_text.replace('\\n', '\n').strip()
                if citation_text:
                    ai_reply += f"\n\n**Nguồn tài liệu:** {citation_text}"
            
            print(f"[AI Đánh giá Trạng thái]: {diagnose_result.cognitive_state}")

            new_step = current_step
            # --- XỬ LÝ CHUYỂN BƯỚC / CHUYỂN BÀI (Chỉ khi có bài tập cụ thể với total_steps > 0) ---
            if total_steps > 0:
                if diagnose_result.cognitive_state in ["STEP_CORRECT", "REVEAL_ANSWER"]:
                    new_step = current_step + 1

                elif diagnose_result.cognitive_state == "PROBLEM_COMPLETED":
                    next_question_id = None
                    try:
                        next_question_id = ai_tutor.get_next_question_id(mapped_subj, mapped_chap, current_question_id)
                    except Exception:
                        pass
                    
                    # Nếu file JSON không có bài tiếp theo, tìm trong bảng exercise_ai
                    if not next_question_id:
                        next_ex_row = db.execute(
                            text("SELECT exercise_code, question FROM exercise_ai WHERE chapter_id = :cid AND exercise_code > :code ORDER BY exercise_code ASC LIMIT 1"),
                            {"cid": x_chapter_id, "code": current_question_id}
                        ).fetchone()
                        if next_ex_row:
                            next_question_id = str(next_ex_row[0])
                            new_question_text = next_ex_row[1]
                            ai_reply = f"{ai_reply}\n\n**Bài tập tiếp theo dành cho bạn:**\n{new_question_text}"
                            new_step = 1
                            current_question_id = next_question_id
                    
                    if next_question_id and not next_question_id.startswith("GT1_") and not next_question_id.startswith("COURSE_"):
                        new_question_text = ai_tutor.get_initial_question(mapped_subj, mapped_chap, next_question_id, is_first=False)
                        ai_reply = f"{ai_reply}\n\n**Bài tập tiếp theo dành cho bạn:**\n{new_question_text}"
                        new_step = 1
                        current_question_id = next_question_id
                    elif not next_question_id:
                        ai_reply = f"{ai_reply}\n\nChúc mừng! Bạn đã hoàn thành toàn bộ bài tập của chương này rồi!"
                        new_step = total_steps
        else:
            ai_reply = "Xin lỗi, hệ thống AI đang gặp sự cố kết nối. Bạn vui lòng thử lại nhé!"
            new_step = current_step

        # Cập nhật tiến độ nếu có question_id và có thay đổi
        if current_question_id and (new_step != current_step or current_question_id != original_question_id):
            session_manager.update_progress(
                user_id=current_user_id,
                subject=mapped_subj,
                chapter=mapped_chap,
                question_id=current_question_id,
                step=new_step
            )

        return ChatResponse(reply=ai_reply, status="success")

    except Exception as e:
        db.rollback()
        print(f"Chat API Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="The AI Tutor engine encountered an error. Please try again later."
        )
