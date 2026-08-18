import os
import re
import glob

# Pattern match tất cả variants: Chuong, Chương, CHU'ONG, Bai, Bài, Phan, Phần
CHUONG_PATTERN = r'(?:Ch(?:u|ư)[\'\’]?(?:o|ơ)ng|CHƯƠNG|B(?:a|à)i|BÀI|Ph(?:a|ầ)n|PHẦN)'

def auto_split_large_files(subject: str = None):
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
    AI_DIR = os.path.dirname(CURRENT_DIR)
    RAG_INPUT_DIR = os.path.join(AI_DIR, "data", "rag_input")

    # Nếu truyền subject thì chỉ quét thư mục của môn đó, tránh làm hỏng dữ liệu môn khác
    if subject:
        search_path = os.path.join(RAG_INPUT_DIR, subject, "*.txt")
    else:
        search_path = os.path.join(RAG_INPUT_DIR, "**", "*.txt")

    print(f"ĐANG QUÉT TÌM TÌM GỘP TẠI: {search_path}")
    print("=" * 60)

    # Quét file .txt 
    txt_files = glob.glob(search_path, recursive=True)
    files_processed = 0
    for file_path in txt_files:
        # BỎ QUA file đã được tách rồi (có _chuong_ hoặc _loi_noi_dau trong tên)
        # Tránh trường hợp tách đi tách lại → tên file dài vô tận
        file_name_check = os.path.basename(file_path)
        if "_chuong_" in file_name_check or "_loi_noi_dau" in file_name_check:
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Đếm số lượng Heading Cấp 1 - chương nằm ở đầu các dòng
        chapter_headings = re.findall(
            rf'^#\s*(?:[IVX\d\.\s]*)\s*{CHUONG_PATTERN}',
            content, flags=re.IGNORECASE | re.MULTILINE
        )
        
        # NẾU TÌM THẤY ÍT NHẤT 1 CHƯƠNG/BÀI/PHẦN -> FILE GỘP CẦN TÁCH
        if len(chapter_headings) > 0:
            file_name = os.path.basename(file_path)
            subject_dir = os.path.dirname(file_path)
            base_name = os.path.splitext(file_name)[0]
            
            print(f"\nPhát hiện file gộp [{len(chapter_headings)} chương]: {file_name}")
            
            # Tiến hành cắt văn bản theo chương
            chunks = re.split(
                rf'(?=(?:^|\n)#\s*(?:[IVX\d\.\s]*)\s*{CHUONG_PATTERN})',
                content, flags=re.IGNORECASE
            )
            
            for i, chunk in enumerate(chunks):
                chunk = chunk.strip()
                if not chunk: 
                    continue
                
                # NẾU ĐOẠN TEXT LÀ MỘT CHƯƠNG HỌC
                if re.search(rf'^#\s*(?:[IVX\d\.\s]*)\s*{CHUONG_PATTERN}', chunk, flags=re.IGNORECASE | re.MULTILINE):
                    # Bóc tách số Chương (VD: lấy số "1" trong "# CHƯƠNG 1")
                    match = re.search(rf'^#\s*{CHUONG_PATTERN}\s+([IVX\d]+)', chunk, flags=re.IGNORECASE | re.MULTILINE)
                    chapter_num = match.group(1) if match else f"part_{i}"
                    
                    new_file_name = f"{base_name}_chuong_{chapter_num}.txt"
                    new_file_path = os.path.join(subject_dir, new_file_name)
                    
                    mode = 'a' if os.path.exists(new_file_path) else 'w'
                    with open(new_file_path, mode, encoding='utf-8') as out_f:
                        if mode == 'a':
                            out_f.write("\n\n")
                        out_f.write(chunk)
                    print(f"  ✅ Đã tách/Gộp: {new_file_name}")
                    
                # NẾU ĐOẠN TEXT ĐỨNG TRƯỚC CHƯƠNG 1 (Lời nói đầu, Mục lục...)
                else:
                    new_file_name = f"{base_name}_loi_noi_dau.txt"
                    new_file_path = os.path.join(subject_dir, new_file_name)
                    with open(new_file_path, 'w', encoding='utf-8') as out_f:
                        out_f.write(chunk)
                    print(f"  ℹ️ Đã tách phần mở đầu: {new_file_name}")
            
            # SAU KHI TÁCH XONG: Xóa file gộp gốc để hệ thống RAG không bị học trùng lặp
            os.remove(file_path)
            files_processed += 1
            
        else:
            # File đã được chia nhỏ -> SKIP
            pass

    if files_processed == 0:
        print("\nFile đã được tách sẵn, không cần xử lý.")
    else:
        print(f"\nĐã tách file thành công.")

if __name__ == "__main__":
    auto_split_large_files()