"""
RAG: Quản lý việc lập chỉ mục tài liệu 
Truy xuất data từ VectorDB
"""
import os
import re
import unicodedata
from typing import List
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma 
from core.config import settings
from core.mapping import get_mapped_paths
import traceback


# NOTE: Dùng E5Embeddings với prefix "query:"/"passage:" để tận dụng tối đa
# khả năng phân biệt câu hỏi và đoạn văn bản của multilingual-e5-large.
# ⚠️  Sau khi bật E5Embeddings, PHẢI chạy lại reindex_rag.py để re-embed toàn bộ tài liệu!

class E5Embeddings:
    def __init__(self, base: HuggingFaceEmbeddings):
        self.base = base

    def embed_documents(self, texts: list) -> list:
        return self.base.embed_documents(["passage: " + t for t in texts])

    def embed_query(self, text: str) -> list:
        return self.base.embed_query("query: " + text)

# Map tên môn (dạng snake_case) sang tên hiển thị tiếng Việt đã bị xóa vì thay thế bằng cấu hình động

class RAGService:
    """
    Lớp dịch vụ chịu trách nhiệm xử lý tài liệu thô thành cơ sở dữ liệu vector
    và tìm kiếm thông tin liên quan theo môn học.
    """
    _shared_embeddings = None

    def __init__(self):
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

    @property
    def embeddings(self):
        if self.__class__._shared_embeddings is None:
            print("[RAG] Đang tải mô hình Embedding vào RAM (Chỉ tải 1 lần)...", flush=True)
            _base = HuggingFaceEmbeddings(
                model_name=os.path.join(settings.BASE_DIR, "multilingual-e5-large-finetuned"),
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            self.__class__._shared_embeddings = E5Embeddings(_base)
            print("[RAG] Tải mô hình thành công!", flush=True)
        return self.__class__._shared_embeddings


    def _normalize_query(self, text: str) -> str:
        """
        Bỏ dấu tiếng Việt trong query để khớp với nội dung OCR không dấu trong DB.
        Ví dụ: 'định nghĩa đạo hàm' → 'dinh nghia dao ham'
        """
        # NFD: tách ký tự + combining diacritics
        nfd = unicodedata.normalize('NFD', text)
        # Loại bỏ tất cả combining diacritical marks
        ascii_text = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
        # Đ → D, d → d (chữ đ trong NFD không bị bỏ dấu bởi bước trên)
        ascii_text = ascii_text.replace('đ', 'd').replace('Đ', 'D')
        return ascii_text

    def _extract_section_from_chunk(self, text: str) -> str:
        """
        Phân tích nội dung chunk để trích xuất heading Markdown.
        Lấy heading ĐẦU TIÊN trong chunk (không phải cuối) để đảm bảo
        section metadata phản ánh đúng nội dung chính của chunk đó.
        Ví dụ: '2.1.2. Hàm số chẵn, lẻ'
        """
        # Priority 1: Markdown heading chuẩn hoặc thiếu khoảng trắng sau # (do OCR)
        headings = re.findall(r'^#{1,4}\s*(.+?)$', text, re.MULTILINE)
        if headings:
            return headings[0].strip()  # heading ĐẦU TIÊN, không phải cuối
        # Priority 2: Số mục dạng "2.1.2. Tên mục" — OCR đôi khi không sinh ra #
        section_nums = re.findall(r'^(\d+(?:\.\d+)+\.?\s+.+?)$', text, re.MULTILINE)
        if section_nums:
            return section_nums[0].strip()
        # Priority 3: Dòng dạng "CHUONG X." hoặc tiêu đề viết hoa toàn bộ
        caps = re.findall(r'^([A-Z][A-Z0-9\s\.]{4,})$', text, re.MULTILINE)
        if caps:
            return caps[0].strip()
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

    def _format_location_label(self, subject_display: str, filename: str, section: str) -> str:
        """
        Tạo nhãn vị trí đầy đủ theo format:
        '[Tên môn] — [Chương X] — [Mục: ...]'
        Ví dụ: 'Giải tích 1 — Chương 1 — Mục: 1.1.2. Cac tinh chat cua tap so thuc'
        """
        chapter_display = self._parse_chapter_from_filename(filename)

        parts = [subject_display]
        if chapter_display:
            parts.append(chapter_display)
        if section:
            parts.append(f"M\u1ee5c: {section}")

        return " \u2014 ".join(parts)

    def clear_subject(self, subject: str) -> bool:
        """
        Xóa toàn bộ vector DB collection của một môn học.
        Hữu ích khi giáo viên upload đè file mới, tránh duplicate dữ liệu.
        """
        try:
            safe_name = unicodedata.normalize('NFKD', subject).encode('ASCII', 'ignore').decode('utf-8')
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', safe_name).lower()
            safe_collection_name = f"subject_{safe_name}"

            vector_db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_name=safe_collection_name
            )
            vector_db.delete_collection()
            print(f"[RAG] Đã xóa toàn bộ VectorDB collection: {safe_collection_name}")
            return True
        except Exception as e:
            print(f"[RAG] Không thể xóa VectorDB collection của môn {subject} (có thể chưa tồn tại): {e}")
            return False

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
                else:
                    # Chunk nhỏ không có heading riêng (bị merge với chunk trước/sau)
                    # → Inject section header vào đầu nội dung để embedding model
                    # có thể nhận diện đúng chủ đề khi tìm kiếm
                    if current_section:
                        chunk.page_content = f"[Mục: {current_section}]\n{chunk.page_content}"
                    
                chunk.metadata["section"] = current_section
                chunk.metadata["chapter"] = chapter_name
                chunk.metadata["subject"] = subject

            # FIX: Dịch tên môn học sang dạng không dấu để đặt tên Collection chuẩn
            safe_name = unicodedata.normalize('NFKD', subject).encode('ASCII', 'ignore').decode('utf-8')
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', safe_name).lower()
            safe_collection_name = f"subject_{safe_name}"

            # 4. Lưu vào ChromaDB với metadata đầy đủ
            # collection_metadata: dùng cosine distance (nhất quán với normalize_embeddings=True)
            # score 0.0 = giống hệt, 1.0 = khác hoàn toàn (cosine distance)
            vector_db = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=self.persist_directory,
                collection_name=safe_collection_name,
                collection_metadata={"hnsw:space": "cosine"},
            )
            print(f"[RAG] Đã index {len(chunks)} chunks từ {os.path.basename(file_path)}")
            return True
        except Exception as e:
            traceback.print_exc()
            print(f"Lỗi nạp dữ liệu rag: {e}")
            return False

    def query_context(self, subject: str, query: str, top_k: int = 6, threshold: float = 0.72, display_subject: str = "") -> str:
        """
        
        NOTE: Không filter theo chapter vì frontend chapters (5 chương) không tương ứng
        với cấu trúc file text (4 chương sách) — thù dựa vào semantic search để tìm đúng nội dung.
        """
        try:
            safe_name = unicodedata.normalize('NFKD', subject).encode('ASCII', 'ignore').decode('utf-8')
            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '', safe_name).lower()
            safe_collection_name = f"subject_{safe_name}"
            vector_db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_name=safe_collection_name,
                collection_metadata={"hnsw:space": "cosine"},
            )

            # Tìm kiếm trên toàn bộ collection, không filter chapter
            # Lấy nhiều hơn (top_k * 3) để bù trừ duplicate section, sau đó deduplicate
            # Chuẩn hóa query (bỏ dấu) để khớp với text OCR bị mất dấu trong DB

            print(f"[RAG] Query: '{query}'")
            raw_k = top_k * 3
            results_with_scores = vector_db.similarity_search_with_score(query, k=raw_k)

            # Debug: in score để dễ điều chỉnh threshold
            for doc, score in results_with_scores:
                src = os.path.basename(doc.metadata.get("source", "")).replace(".txt", "")
                sec = doc.metadata.get("section", "")
                print(f"[RAG DEBUG] score={score:.4f} | {src} | {sec}")

            # Lọc chunk liên quan: cosine distance thấp = liên quan (giữ score < threshold)
            # ChromaDB trả về cosine distance: 0.0 = giống hệt, 2.0 = hoàn toàn khác
            filtered = [doc for doc, score in results_with_scores if score < threshold]
            if not filtered:
                print(f"[RAG] Không có chunk nào lọt qua threshold={threshold}. Trả về rỗng.")
                return "No relevant theoretical context found for this query in the provided documents."

            # Gộp tài liệu nếu lọt qua Threshold
            context_parts = []
            seen_sections = set()  # Loại bỏ duplicate cùng section
            for doc in filtered:
                source = doc.metadata.get("source", "")
                section = doc.metadata.get("section", "")
                doc_subject = doc.metadata.get("subject", subject)

                # Tạo nhãn vị trí theo format: Tên môn — Chương X — Mục: ...
                location_label = self._format_location_label(
                    subject_display=display_subject if display_subject else doc_subject,
                    filename=source,
                    section=section
                )

                # Bỏ qua nếu cùng section đã có (tránh gửi nội dung trùng lặp cho AI)
                if section and section in seen_sections:
                    continue
                seen_sections.add(section)

                print(f"[RAG] ✓ {location_label}")
                context_parts.append(f"[Nguồn: {location_label}]\n{doc.page_content}")

                # Chỉ giữ lại top_k chunk đa dạng sau khi dedup
                if len(context_parts) >= top_k:
                    break

            context_text = "\n\n---\n\n".join(context_parts)
            return context_text

        except Exception as e:
            print(f"[RAG] Query error: {str(e)}")
            return ""