from pydantic import BaseModel, EmailStr, Field 
from datetime import datetime
from typing import Optional 

class UserBase(BaseModel):
    username: str = Field(..., min_length = 3, max_length = 50, description = "The unique username used for account identification and login")
    email: EmailStr = Field(..., description = "The user's primary email address, must be a valid email format")
    full_name: Optional[str] = Field(None, max_length = 100, description = "The user's complete legal name for profile display")

class UserCreate(UserBase):
    password: str = Field(..., min_length = 8, description="A secure, confidential password for account authentication")

# schema cập nhật thông tin user (input)
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None 
    full_name: Optional[str] = None 
    password: Optional[str] = Field(None, min_length = 8)

# schema hiển thị dữ liệu user (Response)
class UserResponse(UserBase):
    id: int = Field(..., description="The unique numeric identifier assigned by the database")
    is_active: bool = Field(..., description="A status flag indicating if the account is currently enabled")
    created_at: datetime = Field(..., description="The timestamp when the user account was successfully created")
    # cho phép pydantic kết nối tới SQL Alchemy
    class Config:
        from_attributes = True