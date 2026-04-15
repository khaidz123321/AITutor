from langchain_chroma import Chroma
from engine.rag_service import RAGService

def peek_inside_chroma():
    rag = RAGService()
    # Chọn môn học Khải muốn kiểm tra (ví dụ: giai_tich_1)
    subject = "triet_hoc_maclenin" 
    
    # Kết nối tới kho dữ liệu
    db = Chroma(
        persist_directory=rag.persist_directory,
        embedding_function=rag.embeddings,
        collection_name=f"subject_{subject}"
    )
    
    # Lấy thử 10 đoạn dữ liệu đầu tiên
    results = db.get(limit=10)
    
    print(f"📊 Tổng số mảnh (chunks) trong môn {subject}: {len(db.get()['ids'])}")
    
    for i, text in enumerate(results['documents']):
        print(f"\n--- 🧩 Mảnh thứ {i+1} ---")
        print(text[:300] + "...") # In 300 ký tự đầu để xem nội dung
        print("-" * 20)

if __name__ == "__main__":
    peek_inside_chroma()