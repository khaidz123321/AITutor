"""
RAG: Quản lý việc lập chỉ mục tài liệu 
Truy xuất data từ VectorDB
"""
import os   
from typing import List
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEndpointEmbeddings
# FIX: Cập nhật thư viện theo khuyến cáo của log để tránh DeprecationWarning
from langchain_chroma import Chroma 
from core.config import settings
# FIX: Import bộ dịch mapping từ thư mục core
from core.mapping import get_mapped_paths

huggingface_token = os.getenv("HUGGING_FACE_API_KEY")

class RAGService:
    """
    Lớp dịch vụ chịu trách nhiệm xử lý tài liệu thô thành cơ sở dữ liệu vector
    và tìm kiếm thông tin liên quan theo môn học.
    """
    def __init__(self):
        self.embeddings = HuggingFaceEndpointEmbeddings(
            huggingfacehub_api_token=huggingface_token,
            model="intfloat/multilingual-e5-large",
            task="feature-extraction" # Thêm task để đảm bảo Cloud hiểu đúng việc cần làm
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

    def index_document(self, file_path: str, subject: str):
        """
        Đọc file, chunking, tạo vector và lưu vào ChromaDB.
        """
        # Chỉ nhận xử lý file .txt từ Marker
        if not file_path.endswith(".txt"):
            print(f"Bỏ qua file: {file_path}")
            return False

        try:
            # Đọc file 
            loader = TextLoader(file_path, encoding="utf-8")

            # 2. Đọc và chunking
            pages = loader.load()
            chunks = self.text_splitter.split_documents(pages)

            # FIX: Dịch tên môn học sang dạng không dấu để đặt tên Collection chuẩn
            mapped_subj, _ = get_mapped_paths(subject, "")
            safe_collection_name = f"subject_{mapped_subj}"

            # 3. Lưu vào ChromaDB với metadata là môn học 
            vector_db = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=self.persist_directory,
                collection_name=safe_collection_name 
            )
            return True
        except Exception as e:
            print(f"Lỗi nạp dữ liệu rag")
            return False

    def query_context(self, subject: str, query: str, top_k: int = 3, threshold: float = 0.55) -> str:
        """
        Tìm kiếm chunk liên quan nhất.
        Dùng similarity_search_with_score để lọc chunk kém liên quan.
        (score thấp = giống nhau nhiều trong không gian vector Chroma).
        """
        try:
            # FIX: Dịch tên môn học tương tự như lúc Index
            mapped_subj, _ = get_mapped_paths(subject, "")
            safe_collection_name = f"subject_{mapped_subj}"
            vector_db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings,
                collection_name=safe_collection_name, # ĐÃ SỬA: Dùng tên an toàn để query đúng collection
            )

            # Lấy kết quả kèm điểm similarity
            results_with_scores = vector_db.similarity_search_with_score(
                query, k=top_k
            )
            filtered = [
                doc
                for doc, score in results_with_scores
                if score < threshold
            ]
            if not filtered:
                return "No relevant theoretical context found for this query in the provided documents."

            # Gộp tài liệu nếu lọt qua Threshold
            context_text = "\n\n---\n\n".join(
                [doc.page_content for doc in filtered]
            )
            return context_text

        except Exception as e:
            # FIX: Log lỗi chi tiết để dễ debug
            print(f"[RAG] Query error: {str(e)}")
            return ""