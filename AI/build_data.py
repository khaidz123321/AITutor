import os
import sys
import subprocess

def run_script(script_path: str, description: str):
    print(f"\n[{description}] Đang chạy {script_path}...")
    result = subprocess.run([sys.executable, script_path], cwd=os.path.dirname(os.path.abspath(__file__)))
    if result.returncode != 0:
        print(f"❌ LỖI KHI CHẠY: {script_path}. Dừng tiến trình.")
        sys.exit(1)
    print(f"✅ Hoàn thành: {script_path}")

def main():
    print("======================================================")
    print("   🚀 DATA PIPELINE - CHUẨN BỊ DỮ LIỆU AI TUTOR 🚀    ")
    print("======================================================")
    print("Chỉ chạy script này khi bạn thêm Giáo trình PDF mới hoặc JSON bài tập mới!\n")

    # 1. Chia nhỏ file lớn thành từng chương (Nếu có)
    run_script("ProcessData/auto_split.py", "BƯỚC 1/5: Chia nhỏ file giáo trình gộp")

    # 2. Dọn dẹp JSON
    run_script("ProcessData/clean/clean_cite_tags.py", "BƯỚC 2/5: Dọn dẹp thẻ [cite: X] trong JSON")

    # 3. Dọn dẹp Text RAG (Header/Footer của slide)
    run_script("ProcessData/clean/clean_data.py", "BƯỚC 3/5: Xóa Header/Footer trong Txt giáo trình")

    # 4. Dọn dẹp Text RAG (Ký tự rác MinerU & Tài liệu tham khảo)
    run_script("ProcessData/clean/clean_rag_input.py", "BƯỚC 4/5: Dọn rác OCR MinerU trong Txt giáo trình")

    # 5. Tạo lại Vector DB
    run_script("reindex_rag.py", "BƯỚC 5/5: Nạp dữ liệu lý thuyết sạch vào Vector DB")

    print("\n======================================================")
    print("  🎉 HOÀN TẤT TẤT CẢ! HỆ THỐNG ĐÃ SẴN SÀNG CHO CHAT 🎉")
    print("======================================================")

if __name__ == "__main__":
    main()
