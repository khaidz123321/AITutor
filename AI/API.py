from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from controller.router import api_router
from core.session import engine
from models.base import Base

# Sau khi đã import đủ, lệnh này sẽ tạo toàn bộ 4 bảng và các liên kết khóa ngoại
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

@app.get("/")
def root():
    return {
        "message": "Gia sư AI PTIT đã sẵn sàng!",
        "status": "Online",
        "database": "Connected"
    }