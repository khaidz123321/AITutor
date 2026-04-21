import os 
import time 
from sqlalchemy.orm import Session 
from core.session import SessionLocal
from models.document import Document 
from engine.rag_service import RAGService

def preload_txt_data():
    """
    Nạp trực tiếp các file .txt 
    """
    db = SessionLocal()
    rag_service = RAGService()
    files_to_process = [
        {"file_name": "data/processed_text/ket_qua_giai_tich.txt", "subject": "giai_tich_1"},
        {"file_name": "data/processed_text/ket_qua_triet_hoc.txt", "subject": "triet_hoc_maclenin"}
    ]

    print(f"Đang bắt đầu nạp tài liệu")
    for index, item in enumerate(files_to_process):
        file_path = item["file_name"]
        subject = item["subject"]

        if not os.path.exists(file_path):
            print(f"không tìm thấy file")
            continue 

        try:
            # gọi rag_service để vector hoá
            success = rag_service.index_document(file_path=file_path, subject = subject)
            if success: 
                # Lưu lịch sử nạp vào Postgre
                existing_doc = db.query(Document).filter(Document.filename == file_path).first()
                if not existing_doc:
                    new_doc = Document(
                        user_id=1,
                        filename=file_path,
                        subject=subject,
                        file_path=file_path,
                        status="completed"
                    )
                    db.add(new_doc)
                    db.commit()
                    print(f"Đã lưu thành công: {file_path}")
                else:
                    print(f"Tài liệu đã tồn tại trong DB, đã cập nhật lại nội dung Vector.")
            else:
                print("Lỗi xử lí Vector")
            # cơ chế chống lỗi 429
            if index < len(files_to_process) - 1:
                print(f"Đang hồi phục Quota API")
                time.sleep(30)
        except Exception as e:
            print(f"Lỗi hệ thống khi xử lý")
            db.rollback()
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print("Cạn hạn mức API. Timeout 60 giây để thử lại...")
                time.sleep(60)

    db.close()
    print("\nHOÀN TẤT!")

if __name__ == "__main__":
    preload_txt_data()