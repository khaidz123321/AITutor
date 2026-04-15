"""
Quan lí tải tài liệu, lưu -> server, cất tài liệu -> dtb
"""
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
from core.session import get_db
from schemas.document import DocumentResponse
from models.document import Document
from engine.rag_service import RAGService

router = APIRouter()
rag_service = RAGService()
UPLOAD_DIR = "uploads/documents"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/", response_model=DocumentResponse)
async def upload_document(
    # sử dụng form metadata để upload file
    subject: str = Form(..., description="Subject identifier in lowercase snake_case (e.g., 'giai_tich_1')"),
    file: UploadFile = File(..., description="The physical document file (PDF, DOCX, etc.)"),
    db: Session = Depends(get_db)
):
    current_user_id = 1 

    try:
        safe_filename = file.filename.lower().replace(" ", "_")
        file_path = os.path.join(UPLOAD_DIR, safe_filename)

        # lưu file
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # tạo bản ghi trong dtb
        new_doc = Document(
            user_id=current_user_id,
            filename=safe_filename,
            subject=subject.lower(), 
            file_path=file_path,
            status="pending" 
        )

        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        success = rag_service.index_document(file_path=file_path, subject=subject.lower())
        
        if not success:
            print("Cảnh báo: File đã lưu nhưng không thể index vào RAG")

        return new_doc

    except Exception as e:
        db.rollback()
        print(f"Document Upload Error: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to upload and store the document metadata."
        )

@router.get("/", response_model=List[DocumentResponse])
def list_student_documents(db: Session = Depends(get_db)):
    """
    nhận tài liệu từ học sinh để upload
    """
    current_user_id = 1
    
    documents = db.query(Document).filter(
        Document.user_id == current_user_id
    ).all()
    
    return documents