import os
import re
import glob

# ============================================================
# PATTERN NHẬN DIỆN BLOCK RÁC (HEADER/FOOTER LẶP LẠI TỪ PDF)
# ============================================================
# Cấu trúc điển hình xuất hiện ở bài giảng PTIT:
#
#   BÀI GIẢNG MÔN TRIẾT HỌC MÁC - LÊNIN
#   [1-8 dòng trắng hoặc chỉ khoảng trắng]
#   BỘ MÔN LÝ LUẬN CHÍNH TRỊ - PTIT
#   Page 4
#
# Pattern đủ linh hoạt để bắt cả:
#   - Tên môn khác (nếu sau này thêm môn mới dạng bài giảng)
#   - Số trang bất kỳ
#   - Dòng trắng chứa space/tab xen kẽ

HEADER_FOOTER_PATTERN = re.compile(
    r'[^\n]*BÀI GIẢNG[^\n]*\n'    # Dòng "BÀI GIẢNG MÔN ..."
    r'(?:[ \t]*\n){1,8}'            # 1-8 dòng trắng / chỉ khoảng trắng
    r'[^\n]*BỘ MÔN[^\n]*\n'        # Dòng "BỘ MÔN ..."
    r'[ \t]*Page[ \t]*\d+[ \t]*\n?', # Dòng "Page X"
    flags=re.IGNORECASE
)


def clean_text(text: str) -> str:
    """
    Làm sạch văn bản trích xuất từ PDF:
      Bước 1 — Xóa block header/footer lặp lại (BÀI GIẢNG / BỘ MÔN / Page X)
      Bước 2 — Thu gọn chuỗi dòng trắng thừa (3+ dòng → 2 dòng)
               Giữ 2 dòng để RecursiveCharacterTextSplitter vẫn nhận ra heading ##
    """
    cleaned = HEADER_FOOTER_PATTERN.sub('', text)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned.strip()


def clean_rag_input():
    """
    Quét toàn bộ file .txt trong data/rag_input,
    áp dụng clean_text() và ghi đè nếu có thay đổi.
    """
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROCESS_DATA_DIR = os.path.dirname(CURRENT_DIR)
    AI_DIR = os.path.dirname(PROCESS_DATA_DIR)
    RAG_INPUT_DIR = os.path.join(AI_DIR, "data", "rag_input")

    print(f"ĐANG QUÉT DỌN RÁC TẠI: {RAG_INPUT_DIR}")
    print("=" * 60)

    txt_files = glob.glob(os.path.join(RAG_INPUT_DIR, "**", "*.txt"), recursive=True)

    if not txt_files:
        print("Không tìm thấy file .txt nào trong rag_input.")
        return

    cleaned_count = 0
    skipped_count = 0

    for file_path in sorted(txt_files):
        file_name = os.path.basename(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()

        cleaned = clean_text(original)

        if cleaned != original:
            # Đếm số block rác đã xóa để báo cáo
            blocks_removed = len(HEADER_FOOTER_PATTERN.findall(original))
            original_lines = original.count('\n')
            cleaned_lines = cleaned.count('\n')

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(cleaned)

            print(
                f"  🧹 [{file_name}]\n"
                f"      Xóa {blocks_removed} block header/footer | "
                f"Số dòng: {original_lines} → {cleaned_lines} "
                f"(-{original_lines - cleaned_lines} dòng)\n"
            )
            cleaned_count += 1
        else:
            print(f"  ✅ [{file_name}] — Sạch, không cần xử lý")
            skipped_count += 1

    print("=" * 60)
    print(f"HOÀN TẤT: Đã làm sạch {cleaned_count} file | Bỏ qua {skipped_count} file sạch.")
    if cleaned_count > 0:
        print("→ Chạy 'python preload.py' để nạp lại dữ liệu sạch vào Vector DB.")


if __name__ == "__main__":
    clean_rag_input()
