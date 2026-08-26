"""
Schema cho kết quả trích xuất câu hỏi từ PDF.
Các field phải khớp chính xác với Spring Boot ExerciseAiServiceImpl.importExercisesFromPdf()
mà nó đang mong đợi từ response:
  - exerciseCode  : String
  - exerciseName  : String
  - difficulty    : "EASY" | "MEDIUM" | "HARD"
  - bloomLevel    : "REMEMBERING" | "UNDERSTANDING" | "APPLYING" | "ANALYZING" | "EVALUATING"
  - question      : String (nội dung câu hỏi)
  - correctAnswer : String (đáp án)
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class Difficulty(str, Enum):
    EASY   = "EASY"
    MEDIUM = "MEDIUM"
    HARD   = "HARD"


class BloomLevel(str, Enum):
    REMEMBERING  = "REMEMBERING"
    UNDERSTANDING = "UNDERSTANDING"
    APPLYING     = "APPLYING"
    ANALYZING    = "ANALYZING"
    EVALUATING   = "EVALUATING"


class ExtractedExercise(BaseModel):
    """Một câu hỏi được AI trích xuất từ PDF — phải khớp với ExerciseAi entity của Spring Boot."""
    exerciseCode:  str        = Field(..., description="Mã bài tập duy nhất, ví dụ 'AI-PDF-001'")
    exerciseName:  str        = Field(default="Bài tập AI dịch từ PDF", description="Tên ngắn gọn")
    difficulty:    Difficulty = Field(default=Difficulty.MEDIUM, description="Độ khó")
    bloomLevel:    BloomLevel = Field(default=BloomLevel.UNDERSTANDING, description="Mức độ tư duy Bloom")
    question:      str        = Field(..., description="Nội dung câu hỏi đầy đủ")
    correctAnswer: str        = Field(..., description="Đáp án đúng")


class ImportPdfResponse(BaseModel):
    """Response trả về cho Spring Boot — danh sách câu hỏi dạng list trực tiếp."""
    data: List[ExtractedExercise]

from typing import Optional

class SyncScaffoldRequest(BaseModel):
    """Request từ Spring Boot để đồng bộ danh sách bài tập AI sang JSON cục bộ."""
    subject: str
    chapter: str
    exercises: List[ExtractedExercise]

class SyncScaffoldResponse(BaseModel):
    """Kết quả đồng bộ JSON."""
    success: bool
    message: str
    jsonPath: Optional[str] = None

class GenerateFromTheoryRequest(BaseModel):
    """Request từ Admin/Giảng viên để tự sinh bài tập AI (JSON) từ file lý thuyết .txt"""
    subject: str
    chapter: str
    course_name: Optional[str] = None  # Tên môn học thật từ DB (ưu tiên hơn _COURSE_FOLDER_MAP)
    chapter_title: Optional[str] = None  # Tên chương thật từ DB (Chapter.chapterName), dùng để khớp nội dung
    # theo ngữ nghĩa khi số thứ tự file trên đĩa lệch so với số chương trong DB (ví dụ do OCR gộp/lệch chương).

class GenerateFromTheoryResponse(BaseModel):
    success: bool
    message: str
    jsonPath: str
    data: List[ExtractedExercise]
