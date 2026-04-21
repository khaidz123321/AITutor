"""
RAG: Quản lý việc lập chỉ mục tài liệu 
Truy xuất data từ VectorDB
"""
import os   
from typing import List
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_community.vectorstores import Chroma
from core.config import settings

huggingface_token = os.getenv("HUGGING_FACE_API_KEY")

class RAGService:
    """
    Lớp dịch vụ chịu trách nhiệm xử lý tài liệu thô thành cơ sở dữ liệu vector
    và tìm kiếm thông tin liên quan theo môn học.
    """
    def __init__(self):
        self.embeddings = HuggingFaceEndpointEmbeddings(
            huggingfacehub_api_token=huggingface_token,
            model="sentence-transformers/all-MiniLM-L6-v2",
            task="feature-extraction" # Thêm task để đảm bảo Cloud hiểu đúng việc cần làm
        )

        # Thư mục lưu trữ cơ sở dữ liệu vector tại local
        self.persist_directory = os.path.join(settings.BASE_DIR, "data", "vector_db")
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap = 200,
            separators=[
                "\n\n## ",         # Ưu tiên cắt mục lớn
                "\n\n### ",        # Cắt mục nhỏ
                "\n\n",            # Cắt đoạn văn
                "$$",              # BẢO VỆ TUYỆT ĐỐI CÔNG THỨC TOÁN
                "\n",              
                " ",               
                ""
            ]
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

            # 3. Lưu vào ChromaDB với metadata là môn học để sau này lọc 
            vector_db = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=self.persist_directory,
                collection_name=f"subject_{subject}" # Mỗi môn học một bộ vector riêng
            )
            return True
        except Exception as e:
            print(f"Lỗi nạp dữ liệu rag")
            return False

    def query_context(self, subject: str, query: str, top_k: int = 3) -> str:
        """
        Tìm kiếm những đoạn văn bản liên quan nhất đến câu hỏi của sinh viên.
        """
        # Load lại DB của môn học tương ứng
        vector_db = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings,
            collection_name=f"subject_{subject}"
        )

        # Tìm kiếm tương đồng 
        results = vector_db.similarity_search(query, k=top_k)
        
        # Gộp các đoạn văn bản tìm được thành một chuỗi context
        context_text = "\n\n".join([doc.page_content for doc in results])
        return context_text