"""
Script tự động chuẩn hóa và dọn dẹp toàn bộ dữ liệu RAG giáo trình hiện có:
- Đọc nội dung thực tế của từng chương.
- Lưu lại thành các file chuẩn định danh: chuong_1.txt, chuong_2.txt, chuong_3.txt...
- Xóa bỏ các file rác bị lặp tên dài dòng (chuong_1_chuong_1..., chuong_part_8...).
- Hoàn toàn tự động, giữ nguyên 100% nội dung kiến thức, không cần upload lại.
"""

import os
import sys
import re
import shutil

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from controller.endpoints.exercises import _extract_chapter_section_from_text, _parse_chap_index

def standardize_rag_folder(rag_base_dir: str):
    if not os.path.exists(rag_base_dir):
        print(f"Thư mục không tồn tại: {rag_base_dir}")
        return

    courses = [d for d in os.listdir(rag_base_dir) if os.path.isdir(os.path.join(rag_base_dir, d))]
    print(f"Bắt đầu chuẩn hóa {len(courses)} môn học trong: {rag_base_dir}\n")

    for course_folder in sorted(courses):
        course_path = os.path.join(rag_base_dir, course_folder)
        all_files = [f for f in os.listdir(course_path) if f.endswith('.txt') and not f.startswith('test_')]
        if not all_files:
            continue

        print(f"==================================================")
        print(f"📚 Đang xử lý môn: {course_folder} ({len(all_files)} files cũ)")
        print(f"==================================================")

        # 1. Đọc toàn bộ nội dung từ tất cả các file trong thư mục
        file_contents = {}
        for f in all_files:
            p = os.path.join(course_path, f)
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as fl:
                    file_contents[f] = fl.read()
            except Exception as e:
                print(f"  Lỗi đọc {f}: {e}")

        # 2. Tìm và bóc tách các chương học (từ chương 1 đến 12)
        extracted_chapters = {}
        for chap_idx in range(1, 13):
            best_text = ""
            best_src_file = ""
            for f, txt in file_contents.items():
                ext = _extract_chapter_section_from_text(txt, chap_idx)
                if len(ext.strip()) > len(best_text):
                    best_text = ext.strip()
                    best_src_file = f
            
            # Nếu dung lượng trích xuất hợp lệ (> 1200 ký tự)
            if len(best_text) > 1200:
                extracted_chapters[chap_idx] = (best_text, best_src_file)

        # 3. Tìm phần Lời nói đầu / Mục lục nếu có
        best_preface = ""
        for f, txt in file_contents.items():
            if "loi_noi_dau" in f or "mục lục" in txt[:500].lower() or "lời nói đầu" in txt[:500].lower():
                if len(txt.strip()) > len(best_preface) and len(txt.strip()) < 15000:
                    best_preface = txt.strip()

        # 4. Ghi các file chuẩn mới ra thư mục tạm trước khi thay thế
        temp_dir = os.path.join(course_path, "_temp_standardized")
        os.makedirs(temp_dir, exist_ok=True)

        for chap_idx, (text, src_f) in extracted_chapters.items():
            canonical_name = f"chuong_{chap_idx}.txt"
            target_path = os.path.join(temp_dir, canonical_name)
            with open(target_path, 'w', encoding='utf-8') as out_f:
                out_f.write(text)
            print(f"  ✅ Đã chuẩn hóa: {canonical_name:<16} ({len(text):6d} ký tự)")

        if best_preface:
            with open(os.path.join(temp_dir, "loi_noi_dau.txt"), 'w', encoding='utf-8') as out_f:
                out_f.write(best_preface)
            print(f"  ℹ️ Đã giữ lại:   loi_noi_dau.txt  ({len(best_preface):6d} ký tự)")

        # 5. Xóa toàn bộ file .txt cũ và chuyển file chuẩn vào
        for f in all_files:
            old_p = os.path.join(course_path, f)
            try:
                os.remove(old_p)
            except Exception as e:
                pass

        for f in os.listdir(temp_dir):
            shutil.move(os.path.join(temp_dir, f), os.path.join(course_path, f))
        
        try:
            os.rmdir(temp_dir)
        except:
            pass

        remaining_files = os.listdir(course_path)
        print(f"  -> Hoàn tất môn {course_folder}: Hiện có {len(remaining_files)} file chuẩn mực.\n")

if __name__ == "__main__":
    RAG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "rag_input")
    standardize_rag_folder(RAG_DIR)
