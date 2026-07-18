import os
import sys
from dotenv import load_dotenv
from auto_split import auto_split_large_files
from clean.clean_data import clean_rag_input as clean_headers_footers
from clean.clean_rag_input import main as clean_ocr_garbage
from clean.clean_ocr_llm import main as clean_ocr_with_llm

# 1. TỰ ĐỘNG XÁC ĐỊNH ĐƯỜNG DẪN TUYỆT ĐỐI
# Lấy thư mục chứa chính file test_function.py này (D:\Project\AITutor\AI)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Lấy thư mục gốc của toàn bộ dự án (D:\Project\AITutor)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

# Thêm PROJECT_ROOT vào hệ thống để tìm được module ProcessData
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from ProcessData.read_data import DataReader
from reindex_rag import reindex_all

load_dotenv()

def run_test():
    AI_DIR = os.path.dirname(CURRENT_DIR)
    DATA_BASE_DIR = os.path.join(AI_DIR, "data")
    
    print(f"KHỞI ĐỘNG TRÍCH XUẤT TẠI: {DATA_BASE_DIR}")
    print("=" * 60)
    
    reader = DataReader()
    
    # Danh sách môn học
    subjects = ["giai_tich_1", "triet_hoc_maclenin"] # Tạm bỏ giai_tich vì chưa được chuẩn hoá
    
    for subject in subjects:
        # Đường dẫn PDF gốc: D:\Project\AITutor\AI\data\subject
        pdf_folder = os.path.join(DATA_BASE_DIR, subject) 
        
        # Đường dẫn Output: D:\Project\AITutor\AI\data\rag_input\subject
        output_dir = os.path.join(DATA_BASE_DIR, "rag_input", subject)
        
        os.makedirs(output_dir, exist_ok=True)
        
        if os.path.exists(pdf_folder):
            print(f"\nĐANG XỬ LÝ MÔN: {subject.upper()}")
            
            pdf_files = sorted([f for f in os.listdir(pdf_folder) if f.endswith('.pdf')])
            
            if not pdf_files:
                print(f"Thư mục trống: {pdf_folder}")
                continue
                
            for pdf_file in pdf_files:
                pdf_path = os.path.join(pdf_folder, pdf_file)
                print(f"Đang trích xuất: {pdf_file}...")
                
                # Gọi hàm đọc (sẽ tự động dùng cache hoặc gửi lên Colab/PyMuPDF)
                content = reader.extract_file(pdf_path, subject)
                if content.startswith("LỖI"):
                    print(f"⚠️ ĐÃ BỎ QUA FILE {pdf_file} DO: {content}")
                    continue
                
                # Lưu vào thư mục rag_input tương ứng
                txt_filename = pdf_file.replace(".pdf", ".txt")
                output_path = os.path.join(output_dir, txt_filename)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)
                    
                print(f"Đã lưu: {output_path}")
        else:
            print(f"KHÔNG TÌM THẤY: {pdf_folder}")

    print("\n HOÀN TẤT TRÍCH XUẤT! Đang tiến hành tách chương...")
    auto_split_large_files()
    
    print("\n TIẾN HÀNH DỌN DẸP RÁC OCR VÀ HEADER/FOOTER...")
    clean_headers_footers() # Xóa header/footer PTIT
    clean_ocr_garbage()     # Xóa rác OCR và mục lục/tài liệu tham khảo
    
    print("\n TIẾN HÀNH KHÔI PHỤC DẤU TIẾNG VIỆT VÀ SỬA LỖI BẰNG LLM...")
    clean_ocr_with_llm()
    
    print("\n TIẾN HÀNH NHÚNG DỮ LIỆU (EMBEDDING) VÀO VECTOR DB...")
    reindex_all()
    
    print("\n TẤT CẢ HOÀN TẤT! Toàn bộ pipeline đã tự động chạy từ PDF -> Vector DB thành công.")

if __name__ == "__main__":
    run_test()