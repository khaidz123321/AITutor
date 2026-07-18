from fastapi import APIRouter
from controller.endpoints import chat, documents, activities, exercises, persona, courses
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

# Prefix /v1/exercises khớp với URL Spring Boot gọi:
# aiServiceUrl + "/v1/exercises/import-pdf"  (ExerciseAiServiceImpl.java)
api_router.include_router(
    exercises.router,
    prefix="/v1/exercises",
    tags=["Exercise AI — PDF Import"]
)

# Prefix /v1/persona — Tự động tạo AI Persona cho khóa học mới
api_router.include_router(
    persona.router,
    prefix="/v1/persona",
    tags=["AI Persona Builder"]
)

# Prefix /v1/courses — Quản lý khóa học (Tạo thư mục)
api_router.include_router(
    courses.router,
    prefix="/v1/courses",
    tags=["Courses Management"]
)
