"""
File quản lý ánh xạ (Mapping) giữa tên hiển thị trên Frontend 
và tên thư mục/file thực tế trong Backend.
"""

# Ánh xạ tên môn học sang tên thư mục (Snake Case)
SUBJECT_MAP = {
    "Giải tích 1": "giai_tich_1",
    "Triết học Mác - Lênin": "triet_hoc_maclenin"
}

# Ánh xạ tên chương sang tên file chuong_x.json
# Tổ chức theo từng môn để tránh trùng lặp tên chương giữa các môn
CHAPTER_MAP = {
    "Giải tích 1": {
        "Giới hạn của dãy số": "chuong_1",
        "Hàm số một biến số": "chuong_2",
        "Đạo hàm và vi phân": "chuong_3",
        "Phép tính tích phân": "chuong_4",
        "Lí thuyết chuỗi": "chuong_5"
    },
    "Triết học Mác - Lênin": {
        "Triết học và vai trò của triết học trong đời sống xã hội": "chuong_1",
        "Chủ nghĩa duy vật biện chứng": "chuong_2",
        "Chủ nghĩa duy vật lịch sử": "chuong_3"
    }
}

def get_mapped_paths(subject: str, chapter: str):
    """
    Hàm tiện ích để lấy folder và file name từ tên tiếng Việt.
    Nếu không tìm thấy, trả về chính tên đó (đã được xử lý lowercase) để tránh lỗi.
    """
    mapped_subj = SUBJECT_MAP.get(subject, subject.lower().replace(" ", "_"))
    
    # Lấy map chương của môn học tương ứng
    subj_chapters = CHAPTER_MAP.get(subject, {})
    mapped_chap = subj_chapters.get(chapter, chapter.lower().replace(" ", "_"))
    
    return mapped_subj, mapped_chap