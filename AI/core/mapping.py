"""
File quản lý ánh xạ (Mapping) giữa tên hiển thị trên Frontend 
và tên thư mục/file thực tế trong Backend.
"""

import json
import os
import re
import unicodedata
from core.config import settings

def remove_accents(input_str: str) -> str:
    s = re.sub(r'[đĐ]', 'd', input_str)
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('utf-8')
    return s

def _get_default_folder_name(name: str) -> str:
    """Tự động chuyển 'Giải tích 1' thành 'giai_tich_1' nếu không có trong JSON"""
    clean_name = remove_accents(name).lower()
    return re.sub(r'[^a-z0-9]+', '_', clean_name).strip('_')

def get_mapped_paths(subject: str, chapter: str):
    """
    Đọc từ file subjects.json để lấy thông tin mapping linh hoạt.
    Nếu admin up môn mới chưa có trong JSON, tự động bỏ dấu tiếng Việt để tạo tên folder.
    """
    json_path = os.path.join(settings.BASE_DIR, "data", "subjects.json")
    
    # Mặc định tự sinh folder name
    mapped_subj = _get_default_folder_name(subject)
    mapped_chap = _get_default_folder_name(chapter)

    try:
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                subj_data = data.get(subject)
                if subj_data:
                    mapped_subj = subj_data.get("folder", mapped_subj)
                    chapters_map = subj_data.get("chapters", {})
                    mapped_chap = chapters_map.get(chapter, mapped_chap)
    except Exception as e:
        print(f"Lỗi đọc subjects.json: {e}")
        
    return mapped_subj, mapped_chap