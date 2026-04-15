"""
Quản lí luồng hoạt động của người dùng
"""
from fastapi import APIRouter, Depends, HTTPException 
from sqlalchemy.orm import Session 
from typing import List 
from core.session import get_db 
from schemas.activity import ActivityCreate, ActivityResponse
from models.activity import Activity

router =  APIRouter()
"""
API 1: ghi nhận hoạt động mới
"""

@router.post("/", response_model=ActivityResponse)
def log_user_activity(request: ActivityCreate, db: Session = Depends(get_db)):
    current_user_id = 1 # giả sử ID tạm thời của sinh viên là 1 <test>
    try: 
        new_activity = Activity(
            user_id = current_user_id,
            action_type = request.action_type.lower(),
            description = request.description
        )
        db.add(new_activity)
        db.commit()
        # làm mới để lấy id + created_at
        db.refresh(new_activity)
    except Exception as e:
        db.rollback()
        print(f"Error logging activity: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail="An error occurred while recording student activity"
        )
    
"""
API 2: lấy hoạt động từ database
"""
@router.get("/", response_model=List[ActivityResponse])
def get_activity_history(db: Session = Depends(get_db)):
    current_user_id = 1
    # Truy vấn lấy toàn bộ hoạt động, sắp xếp mới nhất lên đầu
    activities = db.query(Activity).filter(
        Activity.user_id == current_user_id
    ).order_by(Activity.created_at.desc()).all()
    return activities