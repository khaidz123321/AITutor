try:
    import fitz 
except ImportError:
    fitz = None
import os 
import re 
from .mineru_service import MinerU

# Đã bỏ tính năng tự động phát hiện toán/chữ, đồng nhất dùng MinerU + Ollama.

class DataReader:
    def __init__(self):
        self.mineru_svc = MinerU()
    


    def _normalize_mineru_output(self, text: str, file_name: str) -> str:
        """
        DỌN DẸP KẾT QUẢ MINERU:
        - Chỉ đảm bảo thẻ CHƯƠNG nằm đúng cấp 1 (#) để script auto_split cắt được file.
        - Tuyệt đối KHÔNG ép thẻ Bài/Mục/Chỉ mục bằng Regex để tránh bắt nhầm câu văn bài tập.
        """
        # 1. Nắn "CHƯƠNG" về Cấp 1 (#)
        text = re.sub(r'^#*\s*(CHƯƠNG\s+\d+.*)', r'# \1', text, flags=re.IGNORECASE | re.MULTILINE)
        
        # Đảm bảo luôn có tiêu đề Chương ở đầu để không bị lạc dữ liệu
        if not re.search(r'^#\s+CHƯƠNG', text, flags=re.IGNORECASE | re.MULTILINE):
            chuong_title = file_name.replace('.pdf', '').replace('.txt', '').replace('_', ' ').upper()
            text = f"# {chuong_title}\n\n{text}"

        # 2. Dọn dẹp khoảng trắng thừa (MinerU thỉnh thoảng sinh nhiều dòng trống)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()  

        return text

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
            
            # Gọi hàm xử lý file đơn lẻ (extract_file trả về tuple (text, needs_llm), phải unpack)
            text, _needs_llm = self.extract_file(file_path, subject)

            # Gắn thêm tiêu đề để phân biệt dữ liệu giữa các chương
            all_text += f"\n\n{'='*40}\n--- NGUỒN: {file_name} ---\n{'='*40}\n\n"
            all_text += text
            
        return all_text

    def extract_file(self, pdf_path, subject):
        """
        Hàm điều phối trích xuất chính.
        Đồng nhất sử dụng MinerU + Ollama cho tất cả các loại tài liệu (không tách chữ/toán nữa).
        Fallback sang PyMuPDF (fitz) nếu MinerU GPU server gặp sự cố mạng hoặc timeout.
        Returns: tuple (text: str, needs_llm: bool)
            - needs_llm=True  → Cần Ollama LLM khôi phục dấu sau OCR
        """
        file_name = os.path.basename(pdf_path)

        # 1. Thử dùng MinerU GPU Server trước
        raw_text = self.mineru_svc.process(pdf_path)
        
        # 2. Nếu MinerU lỗi (mạng, timeout, server tắt), tự động Fallback sang PyMuPDF (fitz) tại local
        if raw_text.startswith("LỖI"):
            print(f"[FALLBACK FITZ] MinerU gặp sự cố ({raw_text}). Đang trích xuất trực tiếp bằng PyMuPDF...")
            try:
                doc = fitz.open(pdf_path)
                text_pages = []
                for page in doc:
                    text_pages.append(page.get_text())
                doc.close()
                raw_text = "\n\n".join(text_pages)
                if not raw_text.strip():
                    return "LỖI: File PDF rỗng hoặc không thể trích xuất văn bản.", False
                print(f"[FALLBACK FITZ] Trích xuất thành công {len(raw_text)} ký tự bằng PyMuPDF.")
            except Exception as e:
                print(f"[FALLBACK FITZ] Lỗi khi đọc file bằng PyMuPDF: {e}")
                return f"LỖI: Không thể đọc file PDF: {e}", False
            
        clean_text = self._normalize_mineru_output(raw_text, file_name)
        return clean_text, True   # Luôn cần Ollama LLM khôi phục dấu

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