import os
from dotenv import load_dotenv
from ProcessData.read_data import DataReader

# Nạp biến môi trường (Lấy link API Colab từ file .env)
load_dotenv()

def run_test():
    print("🚀 BẮT ĐẦU KHỞI ĐỘNG HỆ THỐNG ĐỌC DỮ LIỆU AITUTOR 🚀")
    print("=" * 60)
    
    # Khởi tạo bộ đọc thông minh
    reader = DataReader()
    
    # ==========================================
    # TEST 1: THƯ MỤC GIẢI TÍCH (Nhiều Toán)
    # ==========================================
    subject_1 = "giai_tich_1"
    folder_1 = os.path.join("data", subject_1)
    
    if os.path.exists(folder_1):
        print(f"\n▶️ ĐANG TEST THƯ MỤC: {subject_1.upper()}")
        # Gọi hàm xử lý toàn bộ thư mục
        content_1 = reader.extract_folder(folder_1, subject_1)
        
        # Lưu kết quả ra file để kiểm tra
        output_file_1 = "ket_qua_giai_tich.txt"
        with open(output_file_1, "w", encoding="utf-8") as f:
            f.write(content_1)
        print(f"✅ Đã lưu toàn bộ dữ liệu Giải Tích vào: {output_file_1}")
    else:
        print(f"❌ Không tìm thấy thư mục {folder_1}. Khải kiểm tra lại đường dẫn nhé.")

    # ==========================================
    # TEST 2: THƯ MỤC TRIẾT HỌC (Thuần Text)
    # ==========================================
    subject_2 = "triet_hoc_maclenin"
    folder_2 = os.path.join("data", subject_2)
    
    if os.path.exists(folder_2):
        print(f"\n▶️ ĐANG TEST THƯ MỤC: {subject_2.upper()}")
        # Gọi hàm xử lý toàn bộ thư mục
        content_2 = reader.extract_folder(folder_2, subject_2)
        
        # Lưu kết quả ra file để kiểm tra
        output_file_2 = "ket_qua_triet_hoc.txt"
        with open(output_file_2, "w", encoding="utf-8") as f:
            f.write(content_2)
        print(f"✅ Đã lưu toàn bộ dữ liệu Triết Học vào: {output_file_2}")
    else:
        print(f"❌ Không tìm thấy thư mục {folder_2}. Khải kiểm tra lại đường dẫn nhé.")

    print("\n🎉 HOÀN TẤT QUY TRÌNH TEST!")

if __name__ == "__main__":
    run_test()