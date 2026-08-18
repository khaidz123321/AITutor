import sys
import re

sys.path.append(r"d:\Project\AITutor\AI")

# Simulated theory texts for various subjects
test_cases = [
    {
        "code": "course_7",
        "file": "ed7c326e-218c-42e7-85db-d7bc4ade27d2_triet_hoc_maclenin_1_chuong_1.txt",
        "theory": "# CHƯƠNG 1: KHAI LUẬN VỀ TRIẾT HỌC MÁC - LÊNIN\n\nChương này cung cấp cho sinh viên...",
        "expected": "Triết học Mác - Lênin"
    },
    {
        "code": "course_12",
        "file": "320070a4-a43c-414f_tu_tuong_ho_chi_minh_chuong_1.txt",
        "theory": "# CHƯƠNG 1: KHAI LUẬN VỀ TƯ TƯỞNG HỒ CHÍ MINH\n\nTư tưởng Hồ Chí Minh là hệ thống quan điểm...",
        "expected": "Tư tưởng Hồ Chí Minh"
    },
    {
        "code": "course_15",
        "file": "kinh_te_vi_mo_chuong_2.txt",
        "theory": "# GIÁO TRÌNH KINH TẾ VĨ MÔ\n\nChương này giới thiệu tổng quan về sản lượng quốc gia...",
        "expected": "Kinh tế vĩ mô"
    },
    {
        "code": "course_20",
        "file": "luat_kinh_te_chuong_1.txt",
        "theory": "# MÔN HỌC: LUẬT KINH TẾ\n\nKhái niệm và đối tượng điều chỉnh của luật kinh tế...",
        "expected": "Luật kinh tế"
    },
    {
        "code": "course_30",
        "file": "quan_tri_hoc_chuong_1.txt",
        "theory": "# CHƯƠNG 1: TỔNG QUAN VỀ QUẢN TRỊ HỌC\n\nQuản trị học là môn học nghiên cứu các chức năng...",
        "expected": "Quản trị học"
    }
]

print("=== TESTING DYNAMIC SUBJECT EXTRACTOR ===")
from controller.endpoints.exercises import _get_clean_subject_display_name, _extract_subject_from_theory_text, _extract_subject_from_filename

for tc in test_cases:
    ext_theory = _extract_subject_from_theory_text(tc["theory"])
    ext_file = _extract_subject_from_filename(tc["file"])
    res = _get_clean_subject_display_name(tc["code"], target_file=tc["file"], theory_text=tc["theory"])
    print(f"\nCode: {tc['code']} | File: {tc['file']}")
    print(f"  Extracted from Theory: {ext_theory!r}")
    print(f"  Extracted from File:   {ext_file!r}")
    print(f"  Final Resolved Name:   {res!r} (Expected: {tc['expected']!r})")
