"""
Dùng để kiểm tra trường dữ liệu xem đầy đủ ko trước khi đẩy vào dtb
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Lớp cơ sở chứa các thuộc tính chung
class ActivityBase(BaseModel):
    action_type: str = Field(..., description="The category of the action performed (e.g., login, start_chat, view_document)")
    description: Optional[str] = Field(None, description="A detailed explanation or additional metadata regarding the activity")

# Schema dùng khi nhận dữ liệu từ user gửi lên, kế thừa từ activitybase
class ActivityCreate(ActivityBase):
    pass
# Schema dùng khi trả dữ liệu về cho user
class ActivityResponse(ActivityBase):
    id: int
    user_id: int
    created_at: datetime
    class Config:
        # Cấu hình quan trọng để Pydantic có thể đọc trực tiếp từ đối tượng SQLAlchemy
        from_attributes = True