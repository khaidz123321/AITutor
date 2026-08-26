import os
import re
import glob

# Pattern CHỈ nhận diện ranh giới CHƯƠNG thật (Chuong, Chương, CHU'ONG...).
# KHÔNG được gộp "Bài"/"Phần" vào đây: trong dữ liệu OCR thực tế, "Bài X"/"Phần X"
# thường là MỤC CON bên trong 1 chương (đánh số độc lập, không phải chương của cả sách),
# nhưng OCR lại gắn heading cấp 1 (#) cho cả tiêu đề mục con lẫn tiêu đề chương thật.
# Nếu coi "Bài"/"Phần" là ranh giới chương, script sẽ cắt nhầm và gán sai số chương
# (đây là nguyên nhân gốc của hiện tượng nội dung "Định thức" bị lẫn sang file chuong_3.txt
# thay vì chuong_4.txt như đã phát hiện trên course_11).
CHUONG_PATTERN = r'(?:Ch(?:u|ư)[\'\’]?(?:o|ơ)ng|CHƯƠNG)'

# Ranh giới dự phòng khi PDF/OCR bỏ sót hẳn dòng "# CHƯƠNG N" của 1 chương (ví dụ: chương đó
# nằm trên 1 trang tiêu đề bị OCR đọc sai/không nhận diện thành heading cấp 1). Trong trường hợp
# này nội dung chương bị lẫn vào chương liền trước, nhưng mục con đầu tiên của nó "# N.1 ..."
# vẫn được gắn heading cấp 1 bình thường -> dùng làm ranh giới thay thế.
# Yêu cầu "N.1" đứng riêng (không phải "N.1.2" lồng nhau) bằng lookahead phủ định "(?!\.\d)".
IMPLICIT_CHAPTER_START = re.compile(r'^#\s*(\d+)\.1(?!\.\d)\b', re.MULTILINE)

ROMAN_MAP = {'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5',
             'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'}

# Ngưỡng độ dài tối thiểu (ký tự) để 1 đoạn có heading "# CHƯƠNG N" được coi là NỘI DUNG CHƯƠNG THẬT.
# Trang "MỤC LỤC" ở đầu sách thường bị OCR gắn nhầm heading cấp 1 cho từng dòng liệt kê chương
# (VD: "# Chuong 3. Tich phan duong va mat 73"), tạo ra một đoạn cực ngắn (thường vài trăm ký tự)
# dễ bị nhận nhầm là "Chương 3" thật, khiến nội dung chương thật (xuất hiện sau đó trong sách) bị
# đẩy thành "TRÙNG SỐ CHƯƠNG" hoặc tệ hơn là nội dung thật không được nhận diện. Các chương thật
# trong dữ liệu thực tế luôn dài hàng chục KB trở lên; 4000 ký tự đã đủ an toàn để loại nhiễu Mục lục
# mà không đụng tới chương thật ngắn nhất từng quan sát được (~9700 ký tự).
MIN_REAL_CHAPTER_CHARS = 4000


def _split_implicit_chapters(chunk: str, base_chap_num):
    """
    `chunk` đã được xác định là chương `base_chap_num` (None nếu là phần Lời nói đầu/Mục lục,
    tức trước khi gặp bất kỳ heading CHƯƠNG nào). Dò các dòng "# N.1 ..." xuất hiện SAU vị trí ban
    đầu, với N tăng dần liên tục kể từ base_chap_num + 1, coi đó là ranh giới của (các) chương kế
    tiếp bị OCR bỏ sót heading "# CHƯƠNG N". Trả về list[(so_chuong_hoac_None, noi_dung)].
    """
    base_num = int(base_chap_num) if (base_chap_num and str(base_chap_num).isdigit()) else None
    expected_next = (base_num + 1) if base_num is not None else 1

    boundaries = []  # (vi_tri_bat_dau, so_chuong)
    for m in IMPLICIT_CHAPTER_START.finditer(chunk):
        n = int(m.group(1))
        if n == expected_next:
            boundaries.append((m.start(), str(n)))
            expected_next = n + 1

    if not boundaries:
        return [(base_chap_num, chunk)]

    result = []
    prev_start, prev_num = 0, base_chap_num
    for start, num in boundaries:
        piece = chunk[prev_start:start].strip()
        if piece:
            result.append((prev_num, piece))
        prev_start, prev_num = start, num
    tail = chunk[prev_start:].strip()
    if tail:
        result.append((prev_num, tail))
    return result


def _write_chapter_safely(subject_dir: str, chapter_num: str, content: str, idx_hint: int):
    """Ghi file chuong_N.txt, không ghi đè âm thầm nếu đã tồn tại (lưu ra bản _TRUNG_LAP_ để kiểm tra thủ công)."""
    new_file_name = f"chuong_{chapter_num}.txt"
    new_file_path = os.path.join(subject_dir, new_file_name)

    if os.path.exists(new_file_path):
        conflict_name = f"chuong_{chapter_num}_TRUNG_LAP_{idx_hint}.txt"
        conflict_path = os.path.join(subject_dir, conflict_name)
        with open(conflict_path, 'w', encoding='utf-8') as out_f:
            out_f.write(content)
        print(f"  ⚠️ TRÙNG SỐ CHƯƠNG {chapter_num} với file đã tách trước đó! "
              f"Đã lưu riêng ra {conflict_name} thay vì ghi đè — cần kiểm tra thủ công.")
        return

    with open(new_file_path, 'w', encoding='utf-8') as out_f:
        out_f.write(content)
    print(f"  ✅ Đã tách chuẩn mực: {new_file_name}")


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

        # NẾU TÌM THẤY ÍT NHẤT 1 CHƯƠNG -> FILE GỘP CẦN TÁCH
        if len(chapter_headings) > 0:
            file_name = os.path.basename(file_path)
            subject_dir = os.path.dirname(file_path)

            print(f"\nPhát hiện file gộp [{len(chapter_headings)} chương]: {file_name}")

            # Tiến hành cắt văn bản theo chương
            chunks = re.split(
                rf'(?=(?:^|\n)#\s*(?:[IVX\d\.\s]*)\s*{CHUONG_PATTERN})',
                content, flags=re.IGNORECASE
            )

            # Gom mọi đoạn "mở đầu"/nhiễu Mục lục vào đây, ghi ra loi_noi_dau.txt 1 lần duy nhất sau khi
            # duyệt hết toàn bộ chunks (thay vì ghi ngay — vì nhiễu Mục lục có thể xuất hiện rải rác xen
            # giữa các đoạn, không chỉ ở đầu file).
            front_matter_parts = []

            for i, chunk in enumerate(chunks):
                chunk = chunk.strip()
                if not chunk:
                    continue

                # NẾU ĐOẠN TEXT LÀ MỘT CHƯƠNG HỌC
                if re.search(rf'^#\s*(?:[IVX\d\.\s]*)\s*{CHUONG_PATTERN}', chunk, flags=re.IGNORECASE | re.MULTILINE):
                    # Bóc tách số Chương (VD: lấy số "1" trong "# CHƯƠNG 1", hoặc số La Mã I -> 1)
                    match = re.search(rf'^#\s*{CHUONG_PATTERN}\s*([IVX\d]+)', chunk, flags=re.IGNORECASE | re.MULTILINE)
                    if match:
                        raw_c = match.group(1).lower()
                        chapter_num = ROMAN_MAP.get(raw_c, raw_c)
                    else:
                        # KHÔNG đoán số chương bừa từ 1 dòng "X.Y" bất kỳ trong đoạn (không đảm bảo đúng ngữ cảnh).
                        # An toàn hơn: giữ nguyên đoạn dưới tên rõ ràng cần người kiểm tra thủ công.
                        chapter_num = None

                    if chapter_num is None:
                        new_file_name = f"chuong_KHONG_XAC_DINH_SO_{i}.txt"
                        new_file_path = os.path.join(subject_dir, new_file_name)
                        with open(new_file_path, 'w', encoding='utf-8') as out_f:
                            out_f.write(chunk)
                        print(f"  ⚠️ KHÔNG XÁC ĐỊNH ĐƯỢC SỐ CHƯƠNG, cần kiểm tra thủ công: {new_file_name}")
                        continue

                    # Đoạn quá ngắn để là 1 chương thật -> nhiều khả năng chỉ là 1 dòng liệt kê trong
                    # trang Mục lục bị OCR gắn nhầm heading cấp 1. Gộp vào phần mở đầu thay vì tạo
                    # file chuong_N.txt giả (tránh nội dung chương thật xuất hiện sau đó bị đẩy thành
                    # "TRÙNG SỐ CHƯƠNG" một cách oan uổng).
                    if len(chunk) < MIN_REAL_CHAPTER_CHARS:
                        front_matter_parts.append(chunk)
                        print(f"  ℹ️ Bỏ qua heading 'CHƯƠNG {chapter_num}' quá ngắn ({len(chunk)} ký tự) — "
                              f"coi là nhiễu Mục lục, đã gộp vào phần mở đầu.")
                        continue

                    # Dò thêm chương kế tiếp bị OCR bỏ sót heading "# CHƯƠNG N" (nằm lồng trong chunk này,
                    # nhận diện qua mục con đầu tiên "# N.1 ...").
                    for sub_num, sub_content in _split_implicit_chapters(chunk, chapter_num):
                        if sub_num is None:
                            new_file_name = f"chuong_KHONG_XAC_DINH_SO_{i}.txt"
                            new_file_path = os.path.join(subject_dir, new_file_name)
                            with open(new_file_path, 'w', encoding='utf-8') as out_f:
                                out_f.write(sub_content)
                            print(f"  ⚠️ KHÔNG XÁC ĐỊNH ĐƯỢC SỐ CHƯƠNG, cần kiểm tra thủ công: {new_file_name}")
                        else:
                            _write_chapter_safely(subject_dir, sub_num, sub_content, i)

                # NẾU ĐOẠN TEXT ĐỨNG TRƯỚC CHƯƠNG 1 (Lời nói đầu, Mục lục...)
                else:
                    # Chương 1 cũng có thể bị OCR bỏ sót heading -> nằm lẫn trong phần mở đầu này.
                    sub_pieces = _split_implicit_chapters(chunk, None)
                    for sub_num, sub_content in sub_pieces:
                        if sub_num is None:
                            front_matter_parts.append(sub_content)
                        elif len(sub_content) < MIN_REAL_CHAPTER_CHARS:
                            front_matter_parts.append(sub_content)
                            print(f"  ℹ️ Bỏ qua heading 'CHƯƠNG {sub_num}' quá ngắn ({len(sub_content)} ký tự) — "
                                  f"coi là nhiễu Mục lục, đã gộp vào phần mở đầu.")
                        else:
                            _write_chapter_safely(subject_dir, sub_num, sub_content, i)

            if front_matter_parts:
                new_file_path = os.path.join(subject_dir, "loi_noi_dau.txt")
                with open(new_file_path, 'w', encoding='utf-8') as out_f:
                    out_f.write("\n\n".join(front_matter_parts))
                print(f"  ℹ️ Đã tách phần mở đầu (gộp {len(front_matter_parts)} đoạn): loi_noi_dau.txt")

            # SAU KHI TÁCH XONG: Xóa file gộp gốc để hệ thống RAG không bị học trùng lặp
            if os.path.exists(file_path):
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
