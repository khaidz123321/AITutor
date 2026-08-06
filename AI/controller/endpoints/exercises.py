"""
Endpoint nhận file PDF từ Spring Boot (giảng viên upload),
dùng Local LLM (Qwen 2.5 via Ollama) để trích xuất danh sách câu hỏi tự luận/trắc nghiệm,
rồi trả về list JSON để Spring Boot lưu vào bảng exercise_ai.

LUỒNG:
  Spring Boot → POST /v1/exercises/import-pdf (multipart file)
             ← Python: list[ExtractedExercise] dạng {"data": [...]}
  Spring Boot tự parse và lưu vào bảng exercise_ai.
"""

import os
import io
import json
import re
import tempfile
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from core.config import settings
from schemas.exercise import ExtractedExercise, ImportPdfResponse, Difficulty, BloomLevel, SyncScaffoldRequest, SyncScaffoldResponse, GenerateFromTheoryRequest, GenerateFromTheoryResponse
from core.mapping import _get_default_folder_name
from openai import OpenAI
import requests

import subprocess
import tempfile

def _call_llm(model: str, messages: list, temperature: float, response_format: dict = None) -> str:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True, # BẬT STREAM ĐỂ GIỮ KẾT NỐI NGROK KHÔNG BỊ CHẾT (Lỗi 56)
        "max_tokens": 8192 # Tăng max_tokens/num_predict để tránh DeepSeek bị ngắt giữa chừng khi reasoning
    }
    if response_format:
        payload["response_format"] = response_format
        
    # Write payload to a temporary file to avoid command-line length limits
    fd, temp_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(payload, f)
        
    try:
        result = subprocess.run([
            "curl.exe",
            "-s",
            "-X", "POST",
            url,
            "-H", "Content-Type: application/json",
            "-H", "ngrok-skip-browser-warning: true",
            "-d", f"@{temp_path}"
        ], capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode != 0:
            raise Exception(f"curl failed with return code {result.returncode}: {result.stderr}")
            
        full_content = ""
        full_reasoning = ""
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    if "error" in data:
                        raise Exception(f"LLM Error: {data['error']}")
                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            full_content += delta["content"]
                        if "reasoning" in delta and delta["reasoning"]:
                            full_reasoning += delta["reasoning"]
                except json.JSONDecodeError:
                    pass
                    
        # Nếu model trả về reasoning riêng, gộp chung vào content dưới dạng <think>
        if full_reasoning and not full_content.startswith("<think>"):
            full_content = f"<think>\n{full_reasoning}\n</think>\n{full_content}"
            
        if not full_content.strip():
            raise Exception(f"Empty response or parsing failed. Raw output: {result.stdout[:500]}")
            
        return full_content.strip()
    finally:
        try:
            os.remove(temp_path)
        except:
            pass

router = APIRouter()

# Đọc cấu hình từ .env — dùng chung cho cả import-pdf và generate-scaffold-local
LOCAL_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-r1:14b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.ptitaitutor.com/v1")

local_client = OpenAI(
    api_key="sk-no-key-required",
    base_url=OLLAMA_BASE_URL,
    default_headers={"ngrok-skip-browser-warning": "true"}
)

# ================================================================
# PROMPT dùng để Qwen trích xuất câu hỏi từ nội dung PDF
# ================================================================
_EXTRACT_PROMPT = """Bạn là trợ lý học thuật. Nhiệm vụ: đọc nội dung tài liệu học tập dưới đây và trích xuất TẤT CẢ câu hỏi/bài tập.

YÊU CẦU OUTPUT:
- Trả về ĐÚNG MỘT JSON OBJECT chứa key "data" là một mảng, không thêm bất kỳ văn bản nào khác.
- Định dạng bắt buộc:
  {{
    "data": [
      {{
        "exerciseCode":  "<mã duy nhất, ví dụ AI-PDF-001>",
        "exerciseName":  "<tên ngắn gọn, ≤ 100 ký tự>",
        "difficulty":    "<EASY | MEDIUM | HARD>",
        "bloomLevel":    "<REMEMBERING | UNDERSTANDING | APPLYING | ANALYZING | EVALUATING>",
        "question":      "<nội dung câu hỏi đầy đủ>",
        "correctAnswer": "<đáp án đúng, nếu có; nếu không có thì ghi 'Chưa có đáp án'>"
      }}
    ]
  }}

QUY TẮC xác định difficulty:
- EASY:   câu hỏi nhận biết, định nghĩa đơn giản
- MEDIUM: câu hỏi áp dụng công thức, giải thích
- HARD:   câu hỏi phân tích, tổng hợp, chứng minh

QUY TẮC xác định bloomLevel:
- REMEMBERING:   nhớ lại định nghĩa, liệt kê
- UNDERSTANDING: giải thích, mô tả
- APPLYING:      áp dụng công thức, tính toán
- ANALYZING:     phân tích, so sánh
- EVALUATING:    đánh giá, lập luận, chứng minh

NỘI DUNG TÀI LIỆU:
{content}

JSON OUTPUT (chỉ Object, không giải thích):"""


def _read_pdf_text(file_bytes: bytes) -> str:
    """Trích xuất văn bản từ PDF bằng pypdf (thuần Python, không cần Tesseract)."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text.strip())
        return "\n\n".join(pages_text)
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Thư viện pypdf chưa được cài đặt. Vui lòng chạy: pip install pypdf"
        )
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Không thể đọc file PDF: {str(e)}"
        )


def _parse_llm_json(raw: str) -> list:
    """Parse JSON từ response LLM — hỗ trợ cả JSON Object {data:[...]} và Array [...]"""
    raw = raw.strip()
    
    # 1. Cố gắng trích xuất phần bên trong block ```json ... ```
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
    if match:
        raw = match.group(1).strip()
    else:
        # Nếu không có block, cố gắng xóa markdown rác ở 2 đầu
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()
        
        # Thử lấy từ dấu { đầu tiên đến cuối cùng nếu có text thừa (Bỏ qua [ để tránh nhầm với LaTeX \[ ... \])
        start_idx = raw.find('{')
        if start_idx != -1:
            raw = raw[start_idx:raw.rfind('}')+1]
            
    # Sửa lỗi Invalid \escape thường gặp khi LLM trả về LaTeX (vd: \mathbb, \Q, \l, \sum...)
    # Bằng cách thay thế một dấu \ đơn (không hợp lệ) thành \\
    raw = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', raw)
            
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "data" in parsed:
            return parsed["data"]
        elif isinstance(parsed, list):
            return parsed
    except Exception as e:
        print(f"[LLM JSON Error] Loi parse JSON: {e}. Raw content: {raw[:300]}...")
        
    return []


# ================================================================
# ENDPOINT: POST /v1/exercises/import-pdf
# Spring Boot gọi endpoint này (ExerciseAiServiceImpl.importExercisesFromPdf)
# ================================================================
@router.post("/import-pdf", response_model=ImportPdfResponse)
async def import_exercises_from_pdf(
    file: UploadFile = File(..., description="File PDF chứa đề thi/bài tập do giảng viên upload"),
    authorization: str = Header(default=None, description="Bearer token từ Spring Boot")
):
    """
    Nhận file PDF từ Spring Boot, dùng Qwen 2.5 (Ollama Local) trích xuất câu hỏi,
    trả về list câu hỏi để Spring Boot lưu vào bảng exercise_ai.

    Spring Boot đọc response tại field 'data' (ImportPdfResponse.data).
    """

    # 1. Kiểm tra định dạng file
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Chỉ chấp nhận file PDF (.pdf)"
        )

    # 2. Đọc bytes của file
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không thể đọc file: {str(e)}")

    if not file_bytes:
        raise HTTPException(status_code=400, detail="File PDF trống")

    # 3. Trích xuất văn bản từ PDF
    print(f"[PDF Import] Dang doc file: {filename} ({len(file_bytes) / 1024:.1f} KB)")
    pdf_text = _read_pdf_text(file_bytes)

    if not pdf_text.strip():
        print(f"[Import PDF] Khong the trich xuat text tu file {file.filename}")
        raise HTTPException(
            status_code=422,
            detail="Không thể trích xuất văn bản từ PDF. File có thể là scan (ảnh) — cần PDF dạng text."
        )

    # Qwen 2.5 hỗ trợ context lớn — tăng lên 30.000 ký tự so với giới hạn cũ của Gemini
    pdf_text_truncated = pdf_text[:30000]
    print(f"[PDF Import] Da trich xuat {len(pdf_text)} ky tu tu PDF.")

    # 4. Gọi Qwen 2.5 (Ollama local) để trích xuất câu hỏi
    prompt_text = _EXTRACT_PROMPT.format(content=pdf_text_truncated)
    try:
        raw_output = _call_llm(
            model=LOCAL_MODEL,
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        print(f"[PDF Import] {LOCAL_MODEL} tra ve {len(raw_output)} ky tu JSON.")
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Local LLM ({LOCAL_MODEL}) khong phan hoi: {str(e)}"
        )

    # 5. Parse JSON response
    try:
        raw_list = _parse_llm_json(raw_output)
    except json.JSONDecodeError as e:
        print(f"[Import PDF] Loi parse JSON: {e}\nRaw output:\n{raw_output[:500]}")
        raise HTTPException(
            status_code=500,
            detail="AI không trả về JSON hợp lệ. Vui lòng thử lại."
        )

    if not raw_list:
        raise HTTPException(
            status_code=404,
            detail="AI không tìm thấy câu hỏi nào trong file PDF này."
        )

    # 6. Validate và map sang ExtractedExercise schema
    exercises: List[ExtractedExercise] = []
    for idx, item in enumerate(raw_list, start=1):
        if not isinstance(item, dict):
            continue
        question = item.get("question", "").strip()
        if not question:
            continue  # Bỏ qua câu hỏi trống

        # Đảm bảo exerciseCode luôn unique trong list này
        code = item.get("exerciseCode", f"AI-PDF-{idx:03d}").strip() or f"AI-PDF-{idx:03d}"

        # Ép kiểu enum an toàn — fallback về giá trị mặc định nếu AI trả về sai
        try:
            diff = Difficulty(item.get("difficulty", "MEDIUM").upper())
        except ValueError:
            diff = Difficulty.MEDIUM

        try:
            bloom = BloomLevel(item.get("bloomLevel", "UNDERSTANDING").upper())
        except ValueError:
            bloom = BloomLevel.UNDERSTANDING

        correct_answer = (item.get("correctAnswer") or "Chưa có đáp án").strip()

        exercises.append(ExtractedExercise(
            exerciseCode=code,
            exerciseName=(item.get("exerciseName") or f"Câu hỏi {idx}").strip()[:200],
            difficulty=diff,
            bloomLevel=bloom,
            question=question,
            correctAnswer=correct_answer,
        ))

    print(f"[Import PDF] Hoan tat. AI da tao {len(exercises)} cau hoi tu {filename}")

    return ImportPdfResponse(data=exercises)

# ================================================================
# ENDPOINT: POST /v1/exercises/generate-scaffold-local
# (local_client và LOCAL_MODEL đã được khởi tạo ở đầu file)
# ================================================================

_SCAFFOLD_PROMPT = """Bạn là một giáo sư sư phạm xuất sắc. Dưới đây là một bài tập và đáp án. Nhiệm vụ của bạn là tạo ra một kịch bản dạy học Socratic (scaffolding_steps) gồm 3 đến 5 bước để hướng dẫn sinh viên tự tìm ra đáp án thay vì giải sẵn cho họ.
Hãy suy luận từng bước.

Nội dung bài tập:
{question}

Đáp án đúng:
{answer}

Yêu cầu định dạng: BẮT BUỘC TRẢ VỀ ĐÚNG MỘT MẢNG JSON CHO `scaffolding_steps`, không giải thích gì thêm, định dạng như sau:
[
  {{
    "step_number": 1,
    "step_detail": "<Câu hỏi gợi mở đầu tiên để bắt đầu suy nghĩ>"
  }},
  {{
    "step_number": 2,
    "step_detail": "<Gợi ý tiếp theo nếu sinh viên bí>"
  }}
]
"""

@router.post("/generate-scaffold-local", response_model=SyncScaffoldResponse)
async def generate_scaffold_local(req: SyncScaffoldRequest):
    """
    Sinh Socratic scaffolding_steps cho danh sách bài tập bằng Ollama,
    và ghi ra file JSON để AI Tutor sử dụng.
    """
    safe_subj = _get_default_folder_name(req.subject)
    safe_chap = _get_default_folder_name(req.chapter)
    
    question_bank_dir = os.path.join(settings.BASE_DIR, "prompts", safe_subj, "question_bank")
    os.makedirs(question_bank_dir, exist_ok=True)
    json_path = os.path.join(question_bank_dir, f"{safe_chap}.json")
    
    final_questions = []
    
    print(f"[Scaffold Sync] Dang xu ly {len(req.exercises)} bai tap cho {req.subject} - {req.chapter} bang mo hinh {LOCAL_MODEL}")
    print(f"[Scaffold Sync] Bat dau tao kich ban AI cho chuong {req.chapter}")
    
    for ex in req.exercises:
        print(f"  -> Dang xu ly cau: {ex.exerciseCode}...")
        prompt_text = _SCAFFOLD_PROMPT.format(question=ex.question, answer=ex.correctAnswer)
        
        scaffold_steps = []
        try:
            raw_output = _call_llm(
                model=LOCAL_MODEL,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.1,
                # Try to force JSON if supported (Qwen2.5 supports it nicely)
                response_format={"type": "json_object"} if "qwen" in LOCAL_MODEL.lower() or "llama" in LOCAL_MODEL.lower() else None
            )
            
            # Làm sạch JSON (phòng trường hợp Ollama trả về markdown code block)
            raw_output = re.sub(r"^```(?:json)?\s*", "", raw_output, flags=re.IGNORECASE)
            raw_output = re.sub(r"\s*```$", "", raw_output)
            raw_output = raw_output.strip()
            
            parsed_json = json.loads(raw_output)
            if isinstance(parsed_json, dict) and "scaffolding_steps" in parsed_json:
                scaffold_steps = parsed_json["scaffolding_steps"]
            elif isinstance(parsed_json, list):
                scaffold_steps = parsed_json
            else:
                scaffold_steps = [{"step_number": 1, "step_detail": "Gợi ý: " + ex.correctAnswer}]
                
        except Exception as e:
            print(f"[Scaffold Sync] Loi sinh kich ban cho {ex.exerciseCode}: {e}")
            scaffold_steps = [{"step_number": 1, "step_detail": "Hãy phân tích bài toán và tìm hướng giải. Đáp án tham khảo: " + ex.correctAnswer}]
            
        final_questions.append({
            "id": ex.exerciseCode,
            "topic": ex.exerciseName,
            "question_text": ex.question,
            "scaffolding_steps": scaffold_steps
        })
        
    # Ghi ra JSON file
    output_data = {"questions": final_questions}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)
    print(f"[Scaffold Sync] Hoan tat. Da luu {len(final_questions)} cau vao {json_path}")
    
    return SyncScaffoldResponse(
        success=True,
        message=f"Đã đồng bộ {len(final_questions)} bài tập",
        jsonPath=json_path
    )

# ================================================================
# ENDPOINT: POST /v1/exercises/generate-from-theory
# ================================================================
_DEEPSEEK_GENERATE_QA_PROMPT = """Bạn là một chuyên gia giáo dục và giải toán. 
Nhiệm vụ của bạn là đọc nội dung lý thuyết dưới đây và sinh ra 10 bài tập cốt lõi hoàn toàn mới, trải dài từ mức độ Dễ đến Khó để kiểm tra sự thấu hiểu của sinh viên.
Với MỖI bài tập, bạn phải cung cấp:
1. Nội dung câu hỏi.
2. Đáp án đúng và giải thích chi tiết.

YÊU CẦU ĐỊNH DẠNG OUTPUT: BẮT BUỘC TRẢ VỀ ĐÚNG MỘT OBJECT JSON NẰM TRONG KEY "data", không giải thích gì thêm ngoài phần suy nghĩ của bạn (sẽ nằm trong thẻ <think>).
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

QUY TẮC xác định difficulty:
- EASY:   câu hỏi nhận biết, định nghĩa đơn giản
- MEDIUM: câu hỏi áp dụng công thức, giải thích
- HARD:   câu hỏi phân tích, tổng hợp, chứng minh

QUY TẮC xác định bloom_level:
- REMEMBERING:   nhớ lại định nghĩa, liệt kê
- UNDERSTANDING: giải thích, mô tả
- APPLYING:      áp dụng công thức, tính toán
- ANALYZING:     phân tích, so sánh
- EVALUATING:    đánh giá, lập luận, chứng minh

Nội dung lý thuyết:
{content}
"""

_QWEN_GENERATE_SCAFFOLD_PROMPT = """Bạn là một giáo sư sư phạm xuất sắc.
Dưới đây là danh sách các câu hỏi và đáp án đúng. Nhiệm vụ của bạn là tạo ra các bước gợi mở Socratic (scaffolding_steps) gồm 2-4 bước cho từng câu hỏi, để hướng dẫn sinh viên tự tìm ra đáp án thay vì giải sẵn.

YÊU CẦU ĐỊNH DẠNG OUTPUT: BẮT BUỘC TRẢ VỀ ĐÚNG MỘT MẢNG JSON TRONG OBJECT "data", không giải thích gì thêm.
Cấu trúc JSON bắt buộc phải theo format sau:
{{
  "data": [
    {{
      "id": "<mã duy nhất giữ nguyên từ đầu vào>",
      "topic": "<tên chủ đề giữ nguyên>",
      "question_text": "<nội dung câu hỏi giữ nguyên>",
      "scaffolding_steps": [
        {{
          "step_number": 1,
          "hint": "<gợi ý hoặc câu hỏi gợi mở cho học sinh>",
          "step_detail": "<giải thích chi tiết cho bước này>"
        }},
        {{
          "step_number": 2,
          "hint": "<gợi ý tiếp theo>",
          "step_detail": "<giải thích>"
        }}
      ],
      "common_mistakes": [
        "<sai lầm phổ biến 1 của học sinh>",
        "<sai lầm phổ biến 2>"
      ]
    }}
  ]
}}

Danh sách Câu hỏi và Đáp án:
{qa_json}
"""

import traceback

@router.post("/generate-from-theory", response_model=GenerateFromTheoryResponse)
async def generate_from_theory(req: GenerateFromTheoryRequest):
    try:
        safe_subj = _get_default_folder_name(req.subject)
        safe_chap = _get_default_folder_name(req.chapter)
        
        # 1. TÌM FILE LÝ THUYẾT
        rag_input_dir = os.path.join(settings.BASE_DIR, "data", "rag_input", safe_subj)
        target_file = None
        
        if os.path.exists(rag_input_dir):
            for f in os.listdir(rag_input_dir):
                fname_lower = f.lower()
                # safe_chap đã có dạng "chuong_1" rồi, nên tìm trực tiếp trong tên file
                if f.endswith(".txt") and safe_chap in fname_lower:
                    # Loại trừ loi_noi_dau và các file không phải chương mục tiêu
                    if "loi_noi_dau" not in fname_lower:
                        target_file = os.path.join(rag_input_dir, f)
                        break
                        
        if not target_file:
            raise HTTPException(status_code=404, detail=f"Khong tim thay file ly thuyet cho chuong {req.chapter} mon {req.subject} trong {rag_input_dir}")
            
        print(f"[Multi-Agent] Found theory file: {target_file}")
        with open(target_file, "r", encoding="utf-8") as f:
            theory_content = f.read()
        theory_truncated = theory_content[:2500] # Phải giảm xuống 2500 ký tự vì server Ollama/ngrok của bạn xử lý quá chậm dẫn đến bị ngrok cắt kết nối (Error 56)
        
        print(f"[Multi-Agent] Dang sinh bai tap cho {req.subject} - {req.chapter}")
        
        # 2. STAGE 1: DEEPSEEK GIẢI TOÁN / SINH CÂU HỎI
        qa_list = []
        extracted_subject = ""
        extracted_chapter_number = ""
        extracted_chapter_name = ""
        
        for batch_num in range(3):
            print(f"  -> Stage 1: DeepSeek dang sinh bai tap... (Batch {batch_num + 1}/3)")
            prompt_stage1 = _DEEPSEEK_GENERATE_QA_PROMPT.format(content=theory_truncated)
            try:
                raw_output_stage1 = _call_llm(
                    model=DEEPSEEK_MODEL,
                    messages=[{"role": "user", "content": prompt_stage1}],
                    temperature=0.7 + (batch_num * 0.1), # Tăng nhẹ nhiệt độ để sinh câu hỏi khác nhau mỗi lần
                    response_format={"type": "json_object"}
                )
                    
                if "</think>" in raw_output_stage1:
                    raw_output_stage1 = raw_output_stage1.split("</think>")[-1].strip()
                    
                batch_data = _parse_llm_json(raw_output_stage1)
                if isinstance(batch_data, dict):
                    if not extracted_subject:
                        extracted_subject = batch_data.get("subject", req.subject)
                        extracted_chapter_number = batch_data.get("chapter_number", req.chapter)
                        extracted_chapter_name = batch_data.get("chapter_name", req.chapter)
                    qa_list.extend(batch_data.get("questions", []))
                elif isinstance(batch_data, list):
                    qa_list.extend(batch_data)
            except Exception as e:
                print(f"Lỗi ở batch {batch_num + 1}: {e}")
                
        if len(qa_list) == 0:
            raise HTTPException(status_code=500, detail="DeepSeek Stage 1 khong the sinh ra cau hoi nao.")
            
        # 3. STAGE 2: DÙNG DEEPSEEK (vì Qwen có thể chưa load) VIẾT KỊCH BẢN SƯ PHẠM
        print(f"  -> Stage 2: AI dang soan kich ban Socratic cho {len(qa_list)} bai tap...")
        stage2_model = DEEPSEEK_MODEL  # dùng deepseek vì đây là model duy nhất đang chạy
        final_list = []
        
        # CHIA NHỎ ĐỂ TRÁNH LỖI OOM KHI XỬ LÝ QUÁ NHIỀU CÂU (Batching Stage 2)
        chunk_size = 10
        for i in range(0, len(qa_list), chunk_size):
            qa_chunk = qa_list[i:i + chunk_size]
            print(f"    -> Đang xử lý Stage 2 cho batch {i//chunk_size + 1} (Câu {i+1} đến {i+len(qa_chunk)})...")
            prompt_stage2 = _QWEN_GENERATE_SCAFFOLD_PROMPT.format(qa_json=json.dumps(qa_chunk, ensure_ascii=False))
            try:
                raw_output_stage2 = _call_llm(
                    model=stage2_model,
                    messages=[{"role": "user", "content": prompt_stage2}],
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                if "</think>" in raw_output_stage2:
                    raw_output_stage2 = raw_output_stage2.split("</think>")[-1].strip()
                    
                chunk_final = _parse_llm_json(raw_output_stage2)
                if chunk_final:
                    final_list.extend(chunk_final)
            except Exception as e:
                print(f"Lỗi Stage 2 ở batch {i//chunk_size + 1}: {e}")
                
        if not final_list:
            raise HTTPException(status_code=500, detail="AI Stage 2 khong the tao kich ban cho bat ky cau hoi nao.")
            
        # Kết hợp kết quả Stage 1 và Stage 2 để trả về cho Spring Boot lưu DB, đồng thời inject dữ liệu vào final_list
        db_exercises = []
        
        for final_item in final_list:
            # Tìm dữ liệu từ Stage 1
            correct_answer = "Tham khao kich ban AI"
            difficulty = Difficulty.MEDIUM
            bloom_level = BloomLevel.UNDERSTANDING
            diff_str = "Medium"
            bloom_str = "Understanding"
            lesson_num = ""
            lesson_nam = ""
            
            for stage1_item in qa_list:
                if stage1_item.get("id") == final_item.get("id"):
                    correct_answer = stage1_item.get("correct_answer") or "Khong co dap an"
                    diff_str = str(stage1_item.get("difficulty", "MEDIUM"))
                    bloom_str = str(stage1_item.get("bloom_level", "UNDERSTANDING"))
                    lesson_num = str(stage1_item.get("lesson_number", ""))
                    lesson_nam = str(stage1_item.get("lesson_name", ""))
                    
                    try:
                        difficulty = Difficulty(diff_str.upper())
                    except ValueError:
                        pass
                        
                    try:
                        bloom_level = BloomLevel(bloom_str.upper())
                    except ValueError:
                        pass
                    break
                    
            # Tạo một dict mới với thứ tự key y hệt như template yêu cầu
            ordered_item = {
                "id": final_item.get("id", ""),
                "lesson_number": lesson_num,
                "lesson_name": lesson_nam,
                "topic": final_item.get("topic", ""),
                "difficulty": diff_str.capitalize(),
                "bloom_level": bloom_str.capitalize(),
                "question_text": final_item.get("question_text", ""),
                "full_answer": correct_answer,
                "scaffolding_steps": final_item.get("scaffolding_steps", []),
                "common_mistakes": final_item.get("common_mistakes", [])
            }
            # Cập nhật lại final_item thành ordered_item
            final_item.clear()
            final_item.update(ordered_item)
            
            db_exercises.append(ExtractedExercise(
                exerciseCode=str(final_item.get("id") or "AI-GEN"),
                exerciseName=str(final_item.get("topic") or "Bai tap AI Sinh"),
                difficulty=difficulty,
                bloomLevel=bloom_level,
                question=str(final_item.get("question_text") or "Chua co noi dung cau hoi"),
                correctAnswer=str(correct_answer)
            ))
            
        # 4. LƯU KẾT QUẢ VÀO FILE (Sau khi đã merge xong toàn bộ thông tin)
        question_bank_dir = os.path.join(settings.BASE_DIR, "prompts", safe_subj, "question_bank")
        os.makedirs(question_bank_dir, exist_ok=True)
        json_path = os.path.join(question_bank_dir, f"{safe_chap}.json")
        
        # Thêm meta-data ở mức gốc (Root) của JSON
        output_data = {
            "subject": extracted_subject if extracted_subject else req.subject,
            "chapter_number": extracted_chapter_number if extracted_chapter_number else safe_chap,
            "chapter_name": extracted_chapter_name if extracted_chapter_name else req.chapter,
            "questions": final_list
        }
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=4)
            
        print(f"[Multi-Agent] Hoan tat. Da luu {len(final_list)} cau vao {json_path}")
        
        return GenerateFromTheoryResponse(
            success=True,
            message=f"Multi-Agent đã tự động sinh {len(final_list)} câu hỏi",
            jsonPath=json_path,
            data=db_exercises
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        try:
            with open("crash.log", "w", encoding="utf-8") as f:
                f.write(trace)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Loi he thong: {str(e)}")
