"""
Xác minh tài liệu metadata cho RAG và quản lý file
"""

from pydantic import BaseModel, Field 
from datetime import datetime 

class DocumentBase(BaseModel):
    filename: str = Field(
        ..., 
        description="The original name of the uploaded file in lowercase (e.g., 'calculus_syllabus.pdf')"
    )
    subject: str = Field(
        ..., 
        description="The academic subject identifier in lowercase snake_case (e.g., 'giai_tich_1', 'triet_hoc_maclenin')"
    )

# Schema cho output dữ liệu document
# 'file_path' được tạo để tránh lỗi server
class DocumentResponse(DocumentBase):
    id: int = Field(..., description="The unique numeric identifier for the document")
    user_id: int = Field(..., description="The ID of the student who uploaded the file")
    status: str = Field(
        default="pending", 
        description="The processing state of the document (e.g., 'pending', 'processing', 'completed')"
    )
    uploaded_at: datetime = Field(
        ..., 
        description="The timestamp indicating when the upload was finalized"
    )

    class Config:
        from_attributes = True