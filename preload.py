import os
import time  # Thêm thư viện để dùng hàm sleep
from sqlalchemy.orm import Session
from core.session import SessionLocal
from models.document import Document
from engine.rag_service import RAGService

def preload_with_backoff():
    """
    Quét thư mục data, nạp tài liệu và có khoảng nghỉ 
    để tránh lỗi 429 RESOURCE_EXHAUSTED.
    """
    db = SessionLocal()
    rag_service = RAGService()
    source_path = "data"
    
    if not os.path.exists(source_path):
        print(f"❌ Không tìm thấy thư mục: {source_path}")
        return

    # Lấy danh sách file PDF/Docx trong folder data
    files = [f for f in os.listdir(source_path) 
             if os.path.isfile(os.path.join(source_path, f)) and f.endswith(('.pdf', '.docx'))]
    
    if not files:
        print(f"ℹ️ Không có tài liệu nào để nạp trong {source_path}")
        return

    print(f"🚀 Bắt đầu nạp {len(files)} tài liệu. Quy tắc: Nghỉ 15 giây giữa mỗi file.")

    for index, file_name in enumerate(files):
        file_path = os.path.join(source_path, file_name)
        subject = os.path.splitext(file_name)[0]
        
        try:
            print(f"\n📖 [{index + 1}/{len(files)}] AI đang đọc môn {subject}: {file_name}...")
            
            # 1. Gọi RAG Service để vector hóa
            success = rag_service.index_document(file_path=file_path, subject=subject)
            
            if success:
                # 2. Lưu vào PostgreSQL
                existing_doc = db.query(Document).filter(Document.filename == file_name).first()
                if not existing_doc:
                    new_doc = Document(
                        user_id=1,
                        filename=file_name,
                        subject=subject,
                        file_path=file_path,
                        status="completed"
                    )
                    db.add(new_doc)
                    db.commit()
                    print(f"✅ Preload thành công: {file_name}")
                else:
                    print(f"⏩ Đã có trong DB, AI đã cập nhật lại nội dung.")
            else:
                print(f"❌ Lỗi xử lý AI cho: {file_name} (Kiểm tra lại API Key hoặc File)")

            # BƯỚC QUAN TRỌNG: Nghỉ giữa các file để tránh bị Google chặn (429)
            if index < len(files) - 1: # Không cần nghỉ sau file cuối cùng
                print(f"⏳ Đang nghỉ 15 giây để hồi phục Quota API...")
                time.sleep(60) 

        except Exception as e:
            print(f"⚠️ Lỗi hệ thống khi xử lý {file_name}: {str(e)}")
            db.rollback()
            # Nếu gặp lỗi cạn hạn mức, nghỉ lâu hơn (30s) trước khi tiếp tục file sau
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print("🚨 Cạn hạn mức API! Nghỉ 30 giây để thử lại...")
                time.sleep(60)

    db.close()
    print("\n✨ Hoàn tất! Kho tri thức của Khải đã sẵn sàng.")

if __name__ == "__main__":
    preload_with_backoff()