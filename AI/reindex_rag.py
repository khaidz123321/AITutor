"""
Script tai lap chi muc (re-index) toan bo tai lieu RAG.
Chay script nay sau khi cap nhat logic chunking de metadata `section` duoc gan dung.

Cach dung:
    cd d:/Project/AITutor/AI
    D:\\Project\\venv\\Scripts\\python.exe reindex_rag.py
"""
import os
import sys
import shutil

# Fix encoding cho Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

from core.config import settings
from engine.rag_service import RAGService

# Mapping: ten thu muc tai lieu -> ten mon hoc (dung lam collection name)
SUBJECT_FOLDERS = {
    "giai_tich_1": "giai_tich_1",
    "triet_hoc_maclenin": "triet_hoc_maclenin",
}

RAG_INPUT_DIR = os.path.join(settings.BASE_DIR, "data", "rag_input")
VECTOR_DB_DIR = os.path.join(settings.BASE_DIR, "data", "vector_db")

def reindex_all():
    rag = RAGService()

    # Buoc 1: Xoa toan bo vector DB cu de tranh duplicate
    if os.path.exists(VECTOR_DB_DIR):
        print(f"[RE-INDEX] Dang xoa vector DB cu tai: {VECTOR_DB_DIR}")
        shutil.rmtree(VECTOR_DB_DIR)
        os.makedirs(VECTOR_DB_DIR, exist_ok=True)
        print("[RE-INDEX] Da xoa xong.")
    else:
        os.makedirs(VECTOR_DB_DIR, exist_ok=True)

    # Buoc 2: Index lai tung file trong tung thu muc mon hoc
    total_files = 0
    total_success = 0

    for folder_name, subject_name in SUBJECT_FOLDERS.items():
        folder_path = os.path.join(RAG_INPUT_DIR, folder_name)
        if not os.path.exists(folder_path):
            print(f"[WARN] Khong tim thay thu muc: {folder_path}")
            continue

        txt_files = [f for f in os.listdir(folder_path) if f.endswith(".txt")]
        print(f"\n[RE-INDEX] Mon: {subject_name} --- {len(txt_files)} file(s)")

        for fname in sorted(txt_files):
            fpath = os.path.join(folder_path, fname)
            total_files += 1
            print(f"  -> Dang index: {fname} ...", end=" ", flush=True)
            success = rag.index_document(file_path=fpath, subject=subject_name)
            if success:
                total_success += 1
                print("OK")
            else:
                print("THAT BAI")

    print(f"\n[RE-INDEX] Hoan tat: {total_success}/{total_files} file(s) thanh cong.")

if __name__ == "__main__":
    reindex_all()
