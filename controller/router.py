from fastapi import APIRouter
from controller.endpoints import chat, documents, activities

# Khởi tạo Điều Hành chính
api_router = APIRouter()

# Đăng ký các nhánh con vào điều hành chính
# Prefix giúp tạo đường dẫn 
# Tags giúp phân loại các nhóm API trên trang Swagger UI (/docs)

api_router.include_router(
    chat.router, 
    prefix="/chat", 
    tags=["Chat Interface"]
)

api_router.include_router(
    activities.router, 
    prefix="/activities", 
    tags=["User Activity Logs"]
)

api_router.include_router(
    documents.router, 
    prefix="/documents", 
    tags=["Knowledge Base (RAG)"]
)