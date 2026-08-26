import os
import shutil
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from schemas.course import InitFolderRequest, InitFolderResponse, DeleteFolderRequest, DeleteFolderResponse
from core.config import settings
from core.mapping import _get_default_folder_name
from core.session import get_db

router = APIRouter()

@router.post("/init-folder", response_model=InitFolderResponse)
async def init_course_folder(req: InitFolderRequest, db: Session = Depends(get_db)):
    """
    Tạo cấu trúc thư mục tự động cho môn học mới và lưu assignment_persona.txt
    Spring Boot gọi API này sau khi Admin tạo/lưu một Khóa học (Course).
    """
    safe_name = None
    
    if req.courseId:
        safe_name = f"course_{req.courseId}"
    else:
        # Nếu Spring Boot chưa update gửi courseId, truy vấn DB dựa vào title hoặc code
        try:
            # Truy vấn DB dựa vào title để đảm bảo an toàn vì title chắc chắn tồn tại
            # Dùng LOWER và TRIM để so khớp linh hoạt hơn
            result = db.execute(
                text("SELECT id FROM courses WHERE LOWER(TRIM(title)) = LOWER(TRIM(:title)) LIMIT 1"),
                {"title": req.courseTitle}
            ).fetchone()
            
            if result:
                safe_name = f"course_{result[0]}"
        except Exception as e:
            print(f"Lỗi truy vấn DB courseId: {e}")
            pass
            
    if not safe_name:
        safe_name = _get_default_folder_name(req.courseCode)
        
    base_path = os.path.join(settings.BASE_DIR, "prompts", safe_name)
    question_bank_path = os.path.join(base_path, "question_bank")
    
    try:
        # Tạo thư mục prompts/{tên_môn}/question_bank/
        os.makedirs(question_bank_path, exist_ok=True)
        
        # Lưu nội dung persona nếu có
        if req.personaContent:
            persona_file = os.path.join(base_path, "assignment_persona.txt")
            with open(persona_file, "w", encoding="utf-8") as f:
                f.write(req.personaContent)
                
        return InitFolderResponse(
            success=True,
            message=f"Tạo thư mục môn học thành công tại {base_path}",
            folderPath=base_path
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi tạo thư mục môn học: {str(e)}")


@router.post("/delete-folder", response_model=DeleteFolderResponse)
async def delete_course_folder(req: DeleteFolderRequest):
    """
    Dọn dẹp sạch sẽ toàn bộ thư mục dữ liệu, bài tập và cache của môn học khi bị xóa từ Spring Boot.
    Tránh tình trạng lệch ID hoặc tồn đọng dữ liệu cũ khi tạo lại môn học cùng tên.
    """
    safe_name = _get_default_folder_name(req.courseCode)
    
    prompts_path = os.path.join(settings.BASE_DIR, "prompts", safe_name)
    rag_input_path = os.path.join(settings.BASE_DIR, "data", "rag_input", safe_name)
    
    try:
        # Xóa thư mục prompts/<course_code>
        if os.path.exists(prompts_path):
            shutil.rmtree(prompts_path, ignore_errors=True)
            print(f"[COURSE CLEANUP] Đã xóa thư mục prompts: {prompts_path}")
            
        # Xóa thư mục data/rag_input/<course_code>
        if os.path.exists(rag_input_path):
            shutil.rmtree(rag_input_path, ignore_errors=True)
            print(f"[COURSE CLEANUP] Đã xóa thư mục rag_input: {rag_input_path}")
            
        return DeleteFolderResponse(
            success=True,
            message=f"Đã dọn dẹp sạch sẽ dữ liệu của môn học {req.courseCode}"
        )
    except Exception as e:
        print(f"[COURSE CLEANUP] Cảnh báo lỗi khi dọn dẹp {req.courseCode}: {e}")
        return DeleteFolderResponse(
            success=False,
            message=f"Lỗi dọn dẹp môn học: {str(e)}"
        )

