from pydantic import BaseModel
from typing import Optional

class InitFolderRequest(BaseModel):
    courseId: Optional[int] = None
    courseCode: str
    courseTitle: str
    personaContent: Optional[str] = None

class InitFolderResponse(BaseModel):
    success: bool
    message: str
    folderPath: Optional[str] = None

class DeleteFolderRequest(BaseModel):
    courseCode: str

class DeleteFolderResponse(BaseModel):
    success: bool
    message: str

