import os
import json
import re
from openai import OpenAI

client = OpenAI(
    api_key='sk-no-key-required',
    base_url='https://ollama.ptitaitutor.com/v1',
    default_headers={
        'ngrok-skip-browser-warning': 'true',
        'User-Agent': 'curl/7.81.0'
    }
)

_DEEPSEEK_GENERATE_QA_PROMPT = """Bạn là một chuyên gia giáo dục và giải toán. 
Nhiệm vụ của bạn là đọc nội dung lý thuyết dưới đây và sinh ra 2 bài tập cốt lõi hoàn toàn mới, trải dài từ mức độ Dễ đến Khó để kiểm tra sự thấu hiểu của sinh viên.
Với MỖI bài tập, bạn phải cung cấp:
1. Nội dung câu hỏi.
2. Đáp án đúng và giải thích chi tiết.

YÊU CẦU ĐỊNH DẠNG OUTPUT: BẮT BUỘC TRẢ VỀ ĐÚNG MỘT OBJECT JSON NẰM TRONG KEY "data", không giải thích gì thêm ngoài phần suy nghĩ của bạn (sẽ nằm trong thẻ <think>).
1. BẮT BUỘC 100% TIẾNG VIỆT CHO TOÀN BỘ CÂU HỎI, ĐÁP ÁN. TUYỆT ĐỐI KHÔNG DÙNG TIẾNG ANH HAY TIẾNG TRUNG QUỐC (ngoại trừ các thuật ngữ toán học nếu cần).
2. ĐỐI VỚI CÔNG THỨC LATEX: Bắt buộc phải double-backslash (ví dụ: viết "\\frac", "\\text" thay vì "\frac", "\text").
3. JSON PHẢI HỢP LỆ: Sử dụng dấu nháy kép (") cho CẢ KEY VÀ VALUE. Nếu trong chuỗi value có dấu nháy kép thì escape bằng \".
4. QUAN TRỌNG: CÁC TỪ KHOÁ (KEYS) TRONG JSON BẮT BUỘC PHẢI GIỮ NGUYÊN BẰNG TIẾNG ANH NHƯ MẪU DƯỚI ĐÂY (id, topic, question_text...), KHÔNG ĐƯỢC DỊCH SANG TIẾNG VIỆT.
Cấu trúc JSON bắt buộc phải tuân thủ NGHIÊM NGẶT format sau:
{{
  "data": {{
    "subject": "<Tên môn học trích xuất từ lý thuyết, ví dụ: Giải tích 1 - PTIT>",
    "chapter_number": <Số chương, dạng số nguyên, ví dụ: 1>,
    "chapter_name": "<Tên chương trích xuất từ lý thuyết, ví dụ: Giới hạn của dãy số>",
    "questions": [
      {{
        "id": "<mã duy nhất, ví dụ GT1_C1_1.1_001>",
        "lesson_number": "<số bài học, ví dụ 1.1>",
        "lesson_name": "<tên bài học>",
        "topic": "<tên chủ đề ngắn gọn của câu hỏi>",
        "difficulty": "<Easy | Medium | Hard>",
        "bloom_level": "<Remembering | Understanding | Applying | Analyzing | Evaluating>",
        "question_text": "<nội dung câu hỏi>",
        "correct_answer": "<đáp án/giải chi tiết>"
      }}
    ]
  }}
}}
"""

print('Calling API...')
try:
    response = client.chat.completions.create(
        model='deepseek-r1:14b',
        messages=[{'role': 'system', 'content': _DEEPSEEK_GENERATE_QA_PROMPT}, {'role': 'user', 'content': 'LY THUYET:\nSo phuc z = a + bi'}],
        stream=False,
        temperature=0.7
    )
    raw_output = response.choices[0].message.content
    with open('test_output.txt', 'w', encoding='utf-8') as f:
        f.write(raw_output)
    print('Saved raw output to test_output.txt')
except Exception as e:
    print('API Error:', e)
