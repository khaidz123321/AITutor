import os
import re

def find_target_file(rag_input_dir, safe_chap):
    if not os.path.exists(rag_input_dir):
        return None
        
    all_txt_files = []
    for f in os.listdir(rag_input_dir):
        fname_lower = f.lower()
        if f.endswith(".txt"):
            full_p = os.path.join(rag_input_dir, f)
            fsize = os.path.getsize(full_p)
            if fsize > 10:
                all_txt_files.append((f, fname_lower, full_p, fsize))
                
    if not all_txt_files:
        return None

    # Trích xuất con số chương (ví dụ 'chuong_1' -> '1', 'chuong_part_1' -> '1', 'c1' -> '1')
    m_num = re.search(r'\d+', safe_chap)
    chap_num = m_num.group(0) if m_num else ""

    matching_files = []
    for f, fname_lower, full_p, fsize in all_txt_files:
        is_loi_noi_dau = 1 if "loi_noi_dau" in fname_lower else 0
        is_test = 1 if (fname_lower.startswith("test_") or "test" in fname_lower) else 0
        
        # Đánh giá mức độ khớp
        match_score = 99  # Mặc định ít ưu tiên nhất
        
        if safe_chap in fname_lower:
            match_score = 0  # Trùng khớp nguyên văn (ví dụ 'chuong_1' trong '..._chuong_1.txt')
        elif chap_num:
            # Khớp theo các biến thể số chương
            if f"chuong_{chap_num}" in fname_lower or f"chuong_part_{chap_num}" in fname_lower or f"part_{chap_num}" in fname_lower or f"part{chap_num}" in fname_lower:
                match_score = 1
            elif f"c{chap_num}" in fname_lower or f"_{chap_num}." in fname_lower or f"_{chap_num}_" in fname_lower:
                match_score = 2
            elif f"{chap_num}" in fname_lower:
                match_score = 3
                
        matching_files.append((is_test, is_loi_noi_dau, match_score, -fsize, full_p))

    matching_files.sort()
    return matching_files[0][4]

# Quick test with simulated filenames
dir_files = [
    "addb4c3d-4afe-4276-8021-6ebb4e96c050_giáo_trình_kinh_tế_chính_trị_mác_lê_nin_--_2019_loi_noi_dau.txt",
    "addb4c3d-4afe-4276-8021-6ebb4e96c050_giáo_trình_kinh_tế_chính_trị_mác_lê_nin_-_2019_chuong_part_1.txt"
]

print("=== TESTING FILE MATCHING ===")
# Simulated test
chap_request = "chuong_1"

m_num = re.search(r'\d+', chap_request)
chap_num = m_num.group(0) if m_num else ""

matching_files = []
for f in dir_files:
    fname_lower = f.lower()
    is_loi_noi_dau = 1 if "loi_noi_dau" in fname_lower else 0
    is_test = 1 if (fname_lower.startswith("test_") or "test" in fname_lower) else 0
    fsize = 50000
    
    match_score = 99
    if chap_request in fname_lower:
        match_score = 0
    elif chap_num:
        if f"chuong_{chap_num}" in fname_lower or f"chuong_part_{chap_num}" in fname_lower or f"part_{chap_num}" in fname_lower or f"part{chap_num}" in fname_lower:
            match_score = 1
        elif f"c{chap_num}" in fname_lower or f"_{chap_num}." in fname_lower or f"_{chap_num}_" in fname_lower:
            match_score = 2
        elif f"{chap_num}" in fname_lower:
            match_score = 3
            
    matching_files.append((is_test, is_loi_noi_dau, match_score, -fsize, f))

matching_files.sort()
print("Selected file:", matching_files[0][4])
