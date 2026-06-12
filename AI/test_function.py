# Chạy script này để xem metadata trong vector DB
import os
os.environ["HF_HOME"] = r"D:\HuggingFaceCache"  # nếu có

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
)

vector_db = Chroma(
    persist_directory=r"D:\Project\AITutor\AI\data\vector_db",
    embedding_function=embeddings,
    collection_name="subject_giai_tich_1"
)

# Lấy 3 chunk đầu xem metadata
results = vector_db.get(limit=3, include=["metadatas"])
for i, meta in enumerate(results["metadatas"]):
    print(f"Chunk {i+1}: {meta}")