"""
Script dọn dẹp [cite: X] rác khỏi toàn bộ file JSON trong thư mục question_bank.
Chạy 1 lần duy nhất, tự động tìm & xử lý tất cả các môn học.
"""
import os
import re
import json
import glob

# Đường dẫn gốc tới thư mục AI (thêm 1 mức dirname vì file đã move vào clean/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")

# Regex khớp [cite: 8], [cite:8], [cite: 123], v.v.
CITE_PATTERN = re.compile(r'\[cite:\s*\d+\]', re.IGNORECASE)


def clean_value(value):
    """Đệ quy xóa [cite: X] trong mọi kiểu dữ liệu (str, list, dict)."""
    if isinstance(value, str):
        return CITE_PATTERN.sub('', value).strip()
    elif isinstance(value, list):
        return [clean_value(item) for item in value]
    elif isinstance(value, dict):
        return {k: clean_value(v) for k, v in value.items()}
    return value


def process_file(filepath: str) -> int:
    """
    Đọc, clean và ghi lại file JSON.
    Trả về số lần thay thế đã thực hiện.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        raw_content = f.read()

    # Đếm số lần xuất hiện trước khi xóa
    count = len(CITE_PATTERN.findall(raw_content))

    if count == 0:
        print(f"  ✓ Bỏ qua (sạch rồi): {os.path.relpath(filepath, BASE_DIR)}")
        return 0

    # Parse -> clean -> ghi lại với indent chuẩn
    data = json.loads(raw_content)
    cleaned_data = clean_value(data)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"  ✅ Đã xóa {count:>3} thẻ [cite:X] trong: {os.path.relpath(filepath, BASE_DIR)}")
    return count


def main():
    print("=" * 60)
    print("  CLEAN [cite: X] TAGS - AI Tutor PTIT")
    print("=" * 60)

    # Tìm toàn bộ file JSON trong các thư mục question_bank
    pattern = os.path.join(PROMPTS_DIR, "**", "question_bank", "*.json")
    json_files = glob.glob(pattern, recursive=True)

    if not json_files:
        print("❌ Không tìm thấy file JSON nào trong thư mục prompts/")
        return

    print(f"\nTìm thấy {len(json_files)} file JSON cần kiểm tra:\n")

    total_removed = 0
    for filepath in sorted(json_files):
        total_removed += process_file(filepath)

    print("\n" + "=" * 60)
    print(f"  HOÀN THÀNH: Đã xóa tổng cộng {total_removed} thẻ [cite:X]")
    print("=" * 60)


if __name__ == "__main__":
    main()
