"""
RAG: Quản lý việc lập chỉ mục tài liệu 
Truy xuất data từ VectorDB
"""
import os
import re
from typing import List
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma 
from core.config import settings
from core.mapping import get_mapped_paths
import traceback

# Map tên môn (dạng snake_case) sang tên hiển thị tiếng Việt
SUBJECT_DISPLAY_MAP = {
    "giai_tich_1": "Giải tích 1",
    "triet_hoc_maclenin": "Triết học Mac-Lenin",
}

class RAGService:
    """
    Lớp dịch vụ chịu trách nhiệm xử lý tài liệu thô thành cơ sở dữ liệu vector
    và tìm kiếm thông tin liên quan theo môn học.
    """
    def __init__(self):
        # text-embedding-004: dùng chung GOOGLE_API_KEY trong .env, không cần key mới
        self.embeddings = HuggingFaceEmbeddings(
            model_name="bkai-foundation-models/vietnamese-bi-encoder"
        )
        # Thư mục lưu trữ cơ sở dữ liệu vector tại local
        self.persist_directory = os.path.join(settings.BASE_DIR, "data", "vector_db")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            separators=[
                "\n\n## ",    # Cắt tại tiêu đề lớn (ưu tiên cao nhất)
                "\n\n### ",   # Cắt tại tiêu đề nhỏ
                "\n\n#### ",
                "\n\n",       # Cắt tại đoạn văn trống
                "\n",         # Cắt tại xuống dòng
                ". ",         # Cắt tại câu
                " ",
                "",
            ],
            # keep_separator=True giữ lại ký tự separator trong chunk
            # giúp chunk vẫn có heading để RAG hiểu ngữ cảnh
            keep_separator=True,
        )

    def _extract_section_from_chunk(self, text: str) -> str:
        """
        Phân tích nội dung chunk để trích xuất heading Markdown gần nhất.
        Trả về chuỗi mô tả vị trí, ví dụ: '1.1.2. Các tính chất của tập số thực'
        """
        headings = re.findall(r'^#{1,4}\s+(.+)$', text, re.MULTILINE)
        if headings:
            return headings[-1].strip()
        return ""

    def _parse_chapter_from_filename(self, filename: str) -> str:
        """
        Trích số chương từ tên file.
        Ví dụ: 'giai_tich_1_chuong_2.txt' -> 'Chương 2'
                 'giai_tich_1_loi_noi_dau.txt' -> 'Lời nói đầu'
        """
        base = os.path.basename(filename).replace(".txt", "")
        # Tìm dạng _chuong_N
        match = re.search(r'_chuong_(\d+)$', base)
        if match:
            return f"Ch\u01b0\u01a1ng {match.group(1)}"
        if "loi_noi_dau" in base:
            return "L\u1eddi n\u00f3i \u0111\u1ea7u"
        return ""

    def _format_location_label(self, subject: str, filename: str, section: str) -> str:
        """
        Tạo nhãn vị trí đầy đủ theo format:
        '[Tên môn] — [Chương X] — [Mục: ...]'
        Ví dụ: 'Giải tích 1 — Chương 1 — Mục: 1.1.2. Cac tinh chat cua tap so thuc'
        """
        subject_display = SUBJECT_DISPLAY_MAP.get(subject, subject)
        chapter_display = self._parse_chapter_from_filename(filename)

        parts = [subject_display]
        if chapter_display:
            parts.append(chapter_display)
        if section:
            parts.append(f"M\u1ee5c: {section}")

        return " \u2014 ".join(parts)

    def index_document(self, file_path: str, subject: str):
        """
        Đọc file, chunking, tạo vector và lưu vào ChromaDB.
        Bổ sung metadata `section` để AI biết chunk thuộc mục nào trong giáo trình.
        """
        # Chỉ nhận xử lý file .txt từ Marker
        if not file_path.endswith(".txt"):
            print(f"Bỏ qua file: {file_path}")
            return False

        try:
            # 1. Đọc file 
            loader = TextLoader(file_path, encoding="utf-8")

            # 2. Đọc và chunking
            pages = loader.load()
            chunks = self.text_splitter.split_documents(pages)

            # 3. Bổ sung metadata `section` và `chapter` cho từng chunk
            current_section = ""
            chapter_name = self._parse_chapter_from_filename(file_path)
            
            for chunk in chunks:
                section = self._extract_section_from_chunk(chunk.page_content)
                if section:
                    current_section = section
                    
                chunk.metadata["section"] = current_section
                chunk.metadata["chapter"] = chapter_name
                chunk.metadata["subject"] = subject

            # FIX: Dịch tên môn học sang dạng không dấu để đặt tên Collection chuẩn
            safe_collection_name = f"subject_{subject}"

            # 4. Lưu vào ChromaDB với metadata đầy đủ
            vector_db = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=self.persist_directory,
                collection_name=safe_collection_name 
            )
            print(f"[RAG] Đã index {len(chunks)} chunks từ {os.path.basename(file_path)}")
            return True
        except Exception as e:
            traceback.print_exc()
            print(f"Lỗi nạp dữ liệu rag: {e}")
            return False

    def query_context(self, subject: str, query: str, top_k: int = 4, threshold: float = 55.0) -> str:
        """
        Tìm kiếm chunk liên quan nhất.
        Model bkai-foundation-models/vietnamese-bi-encoder dùng L2 distance.
        Score thực tế: 33-50 = liên quan tốt, > 55 = không liên quan.
        """
        try:
            safe_collection_name = f"subject_{subject}"
            vector_db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_name=safe_collection_name,
            )

            # Lấy kết quả kèm điểm similarity
            results_with_scores = vector_db.similarity_search_with_score(
                query, k=top_k
            )

            # Debug: in score để dễ điều chỉnh threshold
            for doc, score in results_with_scores:
                src = os.path.basename(doc.metadata.get("source", "")).replace(".txt", "")
                sec = doc.metadata.get("section", "")
                print(f"[RAG DEBUG] score={score:.4f} | {src} | {sec}")

            # Lọc chunk có score quá cao (hoàn toàn không liên quan)
            filtered = [
                doc
                for doc, score in results_with_scores
                if score < threshold
            ]
            if not filtered:
                print(f"[RAG] Không có chunk nào lọt qua threshold={threshold}. Trả về rỗng.")
                return "No relevant theoretical context found for this query in the provided documents."

            # Gộp tài liệu nếu lọt qua Threshold
            context_parts = []
            for doc in filtered:
                source = doc.metadata.get("source", "")
                section = doc.metadata.get("section", "")
                # Ưu tiên lấy subject từ metadata, fallback về tham số subject
                doc_subject = doc.metadata.get("subject", subject)

                # Tạo nhãn vị trí theo format: Tên môn — Chương X — Mục: ...
                location_label = self._format_location_label(
                    subject=doc_subject,
                    filename=source,
                    section=section
                )

                print(f"[RAG] ✓ {location_label}")
                context_parts.append(f"[Nguồn: {location_label}]\n{doc.page_content}")

            context_text = "\n\n---\n\n".join(context_parts)
            return context_text

        except Exception as e:
            # FIX: Log lỗi chi tiết để dễ debug
            print(f"[RAG] Query error: {str(e)}")
            return ""