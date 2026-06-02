import os 
import time 
from sqlalchemy.orm import Session 
from core.session import SessionLocal
from models.document import Document 
from engine.rag_service import RAGService

def preload_txt_data():
    """
    Tự động quét và nạp các file .txt từ thư mục rag_input vào VectorDB
    """
    db = SessionLocal()
    rag_service = RAGService()
    
    # Danh sách các môn học cần nạp (Khải đảm bảo tên này khớp với thư mục trong rag_input)
    subjects = ["giai_tich_1", "triet_hoc_maclenin"]

    print(f"Đang nạp dữ liệu vào VetorDB")
    print("=" * 60)

    for subject in subjects:
        # Đường dẫn tới thư mục chứa các file .txt của môn học đó
        subject_dir = os.path.join("data", "rag_input", subject)

        if not os.path.exists(subject_dir):
            print(f"Không tìm thấy thư mục dữ liệu cho môn {subject}")
            continue 

        # Lấy danh sách tất cả file .txt trong thư mục môn học
        txt_files = sorted([f for f in os.listdir(subject_dir) if f.endswith(".txt")])
        
        if not txt_files:
            print(f"Cảnh báo: Thư mục {subject} đang trống, không có file .txt để nạp.")
            continue

        print(f"\nĐang xử lý môn: {subject.upper()} ({len(txt_files)} file)")

        for index, file_name in enumerate(txt_files):
            file_path = os.path.join(subject_dir, file_name)

            try:
                print(f"  [+] Đang Vector hóa: {file_name}")
                
                # Gọi rag_service để băm nhỏ và tạo index
                success = rag_service.index_document(file_path=file_path, subject=subject)
                
                if success: 
                    # Kiểm tra và lưu lịch sử nạp vào PostgreSQL
                    existing_doc = db.query(Document).filter(Document.filename == file_path).first()
                    if not existing_doc:
                        new_doc = Document(
                            user_id=1, # Mặc định admin hoặc user đầu tiên
                            filename=file_name,
                            subject=subject,
                            file_path=file_path,
                            status="completed"
                        )
                        db.add(new_doc)
                        db.commit()
                        print(f" Đã lưu thông tin file vào DB.")
                    else:
                        print(f" File đã tồn tại trong DB, đã cập nhật nội dung Vector mới.")
                else:
                    print(f" Lỗi khi xử lý Vector cho file: {file_name}")

                # Cơ chế chống lỗi 429 (Rate Limit) của Embedding API
                # Nghỉ ngắn giữa các file để tránh bị khóa API
                if index < len(txt_files) - 1:
                    time.sleep(5) 

            except Exception as e:
                print(f" Lỗi hệ thống khi xử lý {file_name}: {str(e)}")
                db.rollback()
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    print(" Cạn hạn mức API. Skip 60 giây để hồi phục...")
                    time.sleep(60)

    db.close()
    print("\n" + "=" * 60)
    print("DỮ LIỆU ĐÃ ĐƯỢC NẠP VÀO HỆ THỐNG")

if __name__ == "__main__":
    preload_txt_data()