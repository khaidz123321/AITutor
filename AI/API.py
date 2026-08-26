import sys
import io

# Force stdout & stderr encoding to UTF-8 with replace error handling to prevent UnicodeEncodeError
if hasattr(sys.stdout, 'buffer'):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

if hasattr(sys.stderr, 'buffer'):
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from controller.router import api_router
from core.session import engine
from models.base import Base

# Tạo bảng Python-owned: documents + activities (nếu chưa tồn tại)
# Bảng users, chat_sessions, chat_messages do Spring Boot (Hibernate) quản lý — KHÔNG tạo ở đây
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Tutor PTIT - Backend")

# 1. Cấu hình CORS: Cho phép Streamlit (thường chạy ở port 8501) gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Kết nối bộ điều hướng (Router) cho các API Chat, Tài liệu và Hoạt động
app.include_router(api_router)

@app.on_event("startup")
def auto_standardize_rag():
    """Tự động chuẩn hóa và gộp các file giáo trình cũ thành chuong_1.txt, chuong_2.txt khi server khởi động."""
    try:
        from standardize_rag_files import standardize_rag_folder
        import os
        from core.config import settings
        rag_base = os.path.join(settings.BASE_DIR, "data", "rag_input")
        if os.path.exists(rag_base):
            standardize_rag_folder(rag_base)
    except Exception as e:
        print(f"[RAG Auto-Standardize Warning]: {e}")

@app.get("/")
def root():
    return {
        "message": "Gia sư AI PTIT đã sẵn sàng!",
        "status": "Online",
        "database": "Connected"
    }

from fastapi import HTTPException
@app.get("/test-500")
def test_500():
    raise HTTPException(status_code=500, detail="This is a test 500 error")