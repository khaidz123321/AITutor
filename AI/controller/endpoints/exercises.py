"""
Endpoint nhận file PDF từ Spring Boot (giảng viên upload),
dùng Local LLM (Qwen 2.5 via Ollama) để trích xuất danh sách câu hỏi tự luận/trắc nghiệm,
rồi trả về list JSON để Spring Boot lưu vào bảng exercise_ai.

LUỒNG:
  Spring Boot → POST /v1/exercises/import-pdf (multipart file)
             ← Python: list[ExtractedExercise] dạng {"data": [...]}
  Spring Boot tự parse và lưu vào bảng exercise_ai.
"""

import sys
import io

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

_orig_print = print
def print(*args, **kwargs):
    sep = kwargs.get('sep', ' ')
    end = kwargs.get('end', '\n')
    file = kwargs.get('file', sys.stdout)
    msg = sep.join(str(a) for a in args) + end
    try:
        file.write(msg)
        file.flush()
    except Exception:
        try:
            encoding = getattr(file, 'encoding', None) or 'utf-8'
            clean_msg = msg.encode(encoding, errors='replace').decode(encoding, errors='replace')
            file.write(clean_msg)
            file.flush()
        except Exception:
            pass

import os
import json
import re
import tempfile
import time
import random
from typing import List
import traceback

from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from core.config import settings
from schemas.exercise import ExtractedExercise, ImportPdfResponse, Difficulty, BloomLevel, SyncScaffoldRequest, SyncScaffoldResponse, GenerateFromTheoryRequest, GenerateFromTheoryResponse
from core.mapping import _get_default_folder_name
from openai import OpenAI
import requests

import subprocess
import tempfile

def _call_llm(model: str, messages: list, temperature: float, response_format: dict = None) -> str:
    try:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "max_tokens": 8192
        }
        if response_format:
            kwargs["response_format"] = response_format
            
        response = local_client.chat.completions.create(**kwargs)
        
        full_content = ""
        full_reasoning = ""
        
        for chunk in response:
            if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    full_reasoning += delta.reasoning_content
                if hasattr(delta, 'content') and delta.content:
                    full_content += delta.content
                    
        if not full_content and full_reasoning:
            return "</think>\n" + full_reasoning
            
        return full_content
    except Exception as e:
        print(f"[{model}] Loi khi goi qua API: {e}")
        raise Exception(f"Failed to call {model} via API: {e}")

router = APIRouter()

# Đọc cấu hình từ .env — dùng chung cho cả import-pdf và generate-scaffold-local
LOCAL_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-r1:14b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.ptitaitutor.com/v1")

local_client = OpenAI(
    api_key="sk-no-key-required",
    base_url=OLLAMA_BASE_URL,
    timeout=600.0,
    default_headers={
        "ngrok-skip-browser-warning": "true",
        "User-Agent": "curl/7.81.0"
    }
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



_DIFFICULTY_MAP = {
    "easy": "EASY", "de": "EASY", "đễ": "EASY", "simple": "EASY", "dễ": "EASY",
    "medium": "MEDIUM", "trung binh": "MEDIUM", "trung bình": "MEDIUM", "moderate": "MEDIUM",
    "hard": "HARD", "kho": "HARD", "khó": "HARD", "difficult": "HARD", "advanced": "HARD",
}

_BLOOM_MAP = {
    "remembering": "REMEMBERING", "nhớ": "REMEMBERING", "nhan biet": "REMEMBERING", "nhận biết": "REMEMBERING",
    "understanding": "UNDERSTANDING", "hieu": "UNDERSTANDING", "hiểu": "UNDERSTANDING", "giai thich": "UNDERSTANDING",
    "applying": "APPLYING", "ap dung": "APPLYING", "áp dụng": "APPLYING", "van dung": "APPLYING",
    "analyzing": "ANALYZING", "phan tich": "ANALYZING", "phân tích": "ANALYZING",
    "evaluating": "EVALUATING", "danh gia": "EVALUATING", "đánh giá": "EVALUATING",
    "creating": "EVALUATING", "sang tao": "EVALUATING",
}

def _normalize_difficulty(raw: str) -> Difficulty:
    key = str(raw).strip().lower()
    mapped = _DIFFICULTY_MAP.get(key)
    if mapped:
        try:
            return Difficulty(mapped)
        except ValueError:
            pass
    try:
        return Difficulty(str(key).upper())
    except ValueError:
        return Difficulty.MEDIUM

def _normalize_bloom(raw: str) -> BloomLevel:
    key = str(raw).strip().lower()
    mapped = _BLOOM_MAP.get(key)
    if mapped:
        try:
            return BloomLevel(mapped)
        except ValueError:
            pass
    try:
        return BloomLevel(key.upper())
    except ValueError:
        return BloomLevel.UNDERSTANDING

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


def _force_vietnamese_math(text: str) -> str:
    if not text or not isinstance(text, str):
        return text
    replacements = [
        ("Compute the definite integral", "Tính tích phân xác định"),
        ("Compute the integral", "Tính tích phân"),
        ("Compute the value of", "Tính giá trị của"),
        ("Compute", "Tính"),
        ("Calculate the value of", "Tính giá trị của"),
        ("Calculate", "Tính"),
        ("Find the domain of the function", "Tìm miền xác định của hàm số"),
        ("Find the domain of", "Tìm miền xác định của"),
        ("Find the domain", "Tìm miền xác định"),
        ("Domain of the function", "Miền xác định của hàm số"),
        ("Domain of", "Miền xác định của"),
        ("Domain", "Miền xác định"),
        ("Find the range of", "Tìm tập giá trị của"),
        ("Find the range", "Tìm tập giá trị"),
        ("Find the value of", "Tìm giá trị của"),
        ("Find the limit of", "Tìm giới hạn của"),
        ("Find the limit", "Tìm giới hạn"),
        ("Find the", "Tìm"),
        ("The value of", "Giá trị của"),
        ("Determine whether the integral", "Xét xem tích phân"),
        ("Determine whether the series", "Xét tính hội tụ của chuỗi"),
        ("Determine whether", "Xét xem"),
        ("Determine the", "Xác định"),
        ("Determine", "Xác định"),
        ("Evaluate the integral", "Tính tích phân"),
        ("Evaluate the", "Tính giá trị"),
        ("Evaluate", "Tính giá trị"),
        ("Given that", "Cho biết"),
        ("Given ", "Cho "),
        ("Let ", "Xét "),
        ("Consider the function", "Xét hàm số"),
        ("Show that", "Chứng minh rằng"),
        ("Prove that", "Chứng minh rằng"),
        ("State the", "Nêu"),
        ("Using the definition of", "Sử dụng định nghĩa của"),
        ("Using the definition", "Sử dụng định nghĩa"),
        ("Using ", "Sử dụng "),
        ("True or False", "Đúng hay Sai"),
        ("Solution:", "Lời giải:"),
        ("Answer:", "Đáp án:"),
        ("Question:", "Câu hỏi:"),
        ("Step ", "Bước "),
        ("Sequence", "Dãy số"),
        ("Series", "Chuỗi số"),
        ("Convergent", "Hội tụ"),
        ("Divergent", "Phân kỳ"),
        ("Continuous", "Liên tục"),
    ]
    res = text
    for eng, vie in replacements:
        res = re.sub(re.escape(eng), vie, res, flags=re.IGNORECASE)
    return res


def _contains_foreign_language(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    # Quét chữ Trung, Nhật, Hàn, Nga, Thái, Ả rập
    pattern = r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0400-\u04ff\u0e00-\u0e7f\u0600-\u06ff]'
    return bool(re.search(pattern, text))


def _contains_chinese(text: str) -> bool:
    return _contains_foreign_language(text)


# Các từ toán học / từ viết tắt tiếng Anh được phép xuất hiện trong công thức LaTeX (không bị tính là từ tiếng Anh)
_MATH_EXCEPTIONS = {
    # Biến số đơn ký tự
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm',
    'n', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
    # Từ ngắn không mang nghĩa tiếng Anh trong ngữ cảnh toán
    'in', 'to', 'of', 'on', 'is', 'at', 'or', 'if', 'by', 'do',
    # Hàm / ký hiệu toán học tiêu chuẩn
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'log', 'ln', 'exp', 'lim', 'sup', 'inf',
    'max', 'min', 'det', 'ker', 'dim', 'span', 'rank',
    'div', 'curl', 'grad', 'mod', 'arg', 'sgn',
    # Ký hiệu tập hợp / không gian thường thấy
    'R', 'N', 'Z', 'Q', 'C',
    # Các từ Tiếng Việt thường bị nhận nhầm là Tiếng Anh (ASCII thuần)
    'Cho', 'cho', 'Hay', 'hay', 'Tim', 'tim', 'Tinh', 'tinh',
    'Viet', 'viet', 'cua', 'cac', 'mot', 'hai', 'ba', 'bon',
    'nam', 'sau', 'bay', 'tam', 'chin', 'muoi', 'tren', 'duoi',
    'theo', 'bien', 'ham', 'dao', 'tich', 'phan', 'tong', 'hieu',
    'tiep', 'tuyen', 'phap', 'tuyen', 'diem', 'doan', 'duong',
    # Từ toán học thường xuất hiện trong đề bài tiếng Việt
    'vector', 'norm', 'matrix', 'basis', 'scalar', 'space',
    'null', 'true', 'false',
}


def _count_english_words(text: str) -> tuple:
    """Đếm từ Tiếng Anh thực sự và tổng từ trong văn bản.
    Trả về (số_từ_anh, tổng_từ, tỷ_lệ).
    """
    # Bỏ qua nội dung trong công thức LaTeX $...$ hay \\(...\\) hay \\[...\\]
    text_no_latex = re.sub(r'\$[^$]+\$', ' ', text)
    text_no_latex = re.sub(r'\\\([^)]+\\\)', ' ', text_no_latex)
    text_no_latex = re.sub(r'\\\[[^\]]+\\\]', ' ', text_no_latex)
    # Bỏ qua URL, email, số
    text_no_latex = re.sub(r'https?://\S+', ' ', text_no_latex)
    text_no_latex = re.sub(r'\d+', ' ', text_no_latex)

    all_words = re.findall(r'\b[a-zA-Z]{3,}\b', text_no_latex)
    total = len(all_words)
    if total == 0:
        return 0, 0, 0.0
    real_english = [w for w in all_words if w not in _MATH_EXCEPTIONS and w.lower() not in _MATH_EXCEPTIONS]
    count = len(real_english)
    ratio = count / total
    return count, total, ratio


def _is_english_or_foreign(text: str) -> bool:
    """Phát hiện Tiếng Anh dựa trên TỶ LỆ từ Tiếng Anh (không phải khớp từ khóa cứng).
    - Văn bản dài: tỷ lệ > 35% VÀ ≥ 8 từ Anh → dịch
    - Văn bản ngắn (< 15 từ): ≥ 4 từ Anh thực sự → dịch
    """
    if not text or not isinstance(text, str):
        return False
    if _contains_foreign_language(text):
        return True
    count, total, ratio = _count_english_words(text)
    if total >= 15:
        return ratio > 0.35 and count >= 8
    else:
        # Văn bản ngắn: chỉ cần 4 từ Anh thực sự là đủ để kích hoạt dịch
        return count >= 4


def _ai_translate_item_with_context(item: dict, theory_context: str) -> dict:
    """Sử dụng Qwen 2.5 để dịch BÀI TẬP sang 100% Tiếng Việt dựa vào ĐÚNG NGỮ CẢNH GIÁO TRÌNH MÔN HỌC đó."""
    # Chỉ gửi các trường cần dịch, không gửi scaffolding_steps để tiết kiệm token
    item_to_translate = {
        k: v for k, v in item.items()
        if k in ('topic', 'question_text', 'full_answer', 'detailed_solution', 'common_mistakes')
    }
    prompt = f"""Bạn là một giáo sư sư phạm và dịch thuật chuyên ngành HÀNG ĐẦU VIỆT NAM.
Dưới đây là NỘI DUNG GIÁO TRÌNH LÝ THUYẾT MÔN HỌC và một bài tập đang bị viết bằng tiếng Anh hoặc ngôn ngữ khác.

NỘI DUNG GIÁO TRÌNH MÔN HỌC (dùng để lấy đúng thuật ngữ chuyên ngành):
{theory_context[:1800]}

BÀI TẬP CẦN DỊCH SANG TIẾNG VIỆT:
{json.dumps(item_to_translate, ensure_ascii=False, indent=2)}

YÊU CẦU BẮT BUỘC:
1. DỊCH TOÀN BỘ các trường 'topic', 'question_text', 'full_answer', 'detailed_solution' sang 100% TIẾNG VIỆT tự nhiên.
2. Dùng đúng thuật ngữ chuyên ngành của GIÁO TRÌNH MÔN HỌC ở trên (không phải thuật ngữ chung chung).
3. GIỮ NGUYÊN 100% tất cả công thức LaTeX ($...$, \\(...\\), \\[...\\]). KHÔNG dịch ký hiệu toán học.
4. KHÔNG giải lại bài tập. Chỉ dịch ngôn ngữ, giữ nguyên logic và kết quả.
5. Trả về JSON Object với đúng các trường đã dịch. KHÔNG sinh văn bản nào bên ngoài JSON."""

    try:
        raw = _call_llm(
            model=LOCAL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        if "</think>" in raw:
            raw = raw.split("</think>")[-1].strip()
        parsed = _parse_llm_json(raw)
        if isinstance(parsed, dict) and parsed:
            cleaned_parsed = {
                k: v for k, v in parsed.items()
                if v and isinstance(v, str) and len(v.strip()) > 2 and not _is_placeholder(v)
            }
            return cleaned_parsed if cleaned_parsed else item
        elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
            cleaned_parsed = {
                k: v for k, v in parsed[0].items()
                if v and isinstance(v, str) and len(v.strip()) > 2 and not _is_placeholder(v)
            }
            return cleaned_parsed if cleaned_parsed else item
    except Exception as e:
        print(f"  [AI Translator Error]: {e}")
    return item


def _clean_val(val) -> str:
    if val is None or isinstance(val, (dict, list)):
        return ""
    s = str(val).strip()
    if s in ("{}", "[]", "null", "None"):
        return ""
    return s


_EXACT_PLACEHOLDERS = {
    "{}", "[]", "null", "none",
    "nội dung câu hỏi 100% tiếng việt",
    "<nội dung câu hỏi tự luận bám sát giáo trình bằng 100% tiếng việt>",
    "nội dung câu hỏi tự luận bám sát giáo trình bằng 100% tiếng việt",
    "bài toán tính toán đơn giản có số liệu cụ thể.",
    "bài toán tính toán nhiều bước có số liệu cụ thể.",
    "bài toán chứng minh hoặc tư duy phức tạp.",
    "chưa có nội dung câu hỏi",
    "chưa có đáp án",
    "chỉ ghi kết quả cuối cùng (vd: x=5). cấm lặp lại đề bài.",
    "chỉ ghi kết quả cuối cùng. cấm lặp lại đề bài.",
    "chỉ ghi kết quả cuối cùng hoặc điều phải chứng minh.",
    "dịch từ correct_answer gốc. không lặp lại đề bài.",
    "dịch từ correct_answer gốc",
    "dịch từ detailed_explanation gốc",
    "tên chủ đề",
    "chủ đề 1",
    "chủ đề 2",
    "chủ đề 3",
    "tên bài",
    "<bai_toan_tinh_toan_don_gian_co_so_lieu_cu_the>",
    "<chi_ghi_ket_qua_cuoi_cung_vd_x_bang_5>",
    "<bai_toan_tinh_toan_nhieu_buoc_co_so_lieu_cu_the>",
    "<chi_ghi_ket_qua_cuoi_cung_cam_lap_lai_de_bai>",
    "<bai_toan_chung_minh_hoac_tu_duy_phuc_tap>",
    "<chi_ghi_ket_qua_cuoi_cung_hoac_dieu_phai_chung_minh>",
    "<cau_hoi_ly_thuyet_co_ban_hoac_tinh_huong_don_gian>",
    "<chi_ghi_y_chinh_hoac_ket_luan>",
    "<cau_hoi_tinh_huong_thuc_te_hoac_case_study_muc_trung_binh>",
    "<cau_hoi_danh_gia_phan_bien_hoac_tinh_huong_phuc_tap>",
    "<loi_giai_chi_tiet_tung_buoc>",
    "<giai_thich_chi_tiet_tung_y>",
    "tham khao kich ban ai",
    "tham khảo kịch bản ai",
    "tham khảo kịch bản sư phạm",
    "tham khao kich ban su pham",
    "bài toán tự luận bám sát giáo trình.",
    "bài toán tự luận bám sát giáo trình",
    "xem chi tiết lời giải từng bước trong phần đáp án chi tiết.",
    "xem chi tiết lời giải",
    "xem chi tiết",
    "đáp án 1", "đáp án 2", "đáp án 3",
    "kết quả chính xác 1", "kết quả chính xác 2", "kết quả chính xác 3",
}

def _is_placeholder(val: str) -> bool:
    if not val:
        return True
    s = str(val).lower().strip()
    if s in _EXACT_PLACEHOLDERS:
        return True
    if len(s) < 5 and s in ("{}", "[]", "null", "none"):
        return True
    if any(p in s for p in ["tham khảo kịch bản", "tham khao kich ban", "đáp án 1", "đáp án 2", "đáp án 3", "kết quả chính xác 1", "bài toán tự luận bám sát"]):
        return True
    return False


def _clean_latex_string(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    text = text.strip()
    if text in ("{}", "[]", "null", "None"):
        return ""
    # 0. Loại bỏ block mã JSON thô nếu trót lọt vào văn bản (```json { "question": ... })
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()
    if text.startswith("{") or text.startswith("["):
        # Cố gắng bóc tách câu hỏi bên trong JSON thô bằng regex
        m = re.search(r'"question(?:_text)?"\s*:\s*"([^"]+)"', text)
        if m:
            text = m.group(1)
        elif text in ("{}", "[]"):
            return ""

    # 1. Khôi phục các ký tự LaTeX bị mất backslash (\f -> rac{ -> \frac{, \b -> ar{ -> \bar{, sqrt{ -> \sqrt{)
    text = re.sub(r'(?<!\\)\brac\{', r'\\frac{', text)
    text = re.sub(r'(?<!\\)\bar\{', r'\\bar{', text)
    text = re.sub(r'(?<!\\)\bsqrt\{', r'\\sqrt{', text)
    text = re.sub(r'(?<!\\)\boverline\{', r'\\overline{', text)
    text = text.replace("♠rac", r"\frac").replace("♠", r"\f")
    # 2. Xóa bỏ dấu double backslash phân cách LaTeX dư thừa cho KaTeX / UI renderer (\\( -> \(, \\) -> \))
    text = text.replace(r"\\(", r"\(").replace(r"\\)", r"\)").replace(r"\\[", r"\[").replace(r"\\]", r"\]")
    return text


def _clean_robotic_answer_prefix(question: str, answer: str) -> str:
    """Loại bỏ các câu lặp lại đề bài theo khuôn mẫu ở đầu đáp án (ví dụ: 'Triết học Mác - Lênin được xem là bước tiến vì...')."""
    if not answer or not isinstance(answer, str):
        return answer
    ans = answer.strip()
    if not question or not isinstance(question, str):
        return ans

    # Tìm đoạn tiền tố lặp lại đề bài kéo dài đến từ 'vì', 'là', 'gồm', 'khi', 'rằng' trước mệnh đề nội dung thực sự
    m = re.match(r"^([^.:?!]{15,140}?\b(?:vì|là|gồm|khi|rằng)\b\s*)", ans, flags=re.IGNORECASE)
    if m:
        prefix = m.group(1)
        words_prefix = set(re.findall(r'\w+', prefix.lower()))
        words_q = set(re.findall(r'\w+', question.lower()))
        # Nếu đoạn tiền tố này trùng > 35% từ vựng với câu hỏi (nghĩa là đang lặp lại đề bài)
        if len(words_prefix) >= 3 and len(words_prefix.intersection(words_q)) / len(words_prefix) > 0.35:
            remainder = ans[len(prefix):].strip()
            if remainder and len(remainder) > 15:
                remainder = remainder[0].upper() + remainder[1:]
                return remainder
    return ans


_COURSE_FOLDER_MAP = {
    "course_1": "Triết học Mác - Lênin",
    "course_6": "Kinh tế chính trị Mác - Lênin",
    "course_7": "Triết học Mác - Lênin",
    "course_25": "Giải tích 1",
    "course_26": "Giải tích 2",
    "course_27": "Triết học Mác - Lênin",
    "course_28": "Đại số tuyến tính",
    "course_29": "Toán rời rạc",
}

def _extract_subject_from_theory_text(theory_text: str) -> str:
    """Trích xuất tự động tên môn học từ các dòng tiêu đề (# Header) ở 2000 ký tự đầu tiên của file lý thuyết."""
    if not theory_text:
        return ""
    
    first_chunk = theory_text[:2000]
    lines = [l.strip() for l in first_chunk.splitlines() if l.strip()]
    
    for line in lines[:10]:
        if len(line) < 5:
            continue
            
        clean_line = re.sub(r'^[#*=\-\s]+', '', line).strip()
        
        # 1. Trích xuất từ dạng "KHAI LUẬN VỀ <TÊN MÔN>", "GIỚI THIỆU VỀ <TÊN MÔN>", "TỔNG QUAN VỀ <TÊN MÔN>"
        m_ve = re.search(r'\b(?:khai luận|giới thiệu|tổng quan|nhập môn|bài giảng|giáo trình|nghiên cứu)\s+về\s+([A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸa-zàáảãạăắằẳẵặâấầnẩẫậnđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹ\s\-0-9]{3,60})', clean_line, re.IGNORECASE)
        if m_ve:
            subj = m_ve.group(1).strip()
            subj = re.split(r'[:\-\n]', subj)[0].strip()
            if len(subj) >= 4 and not any(kw in subj.lower() for kw in ["chương", "bài học", "phần", "mục"]):
                return subj.title() if subj.islower() or subj.isupper() else subj

        # 2. Trích xuất từ mẫu "GIÁO TRÌNH <TÊN MÔN>", "MÔN HỌC: <TÊN MÔN>", "HỌC PHẦN: <TÊN MÔN>"
        m_gt = re.search(r'\b(?:giáo trình|môn học|học phần|bài giảng|tài liệu)\s*[:\-]?\s*([A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸa-zàáảãạăắằẳẵặâấầnẩẫậnđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹ\s\-0-9]{3,60})', clean_line, re.IGNORECASE)
        if m_gt:
            subj = m_gt.group(1).strip()
            subj = re.split(r'[:\-\n]', subj)[0].strip()
            if len(subj) >= 4 and not any(kw in subj.lower() for kw in ["chương", "bài học", "phần", "mục"]):
                return subj.title() if subj.islower() or subj.isupper() else subj

        # 3. Nếu dòng bắt đầu bằng # CHƯƠNG X: <TÊN CHỦ ĐỀ/TÊN MÔN>
        if clean_line.isupper() or len(clean_line) > 10:
            m_chuong = re.search(r'^chuơng\s+\d+\s*:\s*(?:khai luận về|tổng quan về|giới thiệu)?\s*([A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸa-zàáảãạăắằẳẵặâấầnẩẫậnđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹ\s\-0-9]{3,60})', clean_line, re.IGNORECASE)
            if m_chuong:
                subj = m_chuong.group(1).strip()
                subj = re.split(r'[:\-\n]', subj)[0].strip()
                if len(subj) >= 4 and not any(kw in subj.lower() for kw in ["chương", "bài học", "phần"]):
                    return subj.title() if subj.islower() or subj.isupper() else subj

    return ""


def _extract_subject_from_filename(filename: str) -> str:
    """Tự động bóc tách tên môn học từ tên file dữ liệu (loại bỏ UUID và thông tin chương/bài)."""
    if not filename:
        return ""
    base = os.path.basename(filename)
    base = os.path.splitext(base)[0]
    
    # Loại bỏ UUID ở đầu file nếu có
    base = re.sub(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}_', '', base, flags=re.IGNORECASE)
    
    # Loại bỏ các hậu tố chỉ chương/bài (như _chuong_1, _chuong_1_chuong_1, _ch1, _part1)
    base = re.sub(r'(?:_chuong_\d+)+', '', base, flags=re.IGNORECASE)
    base = re.sub(r'_ch\d+$', '', base, flags=re.IGNORECASE)
    base = re.sub(r'_part\d+$', '', base, flags=re.IGNORECASE)
    
    clean_name = base.replace("_", " ").strip()
    
    kw_map = {
        "triet hoc maclenin": "Triết học Mác - Lênin",
        "triet hoc mac lenin": "Triết học Mác - Lênin",
        "kinh te chinh tri maclenin": "Kinh tế chính trị Mác - Lênin",
        "tu tuong ho chi minh": "Tư tưởng Hồ Chí Minh",
        "chu nghia xa hoi khoa hoc": "Chủ nghĩa xã hội khoa học",
        "lich su dang": "Lịch sử Đảng Cộng sản Việt Nam",
        "kinh te vi mo": "Kinh tế vĩ mô",
        "kinh te vi mo": "Kinh tế vi mô",
        "luat kinh te": "Luật kinh tế",
        "luat thuong mai": "Luật thương mại",
        "quan tri hoc": "Quản trị học",
        "marketing can ban": "Marketing căn bản",
        "tam ly hoc dai cuong": "Tâm lý học đại cương",
        "xa hoi hoc": "Xã hội học",
        "ly luan nha nuoc va phap luat": "Lý luận Nhà nước và Pháp luật",
        "giai tich 1": "Giải tích 1",
        "giai tich 2": "Giải tích 2",
        "dai so tuyen tinh": "Đại số tuyến tính",
        "toan roi rac": "Toán rời rạc",
        "vat ly dai cuong": "Vật lý đại cương",
        "co so du lieu": "Hệ quản trị cơ sở dữ liệu",
        "mang may tinh": "Mạng máy tính",
    }
    
    clean_lower = clean_name.lower()
    for kw, display in kw_map.items():
        if kw in clean_lower:
            return display
            
    if len(clean_name) >= 3 and not re.match(r'^course_\d+$', clean_name, re.IGNORECASE):
        return clean_name.title()
        
    return ""


def _get_clean_subject_display_name(subject_code: str, target_file: str = "", theory_text: str = "") -> str:
    """Tự động chuyển mã môn dạng 'course_7' hoặc 'course_27' thành tên hiển thị tiếng Việt tổng quát cho MỌI môn học."""
    if not subject_code:
        return "môn học"

    code_lower = subject_code.strip().lower()
    
    # 1. Tra từ điển tĩnh trước
    if code_lower in _COURSE_FOLDER_MAP:
        return _COURSE_FOLDER_MAP[code_lower]

    # 2. Nếu tên subject đã là tiếng Việt có dấu/tự nhiên (không phải dạng mã course_X)
    if not re.match(r'^course_\d+$', code_lower, re.IGNORECASE):
        clean_s = subject_code.replace("_", " ").strip()
        return clean_s.title() if clean_s.islower() or clean_s.isupper() else clean_s

    # 3. Trích xuất tự động từ tiêu đề nội dung lý thuyết (Động cho mọi môn)
    subj_from_theory = _extract_subject_from_theory_text(theory_text)
    if subj_from_theory:
        return subj_from_theory

    # 4. Trích xuất tự động từ tên file tài liệu target_file
    subj_from_file = _extract_subject_from_filename(target_file)
    if subj_from_file:
        return subj_from_file

    return "môn học"


def _sanitize_course_code_mentions(text: str, clean_subject: str) -> str:
    """Tự động thay thế các từ 'course_7', 'course_27' xuất hiện dư thừa trong câu hỏi/đáp án thành tên môn học chuẩn."""
    if not text or not isinstance(text, str):
        return text
    if not clean_subject:
        clean_subject = "môn học"
    # Thay 'môn course_7' hoặc 'môn course_27' -> 'môn Triết học Mác - Lênin'
    text = re.sub(r'môn\s+course_\d+', f"môn {clean_subject}", text, flags=re.IGNORECASE)
    # Thay độc lập 'course_7' -> 'Triết học Mác - Lênin'
    text = re.sub(r'\bcourse_\d+\b', clean_subject, text, flags=re.IGNORECASE)
    return text


def _fix_json_backslashes(raw: str) -> str:
    """
    Chiến lược: thay thế từng ký tự backslash không hợp lệ JSON bằng double-backslash.
    Đây là cách duy nhất tránh được vòng lặp regex chồng chéo.
    """
    result = []
    i = 0
    valid_escapes = set(r'"\/ntu')
    while i < len(raw):
        ch = raw[i]
        if ch == '\\':
            # Look at next char
            if i + 1 < len(raw):
                nch = raw[i + 1]
                if nch == '\\':
                    # Already a valid \\ pair – keep as-is
                    result.append('\\\\')
                    i += 2
                    continue
                elif nch in valid_escapes:
                    if nch == 'u':
                        # Check \uXXXX
                        if i + 5 < len(raw) and all(c in '0123456789abcdefABCDEF' for c in raw[i+2:i+6]):
                            result.append(raw[i:i+6])
                            i += 6
                            continue
                    # Valid JSON escape like \n, \t, \r, \", \/
                    result.append('\\')
                    result.append(nch)
                    i += 2
                    continue
                else:
                    # Invalid JSON escape like \s, \{, \f, \sqrt, \frac etc.
                    # Escape the backslash
                    result.append('\\\\')
                    i += 1
                    continue
            else:
                result.append('\\\\')
                i += 1
        else:
            result.append(ch)
            i += 1
    return ''.join(result)


def _extract_json_block(raw: str) -> str:
    """Extract first JSON block from raw LLM output."""
    raw = raw.strip()
    # Try to strip markdown code fences first
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Strip leading/trailing backtick fences without closing
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw).strip()
    return raw


def _try_load_json(raw: str):
    """Try to load JSON, and return parsed object or None."""
    # Pre-fix common single-backslash LaTeX commands in raw JSON strings before json.loads parses \f, \b, \t
    raw = re.sub(r'\\(frac|sqrt|bar|overline|lim|sum|int|infty|theta|alpha|beta|gamma|delta|epsilon|in|subset|cup|cap|le|ge|neq|times|div)\b', r'\\\\\1', raw)
    # Remove trailing commas before ] or }
    cleaned = re.sub(r',\s*([\]}])', r'\1', raw)
    # Remove JS-style comments
    cleaned = re.sub(r'//[^\n]*', '', cleaned)
    try:
        return json.loads(cleaned, strict=False)
    except Exception:
        return None


def _parse_llm_json(raw: str):
    """
    Robust JSON parser for LLM output.
    Strategy:
    1. Extract markdown code block if any
    2. Strip think tags
    3. Try direct parse
    4. Fix backslashes character-by-character, retry
    5. Fallback: regex extraction
    6. Last resort: wrap raw string as list of dicts
    """
    if not raw:
        return []

    # Step 0: Pre-fix LaTeX commands before stripping control chars
    raw = re.sub(r'\\(frac|sqrt|bar|overline|lim|sum|int|infty|theta|alpha|beta|gamma|delta|epsilon|in|subset|cup|cap|le|ge|neq|times|div)\b', r'\\\\\1', raw)
    # Strip control chars except legal whitespace
    raw = raw.replace('\x0c', '').replace('\u2660', '')
    raw = re.sub(r'[\x00-\x08\x0b\x0e-\x1f]', '', raw)

    # Step 1: Extract JSON block from markdown fences
    raw = _extract_json_block(raw)

    # Step 2: Remove <think>...</think> tags
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    if '</think>' in raw:
        raw = raw.split('</think>')[-1].strip()

    def _unwrap(parsed):
        """Extract list from parsed JSON."""
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            if 'data' in parsed:
                d = parsed['data']
                if isinstance(d, list):
                    return d
                if isinstance(d, dict) and 'questions' in d and isinstance(d['questions'], list):
                    return d['questions']
                if isinstance(d, dict) and 'exercises' in d and isinstance(d['exercises'], list):
                    return d['exercises']
            if 'questions' in parsed and isinstance(parsed['questions'], list):
                return parsed['questions']
            if 'exercises' in parsed and isinstance(parsed['exercises'], list):
                return parsed['exercises']
            # Chỉ unwrap thành list NẾU dict này thực sự chứa trường câu hỏi
            if parsed.get("question_text") or parsed.get("question") or parsed.get("questionText"):
                return [parsed]
            return []
        return None

    # Step 3: Try parse as-is
    parsed = _try_load_json(raw)
    if parsed is not None:
        result = _unwrap(parsed)
        if result is not None:
            return result

    # Step 4: Fix backslashes and retry
    fixed = _fix_json_backslashes(raw)
    parsed = _try_load_json(fixed)
    if parsed is not None:
        result = _unwrap(parsed)
        if result is not None:
            return result

    # Step 5: Log error and try Fallback - extract individual {...} objects
    print(f"      [LLM JSON Error] Loi parse JSON. RAW: {repr(raw[:300])}")
    extracted_objects = []
    object_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(object_pattern, fixed, re.DOTALL)
    for m in matches:
        m_cleaned = re.sub(r',\s*\}', '}', m)
        p = _try_load_json(m_cleaned)
        if isinstance(p, dict):
            extracted_objects.append(p)
    if extracted_objects:
        return extracted_objects

    # Step 6: Last resort
    return [{"raw_content": raw}]




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

# ----------------------------------------------------------------
# SUBJECT CLASSIFIER
# Giải pháp thực sự: 2 tầng
#   Tầng 1 — Exact map: khớp tên môn chính xác (không sai), bảo trì dễ
#   Tầng 2 — Keyword fallback: có môn mới chưa có trong map
# ----------------------------------------------------------------

# Tầng 1: Map chính xác theo tên môn (bảo trì bằng cách thêm vào dict)
_SUBJECT_TYPE_MAP: dict[str, str] = {
    # ===== XÃ HỘI / LÝ LUẬN =====
    "triết học mác-lệnin":         "SOCIAL",
    "triết học":                    "SOCIAL",
    "kinh tế chính trị mác-lệnin": "SOCIAL",
    "kinh tế chính trị":           "SOCIAL",
    "chủ nghĩa xã hội khoa học":  "SOCIAL",
    "tư tưởng hồ chí minh":       "SOCIAL",
    "tư tưởng hcm":                 "SOCIAL",
    "pháp luật đại cương":          "SOCIAL",
    "luật đại cương":               "SOCIAL",
    "luật kinh tế":                 "SOCIAL",
    "luật lao động":                "SOCIAL",
    "kinh tế vi mô":                 "SOCIAL",
    "kinh tế vĩ mô":                 "SOCIAL",
    "kế toán đại cương":            "SOCIAL",
    "quản trị học":                 "SOCIAL",
    "marketing":                     "SOCIAL",
    "xã hội học":                   "SOCIAL",
    "lịch sử đảng cộng sản việt nam": "SOCIAL",
    "lịch sử việt nam":             "SOCIAL",
    # ===== STEM =====
    "giải tích 1":                   "STEM",
    "giải tích 2":                   "STEM",
    "giải tích":                     "STEM",
    "đại số":                        "STEM",
    "đại số tuyến tính":            "STEM",
    "xác suất thống kê":             "STEM",
    "toán rời rạc 1":               "STEM",
    "toán rời rạc 2":               "STEM",
    "toán rời rạc":                 "STEM",
    "vật lý ứng dụng":               "STEM",
    "vật lý đại cương":              "STEM",
    "vật lý":                        "STEM",
    "kỹ thuật số":                  "STEM",
    "điện tử số":                    "STEM",
    "xử lý tín hiệu số":            "STEM",
    "lý thuyết thông tin":           "STEM",
    "kiến trúc máy tính":            "STEM",
    "hệ điều hành":                  "STEM",
    "cơ sở dữ liệu":               "STEM",
    "hệ quản trị cơ sở dữ liệu": "STEM",
    "mạng máy tính":                 "STEM",
    "nhập môn công nghệ phần mềm":  "STEM",
    "nhập môn trí tuệ nhân tạo":    "STEM",
    "an toàn và bảo mật hệ thống thông tin": "STEM",
    "an toàn thông tin":              "STEM",
    "bảo mật mạng":                 "STEM",
    "lập trình hướng đối tượng":    "STEM",
    "cấu trúc dữ liệu và thuật toán": "STEM",
    "cấu trúc dữ liệu":            "STEM",
    "lập trình c":                   "STEM",
    "lập trình python":             "STEM",
    "lập trình java":               "STEM",
    "phát triển ứng dụng web":       "STEM",
    "hóa học":                       "STEM",
    "sinh học":                      "STEM",
}

# Tầng 2: Keyword fallback (cho môn chưa có trong map)
_SOCIAL_KW = {
    "triết", "mác", "lệnin", "chủ nghĩa", "xã hội học",
    "tư tưởng", "kinh tế chính trị", "pháp luật", "luật",
    "lịch sử", "tâm lý", "giáo dục", "nhân văn", "văn hóa",
    "tiếng anh", "english", "ngoại ngữ", "marketing", "kế toán",
}
_STEM_KW = {
    "toán", "giải tích", "đại số", "xác suất", "vật lý", "hóa", "sinh học",
    "kỹ thuật", "điện", "mạng", "thuật toán", "lập trình", "cơ sở dữ liệu",
    "hệ điều hành", "an toàn", "bảo mật", "tin học", "công nghệ", "cntt",
    "máy tính", "phần mềm", "trí tuệ", "tín hiệu", "công nghệ thông tin",
}

def _classify_subject_type(subject: str, target_file: str = "", theory_text: str = "") -> str:
    """
    Phân loại môn học thành 'STEM' hoặc 'SOCIAL'.
    Tầng 1: Kiểm tra exact map cho tên môn.
    Tầng 2: Quét từ khóa fuzzy trong mã môn + tên file giáo trình + 2000 ký tự lý thuyết.
    Default: STEM.
    """
    search_text = f"{subject} {target_file} {theory_text[:2000]}".lower().strip()
    normalized_subj = subject.lower().strip()

    # Tầng 1 — exact map
    if normalized_subj in _SUBJECT_TYPE_MAP:
        result = _SUBJECT_TYPE_MAP[normalized_subj]
        print(f"[Classifier] '{subject}' -> {result} (exact map)")
        return result

    # Tầng 2 — Quét từ khóa trong tổng thể (tên môn, tên file, nội dung lý thuyết)
    social_score = sum(1 for kw in _SOCIAL_KW if kw in search_text)
    stem_score = sum(1 for kw in _STEM_KW if kw in search_text)

    if social_score > stem_score:
        print(f"[Classifier] '{subject}' -> SOCIAL (matched content score: social={social_score}, stem={stem_score})")
        return "SOCIAL"
    elif stem_score > social_score:
        print(f"[Classifier] '{subject}' -> STEM (matched content score: social={social_score}, stem={stem_score})")
        return "STEM"

    print(f"[Classifier] '{subject}' -> STEM (default fallback)")
    return "STEM"


# ----------------------------------------------------------------
# PROMPT NHÁNH 1: STEM
# ----------------------------------------------------------------
def _is_valid_exercise_data(batch_data) -> bool:
    """Kiểm tra xem dữ liệu JSON trả về có chứa danh sách bài tập/câu hỏi hợp lệ không (có question_text hoặc question)."""
    if not batch_data:
        return False
    
    questions_list = []
    if isinstance(batch_data, dict):
        q = batch_data.get("questions") or batch_data.get("data") or batch_data.get("exercises")
        if isinstance(q, list):
            questions_list = q
        elif isinstance(q, dict):
            sub_q = q.get("questions") or q.get("exercises")
            if isinstance(sub_q, list):
                questions_list = sub_q
            elif q.get("question_text") or q.get("question"):
                return True
        elif batch_data.get("question_text") or batch_data.get("question"):
            return True
    elif isinstance(batch_data, list):
        questions_list = batch_data

    if not questions_list:
        return False

    for item in questions_list:
        if isinstance(item, dict):
            q_text = item.get("question_text") or item.get("question") or item.get("questionText") or item.get("raw_content")
            if q_text and len(str(q_text).strip()) > 10 and not _is_placeholder(str(q_text)):
                return True
        elif isinstance(item, str) and len(item.strip()) > 15:
            return True
            
    return False


def _is_duplicate_question(new_q: str, existing_questions: list) -> bool:
    """Kiểm tra câu hỏi mới có bị trùng lặp nội dung với danh sách đã có hay không (>65% similarity)."""
    if not new_q or not isinstance(new_q, str):
        return False
    q1 = re.sub(r'[\s\W]+', '', new_q.lower())
    if len(q1) < 10:
        return False
    for existing in existing_questions:
        if not existing or not isinstance(existing, str):
            continue
        q2 = re.sub(r'[\s\W]+', '', existing.lower())
        if q1 == q2:
            return True
        if len(q1) > 15 and len(q2) > 15:
            min_len = min(len(q1), len(q2))
            common = 0
            for a, b in zip(q1, q2):
                if a == b:
                    common += 1
                else:
                    break
            if common / min_len > 0.65:
                return True
    return False


def _generate_fallback_exercises(subject: str, chapter: str, theory_text: str) -> list:
    """Hàm tạo bài tập cấp cứu trực tiếp BẬC ĐẠI HỌC tổng quát cho mọi môn khi LLM gặp sự cố."""
    prompt = f"""Bạn là Giáo sư / Giảng viên Đại học biên soạn đề thi môn {subject}. Hãy biên soạn CHÍNH XÁC 3 bài tập tự luận BẬC ĐẠI HỌC SÂU SẮC bằng Tiếng Việt dựa trên nội dung lý thuyết sau:

Lý thuyết chương {chapter}:
{theory_text[:5000]}

══════════════════════════════════════════════
 QUY ĐỊNH BẮT BUỘC VỀ TRÌNH ĐỘ BẬC ĐẠI HỌC, ĐỘ PHỨC TẠP VÀ ĐA DẠNG HÓA
══════════════════════════════════════════════
1. TỔNG QUÁT VÀ BÁM SÁT MÔN {subject}:
   - Đọc kỹ lý thuyết chương {chapter} môn {subject} để khai thác kiến thức chuyên môn bậc Đại học.
2. QUY TẮC RẢI ĐỀU NỘI DUNG THEO 3 PHẦN CỦA VĂN BẢN:
   - Đọc TOÀN BỘ văn bản từ đầu đến cuối và chia văn bản thành 3 phân đoạn tỷ lệ: PHẦN ĐẦU (1/3 đầu), PHẦN GIỮA (1/3 giữa), PHẦN CUỐI (1/3 cuối).
   - Trích xuất ĐÚNG mã số bài/mục (`lesson_number`) và tên bài/tiêu đề mục (`lesson_name`) THỰC TẾ có trong file lý thuyết.
3. CƠ CHẾ ĐA DẠNG HÓA VÀ CHỐNG LẶP ĐỀ (ANTI-REPETITION):
   - TUYỆT ĐỐI CẤM chỉ khai thác duy nhất một định lý hay bài toán quen thuộc (như Rolle / Lagrange) từ lần này sang lần khác. Hãy chủ động chọn các chủ đề và dạng bài khác trong giáo trình.
4. YÊU CẦU ĐỀ BÀI CHI TIẾT & TĂNG ĐỘ PHỨC TẠP (HIGH COMPLEXITY):
   - TUYỆT ĐỐI CẤM các câu hỏi phát biểu định lý ngắn 1 dòng suông dạng 'Cho hàm số f(x)... chứng minh c tồn tại'.
   - Đề bài tự luận BẮT BUỘC phải CHI TIẾT với các biểu thức/hàm số/tham số cụ thể hoặc bài toán 2-3 ý a, b, c yêu cầu tính toán / biến đổi chuyên sâu.
5. ĐÁP ÁN `full_answer` BẮT BUỘC PHẢI LÀ KẾT QUẢ/ĐÁP SỐ CHÍNH XÁC CỤ THỂ 100%:
   - TUYỆT ĐỐI CẤM bịa đáp án bằng số 0, 1 hoặc các chuỗi giữ chỗ lười 3 chữ như 'Điểm c tồn tại'. `full_answer` phải ghi rõ kết quả tính toán hoặc kết luận biểu thức chính xác của môn {subject}.
6. BẮT BUỘC trả về kết quả dưới định dạng JSON.

Trả về ĐÚNG MỘT JSON Object có key "questions" chứa mảng 3 bài tập tự luận bậc Đại học:
{{
  "questions": [
    {{
      "id": "FB_001",
      "lesson_number": "Mã bài/mục thực tế ở phần đầu văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần đầu văn bản",
      "topic": "Bài tập Nền tảng Bậc Đại học môn {subject}",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "question_text": "Nội dung câu 1 tự luận Bậc Đại học mức Dễ (Phần đầu tài liệu) môn {subject}...",
      "full_answer": "Kết quả / Đáp số chính xác của câu 1 môn {subject}",
      "detailed_solution": "Lời giải chi tiết từng bước bằng Tiếng Việt",
      "scaffolding_steps": [{{"step_number": 1, "hint": "Gợi ý 1", "step_detail": "Bước 1"}}]
    }},
    {{
      "id": "FB_002",
      "lesson_number": "Mã bài/mục thực tế ở phần giữa văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần giữa văn bản",
      "topic": "Bài tập Vận dụng Bậc Đại học môn {subject}",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "question_text": "Nội dung câu 2 tự luận Bậc Đại học mức Trung bình (Phần giữa tài liệu) môn {subject}...",
      "full_answer": "Kết quả / Đáp số chính xác của câu 2 môn {subject}",
      "detailed_solution": "Lời giải chi tiết từng bước bằng Tiếng Việt",
      "scaffolding_steps": [{{"step_number": 1, "hint": "Gợi ý 2", "step_detail": "Bước 1"}}]
    }},
    {{
      "id": "FB_003",
      "lesson_number": "Mã bài/mục thực tế ở phần cuối văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần cuối văn bản",
      "topic": "Bài tập Nâng cao Bậc Đại học môn {subject}",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "question_text": "Nội dung câu 3 tự luận Bậc Đại học mức Khó (Phần cuối tài liệu) môn {subject}...",
      "full_answer": "Kết luận chứng minh / Đáp số chính xác của câu 3 môn {subject}",
      "detailed_solution": "Lời giải chi tiết từng bước bằng Tiếng Việt",
      "scaffolding_steps": [{{"step_number": 1, "hint": "Gợi ý 3", "step_detail": "Bước 1"}}]
    }}
  ]
}}
"""
    try:
        raw = _call_llm(
            model=LOCAL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            response_format={"type": "json_object"}
        )
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        if "</think>" in raw:
            raw = raw.split("</think>")[-1].strip()
        parsed = _parse_llm_json(raw)
        
        final_list = []
        if isinstance(parsed, dict) and parsed.get("questions"):
            temp_list = parsed["questions"]
        elif isinstance(parsed, list):
            temp_list = parsed
        else:
            temp_list = []
            
        for q in temp_list:
            if not _is_duplicate_question(q, final_list):
                final_list.append(q)
        return final_list
    except Exception as e:
        print(f"  [Fallback Exercise Generator Error]: {e}")
    return []


# ----------------------------------------------------------------
# PROMPT NHÁNH 1: STEM (Kỹ thuật, Tự nhiên, CNTT...)
# ----------------------------------------------------------------
_DEEPSEEK_QA_STEM = """Bạn là một Giáo sư / Giảng viên Đại học biên soạn đề thi cấp Đại học.
Nhiệm vụ: Đọc NỘI DUNG LÝ THUYẾT GIÁO TRÌNH môn {subject} dưới đây và sinh ra CHÍNH XÁC 3 bài tập tự luận BẮT BUỘC BÁM SÁT 100% GIÁO TRÌNH VÀ ĐẠT TRÌNH ĐỘ BẬC ĐẠI HỌC.
Môn học: {subject} (Thuộc khối ngành Kỹ thuật / Tự nhiên / Công nghệ / Toán / Lý / CNTT).

══════════════════════════════════════════════
 QUY ĐỊNH BẮT BUỘC VỀ NGÔN NGỮ VÀ NỘI DUNG
══════════════════════════════════════════════
1. BẮT BUỘC 100% TIẾNG VIỆT CÓ DẤU CHUẨN XÁC:
   - BẮT BUỘC tất cả các trường "topic", "question_text", "correct_answer", "detailed_explanation" PHẢI ĐƯỢC SOẠN 100% BẰNG TIẾNG VIỆT.
   - TUYỆT ĐỐI CẤM SOẠN CÂU HỎI VÀ ĐÁP ÁN BẰNG TIẾNG ANH HOẶC NGOẠI NGỮ KHÁC.
2. TỔNG QUÁT VÀ BÁM SÁT MÔN {subject}:
   - Đọc kỹ toàn bộ văn bản lý thuyết môn {subject} để rút ra các định lý, công thức, mô hình, giải thuật hoặc bài toán chuyên môn cốt lõi.
3. QUY TẮC RẢI ĐỀU NỘI DUNG THEO 3 PHẦN CỦA VĂN BẢN:
   - Chia văn bản thành 3 phân đoạn tỷ lệ (PHẦN ĐẦU - 1/3 đầu, PHẦN GIỮA - 1/3 giữa, PHẦN CUỐI - 1/3 cuối). 3 câu hỏi BẮT BUỘC rải đều:
     * Câu 1 thuộc PHẦN ĐẦU tài liệu (1/3 đầu văn bản).
     * Câu 2 thuộc PHẦN GIỮA tài liệu (1/3 giữa văn bản).
     * Câu 3 thuộc PHẦN CUỐI tài liệu (1/3 cuối văn bản).
   - Trích xuất ĐÚNG mã số bài/mục (`lesson_number`) và tên bài/tiêu đề mục (`lesson_name`) THỰC TẾ xuất hiện trong file lý thuyết.
4. CƠ CHẾ ĐA DẠNG HÓA VÀ CHỐNG LẶP ĐỀ:
   - TUYỆT ĐỐI CẤM chỉ tập trung khai thác duy nhất một định lý quen thuộc từ lần này sang lần khác!
   - Hãy chủ động khai thác các mảng kiến thức khác trong giáo trình môn {subject}.
5. YÊU CẦU ĐỀ BÀI CHI TIẾT & TĂNG ĐỘ PHỨC TẠP BẬC ĐẠI HỌC:
   - TUYỆT ĐỐI CẤM phát biểu đề bài tự luận sáo rỗng ngắn 1 dòng suông.
   - Đề bài tự luận BẮT BUỘC phải CHI TIẾT: Cho biểu thức toán học / tham số / hàm số cụ thể, yêu cầu sinh viên thực hiện 2-3 bước tính toán / biến đổi chuyên sâu.
6. ĐÁP ÁN `correct_answer` BẮT BUỘC PHẢI LÀ KẾT QUẢ/ĐÁP SỐ CHÍNH XÁC CỤ THỂ 100%:
   - Ghi rõ ĐÁP SỐ / KẾT QUẢ TÍNH TOÁN / BIỂU THỨC KẾT LUẬN CỤ THỂ 100%.

══════════════════════════════════════════════
 TIÊU CHUẨN PHÂN HOÁ RANH GIỚI 3 MỨC ĐỘ (DỄ - TRUNG BÌNH - KHÓ)
══════════════════════════════════════════════
► CÂU 1 (Dễ - Thông hiểu | Dành cho mức điểm 5 - 6):
  - Áp dụng trực tiếp 1 công thức / định lý / giải thuật duy nhất thuộc 1/3 PHẦN ĐẦU văn bản. Cho sẵn đầy đủ thông số đầu vào.

► CÂU 2 (Trung bình - Vận dụng | Dành cho mức điểm 7 - 8):
  - Bài toán đa bước tính toán thuộc 1/3 PHẦN GIỮA văn bản. Bắt buộc thực hiện 2 bước tính toán trung gian.

► CÂU 3 (Khó - Đánh giá / Phân tích nâng cao | Dành cho mức điểm 9 - 10):
  - Bài toán tư duy bậc cao thuộc 1/3 PHẦN CUỐI văn bản (Chứng minh tổng quát, tối ưu hóa hệ thống hoặc phân tích biện luận tham số tới hạn).

Cấu trúc JSON bắt buộc:
{{
  "questions": [
    {{
      "id": "EX_001",
      "lesson_number": "Mã bài/mục thực tế ở phần đầu văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần đầu văn bản",
      "topic": "Tên chủ đề bài toán môn {subject} (Phần đầu)",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "question_text": "Nội dung câu 1 tự luận bằng Tiếng Việt bậc Đại học mức Dễ (Chi tiết các thông số)...",
      "correct_answer": "Kết quả tính toán / Đáp số bằng Tiếng Việt chính xác của câu 1 môn {subject}",
      "detailed_explanation": "Lời giải câu 1 chi tiết từng bước bằng Tiếng Việt."
    }},
    {{
      "id": "EX_002",
      "lesson_number": "Mã bài/mục thực tế ở phần giữa văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần giữa văn bản",
      "topic": "Tên chủ đề bài toán môn {subject} (Phần giữa)",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "question_text": "Nội dung câu 2 tự luận bằng Tiếng Việt bậc Đại học mức Trung bình (Bài toán đa bước phần giữa)...",
      "correct_answer": "Kết quả tính toán / Đáp số bằng Tiếng Việt chính xác của câu 2 môn {subject}",
      "detailed_explanation": "Lời giải câu 2 chi tiết từng bước bằng Tiếng Việt."
    }},
    {{
      "id": "EX_003",
      "lesson_number": "Mã bài/mục thực tế ở phần cuối văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần cuối văn bản",
      "topic": "Tên chủ đề bài toán môn {subject} (Phần cuối)",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "question_text": "Nội dung câu 3 tự luận bằng Tiếng Việt bậc Đại học mức Khó (Bài toán chứng minh / nâng cao phần cuối)...",
      "correct_answer": "Đáp số / Kết luận biểu thức bằng Tiếng Việt chính xác của câu 3 môn {subject}",
      "detailed_explanation": "Lời giải câu 3 chi tiết từng bước bằng Tiếng Việt."
    }}
  ]
}}

Nội dung lý thuyết giáo trình môn {subject}:
{content}

BẮT BUỘC TRẢ VỀ CHÍNH XÁC MỘT JSON OBJECT CÓ KEY "questions" LÀ MẢNG GỒM 3 CÂU HỎI SOẠN 100% BẰNG TIẾNG VIỆT.
"""


# ----------------------------------------------------------------
# PROMPT NHÁNH 2: SOCIAL (Xã hội, Kinh tế, Luật, Quản trị, Triết học...)
# ----------------------------------------------------------------
_DEEPSEEK_QA_SOCIAL = """Bạn là một Giáo sư / Giảng viên Đại học biên soạn đề thi cấp Đại học hàng đầu.
Nhiệm vụ: Đọc NỘI DUNG LÝ THUYẾT GIÁO TRÌNH môn {subject} dưới đây và sinh ra CHÍNH XÁC 3 bài tập tự luận BẮT BUỘC BÁM SÁT 100% GIÁO TRÌNH, ĐẠT TRÌNH ĐỘ BẬC ĐẠI HỌC, GIÀU NGỮ CẢNH VÀ CÓ CHIỀU SÂU.
Môn học: {subject} (Khối ngành Xã hội / Lý luận chính trị / Triết học / Kinh tế / Luật / Quản trị / Marketing / Xã hội học).

══════════════════════════════════════════════
══════════════════════════════════════════════
1. BÁM SÁT THỰC TẾ & CHUYÊN MÔN NÂNG CAO MÔN {subject}:
   - Khai thác sâu các quy luật, nguyên lý, cặp phạm trù, mô hình kinh tế / pháp lý / tư tưởng / xã hội cốt lõi trong giáo trình.
   - TUYỆT ĐỐI CẤM các câu hỏi thuộc lòng định nghĩa đơn thuần cấp phổ thông (như "Nêu định nghĩa X" hay "X là gì?").
2. QUY TẮC NỔI BẬT VỀ ĐỘ DÀI & NGỮ CẢNH CÂU HỎI (CONCRETE CONTEXT & ELABORATE DIRECTIVE):
   - MỖI CÂU HỎI TỰ LUẬN BẮT BUỘC PHẢI DÀI TỪ 3 ĐẾN 6 CÂU VĂN.
   - Đề bài phải xây dựng một bối cảnh thực tiễn/nguồn gốc lịch sử/tình huống kinh doanh/vụ việc pháp lý/nghịch lý xã hội hoặc vấn đề triết học cụ thể, sau đó mới đặt ra các yêu cầu phân tích, giải thích hoặc phản biện.
3. QUY TẮC RẢI ĐỀU ĐỘNG THEO 3 PHẦN CỦA VĂN BẢN (LESSON COVERAGE DIRECTIVE):
   - Chia văn bản thành 3 phần (PHẦN ĐẦU - 1/3 đầu, PHẦN GIỮA - 1/3 giữa, PHẦN CUỐI - 1/3 cuối). 3 câu hỏi BẮT BUỘC rải đều:
     * Câu 1 thuộc PHẦN ĐẦU tài liệu (1/3 đầu văn bản).
     * Câu 2 thuộc PHẦN GIỮA tài liệu (1/3 giữa văn bản).
     * Câu 3 thuộc PHẦN CUỐI tài liệu (1/3 cuối văn bản).
   - Trích xuất ĐÚNG mã số bài/mục (`lesson_number`) và tên bài/tiêu đề mục (`lesson_name`) THỰC TẾ xuất hiện trong file lý thuyết.
4. YÊU CẦU VỀ ĐÁP ÁN `correct_answer`:
   - `correct_answer` BẮT BUỘC PHẢI LÀ NỘI DUNG KẾT LUẬN CỐT LÕI / GIẢI PHÁP TÌNH HUỐNG / LUẬN ĐIỂM TRUNG TÂM (Dài 2-4 câu ngắn gọn, súc tích).
   - TUYỆT ĐỐI CẤM ghi "Xem chi tiết...", "Tham khảo...", "Đáp án 1", "Bài toán tự luận bám sát..." hay bất kỳ đáp án sáo rỗng nào!
5. BẮT BUỘC trả về kết quả dưới định dạng JSON.

══════════════════════════════════════════════
 TIÊU CHUẨN PHÂN HOÁ RANH GIỚI 3 MỨC ĐỘ (DỄ - TRUNG BÌNH - KHÓ)
══════════════════════════════════════════════
► CÂU 1 (Easy - Understanding | Dành cho mức điểm 5 - 6):
  - Bản chất: Phân tích bản chất khái niệm / quy luật cơ bản bậc Đại học thuộc 1/3 PHẦN ĐẦU văn bản gắn liền với một biểu hiện thực tiễn hoặc nguồn gốc tư tưởng.
  - Đề bài: Dài 3-4 câu. Đưa ra bối cảnh/hiện tượng xã hội hoặc tư tưởng cụ thể, yêu cầu phân tích bản chất lý luận, chỉ ra nguyên nhân cốt lõi hoặc so sánh 2 khía cạnh liên quan trong giáo trình.

► CÂU 2 (Medium - Applying | Dành cho mức điểm 7 - 8):
  - Bản chất: Bài tập TÌNH HUỐNG CASE STUDY THỰC TẾ chuyên sâu thuộc 1/3 PHẦN GIỮA văn bản.
  - Đề bài: Dài 4-6 câu. Đưa ra KỊCH BẢN CASE STUDY chứa các thông tin, dữ liệu, sự kiện thực tế của doanh nghiệp / thị trường / vụ việc pháp lý / hiện tượng xã hội. Yêu cầu sinh viên vận dụng mô hình/nguyên lý trong giáo trình môn {subject} để chẩn đoán vấn đề và đề xuất giải pháp xử lý trực tiếp.
  - BẮT BUỘC: Có kịch bản Case Study tình huống cụ thể, CẤM hỏi lý thuyết suông!

► CÂU 3 (Hard - Evaluating / Synthesis | Dành cho mức điểm 9 - 10):
  - Bản chất: Bài tập PHẢN BIỆN CHÍNH SÁCH / XỬ LÝ KHỦNG HOẢNG ĐA YẾU TỐ thuộc 1/3 PHẦN CUỐI văn bản.
  - Đề bài: Dài 4-6 câu. Đưa ra tình huống chứa XUNG ĐỘT LỢI ÍCH (Trade-off) hoặc nhiều biến số biến động phức tạp. Yêu cầu sinh viên:
    * Phân tích ưu/nhược điểm đa chiều (Pros & Cons).
    * Phản biện lại một quan điểm/chính sách bất cập hoặc hoạch định chiến lược vĩ mô/giải pháp dài hạn kèm dự báo rủi ro & phương án dự phòng.
  - BẮT BUỘC: Có yếu tố PHẢN BIỆN, ĐÁNH GIÁ RỦI RO và ĐỊNH HƯỚNG QUYẾT ĐỊNH XUNG ĐỘT LỢI ÍCH.

Cấu trúc JSON bắt buộc:
{{
  "questions": [
    {{
      "id": "EX_001",
      "lesson_number": "Mã bài/mục thực tế ở phần đầu văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần đầu văn bản",
      "topic": "Tên chủ đề lý thuyết môn {subject} (Phần đầu)",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "question_text": "Nội dung câu 1 (Dễ - Dài 3-4 câu phân tích bản chất khái niệm/quy luật phần đầu) môn {subject}...",
      "correct_answer": "Kết luận cốt lõi / Luận điểm trung tâm 2-4 câu cho câu 1 môn {subject}",
      "detailed_explanation": "Lời giải và phân tích chi tiết từng bước bằng Tiếng Việt."
    }},
    {{
      "id": "EX_002",
      "lesson_number": "Mã bài/mục thực tế ở phần giữa văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần giữa văn bản",
      "topic": "Tên chủ đề tình huống Case Study môn {subject} (Phần giữa)",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "question_text": "Nội dung Kịch bản Case Study thực tế dài 4-6 câu (Trung bình - Chẩn đoán & Giải pháp phần giữa) môn {subject}...",
      "correct_answer": "Giải pháp cốt lõi / Kết luận 2-4 câu cho tình huống câu 2 môn {subject}",
      "detailed_explanation": "Lời giải và phân tích tình huống chi tiết từng bước bằng Tiếng Việt."
    }},
    {{
      "id": "EX_003",
      "lesson_number": "Mã bài/mục thực tế ở phần cuối văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần cuối văn bản",
      "topic": "Tên chủ đề hoạch định/phản biện môn {subject} (Phần cuối)",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "question_text": "Nội dung bài tập Phản biện chính sách / Xung đột lợi ích dài 4-6 câu (Khó - Phần cuối) môn {subject}...",
      "correct_answer": "Lập luận chính và kết luận 2-4 câu cho câu 3 môn {subject}",
      "detailed_explanation": "Lời giải và phân tích toàn diện chi tiết từng bước bằng Tiếng Việt."
    }}
  ]
}}

Nội dung lý thuyết giáo trình môn {subject}:
{content}

BẮT BUỘC TRẢ VỀ CHÍNH XÁC MỘT JSON OBJECT CÓ KEY "questions" LÀ MẢNG GỒM 3 CÂU HỎI ĐỘC LẶP RẢI ĐỀU KHẮP TÀI LIỆU VÀ PHÂN HOÁ RANH GIỚI RÕ RỆT.
"""


# ================================================================
# OLD single-prompt (giữ lại nhưng sẽ được routing bở qua khi có subject_type)
_DEEPSEEK_GENERATE_QA_PROMPT = """Bạn là một chuyên gia giáo dục và biên soạn đề thi chuyên nghiệp.
Nhiệm vụ của bạn là đọc NỘI DUNG LÝ THUYẾT GIÁO TRÌNH được cung cấp dưới đây và sinh ra CHÍNH XÁC 5 bài tập tự luận BÁM SÁT 100% NỘI DUNG GIÁO TRÌNH với SỰ PHÂN HOÁ RÕ RỆT VỀ ĐỘ KHÓ VÀ MỨC ĐỘ BLOOM.

Với MỖI bài tập, bạn BẮT BUỘC phải cung cấp đầy đủ:
1. Nội dung câu hỏi tự luận.
2. Đáp án đúng và giải thích chi tiết.

QUY TẮC BẮT BUỘC BÁM SÁT GIÁO TRÌNH (GROUNDING DIRECTIVE - QUAN TRỌNG NHẤT):
1. BẮT BUỘC 100% CÂU HỎI PHẢI RÚT RA TRỰC TIẾP TỪ KIẾN THỨC, CÔNG THỨC, KHÁI NIỆM, ĐỊNH LÝ TRONG NỘI DUNG LÝ THUYẾT DƯỚI ĐÂY.
2. TUYỆT ĐỐI CẤM hỏi các khái niệm ngoài phạm vi giáo trình. TUY NHIÊN, ĐƯỢC PHÉP VÀ BẮT BUỘC tự sáng tạo ra CÁC THÔNG SỐ, SỐ LIỆU, HOẶC TÌNH HUỐNG THỰC TẾ (Case Study) mới để làm đề bài thực hành/tính toán, miễn là cách giải dùng đúng công thức/lý thuyết trong giáo trình.
3. Mọi số liệu, bài toán, khái niệm phải kiểm tra trực tiếp khả năng thấu hiểu kiến thức của chương lý thuyết này.
4. YÊU CẦU ĐA DẠNG HÓA CHỦ ĐỀ (QUAN TRỌNG): Bạn phải ĐỌC KỸ TOÀN BỘ VĂN BẢN (từ đầu đến cuối) và RẢI ĐỀU 5 câu hỏi ra các mục/phần khác nhau của tài liệu. TUYỆT ĐỐI KHÔNG tập trung toàn bộ 5 câu hỏi chỉ vào 1-2 trang đầu tiên hay 1 chủ đề duy nhất!
5. TUYỆT ĐỐI BÁM SÁT THUẬT NGỮ CỦA GIÁO TRÌNH: Chỉ được dùng các từ vựng/thuật ngữ có xuất hiện đúng y hệt trong văn bản. CẤM tự ý dùng các thuật ngữ chuyên ngành bằng tiếng nước ngoài hoặc từ ngữ lạ nếu giáo trình không ghi.
6. QUY TẮC CHỐNG DẬP KHUÔN (ANTI-ROBOTIC DIRECTIVE): CẤM sử dụng lặp đi lặp lại một kiểu mở đầu câu hỏi (như toàn bộ 5 câu đều bắt đầu bằng "Giải thích tại sao..."). Hãy hành văn tự nhiên, linh hoạt và đa dạng như một đề thi thực tế (ví dụ dùng các động từ phong phú: "Trình bày...", "Phân tích...", "Tính toán...", "Chứng minh...", "So sánh...").
7. BẮT BUỘC VẬN DỤNG THỰC TIỄN / TÍNH TOÁN (ĐẶC BIỆT DÀNH CHO BẬC ĐẠI HỌC): Vì đây là đề thi cấp Đại học, CẤM toàn bộ 5 câu chỉ hỏi lý thuyết học thuộc lòng (ví dụ: "Nêu định nghĩa..."). 
- Nếu giáo trình thuộc môn Tự nhiên/Kỹ thuật (Toán, Lý, IT...): BẮT BUỘC sinh ra các bài toán TÍNH TOÁN, CHỨNG MINH, VIẾT CODE với các thông số/biểu thức phức tạp (đặc biệt ở mức Medium và Hard).
- Nếu giáo trình thuộc môn Xã hội/Lý thuyết (Triết học, Luật, Kinh tế...): BẮT BUỘC sinh ra các TÌNH HUỐNG THỰC TẾ (Case Study), phân tích nghịch lý, hoặc áp dụng lý thuyết để giải quyết một bài toán xã hội/kinh doanh cụ thể.
QUY TẮC PHÂN HOÁ RÕ RỆT THEO THANG ĐIỂM ĐỀ THI (TỶ LỆ BẮT BUỘC: 2 Easy, 2 Medium, 1 Hard):

1. CÂU 1 & CÂU 2 (EASY - Dễ | Dành cho mức điểm 1 - 3):
   - Mục tiêu: Phù hợp cho mức độ kiến thức điểm 1 đến 3.
   - Bản chất: Kiểm tra mức Nhớ (Remembering) hoặc Hiểu (Understanding). Tái hiện định nghĩa, khái niệm cơ bản, công thức hoặc tính toán/giải thích 1 bước trực tiếp từ giáo trình. Không đánh đố, không biến đổi nhiều bước.

2. CÂU 3 & CÂU 4 (MEDIUM - Trung bình | Dành cho mức điểm 5 - 7):
   - Mục tiêu: Phù hợp cho mức độ kiến thức điểm 5 đến 7.
   - Bản chất: Kiểm tra mức Vận dụng (Applying) hoặc Phân tích (Analyzing). BẮT BUỘC là bài toán thực hành, tính toán, xử lý tình huống cụ thể áp dụng kiến thức/công thức TRONG GIÁO TRÌNH từ 2-3 bước.
   - TUYỆT ĐỐI CẤM: Không sinh câu hỏi lý thuyết suông dạng "Giải thích... và đưa ra ví dụ". Phải cho dữ liệu/số liệu cụ thể dựa trên giáo trình để thực hành giải ra đáp số!

3. CÂU 5 (HARD - Khó | Dành cho mức điểm 9 - 10 phân hoá giỏi/xuất sắc):
   - Mục tiêu: Phù hợp cho mức độ phân hoá điểm 9 đến 10.
   - Bản chất: Kiểm tra mức Đánh giá (Evaluating) hoặc Sáng tạo (Creating). BẮT BUỘC là bài toán vận dụng cao bám sát giáo trình: Chứng minh mệnh đề/định lý toán học/nguyên lý trong giáo trình, bài toán cực trị, đánh giá và lựa chọn giải pháp tối ưu trong các điều kiện ràng buộc phức tạp, hoặc thiết kế giải pháp tổng hợp.
   - TUYỆT ĐỐI CẤM: Cấm sinh câu hỏi định nghĩa hoặc giải thích lý thuyết cơ bản ở câu này!

YÊU CẦU ĐỊNH DẠNG OUTPUT: BẮT BUỘC TRẢ VỀ ĐÚNG MỘT OBJECT JSON NẰM TRONG KEY "data", không giải thích gì thêm ngoài phần suy nghĩ của bạn (sẽ nằm trong thẻ <think>).
1. BẮT BUỘC 100% TIẾNG VIỆT CHO TOÀN BỘ CÂU HỎI, ĐÁP ÁN, VÀ GIẢI THÍCH. NẾU NỘI DUNG LÝ THUYẾT LÀ TIẾNG ANH, BẠN BẮT BUỘC PHẢI DỊCH SANG TIẾNG VIỆT TRƯỚC KHI TẠO CÂU HỎI.
2. BẮT BUỘC 100% CÂU HỎI LÀ DẠNG TỰ LUẬN. TUYỆT ĐỐI KHÔNG SINH CÂU HỎI TRẮC NGHIỆM.
3. BẮT BUỘC tuân thủ tỷ lệ độ khó và mức Bloom phân hoá rõ rệt như trên.
4. ĐỐI VỚI CÔNG THỨC LATEX: Bắt buộc phải double-backslash (ví dụ: viết "\\frac", "\\text" thay vì "\frac", "\text").
5. JSON PHẢI HỢP LỆ: TUYỆT ĐỐI CHỈ SỬ DỤNG DẤU NHÁY KÉP (") cho CẢ KEY VÀ VALUE.
6. CÁC TỪ KHOÁ (KEYS) TRONG JSON BẮT BUỘC PHẢI GIỮ NGUYÊN BẰNG TIẾNG ANH ("id", "topic", "question_text"...).
Cấu trúc JSON bắt buộc phải tuân thủ NGHIÊM NGẶT format sau:
{{
  "data": {{
    "subject": "<Tên môn học>",
    "chapter_number": "<Số chương>",
    "chapter_name": "<Tên chương>",
    "questions": [
      {{
        "id": "<MÃ_MON>_C<SO_CHUONG>_<SO_BAI>_001",
        "lesson_number": "1.1",
        "lesson_name": "<Tên bài học>",
        "topic": "<Chủ đề bài tập cụ thể>",
        "difficulty": "Easy",
        "bloom_level": "Remembering",
        "question_text": "<Nội dung câu hỏi tự luận BÁM SÁT GIÁO TRÌNH bằng 100% TIẾNG VIỆT>",
        "correct_answer": "<Đáp án ngắn gọn>",
        "detailed_explanation": "<Lời giải chi tiết bằng 100% TIẾNG VIỆT>"
      }}
    ]
  }}
}}

Nội dung lý thuyết giáo trình:
{content}

NHẤT ĐỊNH PHẢI TRẢ VỀ KẾT QUẢ DƯỚI DẠNG JSON. BẮT ĐẦU BẰNG ```json VÀ KẾT THÚC BẰNG ```. KHÔNG ĐƯỢC SINH BẤT KỲ ĐỊNH DẠNG NÀO KHÁC BÊN NGOÀI JSON.
"""

_QWEN_GENERATE_SCAFFOLD_PROMPT = """Bạn là một giáo sư sư phạm xuất sắc.
Dưới đây là NỘI DUNG LÝ THUYẾT GIÁO TRÌNH và danh sách các câu hỏi do DeepSeek vừa khởi tạo.

NHIỆM VỤ CỦA BẠN:
1. ĐỌC VÀ BẢO TỒN NGUYÊN VẸN NỘI DUNG NGHĨA VÀ NGỮ CẢNH CỦA CÂU HỎI. Mở rộng và viết LỜI GIẢI CHI TIẾT (detailed_solution) thật CÓ CHIỀU SÂU, giải thích cặn kẽ bản chất vấn đề.
2. BẮT BUỘC GIỮ NGUYÊN ĐỘ DÀI VÀ NGỮ CẢNH CỦA `question_text`. TUYỆT ĐỐI KHÔNG ĐƯỢC CẮT TÓM TẮT HAY LÀM ĐƠN GIẢN HÓA ĐỀ BÀI GỐC CỦA DEEPSEEK.
3. Trong trường `full_answer`: BẮT BUỘC trả lời TRỰC TIẾP VÀ ĐẦY ĐỦ các ý hỏi của đề bài (3-5 câu văn hoặc liệt kê luận điểm 1, 2, 3...). TUYỆT ĐỐI CẤM mở đầu câu đáp án bằng việc lặp lại câu hỏi một cách máy móc (như CẤM viết "Triết học X được xem là bước tiến vì..." hay "X có 2 nguồn gốc là..."). TUYỆT ĐỐI CẤM điền các câu placeholder như "Tham khảo kịch bản...", "Xem chi tiết...", "Đáp án 1", "Bài toán tự luận bám sát...".
4. TẠO KỊCH BẢN SOCRATIC ĐỈNH CAO (scaffolding_steps): Gồm 3-5 bước gợi mở CÓ CHIỀU SÂU. Không đưa ngay đáp án mà phải dắt dẫn học sinh đi từ việc phân tích đề bài, áp dụng công thức/lý thuyết, đến giải quyết từng phần của bài toán. Mỗi bước phải có 'hint' gợi mở tư duy.
5. ĐÓNG GÓI kết quả vào mảng JSON. 

QUY TẮC JSON QUAN TRỌNG:
- BẮT BUỘC sao chép CHÍNH XÁC trường "id" từ danh sách câu hỏi gốc. TUYỆT ĐỐI KHÔNG ĐƯỢC TỰ ĐẶT ID MỚI.
- Dùng double-backslash cho LaTeX (ví dụ: "\\frac").

Cấu trúc JSON bắt buộc:
{{
  "data": [
    {{
      "id": "<id_goc_nhu_GT1_C1_001>",
      "topic": "<ten_chu_de>",
      "difficulty": "<Easy | Medium | Hard>",
      "bloom_level": "<Remembering | Understanding | Applying | Analyzing | Evaluating>",
      "question_text": "<giu_nguyen_ngu_canh_cau_hoi_goc_tieng_viet>",
      "full_answer": "<dap_an_tra_loi_truc_tiep_day_du_3_5_cau_cam_lap_lai_de_bai_o_dau_cau>",
      "detailed_solution": "<loi_giai_chi_tiet_tung_buoc>",
      "scaffolding_steps": [
        {{ "step_number": 1, "hint": "Gợi ý", "step_detail": "Chi tiết" }}
      ],
      "common_mistakes": [ "Sai lầm 1" ]
    }}
  ]
}}

Nội dung lý thuyết (Dùng để đối chiếu):
{theory_context}

Danh sách Bài tập từ DeepSeek:
{qa_json}

NHẤT ĐỊNH PHẢI TRẢ VỀ KẾT QUẢ DƯỚI DẠNG JSON.
"""


@router.post("/generate-from-theory", response_model=GenerateFromTheoryResponse)
async def generate_from_theory(req: GenerateFromTheoryRequest):
    try:
        safe_subj = _get_default_folder_name(req.subject)
        safe_chap = _get_default_folder_name(req.chapter)
        
        # 1. TÌM FILE LÝ THUYẾT CHÍNH XÁC (Ưu tiên file bám sát tên chương, dung lượng lớn và không phải file rác)
        rag_input_dir = os.path.join(settings.BASE_DIR, "data", "rag_input", safe_subj)
        target_file = None
        
        m_num = re.search(r'\d+', safe_chap)
        chap_num = m_num.group(0) if m_num else ""

        matching_files = []
        if os.path.exists(rag_input_dir):
            all_txt_files = [f for f in os.listdir(rag_input_dir) if f.endswith(".txt")]
            for f in all_txt_files:
                fname_lower = f.lower()
                full_p = os.path.join(rag_input_dir, f)
                fsize = os.path.getsize(full_p)
                if fsize <= 10:
                    continue
                    
                is_loi_noi_dau = 1 if "loi_noi_dau" in fname_lower else 0
                is_test = 1 if (fname_lower.startswith("test_") or "test" in fname_lower) else 0
                
                # Tính điểm khớp tên chương (0: Trùng tuyệt đối, 1: Khớp chuong_part_X / part_X, 2: Khớp cX / _X_, 3: Chứa số X, 99: Tùy chọn dự phòng)
                match_score = 99
                if safe_chap in fname_lower:
                    match_score = 0
                elif chap_num:
                    if f"chuong_{chap_num}" in fname_lower or f"chuong_part_{chap_num}" in fname_lower or f"part_{chap_num}" in fname_lower or f"part{chap_num}" in fname_lower:
                        match_score = 1
                    elif f"c{chap_num}" in fname_lower or f"_{chap_num}." in fname_lower or f"_{chap_num}_" in fname_lower:
                        match_score = 2
                    elif f"{chap_num}" in fname_lower:
                        match_score = 3
                        
                matching_files.append((is_test, is_loi_noi_dau, match_score, -fsize, full_p))
                            
        if matching_files:
            matching_files.sort()  # Ưu tiên: non-test (0), non-loi_noi_dau (0), match_score nhỏ nhất (khớp nhất), dung lượng lớn nhất (-fsize)
            target_file = matching_files[0][4]
                        
        if not target_file:
            raise HTTPException(status_code=404, detail=f"Khong tim thay file ly thuyet cho chuong {req.chapter} mon {req.subject} trong {rag_input_dir}")
            
        print(f"[Multi-Agent] Found theory file: {target_file}")
        with open(target_file, "r", encoding="utf-8") as f:
            theory_content = f.read()

        # Bóc tách và bỏ phần Mục lục (Table of Contents) ở 30-40 dòng đầu tiên nếu có
        lines = theory_content.splitlines()
        content_lines = []
        in_body = False
        for line in lines:
            line_str = line.strip()
            if not in_body:
                # Phát hiện vị trí bắt đầu nội dung chi tiết bài học (tiêu đề # CHƯƠNG hoặc ## 1.1)
                if line_str.startswith("# CH") or line_str.startswith("# Ch") or line_str.startswith("## 1.1") or line_str.startswith("1.1."):
                    in_body = True
                    content_lines.append(line)
            else:
                content_lines.append(line)
        
        cleaned_theory = "\n".join(content_lines) if (content_lines and len(content_lines) > 10) else theory_content
        # Lấy 8000 ký tự lý thuyết cốt lõi thực sự để AI nắm trọn vẹn kiến thức sâu của chương
        theory_truncated = cleaned_theory[:8000].strip()
        
        # Ngăn chặn việc truyền file rỗng/quá ngắn vào AI (gây ra lỗi JSON rỗng)
        if len(theory_truncated) < 150:
            err_msg = f"Nội dung file lý thuyết ({target_file}) quá ngắn (chỉ có {len(theory_truncated)} ký tự). File này có thể là file test. Vui lòng cung cấp file giáo trình có nội dung đầy đủ để AI có thể trích xuất bài tập."
            print(f"[Multi-Agent] THẤT BẠI: {err_msg}")
            raise HTTPException(status_code=400, detail=err_msg)

        display_subject = _get_clean_subject_display_name(req.subject, target_file=target_file, theory_text=theory_truncated)
        print(f"[Multi-Agent] Dang sinh bai tap cho '{req.subject}' (Tên hiển thị môn: '{display_subject}') - {req.chapter}")
        print(f"[DEBUG] theory_truncated length: {len(theory_truncated)} chars")
        print(f"[DEBUG] theory_truncated preview: {theory_truncated[:200]!r}...")
        
        # 2. STAGE 1: DEEPSEEK-R1 SUY LUẬN SÂU VÀ RA ĐỀ BÀI
        qa_list = []
        extracted_subject = ""
        extracted_chapter_number = ""
        extracted_chapter_name = ""

        # Classifier -> chọn đúng prompt dựa trên tên môn, tên file và nội dung lý thuyết
        subject_type = _classify_subject_type(display_subject, target_file=target_file, theory_text=theory_truncated)
        if subject_type == "SOCIAL":
            prompt_template = _DEEPSEEK_QA_SOCIAL
        else:
            prompt_template = _DEEPSEEK_QA_STEM
        print(f"[Multi-Agent] Môn '{display_subject}' -> nhánh {subject_type}")

        last_error = ""
        seed_id = int(time.time() * 1000) % 10000
        sys_msg_stage1 = (
            f"Bạn là Giáo sư / Giảng viên Đại học giảng dạy môn {display_subject}. [Phiên sinh đề mã số #{seed_id}] "
            "Nhiệm vụ: Biên soạn CHÍNH XÁC 3 bài tập tự luận BẮT BUỘC TRÌNH ĐỘ BẬC ĐẠI HỌC, BÁM SÁT 100% GIÁO TRÌNH, KHÁC NHAU HOÀN TOÀN VỀ CẢ CHỦ ĐỀ LẪN DẠNG BÀI. "
            "BẮT BUỘC SOẠN CÂU HỎI VÀ ĐÁP ÁN 100% BẰNG TIẾNG VIỆT CÓ DẤU CHUẨN XÁC. TUYỆT ĐỐI CẤM SOẠN CÂU HỎI HOẶC ĐÁP ÁN BẰNG TIẾNG ANH. "
            "TUYỆT ĐỐI CẤM sinh câu hỏi sáo rỗng ngắn 1 dòng. BẮT BUỘC trả về kết quả dưới định dạng JSON."
        )
        for batch_num in range(1):
            print(f"  -> Stage 1: DeepSeek-R1 dang suy luan & ra de... (Batch {batch_num + 1}/1, Seed #{seed_id})")
            prompt_stage1 = prompt_template.format(
                subject=display_subject,
                content=theory_truncated
            )
            stage1_temp = round(0.75 + (random.random() * 0.1), 2)
            try:
                try:
                    raw_output_stage1 = _call_llm(
                        model=DEEPSEEK_MODEL,
                        messages=[
                            {"role": "system", "content": sys_msg_stage1},
                            {"role": "user", "content": prompt_stage1}
                        ],
                        temperature=stage1_temp,
                        response_format={"type": "json_object"}
                    )
                    
                    # Loại bỏ thẻ suy nghĩ <think> của DeepSeek-R1 nếu có
                    raw_output_stage1 = re.sub(r"<think>.*?</think>", "", raw_output_stage1, flags=re.DOTALL).strip()
                    if "</think>" in raw_output_stage1:
                        raw_output_stage1 = raw_output_stage1.split("</think>")[-1].strip()
                        
                    batch_data = _parse_llm_json(raw_output_stage1)
                    
                    # Xác thực cấu trúc dữ liệu cơ bản (phải chứa thông tin câu hỏi)
                    if not _is_valid_exercise_data(batch_data):
                        raise ValueError("DeepSeek generated invalid JSON structure without questions.")
                        
                except Exception as deepseek_err:
                    print(f"  [Fallback Warning] DeepSeek-R1 bi loi hoac parse that bai: {deepseek_err}. Chuyen sang dung Qwen 2.5 cho Batch {batch_num + 1}...")
                    raw_output_stage1 = _call_llm(
                        model=LOCAL_MODEL,
                        messages=[
                            {"role": "system", "content": sys_msg_stage1},
                            {"role": "user", "content": prompt_stage1}
                        ],
                        temperature=stage1_temp,
                        response_format={"type": "json_object"}
                    )
                    
                    raw_output_stage1 = re.sub(r"<think>.*?</think>", "", raw_output_stage1, flags=re.DOTALL).strip()
                    if "</think>" in raw_output_stage1:
                        raw_output_stage1 = raw_output_stage1.split("</think>")[-1].strip()
                        
                    batch_data = _parse_llm_json(raw_output_stage1)
                    
                    # Kiểm tra tính hợp lệ của dữ liệu từ Qwen 2.5
                    if not _is_valid_exercise_data(batch_data):
                        print(f"  [Emergency Fallback] Qwen 2.5 tra ve JSON khong chua cau hoi. Dung prompt cap cuu...")
                        emergency_prompt = f"""Bạn là Giảng viên Đại học môn {req.subject}. Hãy đọc lý thuyết sau và tạo ĐÚNG 3 câu hỏi bài tập tự luận BẬC ĐẠI HỌC (UNIVERSITY LEVEL) HOÀN TOÀN KHÁC NHAU CẢ VỀ CHỦ ĐỀ VÀ DẠNG BÀI.

Lý thuyết:
{theory_truncated[:4500]}

QUY ĐỊNH BẮT BUỘC:
1. TUYỆT ĐỐI CẤM CÁC CÂU HỎI SÁO RỖNG. BẮT BUỘC khai thác bài tập tự luận bậc Đại học chuyên sâu bám sát lý thuyết môn {req.subject}.
2. ĐÁP ÁN `correct_answer`: BẮT BUỘC trả lời TRỰC TIẾP và ĐẦY ĐỦ các ý hỏi của đề bài (3-5 câu). TUYỆT ĐỐI CẤM mở đầu câu đáp án bằng việc lặp lại nguyên văn câu hỏi. CẤM bịa đáp án lười sáo rỗng hay các chuỗi giữ chỗ.
3. TRẢ VỀ JSON OBJECT với tên chủ đề (`topic`) thực tế bóc tách từ giáo trình (KHÔNG dùng từ "Bài tập Nền tảng" hay "Bài tập Vận dụng").

Cấu trúc JSON Object bắt buộc:
{{
  "questions": [
    {{
      "id": "{safe_subj.upper()}_C{safe_chap}_001",
      "topic": "<Tên chủ đề thực tế từ phần đầu giáo trình môn {req.subject}>",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "question_text": "Nội dung câu hỏi tự luận bậc Đại học mức Dễ có ngữ cảnh chi tiết môn {req.subject}...",
      "correct_answer": "Bộ đáp án giải quyết trực tiếp 3-5 câu cho câu 1 (CẤM lặp lại đề bài ở đầu câu)",
      "detailed_explanation": "Lời giải chi tiết từng bước bằng Tiếng Việt"
    }},
    {{
      "id": "{safe_subj.upper()}_C{safe_chap}_002",
      "topic": "<Tên chủ đề thực tế từ phần giữa giáo trình môn {req.subject}>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "question_text": "Nội dung bài tập tình huống thực tế / Case study mức Trung bình môn {req.subject}...",
      "correct_answer": "Giải pháp / Bộ đáp án 3-5 câu giải quyết trực tiếp tình huống câu 2 (CẤM lặp lại đề bài ở đầu câu)",
      "detailed_explanation": "Lời giải chi tiết từng bước bằng Tiếng Việt"
    }},
    {{
      "id": "{safe_subj.upper()}_C{safe_chap}_003",
      "topic": "<Tên chủ đề thực tế từ phần cuối giáo trình môn {req.subject}>",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "question_text": "Nội dung bài tập phân tích đa chiều / phản biện nâng cao mức Khó môn {req.subject}...",
      "correct_answer": "Lập luận chính và đáp án 3-5 câu giải quyết trực tiếp câu 3 (CẤM lặp lại đề bài ở đầu câu)",
      "detailed_explanation": "Lời giải chi tiết từng bước bằng Tiếng Việt"
    }}
  ]
}}
"""
                        raw_output_stage1 = _call_llm(
                            model=LOCAL_MODEL,
                            messages=[{"role": "user", "content": emergency_prompt}],
                            temperature=0.2,
                            response_format={"type": "json_object"}
                        )
                        raw_output_stage1 = re.sub(r"<think>.*?</think>", "", raw_output_stage1, flags=re.DOTALL).strip()
                        if "</think>" in raw_output_stage1:
                            raw_output_stage1 = raw_output_stage1.split("</think>")[-1].strip()
                        batch_data = _parse_llm_json(raw_output_stage1)
                        
                if isinstance(batch_data, dict):
                    if not extracted_subject:
                        extracted_subject = batch_data.get("subject", req.subject)
                        extracted_chapter_number = batch_data.get("chapter_number", req.chapter)
                        extracted_chapter_name = batch_data.get("chapter_name", req.chapter)
                    
                    # Flatten the 'questions' or 'data' array
                    questions_arr = batch_data.get("questions")
                    if not questions_arr and batch_data.get("data"):
                        data_node = batch_data.get("data")
                        if isinstance(data_node, list):
                            questions_arr = data_node
                        elif isinstance(data_node, dict):
                            questions_arr = data_node.get("questions") or data_node.get("exercises")
                    if not questions_arr and batch_data.get("exercises"):
                        questions_arr = batch_data.get("exercises")
                    
                    if not questions_arr:
                        if batch_data.get("question_text") or batch_data.get("question"):
                            questions_arr = [batch_data]
                        else:
                            questions_arr = []
                        
                    if isinstance(questions_arr, list):
                        valid_q = [
                            q for q in questions_arr
                            if isinstance(q, dict) and (q.get("question_text") or q.get("question") or q.get("questionText"))
                        ]
                        qa_list.extend(valid_q if valid_q else questions_arr)
                    else:
                        qa_list.append(batch_data)
                elif isinstance(batch_data, list) and len(batch_data) > 0:
                    valid_q = [
                        q for q in batch_data
                        if isinstance(q, dict) and (q.get("question_text") or q.get("question") or q.get("questionText"))
                    ]
                    qa_list.extend(valid_q if valid_q else batch_data)
                else:
                    if raw_output_stage1:
                        qa_list.append({"raw_content": raw_output_stage1})
                
            except Exception as e:
                last_error = f"API Error: {str(e)}"
                print(f"Loi o batch {batch_num + 1}: {e}")
                
        if len(qa_list) == 0:
            err_msg = f"DeepSeek Stage 1 không thể sinh ra câu hỏi nào. {last_error}"
            print(f"[Multi-Agent] THẤT BẠI: {err_msg}")
            raise HTTPException(status_code=500, detail=err_msg)
            
        # 3. STAGE 2: DÙNG QWEN 2.5 DỊCH THUẬT, ĐA DẠNG HÓA MỨC ĐỘ VÀ ĐÓNG GÓI JSON CHUẨN (CÓ ĐỐI CHIẾU LÝ THUYẾT GIÁO TRÌNH)
        print(f"  -> Stage 2: Qwen 2.5 dang soan kich ban Socratic & bien dich sang Tieng Viet cho {len(qa_list)} bai tap...")
        stage2_model = LOCAL_MODEL
        final_list = []
        
        sys_msg_stage2 = f"Bạn là chuyên gia sư phạm môn {display_subject}. Nhiệm vụ TỐI CAO của bạn là biên soạn, dịch thuật và kiểm tra 100% CÂU HỎI BÁM SÁT NỘI DUNG GIÁO TRÌNH, tuyệt đối loại bỏ các câu hỏi tiểu học bịa đặt không liên quan đến môn {display_subject}. BẮT BUỘC trả về kết quả dưới định dạng JSON."

        chunk_size = 3
        for i in range(0, len(qa_list), chunk_size):
            qa_chunk = qa_list[i:i + chunk_size]
            print(f"    -> Qwen 2.5 xu ly Stage 2 cho batch {i//chunk_size + 1} (Cau {i+1} den {i+len(qa_chunk)})...")
            prompt_stage2 = _QWEN_GENERATE_SCAFFOLD_PROMPT.format(
                qa_json=json.dumps(qa_chunk, ensure_ascii=False),
                theory_context=theory_truncated
            )
            try:
                raw_output_stage2 = _call_llm(
                    model=stage2_model,
                    messages=[
                        {"role": "system", "content": sys_msg_stage2},
                        {"role": "user", "content": prompt_stage2}
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                if "</think>" in raw_output_stage2:
                    raw_output_stage2 = raw_output_stage2.split("</think>")[-1].strip()
                    
                chunk_final = _parse_llm_json(raw_output_stage2)
                if chunk_final:
                    if isinstance(chunk_final, str):
                        final_list.append(chunk_final)
                    elif isinstance(chunk_final, list):
                        final_list.extend(chunk_final)
                    elif isinstance(chunk_final, dict):
                        # Extract the array from 'data' or 'questions' key
                        data_arr = chunk_final.get("data") or chunk_final.get("questions")
                        if isinstance(data_arr, list):
                            final_list.extend(data_arr)
                        else:
                            final_list.append(chunk_final)
                    else:
                        final_list.append(chunk_final)
            except Exception as e:
                print(f"Loi Stage 2 o batch {i//chunk_size + 1}: {e}")
                
        if not final_list:
            print("  [Fallback] Stage 2 khong tra ve list, su dung du lieu tu Stage 1...")
            final_list = qa_list
            
        # Kết hợp kết quả Stage 1 và Stage 2 để trả về cho Spring Boot lưu DB, đồng thời inject dữ liệu vào final_list
        db_exercises = []
        
        for idx, item in enumerate(final_list, start=1):
            if isinstance(item, str):
                final_item = {"question_text": item, "topic": f"Bài tập tự luận {idx}", "full_answer": "Tham khảo kịch bản sư phạm"}
                final_list[idx-1] = final_item
            elif isinstance(item, dict):
                final_item = item
            else:
                continue

            # 1. Ưu tiên lấy dữ liệu trực tiếp từ Stage 2 (do Qwen 2.5 đã phân loại & dịch thuật)
            raw_diff = _clean_val(final_item.get("difficulty"))
            raw_bloom = _clean_val(final_item.get("bloom_level"))
            topic = _clean_val(final_item.get("topic")) or _clean_val(final_item.get("exerciseName")) or _clean_val(final_item.get("title"))
            question_text = _clean_val(final_item.get("question_text")) or _clean_val(final_item.get("question")) or _clean_val(final_item.get("questionText"))
            correct_answer = _clean_val(final_item.get("full_answer")) or _clean_val(final_item.get("correct_answer")) or _clean_val(final_item.get("answer"))
            detailed_sol = _clean_val(final_item.get("detailed_solution")) or _clean_val(final_item.get("detailed_explanation"))
            lesson_num = _clean_val(final_item.get("lesson_number"))
            lesson_nam = _clean_val(final_item.get("lesson_name"))

            # Nếu Stage 2 trả về chuỗi placeholder mẫu của Prompt -> Reset để lấy từ Stage 1
            if _is_placeholder(question_text):
                question_text = ""
            if _is_placeholder(correct_answer):
                correct_answer = ""
            if _is_placeholder(topic):
                topic = ""
            if _is_placeholder(detailed_sol):
                detailed_sol = ""

            # 2. Nếu Stage 2 thiếu thông tin, tìm lại ở Stage 1 (DeepSeek-R1) bằng ID, Topic hoặc Index
            matched_stage1 = None
            for stage1_item in qa_list:
                id1 = _clean_val(stage1_item.get("id"))
                id2 = _clean_val(final_item.get("id"))
                if (id1 and id2 and id1 == id2 and id1 != "None") or (stage1_item.get("topic") and stage1_item.get("topic") == topic):
                    matched_stage1 = stage1_item
                    break

            if not matched_stage1 and (idx - 1) < len(qa_list):
                matched_stage1 = qa_list[idx - 1]

            if matched_stage1:
                if not topic or _is_placeholder(topic):
                    topic = _clean_val(matched_stage1.get("topic")) or _clean_val(matched_stage1.get("exerciseName")) or topic
                if not question_text or _is_placeholder(question_text):
                    question_text = _clean_val(matched_stage1.get("question_text")) or _clean_val(matched_stage1.get("question")) or question_text
                if not correct_answer or _is_placeholder(correct_answer):
                    correct_answer = _clean_val(matched_stage1.get("correct_answer")) or _clean_val(matched_stage1.get("full_answer")) or correct_answer
                if not detailed_sol or _is_placeholder(detailed_sol):
                    detailed_sol = _clean_val(matched_stage1.get("detailed_explanation")) or _clean_val(matched_stage1.get("detailed_solution")) or _clean_val(matched_stage1.get("correct_answer")) or detailed_sol
                if not raw_diff:
                    raw_diff = _clean_val(matched_stage1.get("difficulty"))
                if not raw_bloom:
                    raw_bloom = _clean_val(matched_stage1.get("bloom_level"))
                if not lesson_num:
                    lesson_num = _clean_val(matched_stage1.get("lesson_number"))
                if not lesson_nam:
                    lesson_nam = _clean_val(matched_stage1.get("lesson_name"))

            # 3. Dự phòng 3: Nếu vẫn thiếu đáp án, trích xuất từ bước cuối cùng của kịch bản sư phạm (scaffolding_steps)
            if (not correct_answer or _is_placeholder(correct_answer)) and final_item.get("scaffolding_steps"):
                steps = final_item.get("scaffolding_steps")
                if isinstance(steps, list) and len(steps) > 0:
                    last_step = steps[-1]
                    if isinstance(last_step, dict):
                        correct_answer = _clean_val(last_step.get("step_detail")) or _clean_val(last_step.get("hint"))

            if not question_text or _is_placeholder(question_text):
                raw_c = final_item.get("raw_content") or (matched_stage1.get("raw_content") if matched_stage1 else None)
                if raw_c:
                    raw_str = _clean_val(raw_c)
                    if len(raw_str) > 20 and not _is_placeholder(raw_str):
                        question_text = raw_str

            # Lọc nghiêm ngặt: Bỏ qua hoàn toàn các câu rác, câu chứa tiếng Trung, câu chào mở đầu và câu chưa có nội dung/placeholder
            q_lower = str(question_text).lower().strip()
            if not question_text:
                print(f"[DEBUG] Item bị loại vì không có question_text. raw final_item: {final_item}")
                continue
            if len(q_lower) < 5:
                print(f"[DEBUG] Item bị loại vì question_text quá ngắn: {q_lower!r}")
                continue
            if _is_placeholder(question_text):
                print(f"[DEBUG] Item bị loại vì là placeholder: {q_lower!r}")
                continue
            # Xóa các câu mào đầu vô nghĩa thay vì xóa cả câu hỏi
            if q_lower.startswith("dưới đây là") or q_lower.startswith("sau đây là") or q_lower.startswith("đây là"):
                # Nếu câu dài hơn 30 ký tự, có thể đây là một câu hỏi thực sự bắt đầu bằng chữ đó, ta cố bóc phần sau dấu :
                if ":" in question_text:
                    question_text = question_text.split(":", 1)[1].strip()
                elif len(q_lower) < 30:
                    continue # Câu quá ngắn và là câu mào đầu -> Bỏ qua

            # Kiểm tra chống trùng lặp câu hỏi (Deduplication filter)
            existing_questions = [ex.question for ex in db_exercises]
            if _is_duplicate_question(question_text, existing_questions):
                print(f"  [Deduplication Filter] Bỏ qua câu hỏi bị trùng lặp nội dung: {question_text[:60]}...")
                continue

            # Nếu phát hiện bài tập còn chứa Tiếng Anh hoặc ngoại ngữ khác, tự động dùng AI dịch lại 100% dựa vào đúng NGỮ CẢNH GIÁO TRÌNH MÔN HỌC
            if _is_english_or_foreign(question_text) or _is_english_or_foreign(str(topic)) or _is_english_or_foreign(str(correct_answer)):
                print(f"  [AI Auto-Translator] Đang tự động dịch bài tập dựa theo đúng ngữ cảnh giáo trình môn học: {topic}")
                translated = _ai_translate_item_with_context(final_item, theory_truncated)
                if translated and isinstance(translated, dict):
                    final_item.update(translated)
                    topic = final_item.get("topic") or final_item.get("exerciseName") or topic
                    question_text = final_item.get("question_text") or final_item.get("question") or question_text
                    correct_answer = final_item.get("full_answer") or final_item.get("correct_answer") or correct_answer
                    detailed_sol = final_item.get("detailed_solution") or final_item.get("detailed_explanation") or detailed_sol

            if not topic or any(str(topic).startswith(prefix) for prefix in ["Bài tập tự luận", "Bài tập Nền tảng", "Bài tập Vận dụng", "Bài tập Nâng cao"]):
                if matched_stage1 and matched_stage1.get("topic") and not any(str(matched_stage1.get("topic")).startswith(p) for p in ["Bài tập Nền tảng", "Bài tập Vận dụng", "Bài tập Nâng cao"]):
                    topic = matched_stage1.get("topic")
                elif lesson_nam and len(lesson_nam) > 3:
                    topic = lesson_nam
                else:
                    topic = f"Chủ đề bài tập {idx}"
            
            invalid_ans_set = {
                "", "0", "1", "null", "none", "chưa có đáp án", "tham khao kich ban ai",
                "tham khảo kịch bản ai", "tham khảo kịch bản sư phạm", "tham khao kich ban su pham",
                "đáp án 1", "đáp án 2", "đáp án 3",
                "kết quả chính xác 1", "kết quả chính xác 2", "kết quả chính xác 3",
                "xem chi tiết lời giải từng bước trong phần đáp án chi tiết.",
                "xem chi tiết lời giải", "xem chi tiết", "bài toán tự luận bám sát giáo trình.",
                "bài toán tự luận bám sát giáo trình"
            }
            if not correct_answer or _is_placeholder(correct_answer) or str(correct_answer).strip().lower() in invalid_ans_set:
                if matched_stage1:
                    st1_ans = _clean_val(matched_stage1.get("correct_answer")) or _clean_val(matched_stage1.get("full_answer"))
                    if st1_ans and not _is_placeholder(st1_ans) and str(st1_ans).strip().lower() not in invalid_ans_set:
                        correct_answer = st1_ans

            if not correct_answer or _is_placeholder(correct_answer) or str(correct_answer).strip().lower() in invalid_ans_set:
                if detailed_sol and len(detailed_sol) > 10 and not _is_placeholder(detailed_sol):
                    lines = [l.strip() for l in detailed_sol.splitlines() if l.strip()]
                    res_line = None
                    for line in reversed(lines):
                        l_lower = line.lower()
                        if any(kw in l_lower for kw in ["vậy", "kết quả", "kết luận", "đáp số", "=", "giải pháp", "tóm lại", "như vậy", "do đó"]):
                            res_line = line
                            break
                    if res_line:
                        correct_answer = res_line
                    else:
                        sentences = re.split(r'(?<=[.!?])\s+', detailed_sol)
                        non_empty_sent = [s.strip() for s in sentences if len(s.strip()) > 10 and not _is_placeholder(s)]
                        if non_empty_sent:
                            correct_answer = " ".join(non_empty_sent[:2])

            if not correct_answer or _is_placeholder(correct_answer) or str(correct_answer).strip().lower() in invalid_ans_set:
                if subject_type == "SOCIAL":
                    correct_answer = f"Kết luận và giải pháp phân tích chuyên sâu cho bài tập môn {display_subject}."
                else:
                    correct_answer = f"Kết quả và lời giải toán học chính xác môn {display_subject}."
            if not detailed_sol:
                detailed_sol = correct_answer

            # Ép 100% Tiếng Việt tự nhiên và làm sạch công thức LaTeX
            topic = _clean_latex_string(topic)
            question_text = _clean_latex_string(question_text)
            correct_answer = _clean_latex_string(correct_answer)
            detailed_sol = _clean_latex_string(detailed_sol)

            # Tự động thay thế các từ 'course_7', 'course_27' xuất hiện dư thừa thành tên môn học hiển thị chuẩn
            question_text = _sanitize_course_code_mentions(question_text, display_subject)
            correct_answer = _sanitize_course_code_mentions(correct_answer, display_subject)
            detailed_sol = _sanitize_course_code_mentions(detailed_sol, display_subject)
            topic = _sanitize_course_code_mentions(topic, display_subject)

            # Loại bỏ các câu mở đầu lặp lại đề bài theo khuôn mẫu (ví dụ: 'Triết học Mác - Lênin được xem là bước tiến vì...')
            correct_answer = _clean_robotic_answer_prefix(question_text, correct_answer)

            # Chuẩn hóa mã hóa Enum cho Difficulty & Bloom
            diff_enum = _normalize_difficulty(str(raw_diff or "MEDIUM"))
            bloom_enum = _normalize_bloom(str(raw_bloom or "UNDERSTANDING"))

            diff_str = diff_enum.value.capitalize()
            bloom_str = bloom_enum.value.capitalize()

            ordered_item = {
                "id": str(final_item.get("id") or f"{safe_subj.upper()}_C{safe_chap}_{idx:03d}"),
                "lesson_number": lesson_num or "1.1",
                "lesson_name": lesson_nam or req.chapter,
                "topic": str(topic or "Bài tập AI Sinh"),
                "difficulty": diff_str,
                "bloom_level": bloom_str,
                "question_text": str(question_text or "Chưa có nội dung câu hỏi"),
                "full_answer": str(correct_answer or "Chưa có đáp án"),
                "detailed_solution": detailed_sol,
                "scaffolding_steps": final_item.get("scaffolding_steps", []),
                "common_mistakes": final_item.get("common_mistakes", [])
            }

            final_item.clear()
            final_item.update(ordered_item)

            db_exercises.append(ExtractedExercise(
                exerciseCode=ordered_item["id"],
                exerciseName=ordered_item["topic"][:200],
                difficulty=diff_enum,
                bloomLevel=bloom_enum,
                question=ordered_item["question_text"],
                correctAnswer=str(correct_answer)
            ))

        if len(db_exercises) == 0:
            print("  [Emergency Generator] Không có bài tập hợp lệ sau Stage 2. Đang tự động tạo cấp cứu 3 bài tập từ lý thuyết...")
            fallback_items = _generate_fallback_exercises(req.subject, req.chapter, theory_truncated)
            if fallback_items:
                for idx, fb in enumerate(fallback_items, start=1):
                    q_txt = fb.get("question_text") or fb.get("question") or "Cho dữ kiện bài toán tự luận bám sát giáo trình."
                    ans_txt = fb.get("full_answer") or fb.get("correct_answer") or "Xem chi tiết lời giải"
                    sol_txt = fb.get("detailed_solution") or fb.get("detailed_explanation") or ans_txt
                    top_txt = fb.get("topic") or f"Bài tập tự luận {idx}"
                    diff_e = _normalize_difficulty(fb.get("difficulty", "MEDIUM"))
                    bloom_e = _normalize_bloom(fb.get("bloom_level", "UNDERSTANDING"))
                    ex_id = fb.get("id") or f"{safe_subj.upper()}_C{safe_chap}_{idx:03d}"
                    
                    db_exercises.append(ExtractedExercise(
                        exerciseCode=ex_id,
                        exerciseName=top_txt[:200],
                        difficulty=diff_e,
                        bloomLevel=bloom_e,
                        question=q_txt,
                        correctAnswer=ans_txt
                    ))
                    final_list.append({
                        "id": ex_id,
                        "lesson_number": fb.get("lesson_number", "1.1"),
                        "lesson_name": fb.get("lesson_name", req.chapter),
                        "topic": top_txt,
                        "difficulty": diff_e.value.capitalize(),
                        "bloom_level": bloom_e.value.capitalize(),
                        "question_text": q_txt,
                        "full_answer": ans_txt,
                        "detailed_solution": sol_txt,
                        "scaffolding_steps": fb.get("scaffolding_steps", []),
                        "common_mistakes": fb.get("common_mistakes", [])
                    })

        if len(db_exercises) == 0:
            err_msg = f"Mô hình AI không trích xuất được bài tập hợp lệ nào. Lý do có thể: AI chỉ sinh ra câu hỏi mẫu (placeholder) do nội dung file không chứa đủ kiến thức chuyên môn. Kích thước file: {len(theory_truncated)} ký tự. File: {target_file}"
            print(f"[Multi-Agent] THẤT BẠI: {err_msg}")
            raise HTTPException(status_code=500, detail=err_msg)

        # Cố định đúng 3 bài tập chất lượng cao (1 Easy, 1 Medium, 1 Hard)
        if len(db_exercises) > 3:
            db_exercises = db_exercises[:3]
            final_list = final_list[:3]

        # --- HẬU XỬ LÝ DÙNG CHUNG CHO MỌI MÔN HỌC: Đảm bảo tỷ lệ 3 câu chuẩn phân hoá ---
        if len(db_exercises) >= 3:
            # Mục tiêu chuẩn mực tổng quát cho 3 câu: [Easy-Understanding, Medium-Applying, Hard-Evaluating]
            ALL_TARGET_PROFILES = [
                ("Easy", "Understanding"),
                ("Medium", "Applying"),
                ("Hard", "Evaluating")
            ]
            TARGET_PROFILE = ALL_TARGET_PROFILES[:len(db_exercises)]

            bloom_priority = {
                "Remembering": 0, "Understanding": 1, "Applying": 2,
                "Analyzing": 3, "Evaluating": 4
            }

            # Sắp xếp 5 câu theo độ sâu Bloom hiện tại của chúng (nếu bằng nhau giữ thứ tự sinh ra)
            sorted_indices = sorted(
                range(len(db_exercises)),
                key=lambda i: (
                    bloom_priority.get(db_exercises[i].bloomLevel.value.capitalize(), 1),
                    i
                )
            )

            print("  [DiffRebalancer] Đang tái chuẩn hoá độ khó & Bloom Level tổng quát cho mọi môn học...")
            for rank_pos, item_idx in enumerate(sorted_indices):
                target_diff_str, target_bloom_str = TARGET_PROFILE[rank_pos]
                
                cur_bloom = db_exercises[item_idx].bloomLevel.value.capitalize()
                final_bloom_str = target_bloom_str
                # Nếu câu ở vị trí Medium/Hard mà LLM trót trả về Remembering/Understanding, gán chuẩn theo target
                if rank_pos >= 2 and cur_bloom in ["Remembering", "Understanding"]:
                    final_bloom_str = target_bloom_str
                elif cur_bloom in bloom_priority:
                    # Giữ Bloom từ LLM nếu nó đã ở mức phù hợp hoặc cao hơn
                    if bloom_priority[cur_bloom] > bloom_priority[target_bloom_str]:
                        final_bloom_str = cur_bloom

                new_diff_enum = _normalize_difficulty(target_diff_str)
                new_bloom_enum = _normalize_bloom(final_bloom_str)

                db_exercises[item_idx] = ExtractedExercise(
                    exerciseCode=db_exercises[item_idx].exerciseCode,
                    exerciseName=db_exercises[item_idx].exerciseName,
                    difficulty=new_diff_enum,
                    bloomLevel=new_bloom_enum,
                    question=db_exercises[item_idx].question,
                    correctAnswer=db_exercises[item_idx].correctAnswer
                )

                if item_idx < len(final_list):
                    final_list[item_idx]["difficulty"] = target_diff_str
                    final_list[item_idx]["bloom_level"] = final_bloom_str

            print("  [DiffRebalancer] Hoàn tất phân hoá tổng quát → 2 Easy (Nhớ/Hiểu), 2 Medium (Vận dụng/Phân tích), 1 Hard (Đánh giá) ✓")
            
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
        print(f"[ERROR in generate_from_theory]: {e}\n{trace}", file=sys.stderr)
        try:
            with open("crash.log", "w", encoding="utf-8") as f:
                f.write(trace)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống khi sinh bài tập: {str(e)}")
