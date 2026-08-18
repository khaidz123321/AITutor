import sys, re

path = r'd:\Project\AITutor\AI\controller\endpoints\exercises.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

replacements = [
    ('\"Bài toán tính toán đơn giản có số liệu cụ thể.\"', '\"<bai_toan_tinh_toan_don_gian_co_so_lieu_cu_the>\"'),
    ('\"CHỈ GHI KẾT QUẢ CUỐI CÙNG (Vd: x=5). CẤM LẶP LẠI ĐỀ BÀI.\"', '\"<CHI_GHI_KET_QUA_CUOI_CUNG_VD_X_BANG_5>\"'),
    ('\"Bài toán tính toán nhiều bước có số liệu cụ thể.\"', '\"<bai_toan_tinh_toan_nhieu_buoc_co_so_lieu_cu_the>\"'),
    ('\"CHỈ GHI KẾT QUẢ CUỐI CÙNG. CẤM LẶP LẠI ĐỀ BÀI.\"', '\"<CHI_GHI_KET_QUA_CUOI_CUNG_CAM_LAP_LAI_DE_BAI>\"'),
    ('\"Bài toán chứng minh hoặc tư duy phức tạp.\"', '\"<bai_toan_chung_minh_hoac_tu_duy_phuc_tap>\"'),
    ('\"CHỈ GHI KẾT QUẢ CUỐI CÙNG HOẶC ĐIỀU PHẢI CHỨNG MINH.\"', '\"<CHI_GHI_KET_QUA_CUOI_CUNG_HOAC_DIEU_PHAI_CHUNG_MINH>\"'),
    
    ('\"Câu hỏi lý thuyết cơ bản hoặc tình huống đơn giản.\"', '\"<cau_hoi_ly_thuyet_co_ban_hoac_tinh_huong_don_gian>\"'),
    ('\"CHỈ GHI Ý CHÍNH HOẶC KẾT LUẬN. CẤM LẶP LẠI ĐỀ BÀI.\"', '\"<CHI_GHI_Y_CHINH_HOAC_KET_LUAN>\"'),
    ('\"Câu hỏi tình huống thực tế hoặc case study mức trung bình.\"', '\"<cau_hoi_tinh_huong_thuc_te_hoac_case_study_muc_trung_binh>\"'),
    ('\"Câu hỏi đánh giá phản biện hoặc tình huống thực tế phức tạp.\"', '\"<cau_hoi_danh_gia_phan_bien_hoac_tinh_huong_phuc_tap>\"'),
    ('\"Lời giải chi tiết từng bước\"', '\"<loi_giai_chi_tiet_tung_buoc>\"'),
    ('\"Giải thích chi tiết từng ý\"', '\"<giai_thich_chi_tiet_tung_y>\"')
]

for old, new in replacements:
    text = text.replace(old, new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print('Replaced successfully.')
