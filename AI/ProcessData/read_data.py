import fitz 
import os 
from .marker_service import MarkerService

class DataReader:
    def __init__(self):
        self.marker_svc = MarkerService()
        self.math_heavy_subjects = ["giai_tich_1", "dai_so", "xac_suat_thong_ke"]

    def extract_folder(self, folder_path, subject):
        """
        Nhận đường dẫn thư mục, tự động quét và gom toàn bộ text của các file PDF bên trong.
        """
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return f"Không tìm thấy thư mục '{folder_path}'"

        # Quét tất cả file .pdf trong thư mục và SẮP XẾP theo tên (để đúng thứ tự chương)
        pdf_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.pdf')])

        if not pdf_files:
            return f"Không tìm thấy file PDF nào trong thư mục '{folder_path}'"

        print(f"\n Đã tìm thấy {len(pdf_files)} FILE TRONG THƯ MỤC '{subject}'")
        print("-" * 50)

        all_text = ""
        
        # Lặp qua từng file để xử lý
        for file_name in pdf_files:
            file_path = os.path.join(folder_path, file_name)
            print(f"Đang xử lý: {file_name}")
            
            # Gọi hàm xử lý file đơn lẻ
            text = self.extract_file(file_path, subject)
            
            # Gắn thêm tiêu đề để phân biệt dữ liệu giữa các chương
            all_text += f"\n\n{'='*40}\n--- NGUỒN: {file_name} ---\n{'='*40}\n\n"
            all_text += text
            
        return all_text

    def extract_file(self, pdf_path, subject):
        """
        Trích xuất văn bản thuần tuý từ pdf
        """
        # 1. Nếu là môn chứa toán học -> chuyển sang Marker Service (Cloud)
        if subject in self.math_heavy_subjects:
            print(f"Môn '{subject}'. Giao file cho MarkerService xử lý...")
            return self.marker_svc.process(pdf_path)
        
        # 2. Nếu là môn chữ (Triết học, Lịch sử...) -> Tự đọc bằng PyMuPDF
        else:
            try:
                doc = fitz.open(pdf_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            except Exception as e:
                return f"Lỗi PyMuPDF cục bộ: {str(e)}"

    def get_file_metadata(self, pdf_path: str): 
        """
        Lấy metadata của file
        """
        if not os.path.exists(pdf_path):
            return None 
        doc = fitz.open(pdf_path)
        meta =  doc.metadata
        pages = len(doc)
        doc.close()
        return {"pages": pages, "meta": meta}