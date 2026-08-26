"""
Quan lí tải tài liệu, lưu -> server, cất tài liệu -> dtb
"""
import os
import glob
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List
from core.session import get_db, SessionLocal
from core.config import settings
from schemas.document import DocumentResponse
from models.document import Document
from engine.rag_service import RAGService

import queue
import threading

router = APIRouter()
rag_service = RAGService()
UPLOAD_DIR = "uploads/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Hàng đợi xử lý file tuần tự để chống sập CPU
document_queue = queue.Queue()

def document_worker():
    """
    Worker chạy ngầm liên tục lấy file từ Hàng đợi ra để xử lý từng file một (Sequential).
    Tránh trường hợp 3 file upload lên cùng lúc chạy 3 model AI làm CPU vọt lên 100%.
    """
    while True:
        task = document_queue.get()
        if task is None:
            break
        doc_id, file_path, safe_filename, subject = task
        try:
            print(f"[QUEUE] Đang bắt đầu xử lý file {safe_filename}...")
            process_document_background(doc_id, file_path, safe_filename, subject)
            print(f"[QUEUE] Đã xử lý xong file {safe_filename}!")
        except Exception as e:
            print(f"[QUEUE] Lỗi xử lý file {safe_filename}: {e}")
        finally:
            document_queue.task_done()

# Khởi động worker ngay khi load router
threading.Thread(target=document_worker, daemon=True).start()

def _update_course_status(subject: str, status: str):
    """
    Cập nhật ocr_status của course bằng session riêng biệt để tránh lỗi stale session.
    Dùng CAST để đảm bảo so sánh đúng kiểu dữ liệu.
    """
    db = SessionLocal()
    try:
        result = db.execute(text("""
            UPDATE courses 
            SET ocr_status = :status 
            WHERE LOWER(REPLACE(title, ' ', '_')) = :subject 
               OR CONCAT('course_', id) = :subject
        """), {"status": status, "subject": subject})
        db.commit()
        matched = result.rowcount
        print(f"[STATUS] Đã cập nhật ocr_status={status} cho subject='{subject}' ({matched} dòng)")
        if matched == 0:
            print(f"[STATUS] CẢNH BÁO: Không tìm thấy course nào với subject='{subject}'!")
    except Exception as e:
        db.rollback()
        print(f"[STATUS] Lỗi cập nhật ocr_status={status} cho subject='{subject}': {e}")
    finally:
        db.close()

def _update_doc_status(doc_id: int, status: str):
    """
    Cập nhật trạng thái document bằng session riêng biệt.
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = status
            db.commit()
            print(f"[STATUS] Đã cập nhật document #{doc_id} -> status='{status}'")
    except Exception as e:
        db.rollback()
        print(f"[STATUS] Lỗi cập nhật document #{doc_id}: {e}")
    finally:
        db.close()

def process_document_background(doc_id: int, file_path: str, safe_filename: str, subject: str):
    """
    Tiến trình chạy ngầm: OCR -> Clean Garbage -> Clean LLM -> Chunking -> VectorDB
    Mỗi bước cập nhật DB dùng session riêng biệt để tránh stale transaction.
    """
    # Bước 1: Cập nhật trạng thái PROCESSING
    _update_doc_status(doc_id, "processing")
    _update_course_status(subject, "PROCESSING")

    success = False
    try:
        if file_path.endswith(".pdf"):
            from ProcessData.read_data import DataReader
            from ProcessData.auto_split import auto_split_large_files
            from ProcessData.clean.clean_rag_input import clean_file as clean_garbage
            from ProcessData.clean.clean_ocr_llm import process_file as clean_with_llm, load_checkpoint
            
            reader = DataReader()
            print(f"[BACKGROUND] Đang gọi DataReader để xử lý PDF: {file_path}")
            text_result, needs_llm = reader.extract_file(file_path, subject)
            
            if text_result.startswith("LỖI"):
                print(f"[BACKGROUND] Lỗi Trích xuất: {text_result}")
                success = False
            else:
                rag_input_dir = os.path.join(settings.BASE_DIR, "data", "rag_input", subject)
                os.makedirs(rag_input_dir, exist_ok=True)
                
                # --- XÓA DỮ LIỆU CŨ KHI RE-UPLOAD ---
                try:
                    old_files = glob.glob(os.path.join(rag_input_dir, "*.txt")) + glob.glob(os.path.join(rag_input_dir, "*.json"))
                    for old_f in old_files:
                        os.remove(old_f)
                    print(f"[BACKGROUND] Đã xóa {len(old_files)} file dữ liệu/checkpoint cũ của môn {subject}.")
                    if hasattr(rag_service, 'clear_subject'):
                        rag_service.clear_subject(subject)
                except Exception as e:
                    print(f"[BACKGROUND] Cảnh báo lỗi khi xóa dữ liệu cũ: {e}")
                # --------------------------------------
                
                base_txt_filename = safe_filename.replace(".pdf", ".txt")
                rag_input_path = os.path.join(rag_input_dir, base_txt_filename)
                
                with open(rag_input_path, "w", encoding="utf-8") as f:
                    f.write(text_result)
                
                print("[BACKGROUND] Đang chạy auto_split_large_files...")
                auto_split_large_files(subject=subject)
                
                # Lấy toàn bộ các file .txt trong thư mục môn học (gồm các file chuong_*.txt vừa tách từ auto_split)
                generated_files = sorted([
                    f for f in glob.glob(os.path.join(rag_input_dir, "*.txt"))
                    if not os.path.basename(f).startswith("test_")
                ])
                
                if not generated_files:
                    print(f"[BACKGROUND] Không tìm thấy file được tách, kiểm tra file gốc: {rag_input_path}")
                    if os.path.exists(rag_input_path):
                        generated_files = [rag_input_path]
                        print(f"[BACKGROUND] Sử dụng file gốc để xử lý: {rag_input_path}")
                    else:
                        print(f"[BACKGROUND] File gốc không tồn tại: {rag_input_path}")
                
                print(f"[BACKGROUND] Sẽ xử lý {len(generated_files)} file(s): {[os.path.basename(f) for f in generated_files]}")
                
                print("[BACKGROUND] Đang khởi tạo Checkpoint LLM...")
                checkpoint = load_checkpoint(subject)
                
                success_count = 0
                fail_count = 0
                for gen_file in generated_files:
                    print(f"\n[BACKGROUND] [CLEAN OCR] Đang dọn rác cho: {gen_file}")
                    clean_garbage(gen_file)
                    
                    if needs_llm:
                        print(f"[BACKGROUND] [CLEAN LLM] Đang gọi Ollama khôi phục dấu: {gen_file}")
                        file_key = os.path.basename(gen_file)
                        clean_with_llm(gen_file, file_key, checkpoint)
                    else:
                        print(f"[BACKGROUND] [SKIP LLM] Môn chữ - PyMuPDF đã đủ tiếng Việt, bỏ qua Ollama")
                    
                    print(f"\n[BACKGROUND] [INDEX RAG] Đang index vào RAG: {gen_file}")
                    if rag_service.index_document(file_path=gen_file, subject=subject):
                        success_count += 1
                    else:
                        fail_count += 1
                        print(f"[BACKGROUND] CẢNH BÁO: Index RAG thất bại cho {os.path.basename(gen_file)}")
                
                total = len(generated_files)
                print(f"[BACKGROUND] Kết quả index: {success_count}/{total} file thành công, {fail_count} thất bại")
                # COMPLETED nếu ít nhất 1 file được index thành công
                # Nếu 0/N thành công -> FAILED (RAG hoàn toàn không hoạt động)
                success = (success_count > 0)
        
        elif file_path.endswith(".txt"):
            success = rag_service.index_document(file_path=file_path, subject=subject)

    except Exception as e:
        print(f"[BACKGROUND] Lỗi nghiêm trọng khi xử lý {safe_filename}: {str(e)}")
        success = False

    # Bước cuối: Cập nhật trạng thái hoàn tất (dùng session riêng - tránh stale)
    final_status = "COMPLETED" if success else "FAILED"
    final_doc_status = "completed" if success else "failed"
    print(f"[BACKGROUND] Kết quả xử lý {safe_filename}: success={success} -> {final_status}")
    _update_doc_status(doc_id, final_doc_status)
    _update_course_status(subject, final_status)

@router.post("/", response_model=DocumentResponse)
def upload_document(
    background_tasks: BackgroundTasks,
    subject: str = Form(..., description="Subject identifier in lowercase snake_case (e.g., 'giai_tich_1')"),
    file: UploadFile = File(..., description="The physical document file (PDF, DOCX, etc.)"),
    db: Session = Depends(get_db),
    x_user_id: int = Header(..., description="User ID từ Spring Boot JWT")
):
    current_user_id = x_user_id

    try:
        if not file.filename.lower().endswith((".pdf", ".txt")):
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ xử lý file .pdf hoặc .txt")

        safe_filename = file.filename.lower().replace(" ", "_")
        file_path = os.path.join(UPLOAD_DIR, safe_filename)

        # lưu file (chạy trên threadpool của FastAPI do dùng 'def', không chặn event loop)
        with open(file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)

        # tạo bản ghi trong dtb
        new_doc = Document(
            user_id=current_user_id,
            filename=safe_filename,
            subject=subject.lower(), 
            file_path=file_path,
            status="pending" 
        )

        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        # Cập nhật ocr_status của course thành PENDING (dùng helper riêng tránh stale session)
        _update_course_status(subject.lower(), "PENDING")

        # Đẩy vào Hàng đợi xử lý tuần tự (Worker Queue) để bảo vệ CPU
        print(f"[API] Đã nhận file {safe_filename}. Đang đưa vào hàng đợi...")
        document_queue.put((new_doc.id, file_path, safe_filename, subject.lower()))
        
        # Trả về kết quả ngay lập tức
        return new_doc

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Document Upload Error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to upload and store the document metadata."
        )

@router.get("/", response_model=List[DocumentResponse])
def list_student_documents(
    db: Session = Depends(get_db),
    x_user_id: int = Header(..., description="User ID từ Spring Boot JWT")
):
    """
    Lấy danh sách tài liệu đã upload của người dùng hiện tại
    """
    current_user_id = x_user_id
    
    documents = db.query(Document).filter(
        Document.user_id == current_user_id
    ).all()
    
    return documents