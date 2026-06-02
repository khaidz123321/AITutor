"""
Script dọn dẹp ký tự rác OCR khỏi toàn bộ file .txt trong thư mục rag_input.
- Xóa ký tự rác từ quá trình OCR: （204号, （20, (204号, v.v.
- Xóa section TÀI LIỆU THAM KHẢO và MỤC LỤC ở cuối file
- KHÔNG sửa dấu tiếng Việt (rủi ro làm hỏng LaTeX toán)
"""
import os
import re
import glob
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Đường dẫn gốc tới thư mục AI (thêm 1 mức dirname vì file đã move vào clean/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAG_INPUT_DIR = os.path.join(BASE_DIR, "data", "rag_input")

# ── Các pattern ký tự rác từ OCR MinerU ──────────────────────────────────────
GARBAGE_PATTERNS = [
    (re.compile(r'[（(]20[4号\d]*[号）)]\s*'), ''),   # （204号, （20, (20４号 ...
    (re.compile(r'[（(]\d{2,3}[）)]\s*'), ''),         # （20）, (204) ...
    (re.compile(r'!!\[\]\([a-f0-9]{40,}\.(?:jpg|png)\)\s*'), ''), # ảnh nhúng bị vỡ
]

# ── Các heading đánh dấu bắt đầu phần không cần index ────────────────────────
STOP_SECTIONS = re.compile(
    r'^#+\s*(TÀI LIỆU THAM KHẢO|TAI LIEU THAM KHAO|MỤC LỤC|MUC LUC|'
    r'BIBLIOGRAPHY|REFERENCES|PHỤ LỤC|PHU LUC)',
    re.IGNORECASE | re.MULTILINE
)


def clean_file(filepath: str) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_len = len(content)
    garbage_removed = 0

    # Bước 1: Xóa ký tự rác
    for pattern, replacement in GARBAGE_PATTERNS:
        new_content = pattern.sub(replacement, content)
        garbage_removed += len(content) - len(new_content)
        content = new_content

    # Bước 2: Cắt bỏ phần TÀI LIỆU THAM KHẢO và các section không cần thiết
    stop_match = STOP_SECTIONS.search(content)
    section_cut = False
    if stop_match:
        content = content[:stop_match.start()].rstrip()
        section_cut = True

    # Bước 3: Dọn dẹp khoảng trắng thừa
    content = re.sub(r'\n{4,}', '\n\n\n', content)
    content = content.strip()

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return {
        "original_bytes": original_len,
        "final_bytes": len(content),
        "garbage_removed": garbage_removed,
        "section_cut": section_cut,
    }


def main():
    print("=" * 65)
    print("  CLEAN OCR GARBAGE - AI Tutor RAG Input")
    print("=" * 65)

    txt_files = glob.glob(
        os.path.join(RAG_INPUT_DIR, "**", "*.txt"), recursive=True
    )

    if not txt_files:
        print("Khong tim thay file .txt nao trong", RAG_INPUT_DIR)
        return

    print(f"\nTim thay {len(txt_files)} file can xu ly:\n")

    total_garbage = 0
    sections_cut = 0

    for fpath in sorted(txt_files):
        rel = os.path.relpath(fpath, BASE_DIR)
        result = clean_file(fpath)

        total_garbage += result["garbage_removed"]
        tag = ""
        if result["section_cut"]:
            sections_cut += 1
            tag = " | [DA CAT TAI LIEU THAM KHAO]"

        saved_kb = (result["original_bytes"] - result["final_bytes"]) / 1024
        print(f"  OK {rel}")
        print(f"     Rac da xoa: {result['garbage_removed']} ky tu | "
              f"Giam: {saved_kb:.1f} KB{tag}")

    print("\n" + "=" * 65)
    print(f"  HOAN THANH:")
    print(f"  - Tong ky tu rac da xoa : {total_garbage}")
    print(f"  - So file duoc cat section: {sections_cut}")
    print("=" * 65)


if __name__ == "__main__":
    main()
