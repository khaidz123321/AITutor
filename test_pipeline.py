import os
import sys
import json
from openai import OpenAI
import re

sys.path.append('d:/Project/AITutor/AI')
# Extract constants directly to avoid FastAPI import errors
with open('d:/Project/AITutor/AI/controller/endpoints/exercises.py', 'r', encoding='utf-8') as f:
    content = f.read()

def extract_prompt(name):
    start = content.find(f'{name} = """')
    if start == -1: return ""
    end = content.find('"""\n', start + len(name) + 5)
    return content[start + len(name) + 5:end]

DEEPSEEK_STEM = extract_prompt('_DEEPSEEK_QA_STEM')
QWEN_SCAFFOLD = extract_prompt('_QWEN_GENERATE_SCAFFOLD_PROMPT')

# We need a small theory context
theory = """
Chương 1: Tập hợp số thực
1.1 Số hữu tỉ và số vô tỉ
Số hữu tỉ là số có thể viết dưới dạng phân số p/q, trong đó p và q là các số nguyên và q khác 0. Ví dụ: 3/4, -1/2.
Số vô tỉ là số không thể viết dưới dạng phân số. Ví dụ: căn bậc hai của 2, pi.
1.2 Khoảng và đoạn
Khoảng mở (a, b) là tập hợp tất cả các số thực x sao cho a < x < b.
Khoảng đóng [a, b] là tập hợp tất cả các số thực x sao cho a <= x <= b.
"""

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

print("========== RUNNING STAGE 1 (DEEPSEEK) ==========")
sys_msg1 = "Bạn là giảng viên chuyên ngành Toán học. Hãy biên soạn CHÍNH XÁC 5 bài tập tự luận bằng Tiếng Việt, BÁM SÁT 100% GIÁO TRÌNH. Môn STEM: CÂU HỏI PHẢI CÓ TÍNH TOÁN/CHỨNG MINH, không chỉ lý thuyết thuần túý. TUYỆT ĐỐI KHÔNG BỊA BÀI NGOÀI GIÁO TRÌNH."
prompt1 = DEEPSEEK_STEM.format(subject="Toán học", content=theory)

try:
    r1 = client.chat.completions.create(
        model="deepseek-r1:14b", # guessing the model name
        messages=[{"role": "system", "content": sys_msg1}, {"role": "user", "content": prompt1}],
        temperature=0.3
    )
    out1 = r1.choices[0].message.content
except Exception as e:
    print("Error calling DeepSeek:", e)
    out1 = ""

# clean think tags
clean_out1 = re.sub(r"<think>.*?</think>", "", out1, flags=re.DOTALL).strip()
print("\n[DeepSeek Output Cleaned]:\n", clean_out1[:1000] + "..." if len(clean_out1)>1000 else clean_out1)

print("\n========== RUNNING STAGE 2 (QWEN) ==========")
sys_msg2 = "Bạn là chuyên gia sư phạm môn Toán học. Nhiệm vụ TỐI CAO của bạn là biên soạn, dịch thuật và kiểm tra 100% CÂU HỎI BÁM SÁT NỘI DUNG GIÁO TRÌNH."
prompt2 = QWEN_SCAFFOLD.format(qa_json=clean_out1, theory_context=theory)

try:
    r2 = client.chat.completions.create(
        model="qwen2.5:14b", # guessing
        messages=[{"role": "system", "content": sys_msg2}, {"role": "user", "content": prompt2}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    out2 = r2.choices[0].message.content
except Exception as e:
    print("Error calling Qwen:", e)
    out2 = ""

print("\n[Qwen Output]:\n", out2)

with open('d:/Project/AITutor/test_out.txt', 'w', encoding='utf-8') as f:
    f.write("=== DEEPSEEK ===\n" + out1 + "\n\n=== QWEN ===\n" + out2)
print("\nSaved full output to test_out.txt")
