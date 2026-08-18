import os 
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import urllib.parse

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Tutor PTIT"
    BASE_DIR: str = ROOT_DIR
    
    # 1. Đọc các trường thông thông tin từ .env
    DB_USER: str = os.getenv("POSTGRES_USER", "postgres")
    DB_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    DB_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    DB_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME: str = os.getenv("POSTGRES_DB", "AITutorDb")

    # 2. mã hoá pass
    @property
    def DATABASE_URL(self) -> str:
        encoded_pass = urllib.parse.quote_plus(self.DB_PASSWORD)
        return f"postgresql://{self.DB_USER}:{encoded_pass}@{self.DB_SERVER}:{self.DB_PORT}/{self.DB_NAME}"

    # 3. Cấu hình AI Model chính (Primary)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gemini-2.5-flash")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", 0.1))

    # 4. Cấu hình AI Model cho Chẩn đoán (Agent 1) - Groq/OpenRouter
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    DIAGNOSE_MODEL_NAME: str = os.getenv("DIAGNOSE_MODEL_NAME", "qwen/qwen3-32b")

    # 5. Cấu hình AI Model dự phòng (Fallback) - Qwen qua OpenRouter / Groq
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    FALLBACK_MODEL_NAME_GROQ: str = os.getenv("FALLBACK_MODEL_NAME_GROQ", "qwen/qwen3.6-27b")
    FALLBACK_MODEL_NAME: str = os.getenv("FALLBACK_MODEL_NAME", "qwen/qwen3-next-80b-a3b-instruct:free")

    HUGGING_FACE_API_KEY: str = os.getenv("HUGGING_FACE_API_KEY", "")

settings = Settings()