"""
Script chẩn đoán RAG - chạy trực tiếp để kiểm tra vector DB
Cách dùng: D:\\Project\\venv\\Scripts\\python.exe test_rag_diagnostic.py
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from engine.rag_service import RAGService

rag = RAGService()

TEST_QUERIES = [
    ("Đạo hàm - Định nghĩa",   "giai_tich_1", "định nghĩa đạo hàm tại một điểm giới hạn"),
    ("Đạo hàm - Khả vi",       "giai_tich_1", "đạo hàm và vi phân định nghĩa khả vi"),
    ("Tích phân từng phần",     "giai_tich_1", "tích phân từng phần công thức"),
    ("Hàm số chẵn lẻ",         "giai_tich_1", "hàm số chẵn hàm số lẻ định nghĩa"),
    ("Giới hạn dãy số",        "giai_tich_1", "giới hạn của dãy số định nghĩa"),
]

SUBJECT_DISPLAY = {
    "giai_tich_1": "Giải tích 1",
}

print("=" * 70)
print("DIAGNOSTIC: RAG Vector DB Query Test")
print("=" * 70)

for label, subject, query in TEST_QUERIES:
    print(f"\n{'─'*60}")
    print(f"[TEST] {label}")
    print(f"  Query: '{query}'")
    print(f"  Subject: {subject}")
    print()

    # Gọi thẳng similarity_search với score để xem raw results
    from langchain_chroma import Chroma
    vector_db = Chroma(
        persist_directory=os.path.join("data", "vector_db"),
        embedding_function=rag.embeddings,
        collection_name=f"subject_{subject}",
    )
    
    # Normalize query (bỏ dấu) như rag_service sẽ làm
    normalized_q = rag._normalize_query(query)
    print(f"  Normalized: '{normalized_q}'")
    
    results = vector_db.similarity_search_with_score(normalized_q, k=8)
    
    print(f"  Top 8 kết quả (threshold=65.0):")
    for i, (doc, score) in enumerate(results):
        section = doc.metadata.get("section", "")
        chapter = doc.metadata.get("chapter", "")
        src = os.path.basename(doc.metadata.get("source", "")).replace(".txt","")
        status = "✅ PASS" if score < 65.0 else "❌ FAIL"
        print(f"  [{i+1}] score={score:.4f} {status}")
        print(f"       chapter={chapter} | section={section[:50]}")
        # Hiển thị 100 ký tự đầu của nội dung để xem có đúng topic không
        preview = doc.page_content[:150].replace('\n', ' ').strip()
        print(f"       content: {preview}")
        print()

print("\n" + "=" * 70)
print("Kết luận: Xem score của các section đúng chủ đề")
print("  < 45  = Rất liên quan")
print("  45-55 = Có thể liên quan")
print("  > 55  = Không liên quan (nhưng vẫn pass threshold 65)")
print("=" * 70)
