import json
import re
import urllib.request
import urllib.parse
from typing import Dict, Any

# ==========================================
# TEST CONFIGURATION
# ==========================================
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_STAGE1 = "deepseek-r1:14b"
MODEL_STAGE2 = "qwen2.5:14b"

THEORY = """
Chương 1: Tập hợp số thực
1.1. Các tập hợp số
- Số tự nhiên N = {0, 1, 2, ...}
- Số nguyên Z = {..., -2, -1, 0, 1, 2, ...}
- Số hữu tỉ Q: tập hợp các số dạng m/n (m, n thuộc Z, n khác 0).
- Số vô tỉ I: số thập phân vô hạn không tuần hoàn.
- Số thực R: hội của Q và I.

1.2. Khoảng, đoạn, nửa khoảng
- Khoảng mở (a, b) = {x thuộc R | a < x < b}
- Khoảng đóng [a, b] = {x thuộc R | a <= x <= b}
- Nửa khoảng [a, b) = {x thuộc R | a <= x < b}

1.3. Tính chất đặc trưng của R
- Tính trật tự: Có thể so sánh mọi x, y thuộc R.
- Tính trù mật: Giữa 2 số thực phân biệt luôn có một số thực khác. (Ví dụ: (x+y)/2).
- Khái niệm Sup (cận trên đúng) và Inf (cận dưới đúng).
"""

# ==========================================
# PROMPTS
# ==========================================
PROMPT_STAGE1 = """Bạn là chuyên gia giáo dục môn Toán học. Hãy biên soạn CHÍNH XÁC 5 bài tập tự luận BÁM SÁT 100% NỘI DUNG GIÁO TRÌNH dưới đây.

QUY TẮC BẮT BUỘC:
1. KHÔNG sinh câu hỏi lý thuyết suông dạng "Giải thích X là gì" hay "Nêu định nghĩa". TẤT CẢ câu hỏi phải là BÀI TOÁN có số liệu/dữ kiện cụ thể để chứng minh hoặc tính toán.
2. EASY (2 câu): [Nhắc lại 1 chút lý thuyết] + Yêu cầu áp dụng vào 1 bài toán tính toán cơ bản hoặc chứng minh đơn giản với 1-2 bước.
3. MEDIUM (2 câu): Cho một bài toán có tham số hoặc dữ kiện cụ thể, yêu cầu giải quyết bằng công thức trong giáo trình (2-3 bước).
4. HARD (1 câu): Đưa ra một bài toán tư duy sâu hoặc chứng minh mệnh đề chặt chẽ. CẤM hỏi định nghĩa ở đây.

NỘI DUNG LÝ THUYẾT:
{theory}

Trả về định dạng JSON, không nói gì thêm. Cấu trúc:
{{ "data": [ {{ "id": "...", "topic": "...", "difficulty": "EASY/MEDIUM/HARD", "bloom_level": "...", "question_text": "...", "correct_answer": "...", "detailed_explanation": "..." }} ] }}
"""

PROMPT_STAGE2 = """Bạn là chuyên gia sư phạm. Dưới đây là NỘI DUNG LÝ THUYẾT và danh sách các câu hỏi tự luận.
Nhiệm vụ của bạn là:
1. Dịch chuẩn xác sang 100% Tiếng Việt.
2. TUYỆT ĐỐI GIỮ NGUYÊN ĐỘ KHÓ VÀ Ý ĐỒ BÀI TOÁN CỦA CÂU HỎI. Cấm đơn giản hóa một bài toán tính toán/chứng minh thành một câu hỏi lý thuyết suông (như "Giải thích...").
3. Sinh ra kịch bản Socratic (scaffolding_steps) gồm 2-4 gợi ý từng bước.

NỘI DUNG LÝ THUYẾT:
{theory}

CÂU HỎI GỐC:
{qa}

Trả về JSON format:
{{ "data": [ {{ "id": "...", "topic": "...", "difficulty": "...", "bloom_level": "...", "question_text": "...", "full_answer": "...", "detailed_solution": "...", "scaffolding_steps": [ {{"step_number": 1, "hint": "...", "step_detail": "..."}} ], "common_mistakes": ["..."] }} ] }}
"""

# ==========================================
# UTILS
# ==========================================
def call_ollama(model: str, system: str, user: str, json_format: bool = False) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "stream": False,
        "temperature": 0.3
    }
    if json_format:
        payload["format"] = "json"
        
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"

def clean_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

# ==========================================
# EXECUTION
# ==========================================
if __name__ == "__main__":
    print(">>> 1. STAGE 1: Calling DeepSeek...")
    out1 = call_ollama(MODEL_STAGE1, "System", PROMPT_STAGE1.format(theory=THEORY))
    out1_clean = clean_think(out1)
    
    print("\n[DeepSeek Output]:")
    print(out1_clean[:1000] + "...\n" if len(out1_clean) > 1000 else out1_clean + "\n")
    
    if "ERROR" in out1:
        print("Failed to call Stage 1. Exiting.")
        sys.exit(1)
        
    print(">>> 2. STAGE 2: Calling Qwen...")
    out2 = call_ollama(MODEL_STAGE2, "System", PROMPT_STAGE2.format(theory=THEORY, qa=out1_clean), json_format=True)
    
    print("\n[Qwen Output]:")
    print(out2[:1500] + "...\n" if len(out2) > 1500 else out2 + "\n")
    
    with open("test_results.json", "w", encoding="utf-8") as f:
        f.write(out2)
    print(">>> Saved final output to test_results.json")
