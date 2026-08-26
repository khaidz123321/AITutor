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
import unicodedata

from fastapi import APIRouter, UploadFile, File, HTTPException, Header
from core.config import settings
from schemas.exercise import ExtractedExercise, ImportPdfResponse, Difficulty, BloomLevel, SyncScaffoldRequest, SyncScaffoldResponse, GenerateFromTheoryRequest, GenerateFromTheoryResponse
from core.mapping import _get_default_folder_name
from openai import OpenAI
import requests

import subprocess
import tempfile

def _call_llm(model: str, messages: list, temperature: float, response_format: dict = None, max_tokens: int = 8192) -> str:
    """
    Gọi trực tiếp mô hình Local AI (Ollama: DeepSeek-R1 / Qwen 2.5) trên phần cứng riêng.
    Không bị giới hạn thời gian gấp gáp, cho phép AI suy luận toán học/kỹ thuật chuyên sâu đầy đủ.
    """
    try:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "max_tokens": max_tokens
        }
        # Chỉ áp dụng response_format cho các model thông thường (như Qwen).
        # Không áp dụng cho DeepSeek-R1 để tránh làm đứt thẻ <think> suy luận.
        if response_format and "deepseek" not in model.lower() and "r1" not in model.lower():
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
            return full_reasoning
            
        return full_content
    except Exception as e:
        print(f"[{model}] Lỗi khi gọi qua Ollama API: {e}")
        raise Exception(f"Failed to call {model} via Ollama API: {e}")

router = APIRouter()

# Đọc cấu hình từ .env — dùng chung cho cả import-pdf và generate-scaffold-local
LOCAL_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-r1:14b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.ptitaitutor.com/v1")

local_client = OpenAI(
    api_key="sk-no-key-required",
    base_url=OLLAMA_BASE_URL,
    timeout=600.0,  # Thời gian chờ tối đa 10 phút, để Ollama xử lý thoải mái không bị ngắt quãng
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
    "understanding": "UNDERSTANDING", "hieu": "UNDERSTANDING", "hiểu": "UNDERSTANDING", "thông hiểu": "UNDERSTANDING", "thong hieu": "UNDERSTANDING", "giai thich": "UNDERSTANDING", "giải thích": "UNDERSTANDING",
    "applying": "APPLYING", "ap dung": "APPLYING", "áp dụng": "APPLYING", "van dung": "APPLYING", "vận dụng": "APPLYING", "vận dụng cao": "EVALUATING",
    "analyzing": "ANALYZING", "phan tich": "ANALYZING", "phân tích": "ANALYZING",
    "evaluating": "EVALUATING", "danh gia": "EVALUATING", "đánh giá": "EVALUATING",
    "creating": "EVALUATING", "sang tao": "EVALUATING", "sáng tạo": "EVALUATING",
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
    # Từ toán học & thuật toán tin học thường xuất hiện trong đề bài tiếng Việt
    'vector', 'norm', 'matrix', 'basis', 'scalar', 'space',
    'null', 'true', 'false',
    'branch', 'bound', 'heuristic', 'heuristics', 'backtracking', 'knapsack',
    'tsp', 'algorithm', 'algorithms', 'dijkstra', 'kruskal', 'floyd', 'warshall',
    'bellman', 'ford', 'prim', 'cpu', 'ram', 'io', 'fifo', 'lru', 'semaphore',
    'mutex', 'pipeline', 'pipelining', 'cache', 'instruction', 'datapath',
    'tcp', 'udp', 'ip', 'vlsm', 'cidr', 'osi', 'mac', 'packet', 'router',
    'sql', 'join', 'select', 'where', 'bcnf', 'uml', 'solid', 'pattern',
    'tree', 'graph', 'node', 'edge', 'vertex', 'vertices', 'array', 'binary', 'sort'
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
    """Phát hiện Tiếng Anh thực sự (tránh dịch thừa làm tăng thời gian sinh)."""
    if not text or not isinstance(text, str):
        return False
    if _contains_foreign_language(text):
        return True
        
    # Nếu văn bản đã có nhiều ký tự có dấu Tiếng Việt thì chắc chắn là Tiếng Việt
    has_vn_accents = bool(re.search(r'[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]', text, re.IGNORECASE))
    
    count, total, ratio = _count_english_words(text)
    if has_vn_accents:
        # Đã có tiếng Việt: Chỉ dịch khi đoạn văn bị chèn cả một đoạn tiếng Anh dài
        return total >= 15 and ratio > 0.60 and count >= 12
    else:
        # Không có dấu tiếng Việt (có thể là tiếng Anh hoàn toàn)
        return (total >= 10 and ratio > 0.40 and count >= 6) or (total < 10 and count >= 5)


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
    # Bắt các câu hỏi khung mẫu rỗng (skeleton template) do AI sinh lười
    skeleton_patterns = [
        "một tình huống cụ thể về việc",
        "một tình huống cụ thể",
        "vận dụng lý thuyết để chẩn đoán vấn đề",
        "đề xuất giải pháp khắc phục",
        "chẩn đoán vấn đề dựa trên lý thuyết",
        "giải pháp dựa trên phương pháp",
        "tình huống case study câu",
        "tình huống mâu thuẫn hệ thống vĩ mô",
        "bối cảnh học thuật và yêu cầu",
        "luận điểm cốt lõi và kết luận phương pháp luận",
        "tham khảo kịch bản",
        "tham khao kich ban",
        "đáp án 1", "đáp án 2", "đáp án 3",
        "kết quả chính xác 1",
        "bài toán tự luận bám",
        # Đáp án "meta" — AI tuyên bố đã làm xong nhưng không đưa ra nội dung thật (không có số liệu,
        # phép biến đổi hay lập luận cụ thể nào) — vô giá trị hệt như bỏ trống, ví dụ "Chứng minh thành công".
        "chứng minh thành công",
        "đã chứng minh thành công",
        "đã được chứng minh",
        "chứng minh đúng như yêu cầu",
        "kết quả đúng như yêu cầu",
        "đã giải thành công",
        "giải thành công",
        "đúng như yêu cầu đề bài",
    ]
    if any(p in s for p in skeleton_patterns):
        return True
    # Bắt TỔNG QUÁT mọi placeholder dạng <...> mà AI lỡ trả về nguyên văn thay vì tự viết nội dung
    # (không cần liệt kê từng mẫu cụ thể trong prompt — mẫu prompt có thể đổi/thêm theo thời gian).
    # Chỉ tính là placeholder khi CẢ CÂU chỉ gồm placeholder này (kèm dấu câu/khoảng trắng thừa),
    # tránh chặn nhầm câu hỏi thật có dùng dấu < > hợp lệ (ví dụ bất đẳng thức "x < 5").
    if re.fullmatch(r'[\s.:,;]*<[^<>]{3,120}>[\s.:,;]*', s):
        return True
    # Bắt TỔNG QUÁT placeholder dạng chữ thường (không có dấu <>) mà AI trả về nguyên văn mô tả
    # trường dữ liệu trong prompt thay vì tự đặt tên thật — ví dụ "Tên chuyên đề thực tế phần đầu",
    # "Tên mục phần cuối trong giáo trình trên", "Chủ đề cơ bản trong giáo trình", "Chủ đề thực tế
    # trong giáo trình"... Nhận diện qua việc câu bắt đầu bằng "Tên "/"Chủ đề " và có kèm các từ mô
    # tả vị trí/mức độ chung chung (phần đầu/giữa/cuối, trong giáo trình, cơ bản...) chứ không mang
    # nội dung chuyên môn cụ thể nào của môn học.
    if re.match(r'^(?:tên (?:chuyên đề|mục|chủ đề|định lý|nguyên lý)|chủ đề)\b', s):
        if any(w in s for w in ["phần đầu", "phần giữa", "phần cuối", "trong giáo trình", "cốt lõi", "thực tế", "cơ bản"]):
            return True
    return False


# Ký tự chữ Hán/Nhật/Hàn hoặc dấu câu full-width kiểu Trung Quốc (｡，、etc.) — dấu hiệu model suy luận
# xen tiếng Trung (thường gặp ở các model gốc Trung Quốc như DeepSeek-R1) rò rỉ ra output cuối cùng,
# vi phạm luật "100% Tiếng Việt chuẩn mực" đã đặt ra trong prompt.
_CJK_RE = re.compile(r'[一-鿿぀-ヿ가-힯　-〿＀-￯]')


def _has_cjk_chars(text) -> bool:
    return bool(_CJK_RE.search(str(text or "")))


# Ký tự tiếng Việt có dấu (nguyên âm mang thanh điệu + ă/â/ê/ô/ơ/ư/đ) — dùng để phát hiện TỔNG QUÁT
# đoạn văn bản lẫn tiếng Anh/ngôn ngữ khác (thường gặp ở DeepSeek-R1 khi suy luận), KHÔNG cần liệt kê
# từ điển tiếng Anh (luôn thiếu). Nguyên lý: văn bản tiếng Việt thật luôn có mật độ ký tự có dấu đáng
# kể; nếu 1 đoạn đủ dài mà gần như không có ký tự nào thuộc bộ này, gần chắc chắn không phải tiếng Việt.
_VN_DIACRITIC_RE = re.compile(
    r'[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡ'
    r'ùúụủũưừứựửữỳýỵỷỹđ]', re.IGNORECASE
)
_LATEX_STRIP_RE = re.compile(r'\$[^$]*\$|\\\([^)]*\\\)|\\\[[^\]]*\\\]|\\[a-zA-Z]+\{[^{}]*\}|\\[a-zA-Z]+')


def _lacks_vietnamese_diacritics(text, min_len: int = 80) -> bool:
    """Đoạn văn bản (sau khi bỏ công thức LaTeX/toán) đủ dài mà gần như không có ký tự tiếng Việt có
    dấu nào -> dấu hiệu lẫn tiếng Anh/ngôn ngữ khác, bất kể nội dung cụ thể là gì."""
    s = str(text or "")
    s_no_latex = _LATEX_STRIP_RE.sub(' ', s)
    alpha_count = sum(1 for c in s_no_latex if c.isalpha())
    if alpha_count < min_len:
        return False
    diacritic_count = len(_VN_DIACRITIC_RE.findall(s_no_latex))
    return (diacritic_count / alpha_count) < 0.03


# Câu hỏi STEM bắt đầu bằng động từ mô tả/trình bày suông (đúng loại prompt đã liệt kê CẤM: "Nêu định
# nghĩa...", "Giải thích cách hoạt động...", "So sánh hiệu quả...", "Trình bày khái niệm...").
_STEM_ROTE_PREFIX_RE = re.compile(
    r'^(?:hãy\s+)?(?:nêu|cho biết|giải thích|trình bày|mô tả|liệt kê|so sánh)\b', re.IGNORECASE
)


def _lacks_concrete_stem_data(question_text) -> bool:
    """
    Nhận diện câu hỏi STEM 'hỏi vẹt' lý thuyết suông — không có dữ liệu định lượng/công thức cụ thể
    nào để tính toán/áp dụng, vi phạm chính luật STEM đã đặt ra trong prompt ("BẮT BUỘC có dữ liệu đầu
    vào cụ thể", "CẤM câu hỏi lý thuyết trình bày suông"). Chỉ dùng cho subject_type == "STEM" — câu
    hỏi SOCIAL hợp lệ khi là case-study/phân tích lý luận, không nhất thiết cần số liệu.
    """
    s = str(question_text or "").strip()
    if not s:
        return True
    if _STEM_ROTE_PREFIX_RE.match(s):
        return True
    has_digit = bool(re.search(r'\d', s))
    # Bổ sung ký hiệu logic số (~ ¬ ∧ ∨ → ⊕ ! && || ) — trước đây thiếu, khiến câu hỏi biến đổi
    # biểu thức logic hợp lệ (VD "~(A+B).C", "NOT B OR C") bị coi nhầm là "thiếu dữ liệu cụ thể".
    has_math_symbol = bool(re.search(r'[=\$\\∫∑√≤≥±×÷~¬∧∨⊕⊻⇒⇔]|&&|\|\||\bNOT\b|\bAND\b|\bOR\b|\bXOR\b', s, re.IGNORECASE))
    if not has_digit and not has_math_symbol and len(s) < 250:
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
        m = re.search(r'"question(?:_text)?"\s*:\s*"([^"]+)"', text)
        if m:
            text = m.group(1)
        elif text in ("{}", "[]"):
            return ""

    # Loại bỏ triệt để dấu chấm lặp (.. hoặc ...) thành đúng 1 dấu chấm
    text = re.sub(r'\.{2,}', '.', text)
    text = re.sub(r'([.?!])\s*[.?!]+', r'\1', text)
    text = re.sub(r'\.\s*\n', '.\n', text)

    # 1. Khôi phục các ký tự LaTeX bị mất backslash hoặc bị biến thành ký tự điều khiển
    text = text.replace('\x0crac', r'\frac').replace('\x08ar', r'\bar').replace('\x08egin', r'\begin').replace('\x07lpha', r'\alpha').replace('\x08eta', r'\beta')
    text = text.replace('\x0c', r'\f').replace('\x08', r'\b').replace('\x07', r'\a').replace('\x0b', r'\v')
    text = text.replace('\t', ' ')
    text = re.sub(r'(?<!\\)\brightarrow\b', r'\\rightarrow', text)
    text = re.sub(r'(?<!\\)\bRightarrow\b', r'\\Rightarrow', text)
    text = re.sub(r'(?<!\\)\bleftarrow\b', r'\\leftarrow', text)
    text = text.replace('ightarrow', r'\rightarrow').replace('Leftrightarrow', r'\Leftrightarrow')
    text = re.sub(r'(?<!\\)\brac\{', r'\\frac{', text)
    text = re.sub(r'(?<!\\)\bar\{', r'\\bar{', text)
    text = re.sub(r'(?<!\\)\bsqrt\{', r'\\sqrt{', text)
    text = re.sub(r'(?<!\\)\boverline\{', r'\\overline{', text)
    text = re.sub(r'(?<!\\)\bext\{lim\}', r'\\lim', text)
    text = re.sub(r'(?<!\\)\bext\{max\}', r'\\max', text)
    text = re.sub(r'(?<!\\)\bext\{min\}', r'\\min', text)
    text = re.sub(r'\\text\{lim\}', r'\\lim', text)
    text = re.sub(r'\\text\{max\}', r'\\max', text)
    text = re.sub(r'\\text\{min\}', r'\\min', text)
    text = re.sub(r'(?<!\\)\bext\{([^}]+)\}', r'\\text{\1}', text)
    text = re.sub(r'(?<!\\)\btheta\b', r'\\theta', text)
    text = re.sub(r'(?<!\\)\btimes\b', r'\\times', text)
    text = re.sub(r'(?<!\\)\bto\b', r'\\to', text)
    text = re.sub(r'(?<!\\)\binfty\b', r'\\infty', text)
    text = text.replace("♠rac", r"\frac").replace("♠", r"\f")

    # 2. Xóa bỏ dấu double backslash phân cách LaTeX dư thừa cho KaTeX / UI renderer
    text = text.replace(r"\\frac", r"\frac").replace(r"\\begin", r"\begin").replace(r"\\end", r"\end")
    text = text.replace(r"\\int", r"\int").replace(r"\\iint", r"\iint").replace(r"\\sum", r"\sum")
    text = text.replace(r"\\lim", r"\lim").replace(r"\\cases", r"\cases").replace(r"\\sqrt", r"\sqrt")
    text = text.replace(r"\\partial", r"\partial").replace(r"\\text", r"\text").replace(r"\\mathbf", r"\mathbf")
    text = text.replace(r"\\mathbb", r"\mathbb").replace(r"\\mathcal", r"\mathcal").replace(r"\\ln", r"\ln")
    text = text.replace(r"\\sin", r"\sin").replace(r"\\cos", r"\cos").replace(r"\\tan", r"\tan")
    text = text.replace(r"\\exp", r"\exp").replace(r"\\to", r"\to").replace(r"\\infty", r"\infty")
    text = text.replace(r"\\rightarrow", r"\rightarrow").replace(r"\\Rightarrow", r"\Rightarrow")
    text = text.replace(r"\\approx", r"\approx").replace(r"\\neq", r"\neq").replace(r"\\leq", r"\leq").replace(r"\\geq", r"\geq")
    text = text.replace(r"\\(", r"\(").replace(r"\\)", r"\)").replace(r"\\[", r"\[").replace(r"\\]", r"\]")

    # 3. Làm sạch chữ Hán hoặc từ tiếng Anh sót lại trong câu hỏi toán
    text = text.replace("tách变", "tách biến").replace("变", "biến").replace("求", "Tìm ").replace("解", "Giải ")
    text = text.replace("contiuous", "liên tục").replace("continuous", "liên tục")
    text = text.replace("particular solution", "nghiệm riêng").replace("general solution", "nghiệm tổng quát")
    return text


# Từ chức năng/công cụ chung (không mang ý nghĩa nội dung riêng biệt của bài toán) — loại khỏi phép so
# khớp Jaccard để tránh 2 câu hỏi KHÁC Ý TƯỞNG nhưng cùng dùng thuật ngữ chuyên ngành/chỉ thị đề bài
# (vd "cho", "chứng minh", "tính", "ma trận"...) bị hiểu nhầm là trùng lặp — đặc biệt hay xảy ra với
# các chương STEM có từ vựng chuyên ngành hẹp (VD: mọi câu chương "Định thức" đều có "ma trận", "khả nghịch").
_GENERIC_QUESTION_STOPWORDS = {
    "cho", "la", "va", "cua", "cac", "mot", "nhung", "hay", "khi", "de", "trong", "voi",
    "nay", "do", "sao", "tim", "tinh", "xac", "dinh", "chung", "minh", "rang", "gi", "nhu",
    "sau", "tren", "theo", "neu", "thi", "duoc", "co", "khong", "ban", "hoc", "bai", "tap",
    "so", "hoi", "dap", "an", "giai", "phuong", "trinh", "bang", "day", "phai", "tu", "den",
    "ket", "qua", "hay", "nen", "moi", "hai", "ba", "cho", "biet", "day", "gom",
}

def _content_words(text: str) -> set:
    """Tách từ và loại bỏ stopword chức năng chung, chỉ giữ lại các từ mang nội dung riêng để so trùng lặp."""
    import unicodedata as _ud
    def no_acc(s):
        return "".join(c for c in _ud.normalize('NFKD', s) if not _ud.combining(c)).replace('đ', 'd').replace('Đ', 'D')
    words = re.findall(r'\w+', text.lower())
    return {w for w in words if no_acc(w) not in _GENERIC_QUESTION_STOPWORDS}


def _has_batch_semantic_collision(q_text: str, existing_questions: list, subject_type: str = "STEM") -> bool:
    """
    Kiểm tra xem câu hỏi mới có bị dập khuôn hoặc trùng lặp mô-típ / bài toán với các câu đã có trong bộ đề không.
    - Chống spam mô-típ đố kinh tế/lợi nhuận/nhà máy nhiều câu trong 1 đề.
    - Chống dập khuôn sao chép cùng hàm số hay cùng cấu trúc đề bài (Jaccard token overlap, loại trừ stopword chung).
    Ngưỡng nới rộng hơn cho STEM vì từ vựng chuyên ngành hẹp của 1 chương tự nhiên lặp lại nhiều
    giữa các câu hỏi dù nội dung/ý tưởng thực sự khác nhau (SOCIAL giữ ngưỡng chặt vì văn phong nghị luận
    lặp câu chữ mới thực sự là dấu hiệu trùng ý).
    """
    if not q_text or not existing_questions:
        return False
    threshold = 0.60 if subject_type == "STEM" else 0.45
    q_low = q_text.lower()
    w_new = _content_words(q_low)
    if not w_new:
        return False
    for ex_q in existing_questions:
        ex_low = ex_q.lower()
        # 1. Trùng lặp mô-típ đố kinh tế/lợi nhuận/nhà máy trong cùng bộ đề
        if any(k in q_low for k in ["lợi nhuận", "chi phí c(x)", "nhà sản xuất", "công ty sản xuất", "doanh nghiệp"]) and \
           any(k in ex_low for k in ["lợi nhuận", "chi phí c(x)", "nhà sản xuất", "công ty sản xuất", "doanh nghiệp"]):
            return True
        # 2. Token Jaccard overlap (đã loại stopword chung) vượt ngưỡng theo nhánh môn học
        w_ex = _content_words(ex_low)
        if w_ex:
            inter = len(w_new.intersection(w_ex))
            union = len(w_new.union(w_ex))
            if union and (inter / union) > threshold:
                return True
    return False


def _clean_robotic_answer_prefix(question: str, answer: str) -> str:
    """Loại bỏ các câu lặp lại đề bài theo khuôn mẫu ở đầu đáp án (ví dụ: 'Triết học Mác - Lênin được xem là bước tiến vì...')."""
    if not answer or not isinstance(answer, str):
        return answer
    ans = answer.strip()
    if not question or not isinstance(question, str):
        return ans

    # Tìm đoạn tiền tố lặp lại đề bài kéo dài đến từ 'vì', 'là', 'gồm', 'khi', 'rằng' trước mệnh đề
    m_rep = re.match(r'^(?:[^\n.!?]{10,120}?)\s+(?:là|vì|gồm|khi|rằng)\s*[:,\-–—]?\s*', ans, re.IGNORECASE)
    if m_rep:
        prefix = m_rep.group(0)
        # Chỉ cắt bỏ nếu prefix này chứa các từ khóa trùng lặp với đề bài
        q_words = set(re.findall(r'\w+', question.lower()))
        p_words = set(re.findall(r'\w+', prefix.lower()))
        if len(p_words.intersection(q_words)) >= 3:
            cleaned_ans = ans[len(prefix):].strip()
            if len(cleaned_ans) >= 5:
                return cleaned_ans[0].upper() + cleaned_ans[1:]
    return ans


def _generate_short_subject_code(subject: str) -> str:
    """Tạo mã môn viết tắt ngắn gọn (ví dụ: 'Triết học Mác - Lênin' -> 'THML', 'Kinh tế chính trị' -> 'KTCT', 'Giải tích 2' -> 'GT2')."""
    if not subject:
        return "EX"
    s_norm = "".join([c for c in unicodedata.normalize('NFKD', str(subject)) if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')
    s_norm = s_norm.strip()
    
    # Map cố định một số môn thông dụng
    fixed_map = {
        "triet hoc mac - lenin": "THML",
        "triet hoc mac-lenin": "THML",
        "triet hoc": "TH",
        "kinh te chinh tri mac - lenin": "KTCT",
        "kinh te chinh tri mac-lenin": "KTCT",
        "kinh te chinh tri": "KTCT",
        "chu nghia xa hoi khoa hoc": "CNXHKH",
        "tu tuong ho chi minh": "TTHCM",
        "phap luat dai cuong": "PLDC",
        "giai tich 1": "GT1",
        "giai tich 2": "GT2",
        "dai so tuyen tinh": "DSTT",
        "toan roi rac 1": "TRR1",
        "toan roi rac 2": "TRR2",
        "toan roi rac": "TRR",
        "vat ly 1": "VL1",
        "vat ly 2": "VL2",
        "vat ly 3": "VL3",
        "he dieu hanh": "HDH",
        "co so du lieu": "CSDL",
        "mang may tinh": "MMT",
    }
    s_low = s_norm.lower()
    if s_low in fixed_map:
        return fixed_map[s_low]
        
    words = re.split(r'[\s_\-]+', s_norm)
    code = "".join([w[0].upper() for w in words if w and w[0].isalnum()])
    code = re.sub(r'[^A-Z0-9]', '', code)
    if len(code) >= 2:
        return code[:5]
    clean_s = re.sub(r'[^A-Za-z0-9]', '', s_norm).upper()
    return clean_s[:4] if clean_s else "EX"


def _clean_math_vietnamese(text: str) -> str:
    """Dịch thuật và chuẩn hóa các thuật ngữ toán học / khoa học tiếng Anh còn sót lại sang Tiếng Việt chuẩn mực."""
    if not text or not isinstance(text, str):
        return text
    
    replacements = [
        (r'\bGiven\b', 'Cho'),
        (r'\bLet\b', 'Giả sử'),
        (r'\bFind\b', 'Tìm'),
        (r'\bCalculate\b', 'Tính'),
        (r'\bCompute\b', 'Tính'),
        (r'\bProve\b', 'Chứng minh'),
        (r'\bShow that\b', 'Chứng minh rằng'),
        (r'\bDetermine\b', 'Xác định'),
        (r'\bEvaluate\b', 'Tính giá trị'),
        (r'\bConsider\b', 'Xét'),
        (r'\bAssume\b', 'Giả sử'),
        (r'\bTherefore\b', 'Do đó'),
        (r'\bThus\b', 'Như vậy'),
        (r'\bHence\b', 'Từ đó'),
        (r'\bSolution\b', 'Lời giải'),
        (r'\bAnswer\b', 'Đáp án'),
        (r'\bStep\b', 'Bước'),
        (r'\bwhere\b', 'với'),
        (r'\bcontinuous\b', 'liên tục'),
        (r'\bdifferentiable\b', 'khả vi'),
        (r'\bintegral\b', 'tích phân'),
        (r'\bderivative\b', 'đạo hàm'),
        (r'\bmatrix\b', 'ma trận'),
        (r'\bdeterminant\b', 'định thức'),
        (r'\beigenvalue\b', 'trị riêng'),
        (r'\beigenvector\b', 'vector riêng'),
        (r'\bgraph\b', 'đồ thị'),
        (r'\bvertex\b', 'đỉnh'),
        (r'\bedge\b', 'cạnh'),
        (r'\btree\b', 'cây'),
        (r'\bspanning tree\b', 'cây khung'),
    ]
    res = text
    for pat, rep in replacements:
        res = re.sub(pat, rep, res, flags=re.IGNORECASE)
    return res


def _format_multipart_questions(text: str) -> str:
    """Đảm bảo nếu đề bài có từ 2 yêu cầu trở lên thì chia thành a), b), c), d)... xuống dòng rõ ràng."""
    if not text or not isinstance(text, str):
        return text
    
    # 1. Chuẩn hóa các dạng đánh số 1), 2), 3) hoặc 1., 2., 3. hoặc i), ii), iii) hoặc - thành a), b), c)
    text = re.sub(r'(?:\n|\A)\s*(?:1[\).]|i\))\s*', '\na) ', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:\n|\A)\s*(?:2[\).]|ii\))\s*', '\nb) ', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:\n|\A)\s*(?:3[\).]|iii\))\s*', '\nc) ', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:\n|\A)\s*(?:4[\).]|iv\))\s*', '\nd) ', text, flags=re.IGNORECASE)

    # 2. Đảm bảo a), b), c), d) luôn nằm trên dòng mới nếu đang bị dính liền vào câu trước
    text = re.sub(r'([.?!;])\s*a\)\s+', r'\1\na) ', text)
    text = re.sub(r'([.?!;])\s*b\)\s+', r'\1\nb) ', text)
    text = re.sub(r'([.?!;])\s*c\)\s+', r'\1\nc) ', text)
    text = re.sub(r'([.?!;])\s*d\)\s+', r'\1\nd) ', text)

    # 3. Nếu chưa có a), b) nhưng đề bài có >= 2 câu hỏi / yêu cầu tính toán riêng biệt
    if "a)" not in text and "b)" not in text:
        parts = re.split(r'(?<=[.?!])\s+(?=(?:Tính|Tìm|Khảo sát|Chứng minh|Biện luận|Xác định|Giải|Rút gọn|Vẽ|Cho biết)\s+)', text)
        if len(parts) >= 3:
            lead = parts[0]
            sub_items = []
            markers = ['a)', 'b)', 'c)', 'd)', 'e)']
            for idx, p in enumerate(parts[1:]):
                if idx < len(markers):
                    sub_items.append(f"{markers[idx]} {p}")
                else:
                    sub_items.append(p)
            text = lead + "\n" + "\n".join(sub_items)

    return text.strip()


def _clean_question_text(q_text: str) -> str:
    if not q_text or not isinstance(q_text, str):
        return ""
    s = re.sub(r'[\u4e00-\u9fff]+', '', q_text)
    s = re.sub(r'!\[.*?\]\(.*?\)', '', s)
    
    lines = [l.strip() for l in s.splitlines() if l.strip()]
    clean_lines = []
    skip_hdr = True
    for l in lines:
        l_low = l.lower()
        if skip_hdr and any(l_low.startswith(p) for p in ["dựa trên", "dưới đây là", "sau đây là", "đây là", "---", "===", "theo yêu cầu", "để đáp ứng"]):
            continue
        if any(w in l_low for w in ["boyce", "diprima", "elementary differential", "tài liệu tham khảo", "lời nói đầu", "pgs. ts.", "tác giả:", "tạp đoàn bưu chính", "học viện công nghệ"]) or re.search(r'\(\d{4}\)\.', l):
            continue
        skip_hdr = False
        clean_lines.append(l)
    
    res = "\n".join(clean_lines).strip()
    res = re.sub(r'^(?:Một\s+(?:nhà toán học|nhà khoa học|nhà thiết kế|kỹ sư|chuyên gia|lập trình viên)\s+(?:cần|muốn|đang|phải)?\s*(?:tìm|xác định|tính|tối ưu|khảo sát|nghiên cứu|giải)?\s*[^.!?$\n]{0,80}?(?:của hàm số|của hàm|hàm số|hàm|biểu thức|phương trình|ma trận|hệ phương trình|đồ thị|chuỗi số|chuỗi|tích phân|đạo hàm)\s*)', 'Cho hàm số ', res, flags=re.IGNORECASE)
    res = re.sub(r'^(?:Một\s+đường cong\s+(?:hình học\s+)?được\s+(?:cho bởi|xác định bởi)\s*)', 'Cho đường cong ', res, flags=re.IGNORECASE)
    res = re.sub(r'^(?:Một\s+(?:nhà khoa học|nhà toán học|nhà thiết kế|kỹ sư|công ty|doanh nghiệp)\s+(?:cần|muốn|đang|phải|có|nghiên cứu)\s+[^.!?\n]{10,150}?[.!?]\s*)', '', res, flags=re.IGNORECASE)
    res = re.sub(r'^(?:Một\s+(?:nhà khoa học|nhà toán học|nhà thiết kế|kỹ sư|công ty|doanh nghiệp)\s+(?:cần|muốn|đang|phải)\s+)', '', res, flags=re.IGNORECASE)
    res = re.sub(r'\s*để đảm bảo tính liên tục và khả năng hoạt động của hệ thống kỹ thuật[.,;]?', '.', res, flags=re.IGNORECASE)
    res = re.sub(r'\s*để đảm bảo hoạt động của hệ thống[.,;]?', '.', res, flags=re.IGNORECASE)
    res = re.sub(r'\s*để đảm bảo[^.!?]*[.,;]?', '.', res, flags=re.IGNORECASE)
    res = re.sub(r'\s*và giải thích ý nghĩa thực tế của kết quả[.,;]?', '.', res, flags=re.IGNORECASE)
    res = re.sub(r'\s*và giải thích ý nghĩa thực tế[^.!?]*[.,;]?', '.', res, flags=re.IGNORECASE)
    res = re.sub(r'\s*dựa trên hiệu suất của hệ thống[.,;]?', '.', res, flags=re.IGNORECASE)
    res = re.sub(r'\s*dựa trên hiệu suất[^.!?]*[.,;]?', '.', res, flags=re.IGNORECASE)

    # 4. Loại bỏ triệt để mọi câu bình luận meta-commentary ngoài lề của AI (ở đầu, giữa hoặc cuối câu hỏi)
    meta_patterns = [
        r'(?:Bài toán|Câu hỏi|Bài tập|Đề bài|Yêu cầu|Phần)\s+(?:này\s+)?(?:liên quan|yêu cầu|nhằm|tập trung|kiểm tra|hướng dẫn|giúp|mô tả|được dùng|dùng để|được thiết kế|hướng đến|đòi hỏi)[^.!?\n]*[.!?]?',
        r'Mục tiêu của\s+(?:bài toán|câu hỏi|bài tập|đề bài)\s+(?:này\s+)?[^.!?\n]*[.!?]?',
        r'Hãy lưu ý rằng\s+[^.!?\n]*[.!?]?',
        r'Lưu ý rằng\s+[^.!?\n]*[.!?]?',
        r'Để giải quyết bài toán này[^.!?\n]*[.!?]?'
    ]
    for mp in meta_patterns:
        res = re.sub(mp, '', res, flags=re.IGNORECASE)
    
    # 5. Dọn dẹp khoảng trắng, dấu chấm thừa sau khi loại bỏ câu
    res = re.sub(r'\s*\.\s*\.', '.', res)
    res = re.sub(r'[ \t]+', ' ', res)
    res = re.sub(r'\n{3,}', '\n\n', res)
    
    # 6. Định dạng chia ý a), b), c), d) nếu câu hỏi có nhiều yêu cầu
    res = _format_multipart_questions(res)
    res = res.strip()
    if res:
        if re.match(r'^[a-d]\)\s+', res, re.IGNORECASE):
            res = res[0].lower() + res[1:]
        else:
            res = res[0].upper() + res[1:]
    if len(res) < 15:
        return ""
    return res


def _prepare_balanced_theory_context(theory_content: str, max_chars: int = 15000, offset_phase: int = 0) -> str:
    """
    Trích xuất và cân bằng 3 phân đoạn (Đầu - Giữa - Cuối) của giáo trình.
    Hỗ trợ offset_phase (xoay chuyển phân đoạn) khi người dùng sinh nhiều đợt bài tập,
    giúp AI khám phá các chủ đề/mục con mới thay vì lặp lại các trang đầu.
    """
    theory_content = theory_content.strip()
    if len(theory_content) <= max_chars:
        return theory_content

    chunk_size = max_chars // 3
    total_len = len(theory_content)

    shift = (offset_phase * (chunk_size // 2)) % max(1, total_len - chunk_size)
    
    start1 = min(shift, max(0, total_len - chunk_size))
    part1 = theory_content[start1 : start1 + chunk_size].strip()

    mid_start = min((total_len - chunk_size) // 2 + shift // 2, max(0, total_len - chunk_size))
    part2 = theory_content[mid_start : mid_start + chunk_size].strip()

    end_start = max(0, total_len - chunk_size - (shift // 3))
    part3 = theory_content[end_start : end_start + chunk_size].strip()

    def clean_edge(txt: str, is_start: bool = False, is_end: bool = False) -> str:
        lines = txt.splitlines()
        if not is_start and len(lines) > 2:
            lines = lines[1:]
        if not is_end and len(lines) > 2:
            lines = lines[:-1]
        return "\n".join(lines).strip()

    p1 = clean_edge(part1, is_start=(start1 == 0))
    p2 = clean_edge(part2)
    p3 = clean_edge(part3, is_end=True)

    return f"""═══════════════════════════════════════════════════════════
► PHẦN 1: NỘI DUNG MỤC ĐẦU (DÙNG ĐỂ BIÊN SOẠN CÂU 1 - EASY / MỨC HIỂU)
═══════════════════════════════════════════════════════════
{p1}

═══════════════════════════════════════════════════════════
► PHẦN 2: NỘI DUNG MỤC GIỮA (DÙNG ĐỂ BIÊN SOẠN CÂU 2 - MEDIUM / MỨC VẬN DỤNG)
═══════════════════════════════════════════════════════════
{p2}

═══════════════════════════════════════════════════════════
► PHẦN 3: NỘI DUNG MỤC CUỐI (DÙNG ĐỂ BIÊN SOẠN CÂU 3 - HARD / MỨC ĐÁNH GIÁ)
═══════════════════════════════════════════════════════════
{p3}"""


_ROMAN_TO_ARABIC = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
    "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15, "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19, "xx": 20
}
_ARABIC_TO_ROMAN = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X",
    11: "XI", 12: "XII", 13: "XIV", 14: "XIV", 15: "XV", 16: "XVI", 17: "XVII", 18: "XVIII", 19: "XIX", 20: "XX"
}
_VIETNAMESE_WORDS = {
    1: "một", 2: "hai", 3: "ba", 4: "bốn", 5: "năm", 6: "sáu", 7: "bảy", 8: "tám", 9: "chín", 10: "mười"
}


def _parse_chap_index(chapter_str: str) -> int:
    """Trích xuất chính xác số thứ tự chương (hỗ trợ số Ả Rập, La Mã, chữ Tiếng Việt)."""
    raw = str(chapter_str or "").lower().strip()
    nfkd = unicodedata.normalize('NFKD', raw)
    no_accent = "".join([c for c in nfkd if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')
    # Dấu "-" phải đặt cuối character class, nếu không "[_.-:]" bị hiểu là RANGE từ "." đến ":"
    # (bao trùm cả các chữ số 0-9 trong bảng ASCII) khiến số chương bị xoá mất trước khi trích xuất.
    s = re.sub(r'[_.:-]+', ' ', no_accent)
    
    # 1. Tìm số Ả Rập
    m = re.search(r'(?:chuong|chapter|chap|c|bai|phan)\D*(\d+)', s)
    if m:
        return int(m.group(1))
    m2 = re.search(r'\b(\d+)\b', s)
    if m2:
        return int(m2.group(1))
        
    # 2. Tìm số La Mã
    for roman, val in [("xx", 20), ("xix", 19), ("xviii", 18), ("xvii", 17), ("xvi", 16), ("xv", 15),
                       ("xiv", 14), ("xiii", 13), ("xii", 12), ("xi", 11), ("x", 10), ("ix", 9),
                       ("viii", 8), ("vii", 7), ("vi", 6), ("v", 5), ("iv", 4), ("iii", 3), ("ii", 2), ("i", 1)]:
        if re.search(rf'(?:chuong|chapter|chap|c|bai|phan)\s+{roman}\b', s) or re.match(rf'^{roman}\b', s) or s == roman:
            return val
            
    # 3. Tìm chữ Tiếng Việt
    for word, val in [("muoi", 10), ("chin", 9), ("tam", 8), ("bay", 7), ("sau", 6), ("nam", 5), ("bon", 4), ("ba", 3), ("hai", 2), ("mot", 1)]:
        if re.search(rf'(?:chuong|chapter|chap|c|bai|phan)\s+{word}\b', s) or re.match(rf'^{word}\b', s) or s == word:
            return val
    return 1


def _extract_chapter_section_from_text(txt: str, chap_idx: int, is_filename_matched: bool = False, chapter_title_kw: str = "") -> str:
    """
    Trích xuất chính xác phạm vi lý thuyết của chương chap_idx từ văn bản giáo trình.
    Tự động loại bỏ Mục lục (TOC), Lời nói đầu (Preface) ở đầu file và các chương khác / tài liệu tham khảo ở cuối file.
    """
    if not txt or len(txt.strip()) < 50:
        return ""

    # Nếu file đã khớp chính xác chuong_X.txt thì toàn bộ nội dung file là của chương đó
    if is_filename_matched:
        lines = txt.splitlines()
        total_lines = len(lines)
        end_line = total_lines
        for i in range(25, total_lines):
            line = lines[i].strip()
            if re.search(r'^(?:#+\s*)?(?:tài liệu tham khảo|references|tài liệu trích dẫn)\b', line, re.IGNORECASE):
                end_line = i
                break
            m_other = re.search(r'^(?:#+\s*)?(?:ch[uưƣ]+[oơ]*ng|chapter|chap|b[aà]i|ph[aầ]n)\s*(\d+|[ivx]+)\b', line, re.IGNORECASE)
            if m_other:
                tok = m_other.group(1).lower()
                other_idx = _ROMAN_TO_ARABIC.get(tok) or (int(tok) if tok.isdigit() else -1)
                if other_idx != -1 and other_idx != chap_idx:
                    end_line = i
                    break
        return "\n".join(lines[:end_line]).strip()

    lines = txt.splitlines()
    total_lines = len(lines)

    cur_roman = _ARABIC_TO_ROMAN.get(chap_idx, "")
    cur_word = _VIETNAMESE_WORDS.get(chap_idx, "")

    start_tokens = [str(chap_idx)]
    if cur_roman:
        start_tokens.append(cur_roman)
    if cur_word:
        start_tokens.append(cur_word)
    start_tok_pat = "|".join(re.escape(t) for t in start_tokens)

    # 1. Tìm vị trí xuất hiện tiêu đề Chương chính xác (Chương X hoặc X.1)
    candidates = []
    found_sec_idx = chap_idx
    for i, line in enumerate(lines):
        clean_l = line.strip()
        m1 = re.search(rf'^(?:#+\s*)?(?:ch[uưƣ]+[oơ]*ng|chapter|chap|b[aà]i|ph[aầ]n)\s*(?:{start_tok_pat})\b', clean_l, re.IGNORECASE)
        m2 = re.search(rf'^(?:#+\s*)?{chap_idx}\.(?:0|1)(?:\.|\s|\b)', clean_l)
        if m1 or m2:
            next_sample = [lines[j].strip() for j in range(i+1, min(i+15, total_lines)) if lines[j].strip()]
            toc_lines = sum(1 for l in next_sample if re.search(r'\.{2,}\s*\d+|\b\d{1,3}$', l))
            is_toc = (len(next_sample) > 2 and toc_lines / len(next_sample) >= 0.35)
            is_preface = any(w in l.lower() for l in next_sample for w in ["lời nói đầu", "mục lục", "giáo trình dùng chia thành", "giáo trình này hữu ích"])
            candidates.append((i, is_toc or is_preface, clean_l))

    # 2. Nếu chưa tìm thấy theo số chương, thử tìm theo keyword ở cấp đề mục lớn (# Đề mục)
    if not candidates and chapter_title_kw and len(chapter_title_kw) > 3:
        import unicodedata
        def no_acc(s):
            return u"".join([c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D').lower()
        kw_clean = no_acc(chapter_title_kw)
        for i, line in enumerate(lines):
            clean_l = no_acc(line.strip())
            if re.match(r'^(?:#+\s*)?(?:\d+\.\d+|\d+\s*\.\s*\d+|chương|bài|phần)', clean_l) and kw_clean in clean_l:
                m_kw = re.search(r'(?:^|#|\s)(\d+)\.', clean_l)
                if not m_kw:
                    m_kw = re.search(r'(?:chương|bài|phần)\s+(\d+)', clean_l)
                if m_kw:
                    found_sec_idx = int(m_kw.group(1))
                candidates.append((i, False, clean_l))
                break

    valid_candidates = [c for c in candidates if not c[1]]
    if valid_candidates:
        start_line = valid_candidates[0][0]
    elif candidates:
        start_line = candidates[-1][0]
    elif is_filename_matched:
        start_line = 0
    else:
        return ""

    # 3. Tìm điểm kết thúc chương
    end_line = total_lines
    for i in range(start_line + 25, total_lines):
        line = lines[i].strip()
        if re.search(r'^(?:#+\s*)?(?:tài liệu tham khảo|references|tài liệu trích dẫn)\b', line, re.IGNORECASE) or re.search(r'^\s*1\.\s+[A-Z][a-z]+,\s+[A-Z]', line):
            end_line = i
            break
        m_other = re.search(r'^(?:#+\s*)?(?:ch[uưƣ]+[oơ]*ng|chapter|chap|b[aà]i|ph[aầ]n)\s*(\d+|[ivx]+)\b', line, re.IGNORECASE)
        if m_other:
            tok = m_other.group(1).lower()
            other_idx = _ROMAN_TO_ARABIC.get(tok) or (int(tok) if tok.isdigit() else -1)
            if other_idx != -1 and other_idx != found_sec_idx:
                end_line = i
                break
        m_sec = re.search(r'^(?:#+\s*)?(\d+)\.\d+(?:\.|\s|\b)', line)
        if m_sec:
            sec_idx = int(m_sec.group(1))
            if sec_idx != found_sec_idx and sec_idx != 0:
                end_line = i
                break

    chunk = "\n".join(lines[start_line:end_line]).strip()
    return chunk


def _extract_chapter_title_from_text(theory_text: str) -> str:
    """Trích xuất tự động tên chủ đề của chương từ các dòng tiêu đề đầu tiên."""
    if not theory_text:
        return ""
    lines = [l.strip() for l in theory_text.splitlines() if l.strip()]
    generic_words = ["giới thiệu", "tong quan", "tổng quan", "mở đầu", "mo dau", "khái niệm cơ bản", "các khái niệm mở đầu"]
    candidates = []
    for line in lines[:25]:
        # 1. Khớp dạng # Chương 4: Tên chương hoặc Chương 4. Tên chương
        m = re.search(r'^(?:#+\s*)?(?:ch[uưƣ]+[oơ]*ng|chapter|chap|b[aà]i)\s*(?:\d+|[ivx]+)\s*[:.\-–—]\s*([^\n]+)', line, re.IGNORECASE)
        if m:
            title = re.sub(r'^[\s.\-–—:]+|[\s.\-–—]+\d+$', '', m.group(1)).strip()
            if len(title) >= 3 and not title.lower().startswith('mục lục'):
                candidates.append(title)
        # 2. Khớp dạng # 4.1 / 4.2. Tên mục
        m2 = re.search(r'^(?:#+\s*)?\d+\.\d+(?:\.|\s|:)\s*([^\n]+)', line)
        if m2:
            title = re.sub(r'^[\s.\-–—:]+|[\s.\-–—]+\d+$', '', m2.group(1)).strip()
            if len(title) >= 3 and not title.lower().startswith('mục lục'):
                candidates.append(title)
        # 3. Khớp dạng # CHƯƠNG 4 TÊN CHƯƠNG
        m3 = re.search(r'^(?:#+\s*)?(?:ch[uưƣ]+[oơ]*ng|chapter|chap|b[aà]i)\s*(?:\d+|[ivx]+)\s+([A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸ\s\-]{3,60})', line)
        if m3:
            title = re.sub(r'^[\s.\-–—:]+|[\s.\-–—]+\d+$', '', m3.group(1)).strip()
            if len(title) >= 3:
                candidates.append(title.title())

    if not candidates:
        return ""
    # Ưu tiên candidate có tính học thuật cao và không phải là từ chung chung "giới thiệu", "mở đầu"
    for c in candidates:
        if not any(g in c.lower() for g in generic_words):
            return c
    return candidates[0]


def _resolve_rag_input_dir(subject_str: str, course_name: str = "") -> str:
    """Tự động xác định chính xác thư mục chứa tài liệu giáo trình RAG của môn học."""
    base_rag = os.path.join(settings.BASE_DIR, "data", "rag_input")
    if not os.path.isdir(base_rag):
        return os.path.join(base_rag, str(subject_str or ""))
    
    s_raw = str(subject_str or "").strip()
    c_raw = str(course_name or "").strip()
    
    # 1. Khớp trực tiếp theo đường dẫn tuyệt đối / tên thư mục chính xác
    p1 = os.path.join(base_rag, s_raw)
    if os.path.isdir(p1):
        return p1
        
    s_clean = _get_default_folder_name(s_raw)
    c_clean = _get_default_folder_name(c_raw)
    
    p2 = os.path.join(base_rag, s_clean)
    if os.path.isdir(p2):
        return p2
        
    p3 = os.path.join(base_rag, c_clean)
    if c_clean and os.path.isdir(p3):
        return p3

    # An toàn: nếu subject là mã course cụ thể (course_11, course_15...) mà không tìm thấy thư mục
    # tương ứng, TUYỆT ĐỐI KHÔNG được rơi xuống bước quét động/đoán mò bên dưới — mã course là định
    # danh 1-1 với thư mục theo quy ước đặt tên, không tồn tại nghĩa là dữ liệu THẬT SỰ chưa có/đang
    # upload lại (chưa xong), KHÔNG PHẢI trường hợp "tên thư mục đặt khác đi cần dò tìm". Việc quét động
    # theo nội dung dễ khớp nhầm sang môn hoàn toàn khác chỉ vì trùng vài từ khóa chung (VD "đại số"
    # xuất hiện cả trong "Đại số Boole" của môn Kỹ thuật số) — đã từng gây sinh bài tập Đại số bằng
    # nội dung Kỹ thuật số một cách âm thầm, không cảnh báo gì cả.
    if re.match(r'^course_\d+$', s_raw, re.IGNORECASE):
        print(f"[RAG Resolver] CẢNH BÁO: Không tìm thấy thư mục dữ liệu cho '{s_raw}' — trả về đường dẫn "
              f"trống thay vì đoán sang môn khác. Cần upload lại tài liệu cho môn này.")
        return p1

    # 2. Thuật toán quét động 100% nội dung tài liệu thực tế của TẤT CẢ các thư mục (Không hardcode)
    # (CHỈ áp dụng khi subject KHÔNG phải mã course chuẩn — ví dụ gọi bằng tên môn tự do/legacy)
    import unicodedata
    def remove_accents(s: str) -> str:
        nfkd = unicodedata.normalize('NFKD', str(s or ""))
        return u"".join([c for c in nfkd if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

    def normalize_str(s: str) -> str:
        no_acc = remove_accents(s).lower()
        return re.sub(r'[\s_\-]+', ' ', no_acc).strip()

    # Tạo danh sách các chuỗi tìm kiếm từ input (cả subject và course_name)
    search_queries = []
    for q in [s_raw, c_raw]:
        if q:
            norm = normalize_str(q)
            if norm and norm not in search_queries:
                search_queries.append(norm)

    all_dirs = [d for d in os.listdir(base_rag) if os.path.isdir(os.path.join(base_rag, d))]
    
    best_dir = None
    best_score = 0

    for d in all_dirs:
        sub_path = os.path.join(base_rag, d)
        sub_files = [f for f in os.listdir(sub_path) if f.endswith(".txt") and not f.startswith("test_") and not f.endswith("loi_noi_dau.txt")]
        if not sub_files:
            continue
            
        dir_score = 0
        # Đọc 3 file đầu tiên trong thư mục để trích xuất & chấm điểm ngữ nghĩa
        for f in sub_files[:3]:
            file_path = os.path.join(sub_path, f)
            if os.path.getsize(file_path) < 100:
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fl:
                    head_text = fl.read(8000)
                    head_norm = normalize_str(head_text)
                    
                    for q_norm in search_queries:
                        q_words = [w for w in q_norm.split() if len(w) > 1]
                        
                        # A. Khớp trọn vẹn cụm từ tên môn học (Trọng số cao nhất)
                        if q_norm in head_norm:
                            dir_score += 1000
                            
                        # B. Khớp mật độ từ khóa cốt lõi
                        if q_words:
                            word_matches = sum(1 for w in q_words if w in head_norm)
                            ratio = word_matches / len(q_words)
                            if ratio >= 0.6:
                                dir_score += int(ratio * 500)
                                
                            for w in q_words:
                                if len(w) >= 3:
                                    dir_score += min(head_norm.count(w) * 10, 100)
            except Exception:
                pass
                
        if dir_score > best_score:
            best_score = dir_score
            best_dir = sub_path

    if best_dir and best_score >= 100:
        print(f"[RAG Resolver] Tự động khớp môn '{s_raw}' ({c_raw}) -> Thư mục '{os.path.basename(best_dir)}' (Score: {best_score})")
        return best_dir
        
    return os.path.join(base_rag, s_clean or s_raw)


def _clean_ocr_theory_text(txt: str) -> str:
    """Loại bỏ triệt để rác OCR, câu lặp vô tận và tiếng Trung trong văn bản giáo trình."""
    if not txt:
        return ""
    # 1. Loại bỏ các khối prompt / thông báo lỗi OCR / tiếng Trung
    txt = re.sub(r'<!--\s*❌[^\n]*-->', '', txt)
    txt = re.sub(r'笛卡尔[^\n]*', '', txt)
    txt = re.sub(r'根据提供的内容[^\n]*', '', txt)
    txt = re.sub(r'[\u4e00-\u9fff]+[^\n]*', '', txt)
    
    # 2. Loại bỏ các dòng lặp lại liên tiếp (deduplicate consecutive identical lines)
    lines = txt.splitlines()
    cleaned_lines = []
    prev_line = ""
    for line in lines:
        l_s = line.strip()
        if l_s and l_s == prev_line:
            continue
        prev_line = l_s
        cleaned_lines.append(line)
        
    return "\n".join(cleaned_lines).strip()


def _clean_cjk_and_foreign_artifacts(text: str) -> str:
    """Loại bỏ triệt để ký tự chữ Hán, tiếng Trung và tàn dư ngoại ngữ khỏi câu hỏi/đáp án/lời giải."""
    if not text:
        return ""
    
    # 1. Từ điển thay thế các thuật ngữ tiếng Trung phổ biến nếu bị leak từ mô hình
    cjk_dict = {
        r'逸出功为': 'công thoát bằng ',
        r'逸出功': 'công thoát ',
        r'电子的最大初速度': 'vận tốc ban đầu cực đại của electron',
        r'最大初速度': 'vận tốc ban đầu cực đại',
        r'初速度': 'vận tốc ban đầu',
        r'最大速度': 'vận tốc cực đại',
        r'电子': 'electron',
        r'光子': 'photon',
        r'波长': 'bước sóng',
        r'频率': 'tần số',
        r'加速度': 'gia tốc',
        r'速度': 'vận tốc',
        r'位移': 'độ dịch chuyển',
        r'质量': 'khối lượng',
        r'能量': 'năng lượng',
        r'动能': 'động năng',
        r'势能': 'thế năng',
        r'功': 'công',
        r'力': 'lực',
        r'压强': 'áp suất',
        r'温度': 'nhiệt độ',
        r'电阻': 'điện trở',
        r'电流': 'dòng điện',
        r'电压': 'điện áp',
        r'磁场': 'từ trường',
        r'电场': 'điện trường',
        r'求': 'Tìm ',
        r'计算': 'Tính ',
        r'证明': 'Chứng minh ',
        r'已知': 'Cho ',
        r'设': 'Giả sử ',
        r'若': 'Nếu ',
        r'当': 'Khi ',
        r'则': 'thì ',
    }
    for cjk_k, vn_v in cjk_dict.items():
        text = re.sub(cjk_k, vn_v, text, flags=re.IGNORECASE)

    # 2. Xóa các ký tự CJK còn sót lại (Unicode block 4E00 - 9FFF, 3400 - 4DBF)
    text = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]+', '', text)
    
    # 3. Chuẩn hóa dấu câu CJK (ví dụ: ， → , | 。 → . | ： → :)
    text = text.replace('，', ', ').replace('。', '. ').replace('：', ': ').replace('？', '? ')
    
    # Dọn dẹp khoảng trắng thừa
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


def _harmonize_question_and_answer(question_text: str, correct_answer: str, detailed_solution: str = "") -> tuple[str, str, str]:
    """
    Đồng bộ hóa 100% tính tương thích giữa Đề bài (question_text) và Đáp án (correct_answer).
    Tránh trường hợp đề bài là câu hỏi đơn 1 vế nhưng đáp án lại tự bịa ra 2 vế 'a) ..., b) Chi tiết tính toán'.
    """
    q_clean = _clean_cjk_and_foreign_artifacts(str(question_text or "")).strip()
    ans_clean = _clean_cjk_and_foreign_artifacts(str(correct_answer or "")).strip()
    sol_clean = _clean_cjk_and_foreign_artifacts(str(detailed_solution or "")).strip()

    # Kiểm tra xem Đề bài có phân tách rõ ràng các ý a), b) hay không
    q_has_ab = bool(re.search(r'(?:^|\n|\s)[aA]\)\s+', q_clean) and re.search(r'(?:^|\n|\s)[bB]\)\s+', q_clean))
    q_has_12 = bool(re.search(r'(?:^|\n|\s)1\.\s+', q_clean) and re.search(r'(?:^|\n|\s)2\.\s+', q_clean))
    q_is_multistep = q_has_ab or q_has_12

    # Kiểm tra xem Đáp án có gắn nhãn a), b) không
    ans_m_a = re.search(r'^[aA]\)\s*(.+?)(?:;\s*[bB]\)\s*(.*)|\Z)', ans_clean, flags=re.DOTALL)
    
    if not q_is_multistep and ans_m_a:
        # Trường hợp Đề bài là câu hỏi đơn nhưng Đáp án bị gán nhãn a), b)
        part_a = ans_m_a.group(1).strip() if ans_m_a.group(1) else ""
        part_b = ans_m_a.group(2).strip() if ans_m_a.group(2) else ""
        
        # Nếu ý b) chỉ là câu đệm vô nghĩa như "Chi tiết tính toán", "Xem lời giải", "Xem chi tiết", "..."
        is_generic_b = not part_b or any(kw in part_b.lower() for kw in [
            "chi tiết tính toán", "xem lời giải", "lời giải chi tiết", "tính toán chi tiết",
            "xem chi tiết", "chi tiết", "xem giải", "đã giải ở trên", "như trên"
        ])
        
        if is_generic_b or not part_b:
            ans_clean = part_a
        else:
            ans_clean = f"{part_a}; {part_b}"
            
        # Gọt sạch nhãn a) ở đầu nếu có
        ans_clean = re.sub(r'^[aA]\)\s*', '', ans_clean).strip()

    elif q_is_multistep and not bool(re.search(r'^[aA]\)', ans_clean)):
        # Trường hợp Đề bài chia a), b) nhưng Đáp án chưa có tiền tố a), b)
        if ";" in ans_clean and not ans_clean.startswith("a)"):
            parts = [p.strip() for p in ans_clean.split(";", 1)]
            if len(parts) == 2 and not parts[0].startswith("a)"):
                ans_clean = f"a) {parts[0]}; b) {parts[1]}"

    # Dọn dẹp dấu chấm phẩy lửng hoặc khoảng trắng ở cuối
    ans_clean = ans_clean.rstrip(";,. ")
    return q_clean, ans_clean, sol_clean


def _load_chapter_theory_text(rag_input_dir: str, safe_chap: str, chap_num: str, chapter_title_kw: str = "") -> tuple[str, str]:
    """
    Tìm và trích xuất thông minh, toàn diện nội dung lý thuyết thực tế của chương
    trên tất cả các file giáo trình (loại bỏ triệt để mục lục, lời nói đầu và các chương khác).
    Áp dụng đồng bộ và chuẩn xác cho tất cả các môn ở cả 2 nhánh (STEM và SOCIAL).
    """
    if not os.path.exists(rag_input_dir):
        return "", ""

    all_txt_files = [f for f in os.listdir(rag_input_dir) if f.endswith(".txt") and not f.startswith("test_") and not f.endswith("loi_noi_dau.txt")]
    if not all_txt_files:
        return "", ""

    chap_idx = _parse_chap_index(chap_num or safe_chap)

    # Đánh giá và xếp hạng tất cả các file dựa trên nội dung thực tế trích xuất được
    scored_candidates = []
    for f in all_txt_files:
        full_p = os.path.join(rag_input_dir, f)
        if os.path.getsize(full_p) < 100:
            continue
        try:
            with open(full_p, "r", encoding="utf-8", errors="ignore") as fl:
                raw_txt = fl.read()
        except Exception as e:
            print(f"  [Theory Loader Error] {f}: {e}")
            continue

        # Kiểm tra khớp chính xác tên chương trong filename (ví dụ: chuong_1.txt, _chuong_1_)
        f_low = f.lower()
        fn_match = bool(re.search(rf'[\b_]chuong[_\s]*{chap_idx}[\b_.]', f_low) or re.search(rf'^chuong[_\s]*{chap_idx}\.txt$', f_low))

        raw_txt = _clean_ocr_theory_text(raw_txt)
        
        # Đếm tần suất keyword để ưu tiên file
        kw_match = False
        count_kw = 0
        if chapter_title_kw and len(chapter_title_kw) > 3:
            import unicodedata
            def remove_accents(input_str):
                nfkd_form = unicodedata.normalize('NFKD', input_str)
                return u"".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

            raw_no_accent = remove_accents(raw_txt.lower())
            kw_no_accent = remove_accents(chapter_title_kw.lower())

            count_kw = raw_no_accent.count(kw_no_accent)
            if count_kw >= 1:
                # Cụm tên chương xuất hiện nguyên văn (dù chỉ 1 lần, ví dụ ở dòng tiêu đề) -> tín hiệu mạnh
                kw_match = True
            else:
                # Cụm nguyên văn không xuất hiện lần nào — thử khớp theo TỶ LỆ TỪ thay vì đòi khớp
                # y nguyên cả cụm. Giúp bắt được trường hợp PDF diễn đạt tên chương hơi khác DB
                # (VD tiêu đề DB "Hệ phương trình tuyến tính" nhưng thân bài chỉ nhắc "hệ phương trình"
                # mà không luôn kèm "tuyến tính" mỗi lần) — đây chính là nguyên nhân khiến content-matching
                # không tự sửa được các trường hợp PDF/DB lệch số chương.
                title_words = [w for w in kw_no_accent.split() if len(w) >= 3]
                if len(title_words) >= 2:
                    matched_words = sum(1 for w in title_words if w in raw_no_accent)
                    word_ratio = matched_words / len(title_words)
                    if word_ratio >= 0.7:
                        kw_match = True
                        count_kw = matched_words

        extracted = _extract_chapter_section_from_text(raw_txt, chap_idx, is_filename_matched=fn_match, chapter_title_kw=chapter_title_kw)
        
        # Nếu extraction trả về rỗng nhưng file này match keyword siêu mạnh, thì bypass extraction
        if not extracted and kw_match and count_kw > 10:
            extracted = raw_txt
            
        ext_len = len(extracted.strip())

        # Tính điểm ưu tiên: Nội dung thực tế trích xuất được là quan trọng nhất
        score = ext_len
        if kw_match:
            score += 500000 + count_kw * 1000  # Ưu tiên cao nhất nếu match nội dung tên chương
            
        if fn_match and ext_len > 2000:
            score += 100000  # Ưu tiên cao nếu vừa khớp tên chương vừa có nội dung phong phú (>2000 ký tự)
        elif fn_match and ext_len <= 1500:
            score -= 50000   # Trừ điểm nếu tên file khớp nhưng nội dung chỉ là mục lục ngắn (<1500 ký tự)

        if ext_len > 200:
            scored_candidates.append((score, ext_len, f, extracted, full_p))

    if scored_candidates:
        scored_candidates.sort(key=lambda x: -x[0])
        best = scored_candidates[0]
        return _clean_ocr_theory_text(best[3]), best[4]

    return "", ""


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


def _get_clean_subject_display_name(subject_code: str, target_file: str = "", theory_text: str = "", course_name: str = "") -> str:
    """Tự động chuyển mã môn dạng 'course_7' hoặc 'course_27' thành tên hiển thị tiếng Việt tổng quát cho MỌI môn học."""
    # Ưu tiên 0: Nếu Spring Boot đã truyền tên thật từ DB → dùng ngay, không cần dò
    if course_name and course_name.strip():
        return course_name.strip()

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


def _clean_topic_name(topic: str, subject: str = "") -> str:
    """Làm sạch tên chủ đề bài tập (loại bỏ bullet a), b), tiền tố 'Chủ đề', cụm 'trong môn X', dấu chấm phẩy, số thứ tự rác)."""
    if not topic or not isinstance(topic, str):
        return f"Chuyên đề {subject or 'bài tập'}"

    t = topic.strip()
    # Loại bỏ tiền tố bullet như a), b), 1., 1), Ví dụ 1:, Bài toán 1:
    t = re.sub(r'^(?:[a-dA-D]\)|\d+[\.)]|Ví dụ\s*\d*[:.\-]?|Bài toán\s*\d*[:.\-]?|Bài tập\s*\d*[:.\-]?)\s*', '', t).strip()
    t = re.sub(r'^(?:Chủ đề\s*\d*[:.\-–—]\s*)', '', t, flags=re.IGNORECASE).strip()
    # Loại bỏ cụm thừa "trong môn X" / "thuộc môn X" một cách tổng quát cho mọi môn (không hardcode tên môn)
    if subject:
        sub_escaped = re.escape(subject.strip())
        t = re.sub(rf'\s*(?:trong|ở|của|thuộc)\s*(?:môn\s*)?{sub_escaped}[^,\n.!?]*', '', t, flags=re.IGNORECASE).strip()
    # Loại bỏ dấu kết thúc
    t = t.rstrip(".:,;")
    # Loại bỏ phần sau dấu chấm phẩy hoặc dòng mới
    if ';' in t:
        t = t.split(';')[0].strip()
    if '\n' in t:
        t = t.splitlines()[0].strip()
        
    if len(t) < 4 or any(bad in t.lower() for bad in ["tiền đề", "đáp án", "lời giải", "bài tập", "chủ đề bài tập", "dùng bảng chân lý để", "bảng chân trị để"]):
        return f"Chuyên đề {subject or 'bài tập'}"
    return t[0].upper() + t[1:] if t else f"Chuyên đề {subject or 'bài tập'}"



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

    # Step 0: Pre-fix LaTeX commands before stripping control chars.
    # LÝ DO QUAN TRỌNG: model thường viết LaTeX với 1 dấu \ (như con người hay viết), nhưng trong
    # JSON string 1 dấu \ đứng trước 1 chữ cái CHỈ hợp lệ nếu chữ đó là b/t/n/f/r (backspace/tab/
    # newline/formfeed/return — các escape chuẩn của JSON). Với các lệnh LaTeX BẮT ĐẦU bằng đúng các
    # chữ này mà KHÔNG có trong danh sách sửa (ví dụ "\boxed" chữ 'b', "\text"/"\tan"/"\triangle" chữ
    # 't', "\nabla"/"\nu" chữ 'n', "\forall"/"\phi" chữ 'f', "\rho" chữ 'r') — JSON parser KHÔNG báo lỗi
    # mà ÂM THẦM nuốt mất dấu \ (hiểu nhầm thành ký tự backspace/tab/...), để lại chữ cụt như "oxed",
    # "ext", "abla" — đúng lỗi vỡ LaTeX đã gặp nhiều lần suốt phiên ("\ heta", " riangle", "oxed{...").
    # Danh sách trước chỉ có ~20 lệnh, thiếu rất nhiều — mở rộng đầy đủ hơn các lệnh LaTeX toán học phổ
    # biến. Thêm (?<!\\) để không xử lý nhầm các chuỗi ĐÃ escape kép sẵn (\\theta) thành escape 4 lần.
    _LATEX_CMDS = (
        r'frac|sqrt|bar|overline|underline|hat|dot|ddot|vec|widehat|widetilde|tilde|'
        r'lim|sum|int|iint|iiint|oint|prod|coprod|bigcup|bigcap|bigvee|bigwedge|bigoplus|bigotimes|'
        r'infty|partial|nabla|hbar|ell|aleph|imath|jmath|wp|Re|Im|top|bot|emptyset|prime|backslash|'
        r'alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|lambda|mu|nu|'
        r'xi|pi|varpi|rho|varrho|sigma|varsigma|tau|upsilon|phi|varphi|chi|psi|omega|'
        r'Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega|'
        r'in|notin|subset|subseteq|supset|supseteq|cup|cap|setminus|'
        r'le|leq|ge|geq|neq|ne|approx|equiv|cong|simeq|sim|propto|asymp|doteq|'
        r'times|div|pm|mp|ast|star|circ|bullet|cdot|oplus|ominus|otimes|oslash|odot|wedge|vee|'
        r'forall|exists|nexists|angle|perp|parallel|mid|nmid|'
        r'text|boxed|mathbb|mathcal|mathrm|mathbf|mathit|mathsf|mathtt|operatorname|'
        r'left|right|big|Big|bigg|Bigg|quad|qquad|'
        r'cdots|ldots|dots|vdots|ddots|'
        r'exp|log|ln|min|max|sup|inf|det|dim|ker|deg|arg|gcd|lcm|'
        r'sin|cos|tan|cot|sec|csc|sinh|cosh|tanh|coth|arcsin|arccos|arctan|'
        r'mapsto|to|rightarrow|leftarrow|Rightarrow|Leftarrow|leftrightarrow|Leftrightarrow|'
        r'longrightarrow|longleftarrow|Longrightarrow|Longleftarrow|hookrightarrow|'
        r'dagger|ddagger|nabla|degree|'
        r'triangle|square|diamond|lozenge|sqcup|sqcap|smallsetminus|amalg|'
        r'boxplus|boxminus|boxtimes|rtimes|ltimes|surd|flat|natural|sharp'
    )
    raw = re.sub(rf'(?<!\\)\\({_LATEX_CMDS})\b', r'\\\\\1', raw)
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
    "triết học mác-lênin":         "SOCIAL",
    "triết học mác - lênin":       "SOCIAL",
    "triết học mác-lệnin":         "SOCIAL",
    "triết học":                    "SOCIAL",
    "kinh tế chính trị mác-lênin": "SOCIAL",
    "kinh tế chính trị mác - lênin": "SOCIAL",
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
    "vật lý 1 + 2 + 3":             "STEM",
    "vật lý 1":                      "STEM",
    "vật lý 2":                      "STEM",
    "vật lý 3":                      "STEM",
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
    "triết", "mác", "lênin", "chủ nghĩa", "xã hội học",
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


def _get_dynamic_stem_directive(display_subject: str, display_chapter_name: str) -> str:
    """
    Chỉ thị học thuật động tổng quát 100% cho mọi môn STEM.
    Không hardcode bất kỳ từ khóa môn học nào, buộc AI tự động thích ứng và khai thác toàn diện nội dung giáo trình được nạp.
    """
    return f"""   - NGUYÊN TẮC BIÊN SOẠN ĐỀ BÀI TỰ LUẬN ĐỊNH LƯỢNG (UNIVERSAL PROBLEM-SOLVING CONTRACT):
     * ĐẶC TẢ DỮ LIỆU ĐẦU VÀO CỤ THỂ: 100% bài tập BẮT BUỘC phải cung cấp một bộ dữ liệu, tham số, đối tượng, phương trình, ma trận, đồ thị hoặc cấu hình cụ thể dựa trên các định lý/công thức xuất hiện trong {display_chapter_name}.
     * BẢN CHẤT GIẢI QUYẾT VẤN ĐỀ: Yêu cầu sinh viên phải thực hiện tính toán, biến đổi đại số, giải phương trình, mô phỏng thuật toán từng bước hoặc chứng minh hệ quả toán học/kỹ thuật để tìm ra đáp số hoặc phương án giải quyết tối ưu.
     * TUYỆT ĐỐI CẤM CÂU HỎI LÝ THUYẾT TRÌNH BÀY SUÔNG: Cấm mọi câu hỏi thuộc lòng định nghĩa, giải thích khái niệm hoặc so sánh ưu nhược điểm trừu tượng (CẤM: 'Hãy giải thích cách hoạt động của...', 'Trình bày ưu nhược điểm của...', 'Nêu định nghĩa...').
     * PHỦ RỘNG & ĐA DẠNG NỘI DUNG CHƯƠNG:
       - Câu 1: Bắt buộc khai thác đối tượng/công thức ở PHẦN ĐẦU giáo trình.
       - Câu 2 & 3: Bắt buộc khai thác 2 chủ đề/kỹ thuật KHÁC NHAU ở PHẦN GIỮA giáo trình.
       - Câu 4: Bắt buộc khai thác bài toán tư duy/chứng minh ở PHẦN CUỐI giáo trình.
       - TUYỆT ĐỐI CẤM lặp lại cùng một công thức hay cùng một dạng bài cho nhiều câu."""


def _is_valid_exercise_data(batch_data) -> bool:
    """Kiểm tra xem dữ liệu JSON trả về có chứa danh sách bài tập/câu hỏi hợp lệ không (có question_text, question, general_solution hoặc problem)."""
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
            elif q.get("question_text") or q.get("question") or q.get("general_solution") or q.get("problem"):
                return True
        elif batch_data.get("question_text") or batch_data.get("question") or batch_data.get("general_solution") or batch_data.get("problem"):
            return True
    elif isinstance(batch_data, list):
        questions_list = batch_data

    if not questions_list:
        return False

    for item in questions_list:
        if isinstance(item, dict):
            q_text = (item.get("question_text") or item.get("question") or item.get("questionText") or 
                      item.get("raw_content") or item.get("general_solution") or item.get("statement") or item.get("problem"))
            if q_text and len(str(q_text).strip()) > 10 and not _is_placeholder(str(q_text)):
                return True
        elif isinstance(item, str) and len(item.strip()) > 15:
            return True
            
    return False


def _is_duplicate_question(new_q, existing_questions: list, subject_type: str = "STEM") -> bool:
    """Kiểm tra câu hỏi mới có bị trùng lặp nội dung thực sự với danh sách đã có hay không
    (token overlap sau khi loại stopword chung, hoặc trùng cấu trúc toán học).
    Ngưỡng nới rộng hơn cho STEM (từ vựng chuyên ngành hẹp của 1 chương tự nhiên lặp lại nhiều)."""
    if isinstance(new_q, dict):
        new_q = new_q.get("question_text") or new_q.get("question") or new_q.get("questionText") or ""
    if not new_q or not isinstance(new_q, str):
        return False
    q1_clean = re.sub(r'[\s\W]+', '', new_q.lower())
    if len(q1_clean) < 10:
        return False

    dup_threshold = 0.75 if subject_type == "STEM" else 0.60
    math_dup_threshold = 0.50 if subject_type == "STEM" else 0.35

    words1 = _content_words(new_q.lower())
    if not words1:
        return False

    # Trích xuất các biểu thức toán / tập hợp / hàm số đặc trưng (ví dụ: {1, 2, 3}, f(x)=...)
    math1 = set(re.findall(r'\{[^}]+\}|\$[^\$]+\$|[a-zA-Z]\([a-zA-Z0-9,\s]+\)\s*=', new_q))

    for existing in existing_questions:
        if isinstance(existing, dict):
            existing = existing.get("question_text") or existing.get("question") or existing.get("questionText") or ""
        if not existing or not isinstance(existing, str):
            continue
        q2_clean = re.sub(r'[\s\W]+', '', existing.lower())
        if q1_clean == q2_clean:
            return True
        words2 = _content_words(existing.lower())
        if not words2:
            continue
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        jaccard = len(intersection) / len(union) if union else 0
        if jaccard > dup_threshold:
            return True
        # Nếu trùng nhau về tập hợp / biểu thức toán đặc trưng (ví dụ: cùng dùng tập {1, 2, 3})
        if math1:
            math2 = set(re.findall(r'\{[^}]+\}|\$[^\$]+\$|[a-zA-Z]\([a-zA-Z0-9,\s]+\)\s*=', existing))
            if math1.intersection(math2) and jaccard > math_dup_threshold:
                return True
    return False


def _validate_in_chapter_grounding(question_text: str, topic: str, theory_content: str) -> tuple[bool, str]:
    """
    Kiểm tra chống ảo giác kiến thức ngoài chương (Dynamic Zero-Hallucination Grounding Validator).
    1. Trích xuất tên Định lý / Bổ đề / Nhà khoa học / Khái niệm chuyên biệt xuất hiện trong đề bài.
    2. Bắt buộc khái niệm đó phải có mặt trong văn bản giáo trình của chương (theory_content).
    """
    if not theory_content:
        return True, "OK"

    full_text = f"{topic} {question_text}"
    q_low = full_text.lower()
    th_low = theory_content.lower()

    # 1. Trích xuất các tên riêng, định lý, bổ đề, nhà khoa học (Zorn, Banach, Euler, Hamilton, Bernoulli, Keynes, Fermat...)
    # Lưu ý: "(?:phép\s+)?biến đổi" thay vì bắt buộc "phép biến đổi" — cách nói thường gặp
    # "biến đổi Laplace/Fourier/Z..." (không kèm "phép") trước đây bị bỏ sót hoàn toàn, khiến
    # named-entity check không bắt được các phép biến đổi bịa ngoài chương (VD "biến đổi Laplace"
    # lẫn vào môn Kỹ thuật số) vì regex đòi khớp y nguyên cụm "phép biến đổi".
    named_entities = re.findall(r'(?:định lý|định luật|bổ đề|tiên đề|nguyên lý|quy tắc|thuật toán|bất đẳng thức|không gian|phương trình|chuỗi|(?:phép\s+)?biến đổi|công thức|học thuyết|mô hình)\s+([A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸ][a-zA-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸ0-9\-]*)', full_text)
    # Tên riêng dạng "A-B" ghép 2 người (VD "Rank-Nullity", "Cauchy-Binet", "Cayley-Hamilton",
    # "Gram-Schmidt") — giáo trình đơn giản hóa thường KHÔNG nêu đúng tên riêng này dù khái niệm nền
    # (ma trận/định thức/không gian vector) vẫn thuộc đúng chương. Đòi khớp chính xác tên riêng gây từ
    # chối oan (đo thực tế trên log sản xuất: "Rank-Nullity", "Cauchy-Binet" bị chặn dù đúng chủ đề đại
    # số tuyến tính của chương). Với dạng tên ghép này, chỉ cần lĩnh vực chung đã có mặt trong giáo
    # trình là đủ, không đòi khớp đúng tên riêng.
    _eponym_re = re.compile(r'^[A-ZÀ-Ỹ][a-zà-ỹ]*-[A-ZÀ-Ỹ][a-zà-ỹ]*$')
    _linalg_anchor_kw = ["ma trận", "ma tran", "vector", "vec-tơ", "vec to", "tuyến tính", "tuyen tinh", "định thức", "dinh thuc", "hạng của ma trận", "hang cua ma tran"]
    for entity in named_entities:
        ent_clean = entity.strip().lower()
        if len(ent_clean) >= 3 and ent_clean not in ["toán", "học", "khoa", "tự", "nhiên", "kỹ", "thuật", "cơ", "bản", "chung", "này", "trên", "đại", "học"]:
            if ent_clean not in th_low:
                if _eponym_re.match(entity.strip()) and any(kw in th_low for kw in _linalg_anchor_kw):
                    continue
                return False, f"Ảo giác kiến thức ngoài giáo trình: Khái niệm/Định lý '{entity}' không có trong giáo trình chương này."

    # 2. Danh sách kiểm tra chéo các mảng kiến thức lớn
    domain_checks = [
        (["zorn", "tiên đề chọn", "axiom of choice", "banach"], ["zorn", "banach", "tiên đề chọn"]),
        (["đồ thị", "euler", "hamilton", "bậc của đỉnh", "cây khung", "dijkstra", "đồ thị phẳng"], ["đồ thị", "graph", "euler", "hamilton"]),
        (["chuỗi số", "chuỗi đan dấu", "chuỗi lũy thừa", "chuỗi fourier", "d'alembert", "cauchy"], ["chuỗi", "chuoi"]),
        (["tích phân bội", "tích phân 2 lớp", "tích phân 3 lớp", "tích phân mặt", "tích phân đường", "green", "stokes", "gauss"], ["tích phân", "tich phan"]),
        (["ma trận nghịch đảo", "định thức", "không gian vector", "trị riêng", "vector riêng", "chéo hóa"], ["ma trận", "ma tran", "vector", "tuyến tính", "tuyen tinh"]),
        (["bảng chân trị", "mệnh đề tương đương", "hội", "tuyển", "phủ định", "lượng từ", "vị từ"], ["mệnh đề", "menh de", "logic", "tập hợp", "tap hop"]),
        (["đạo hàm", "hàm số liên tục", "tính liên tục", "tính khả vi", "khảo sát hàm số", "cực trị của hàm số", "tiệm cận", r"\lim", "giới hạn của dãy số"], ["đạo hàm", "dao ham", "tính liên tục", "tinh lien tuc", "khả vi", "kha vi", "vi phân", "vi phan", "tích phân", "tich phan", "tiệm cận", "tiem can", "chuỗi số", "chuoi so"]),
        (["vận tốc v(t)", "gia tốc", "định luật newton", "động năng", "thế năng", "nhiệt dung", "điện trường", "từ trường", "cảm ứng điện từ"], ["vật lý", "chuyển động", "vận tốc", "gia tốc", "lực", "năng lượng", "điện", "từ", "sóng", "nhiệt"]),
        (["duy vật biện chứng", "duy vật lịch sử", "bản thể luận", "nhận thức luận", "vật chất", "ý thức"], ["triết", "triet", "vật chất", "vat chat", "ý thức", "y thuc", "duy vật", "duy vat"]),
        (["giá trị thặng dư", "tư bản", "hàng hóa", "tiền tệ", "tích lũy tư bản"], ["thặng dư", "thang du", "tư bản", "tu ban", "hàng hóa", "hang hoa"]),
    ]

    for question_kws, required_th_kws in domain_checks:
        if any(kw in q_low for kw in question_kws):
            if not any(req_kw in th_low for req_kw in required_th_kws):
                matched_kw = next(kw for kw in question_kws if kw in q_low)
                return False, f"Ảo giác lẫn chương: Câu hỏi chứa khái niệm '{matched_kw}' không có trong giáo trình chương này."

    return True, "OK"


# Stopword HẸP dành riêng cho trích cụm thuật ngữ kỹ thuật — chỉ gồm từ nối/chức năng ngữ pháp thuần túy.
# KHÔNG được dùng chung với _GENERIC_QUESTION_STOPWORDS (bộ đó rộng hơn, phục vụ chống trùng lặp câu hỏi)
# vì các âm tiết như "tính", "trình", "giải", "toán", "số" tuy generic trong _GENERIC_QUESTION_STOPWORDS
# lại là thành phần bắt buộc của rất nhiều thuật ngữ kỹ thuật thật ("phương TRÌNH", "tuyến TÍNH",
# "GIẢI pháp", "hàm SỐ") — nếu lọc mất sẽ phá hỏng chính cụm từ cần kiểm tra.
_PHRASE_EXTRACTION_STOPWORDS = {
    "cho", "la", "va", "cua", "cac", "mot", "nhung", "hay", "khi", "de", "trong", "voi",
    "nay", "do", "duoc", "co", "khong", "neu", "thi", "tu", "den", "moi", "gom", "day",
    "sao", "nen", "hai", "ba", "bon", "nam", "sau", "bay", "tam", "chin", "muoi", "theo",
    "ma", "ban", "bang", "gi", "nhu", "duoi", "tren", "giua", "sao", "the", "hoac", "ra", "vao",
}


def _extract_technical_phrases(text: str) -> set:
    """Trích các TỪ NỘI DUNG (đã loại bỏ công thức LaTeX, số, từ nối ngữ pháp thuần túy) từ văn bản —
    dùng làm 'dấu vân tay' thuật ngữ kỹ thuật để đối chiếu tổng quát với giáo trình, không phụ thuộc
    danh sách từ khóa cấm cố định theo từng cặp môn học.

    LƯU Ý: trước đây hàm này ghép CẶP 2 ÂM TIẾT LIÊN TIẾP làm "cụm từ" (kiểu bigram tiếng Anh) — nhưng
    tiếng Việt là ngôn ngữ đơn âm tiết cách nhau bằng dấu cách, nên cách ghép này tạo ra rất nhiều cặp
    RÁC khi 2 âm tiết liền kề thuộc 2 từ khác nhau (VD: "tập hợp đỉnh" bị tách thành "tập hợp" (đúng)
    VÀ "hợp đỉnh" (rác, ghép lố sang từ khác) — không có bộ phân đoạn từ tiếng Việt chuẩn, không có cách
    nào phân biệt cặp thật/rác một cách đáng tin cậy). Hậu quả đo được thực tế: ~87% "cụm từ" của 1 câu
    hỏi ĐÚNG chủ đề bị coi là "không khớp giáo trình" chỉ vì lẫn cặp rác, khiến câu hỏi đúng bị từ chối
    oan. Đổi sang so khớp theo TỪNG TỪ NỘI DUNG đơn lẻ (loại từ nối/từ ngắn) — không hoàn hảo bằng cụm
    từ thật nhưng miễn nhiễm với lỗi ghép rác, và test thực tế cho tỷ lệ từ chối oan giảm còn ~11%.
    """
    if not text:
        return set()
    # Loại bỏ công thức toán ($...$, \(...\), \[...\]) để không lẫn biến số/ký hiệu vào cụm từ
    clean = re.sub(r'\$[^$]+\$|\\\([^)]+\\\)|\\\[[^\]]+\\\]', ' ', text)
    words = re.findall(r'[^\W\d_]+', clean.lower(), flags=re.UNICODE)

    import unicodedata as _ud
    def no_acc(s):
        return "".join(c for c in _ud.normalize('NFKD', s) if not _ud.combining(c)).replace('đ', 'd').replace('Đ', 'D')

    phrases = set()
    for w in words:
        if len(w) < 3 or no_acc(w) in _PHRASE_EXTRACTION_STOPWORDS:
            continue
        phrases.add(w)
    return phrases


def _validate_dynamic_grounding(question_text: str, topic: str, theory_content: str) -> tuple[bool, str]:
    """
    Kiểm tra chống ảo giác TỔNG QUÁT — không dựa vào danh sách từ khóa cấm cố định theo từng cặp môn
    học (vốn không bao giờ theo kịp mọi trường hợp lẫn chéo khả dĩ giữa 24 môn). Nguyên lý: trích các
    từ nội dung trong câu hỏi, đối chiếu xem chúng có thực sự xuất hiện ở đâu đó trong giáo trình
    chương đã nạp hay không. Nếu phần lớn từ nội dung hoàn toàn vô căn cứ trong giáo trình, nhiều khả
    năng đó là kiến thức bịa/lạc chương — bất kể thuộc lĩnh vực gì (Giải tích, Vật lý, CSDL...), không
    cần liệt kê trước từng lĩnh vực có thể bị lẫn.
    Bổ sung cho _validate_in_chapter_grounding (vẫn giữ nguyên, chỉ bắt tên riêng/định lý cụ thể),
    không thay thế các bộ lọc theo từ khóa hiện có.
    """
    if not theory_content or len(theory_content.strip()) < 200:
        return True, "OK"
    if not question_text or len(question_text.strip()) < 15:
        return True, "OK"

    full_text = f"{topic or ''} {question_text}"
    q_words = _extract_technical_phrases(full_text)
    if len(q_words) < 4:
        # Câu hỏi quá ngắn/ít từ nội dung riêng biệt -> không đủ căn cứ để kết luận, bỏ qua để tránh false positive
        return True, "OK"

    import unicodedata as _ud
    def no_acc(s):
        return "".join(c for c in _ud.normalize('NFKD', s) if not _ud.combining(c)).replace('đ', 'd').replace('Đ', 'D')

    th_no_acc = no_acc(theory_content.lower())

    ungrounded = [w for w in q_words if no_acc(w) not in th_no_acc]
    ungrounded_ratio = len(ungrounded) / len(q_words)

    # Chỉ báo lỗi khi PHẦN LỚN (>=80%) từ nội dung đều vô căn cứ — tránh chặn nhầm câu hỏi diễn đạt
    # khác giáo trình nhưng vẫn đúng chủ đề (chỉ cần vài từ khớp là đủ bằng chứng đã bám giáo trình).
    if ungrounded_ratio >= 0.8:
        sample = ", ".join(f"'{w}'" for w in ungrounded[:3])
        return False, f"Ảo giác kiến thức ngoài giáo trình (kiểm tra tổng quát): các từ {sample} hoàn toàn không xuất hiện trong nội dung chương đã nạp."

    return True, "OK"


def _validate_subject_discipline_integrity(question_text: str, topic: str, subject_name: str) -> tuple[bool, str]:
    """
    Kiểm định nghiêm ngặt tính toàn vẹn chuyên ngành cho TOÀN BỘ 24 MÔN HỌC và các môn kỹ thuật mới.
    Đảm bảo 100% không để lọt bài toán của môn học khác vào đề.
    """
    if not question_text or not subject_name:
        return True, "OK"
        
    full_text = f"{topic} {question_text}".lower()
    import unicodedata
    sub_norm = "".join(c for c in unicodedata.normalize('NFKD', subject_name.lower()) if not unicodedata.combining(c)).replace('đ', 'd').replace('Đ', 'D')
    
    # Từ khóa Vật lý — dùng chung cho các môn TOÁN THUẦN (Giải tích, Đại số, Toán rời rạc): model đôi
    # khi "an toàn hoá" bằng cách sinh bài toán Vật lý phổ thông chung chung (rơi tự do, ma sát...) khi
    # không nghĩ ra được nội dung bám sát chuyên đề toán học đặc thù — phát hiện được từ thực tế test.
    _PHYSICS_KEYWORDS = [
        "khối lượng", "khoi luong", "vận tốc", "van toc", "gia tốc", "gia toc", "ma sát", "ma sat",
        "trọng lực", "trong luc", "rơi tự do", "roi tu do", "định luật bảo toàn năng lượng",
        "dinh luat bao toan nang luong", "định luật newton", "dinh luat newton", "động năng", "dong nang",
        "thế năng", "the nang", "lực tác dụng", "luc tac dung",
    ]

    # Đại số phổ thông (giải phương trình bậc hai/ba, định lý Vi-ét...) là dấu hiệu model "an toàn hoá"
    # bằng kiến thức phổ thông chung chung khi cạn ý tưởng bám sát chuyên đề đặc thù của môn — hợp lệ
    # CHỈ với môn Đại số, còn với MỌI môn khác (Giải tích, Toán rời rạc, Kỹ thuật số, Vật lý, Xác suất...)
    # đều là lạc môn. Phát hiện qua thực tế test: cùng 1 kiểu lạc đề lặp lại ở nhiều môn khác nhau.
    if "dai so" not in sub_norm:
        generic_algebra_kw = [
            "phương trình bậc hai", "phuong trinh bac hai", "phương trình bậc ba", "phuong trinh bac ba",
            "định lý vi-et", "dinh ly vi-et", "vi-ét", "công thức nghiệm", "cong thuc nghiem",
            "nghiệm của phương trình", "nghiem cua phuong trinh", "đa thức bậc hai", "da thuc bac hai",
        ]
        for kw in generic_algebra_kw:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Đại số phổ thông ('{kw}') trong môn {subject_name} (không phải Đại số)."

    # 1. MÔN TOÁN RỜI RẠC (Toán rời rạc 1, Toán rời rạc 2)
    if "roi rac" in sub_norm:
        prohibited = [
            "đạo hàm", "dao ham", "tính liên tục", "hàm số liên tục", "tính khả vi", "kha vi", 
            "vi phân", "vi phan", "tích phân", "tich phan", "tiệm cận", "tiem can", "cực trị", "cuc tri",
            "đồng biến", "nghịch biến", "đơn điệu tăng", "đơn điệu giảm", "khoảng đồng biến", "khoảng nghịch biến",
            "hàm số mũ", "hàm số logarit", "lũy thừa và logarit", "hàm số lũy thừa",
            "đồ thị hàm số", "vẽ đồ thị của hàm số", "hệ thống động lực", "phương trình vi phân",
            "jacobian", "ma trận jacobian", "điểm cực đại", "điểm cực tiểu", r"\lim", "lim_{", "f'(", "f''(", "e^x", r"\ln(", r"\log(",
            "select * from", "primary key", "foreign key", "deadlock cpu", "vlsm"
        ] + _PHYSICS_KEYWORDS
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Giải tích/CSDL/Vật lý ('{kw}') trong môn Toán rời rạc."

    # 2. MÔN GIẢI TÍCH (Giải tích 1, Giải tích 2)
    if "giai tich" in sub_norm:
        prohibited = [
            "bảng chân trị", "bang chan tri", "xâu bit", "xau bit", "bìa karnaugh", "karnaugh", "bộ đếm", "flip-flop",
            "chu trình euler", "dijkstra", "sql", "select *", "tiến trình cpu", "mô hình osi", "chia mạng con", "subnet"
        ] + _PHYSICS_KEYWORDS
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Rời rạc/Mạch số/Mạng/Vật lý ('{kw}') trong môn Giải tích."

    # 3. MÔN ĐẠI SỐ (Đại số, Đại số tuyến tính)
    if "dai so" in sub_norm:
        prohibited = [
            "đạo hàm", "dao ham", "tính liên tục", "tích phân", "tich phan", r"\lim", "lim_{", "f'(",
            "bảng chân trị", "bìa karnaugh", "sql", "select *", "tiến trình cpu", "deadlock"
        ] + _PHYSICS_KEYWORDS
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Giải tích/Mạch số/Vật lý ('{kw}') trong môn Đại số."

    # 4. MÔN VẬT LÝ (Vật lý 1 + 2 + 3)
    if "vat ly" in sub_norm:
        prohibited = [
            "bảng chân trị", "bìa karnaugh", "sql", "tiến trình cpu", "mô hình osi", "mạng con ip", "bộ nhớ cache", 
            "deadlock", "đại số quan hệ", "use case", "scrum", "agile", "cây quyết định id3"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức CNTT/Mạch số ('{kw}') trong môn Vật lý."

    # 5. MÔN XÁC SUẤT THỐNG KÊ
    if "xac suat" in sub_norm or "thong ke" in sub_norm:
        prohibited = [
            "ma trận chuyển vị", "ma trận nghịch đảo", "định thức det", "đại số quan hệ", "select * from", 
            "tiến trình cpu", "deadlock", "bìa karnaugh", "mô hình osi", "subnet mask"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức CSDL/Mạng/Đại số thuần túy ('{kw}') trong môn Xác suất thống kê."

    # 6. MÔN KỸ THUẬT SỐ & ĐIỆN TỬ SỐ
    if "ky thuat so" in sub_norm or "dien tu so" in sub_norm:
        prohibited = [
            "đạo hàm", "tích phân", "nguyên hàm", r"\lim", "tính liên tục", "sql", "select *", "tiến trình cpu",
            "deadlock", "mô hình osi", "subnet mask", "đại số quan hệ", "use case", "triết học",
            # Đại số phổ thông (đa thức, nghiệm phương trình) — phát hiện model từng lẫn câu "chứng minh
            # đa thức bậc hai ax^2+bx+c = a(x-p)(x-q)" vào đề Kỹ thuật số, không liên quan mạch logic.
            "đa thức bậc hai", "phương trình bậc hai", "nghiệm của phương trình", "định lý vi-et", "vi-ét",
        ] + _PHYSICS_KEYWORDS
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Giải tích/CSDL/Mạng/Đại số/Vật lý ('{kw}') trong môn Kỹ thuật số/Điện tử số."

    # 7. MÔN XỬ LÝ TÍN HIỆU SỐ (DSP)
    if "tin hieu" in sub_norm or "dsp" in sub_norm:
        prohibited = [
            "sql", "select *", "tiến trình cpu", "deadlock", "mô hình osi", "subnet mask", "đại số quan hệ", 
            "use case", "triết học", "duy vật", "tư bản", "thặng dư"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức CSDL/Xã hội/Mạng ('{kw}') trong môn Xử lý tín hiệu số."

    # 8. MÔN LÝ THUYẾT THÔNG TIN
    if "ly thuyet thong tin" in sub_norm or ("thong tin" in sub_norm and "an toan" not in sub_norm and "he thong" not in sub_norm):
        prohibited = [
            "sql", "select * from", "tiến trình cpu", "deadlock", "bìa karnaugh", "triết học", "duy vật", 
            "tư bản", "đạo hàm riêng", "tích phân bội"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức CSDL/Giải tích 2 ('{kw}') trong môn Lý thuyết thông tin."

    # 9. MÔN KIẾN TRÚC MÁY TÍNH
    if "kien truc may tinh" in sub_norm or "kien truc" in sub_norm:
        prohibited = [
            "đạo hàm", "tích phân", "sql", "select * from", "đại số quan hệ", "triết học", "duy vật", 
            "subnet mask", "chia mạng con", "định tuyến dijkstra", "use case", "scrum"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Giải tích/CSDL/Mạng ('{kw}') trong môn Kiến trúc máy tính."

    # 10. MÔN HỆ ĐIỀU HÀNH
    if "he dieu hanh" in sub_norm:
        prohibited = [
            "đạo hàm", "tích phân", "ma trận nghịch đảo", "định thức det", "đại số quan hệ", "select * from", 
            "bìa karnaugh", "flip-flop", "mô hình osi", "subnet mask", "triết học"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Giải tích/CSDL/Mạch số ('{kw}') trong môn Hệ điều hành."

    # 11. MÔN MẠNG MÁY TÍNH
    if "mang may tinh" in sub_norm or "mang" in sub_norm:
        prohibited = [
            "đạo hàm", "tích phân", "ma trận nghịch đảo", "định thức det", "đại số quan hệ", "select * from", 
            "bìa karnaugh", "flip-flop", "deadlock cpu", "scheduling cpu", "sjf", "rr", "triết học"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Giải tích/CSDL/Hệ điều hành ('{kw}') trong môn Mạng máy tính."

    # 12. MÔN AN TOÀN VÀ BẢO MẬT HỆ THỐNG THÔNG TIN
    if any(k in sub_norm for k in ["an toan", "bao mat"]):
        prohibited = [
            "flip-flop", "bìa karnaugh", "tích phân bội", "đạo hàm riêng", "tiến trình cpu scheduling", 
            "deadlock banker", "chia mạng con vlsm", "triết học"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Mạch số/Giải tích ('{kw}') trong môn An toàn và bảo mật thông tin."

    # 13. MÔN CƠ SỞ DỮ LIỆU & HỆ QUẢN TRỊ CSDL
    if any(k in sub_norm for k in ["co so du lieu", "csdl"]):
        prohibited = [
            "đạo hàm", "tích phân", "ma trận nghịch đảo", "định luật newton", "điện trường", "từ trường", 
            "tiến trình cpu", "lập lịch cpu", "scheduling", "deadlock banker", "bìa karnaugh", "flip-flop", 
            "chia mạng con", "subnet mask", "mô hình osi", "triết học"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Giải tích/Vật lý/HĐH/Mạng ('{kw}') trong môn Cơ sở dữ liệu."

    # 14. MÔN NHẬP MÔN CÔNG NGHỆ PHẦN MỀM
    if any(k in sub_norm for k in ["cong nghe phan mem", "phan mem"]):
        prohibited = [
            "tích phân", "đạo hàm", "ma trận nghịch đảo", "mạch logic", "flip-flop", "bìa karnaugh", 
            "chia mạng con", "subnet mask", "định tuyến", "triết học"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Giải tích/Mạch số/Mạng ('{kw}') trong môn Công nghệ phần mềm."

    # 15. MÔN NHẬP MÔN TRÍ TUỆ NHÂN TẠO
    # Lưu ý: KHÔNG dùng trigger "ai" trần trụi vì nó là substring của "giAI tích", "đAI số", "đAI cương"...
    # gây dính oan các môn Giải tích/Đại số/Pháp luật đại cương vào bộ lọc của môn AI.
    if "tri tue nhan tao" in sub_norm:
        prohibited = [
            "flip-flop", "bìa karnaugh", "mạch tổ hợp", "chia mạng con", "subnet mask", "bảng định tuyến rip", 
            "tiến trình cpu scheduling", "đại số quan hệ", "triết học"
        ]
        for kw in prohibited:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện kiến thức Mạch số/Mạng/CSDL ('{kw}') trong môn Trí tuệ nhân tạo."

    # 16. MÔN KHOA HỌC XÃ HỘI (Triết học, Kinh tế chính trị, CNXHKH, Tư tưởng HCM, Pháp luật)
    social_subjs = ["triet hoc", "kinh te chinh tri", "xa hoi khoa hoc", "ho chi minh", "phap luat"]
    known_subject_triggers = [
        "roi rac", "giai tich", "dai so", "vat ly", "xac suat", "thong ke",
        "ky thuat so", "dien tu so", "tin hieu", "dsp", "ly thuyet thong tin", "thong tin",
        "kien truc", "he dieu hanh", "mang", "an toan", "bao mat",
        "co so du lieu", "csdl", "cong nghe phan mem", "phan mem", "tri tue nhan tao",
    ] + social_subjs
    if any(s in sub_norm for s in social_subjs):
        stem_kws = [r"\frac", r"\sqrt", r"\int", r"\lim", r"\sum", "đạo hàm", "tích phân", "ma trận", "vector", "ohm", "volt", "sql", "select *", "xâu bit", "flip-flop", "karnaugh", "subnet"]
        for kw in stem_kws:
            if kw in full_text:
                return False, f"Lẫn chéo môn: Phát hiện công thức STEM ('{kw}') trong môn Khoa học Xã hội."

    # 17. FALLBACK TỔNG QUÁT cho MỌI MÔN KHÔNG NẰM TRONG 16 MÔN LIỆT KÊ CỨNG Ở TRÊN
    # (môn mới thêm sau này sẽ không bị "mù" hoàn toàn trước lỗi lẫn chéo môn)
    if not any(trig in sub_norm for trig in known_subject_triggers):
        branch = _classify_subject_type(subject_name)
        if branch == "SOCIAL":
            stem_kws = [r"\frac", r"\sqrt", r"\int", r"\lim", r"\sum", "đạo hàm", "tích phân", "ma trận nghịch đảo",
                        "sql", "select *", "flip-flop", "karnaugh", "subnet"]
            for kw in stem_kws:
                if kw in full_text:
                    return False, f"Lẫn chéo môn: Phát hiện công thức STEM ('{kw}') trong môn {subject_name} (nhánh SOCIAL)."
        else:
            social_kws = ["triết học", "duy vật biện chứng", "tư bản", "giá trị thặng dư", "tư tưởng hồ chí minh"]
            for kw in social_kws:
                if kw in full_text:
                    return False, f"Lẫn chéo môn: Phát hiện kiến thức Xã hội/Triết học ('{kw}') trong môn {subject_name} (nhánh STEM)."

    return True, "OK"


def _audit_academic_rigor(question_text: str, topic: str, difficulty: str, bloom_level: str, subject_type: str = "STEM") -> tuple[bool, str]:
    """
    Thẩm định tính học thuật và chống thoái hóa thành toán cấp 2 sơ đẳng.
    Phát hiện các câu toán quá tầm thường (như f(x) = 2x + 1, tính f(3)) bị gán nhãn HARD/MEDIUM.
    """
    q_low = question_text.lower()
    top_low = topic.lower()

    # 1. Bắt bài toán hàm số tuyến tính cấp 2 một biến f(x) = ax + b tính f(k) hoặc tìm x để f(x) = c
    if re.search(r'f\s*\(\s*x\s*\)\s*=\s*\d*x\s*[\+\-]\s*\d+', q_low) and any(kw in q_low for kw in ["tính f(", "tìm x để f("]):
        if difficulty in ["Hard", "Medium", "HARD", "MEDIUM"] or bloom_level in ["Evaluating", "Creating", "Applying", "EVALUATING", "CREATING", "APPLYING"]:
            return False, "Câu hỏi là toán đại số sơ cấp lớp 7 (f(x) = ax + b), không đạt chuẩn Đại học."

    # 2. Bắt bài toán tìm giao 2 tập số đếm được quá đơn giản ({1, 2, 3} và {2, ...}) bị gán Hard
    if re.search(r'\{\s*1\s*,\s*2\s*,\s*3\s*\}', q_low) and any(w in q_low for w in ["giao", "hợp", "tập hợp"]) and difficulty in ["Hard", "HARD"]:
        return False, "Bài toán tìm giao tập số sơ đẳng không đủ chiều sâu cho mức Hard."

    # 3. Bắt bài toán cộng trừ ma trận 2x2 cơ bản bị gán nhãn Hard
    if "tính tổng của a và b" in q_low and "begin{pmatrix}" in q_low and difficulty in ["Hard", "HARD"]:
        return False, "Cộng ma trận đơn giản không đủ độ sâu cho mức Hard."

    # 4. Bắt câu hỏi lý thuyết trình bày vẹt / không có tính toán trong STEM
    if subject_type == "STEM":
        passive_essay_kws = [
            "cho biết khái niệm", "nêu khái niệm", "nêu định nghĩa", "định nghĩa là gì",
            "hãy giải thích cách hoạt động", "giải thích cách hoạt động", "trình bày cách hoạt động",
            "so sánh hiệu quả của", "so sánh ưu nhược điểm", "nêu ưu điểm và nhược điểm",
            "so sánh giữa", "nêu ý nghĩa của thuật toán", "trình bày khái niệm", "trình bày các bước"
        ]
        if any(q_low.startswith(kw) or f" {kw}" in q_low for kw in passive_essay_kws):
            return False, "Câu hỏi là lý thuyết trình bày/hỏi vẹt, không đạt chuẩn bài toán định lượng STEM."
    else:
        # Nhánh SOCIAL: Chỉ cấm các câu hỏi vẹt định nghĩa quá đơn giản
        passive_essay_kws = [
            "cho biết khái niệm", "nêu khái niệm", "nêu định nghĩa", "định nghĩa là gì"
        ]
        if any(q_low.startswith(kw) or f" {kw}" in q_low for kw in passive_essay_kws):
            return False, "Câu hỏi là lý thuyết hỏi vẹt định nghĩa, không đủ chiều sâu phân tích cho bậc Đại học."

    return True, "OK"


def _generate_hard_exercise_with_deepseek(subject: str, chapter: str, theory_text: str, subject_type: str = "STEM", avoid_topics: list = None) -> dict:
    """
    Sinh RIÊNG 1 câu Hard bằng DeepSeek-R1 (model suy luận, tận dụng thế mạnh chain-of-thought cho
    bài toán kết hợp nhiều bước/chứng minh — đúng loại nội dung Qwen 14B hay làm hời hợt).
    Trả về dict câu hỏi nếu thành công, hoặc None nếu có bất kỳ sự cố gì (model lỗi, JSON không
    parse được, nội dung rỗng...) — gọi nơi khác PHẢI coi None là tín hiệu quay lại luồng Qwen cũ,
    không được để lỗi ở đây làm hỏng toàn bộ luồng sinh bài.
    """
    try:
        short_s = _generate_short_subject_code(subject)
        m_num = re.search(r'\d+', chapter)
        c_num = m_num.group(0) if m_num else "1"
        balanced_theory = _prepare_balanced_theory_context(theory_text, max_chars=6000)

        avoid_block = ""
        if avoid_topics:
            uniq_topics = list(dict.fromkeys([t for t in avoid_topics if t and len(str(t).strip()) > 3]))[:6]
            if uniq_topics:
                avoid_block = (
                    "\n⚠️ CÁC Ý TƯỞNG ĐÃ DÙNG (CẤM LẶP LẠI): " + "; ".join(uniq_topics) + "\n"
                )

        if subject_type == "SOCIAL":
            hard_spec = (
                "BÀI TẬP TƯ DUY PHẢN BIỆN CAO CẤP: phải giải phẫu một mâu thuẫn biện chứng hoặc phản biện "
                "một nhận định phiến diện, kết hợp ÍT NHẤT 2 nguyên lý/quy luật khác nhau trong giáo trình. "
                "TUYỆT ĐỐI CẤM chỉ giải thích 1 khái niệm đơn lẻ."
            )
        else:
            hard_spec = (
                "BÀI TOÁN MỨC HARD THẬT SỰ: BẮT BUỘC thoả ít nhất 1 trong các tiêu chí sau — "
                "(a) kết hợp ÍT NHẤT 2 định lý/công thức/kỹ thuật khác nhau trong 1 bài, "
                "(b) yêu cầu CHỨNG MINH một tính chất/hệ quả tổng quát (không chỉ ra 1 con số), "
                "(c) yêu cầu CHỨNG MINH TÍNH TƯƠNG ĐƯƠNG giữa 2 cách biểu diễn khác nhau, "
                "(d) bài toán TỐI ƯU HOÁ hoặc BIỆN LUẬN theo tham số. "
                "TUYỆT ĐỐI CẤM bài chỉ áp dụng 1 công thức đơn lẻ rồi thay số tính ra kết quả — đó là mức Medium, không phải Hard."
            )

        # ─── BƯỚC 1: DeepSeek-R1 suy luận TỰ DO, KHÔNG ép JSON (đúng sở trường model suy luận) ───
        # Thực nghiệm cho thấy R1 (bản 14B qua Ollama) không kiên định tuân theo JSON sau <think> dài
        # dù nhắc nhở kiểu gì — nên KHÔNG bắt nó định dạng, chỉ để nó viết lời giải tự nhiên.
        draft_prompt = f"""Bạn là Giáo sư Đại học chuyên ngành biên soạn đề thi chính quy môn {subject}, đang ra đề mức KHÓ NHẤT (Hard) cho Chương {c_num} ({chapter}).

NỘI DUNG GIÁO TRÌNH (chỉ được dùng đúng kiến thức trong đoạn này, cấm bịa thêm khái niệm ngoài chương):
{balanced_theory}
{avoid_block}
YÊU CẦU:
1. {hard_spec}
2. Viết 100% bằng tiếng Việt chuẩn mực (đề bài, lời giải). Giữ nguyên công thức toán/LaTeX nếu có ($...$).
3. TUYỆT ĐỐI CẤM viết code lập trình (C++, Python, pseudocode hay bất kỳ ngôn ngữ lập trình nào) dù chương học có liên quan đến thuật toán/cấu trúc dữ liệu. Nếu đề bài cần trình bày thuật toán, BẮT BUỘC diễn giải bằng lời văn và ký hiệu toán học, liệt kê từng bước bằng danh sách đánh số (1., 2., 3.,...) — không được viết dưới dạng code block.
4. Trình bày tự nhiên theo cấu trúc:
ĐỀ BÀI: <nội dung đề bài đầy đủ>
LỜI GIẢI CHI TIẾT: <lời giải/chứng minh từng bước>
ĐÁP SỐ: <kết luận cuối cùng>
TÊN CHUYÊN ĐỀ: <tên chủ đề cụ thể, lấy đúng thuật ngữ trong giáo trình trên>

Không cần JSON, không cần tuân theo khuôn mẫu cứng nhắc — cứ suy nghĩ và trình bày tự nhiên như đang soạn đề thi thật."""

        # Thử tối đa 2 lần: Bước 1 là nơi DeepSeek thật sự suy luận (dễ trống/lẫn tiếng Trung) —
        # đo thực tế trên log sản xuất cho thấy đây là điểm thất bại chiếm phần lớn trong tỷ lệ
        # ~69% câu Hard bị loại, nên cần retry giống Bước 2 thay vì bỏ cuộc ngay sau 1 lần.
        draft_content = ""
        for draft_attempt in range(2):
            draft_raw = _call_llm(
                model=DEEPSEEK_MODEL,
                messages=[{"role": "user", "content": draft_prompt}],
                temperature=0.3,
                max_tokens=12000,  # R1 cần nhiều token cho <think> trước khi viết lời giải thật
            )
            if not draft_raw or not draft_raw.strip():
                print(f"  [DeepSeek-R1] Bước 1 (soạn thảo tự do, lần {draft_attempt+1}/2): không có phản hồi.")
                continue

            # Cắt bỏ phần <think> nếu có, chỉ giữ nội dung soạn thảo thật sự
            candidate = re.sub(r'<think>.*?</think>', '', draft_raw, flags=re.DOTALL).strip()
            if '</think>' in candidate:
                candidate = candidate.split('</think>')[-1].strip()
            if len(candidate) < 40:
                print(f"  [DeepSeek-R1] Bước 1 (lần {draft_attempt+1}/2): nội dung soạn thảo quá ngắn/rỗng sau khi cắt <think>.")
                continue

            draft_content = candidate
            break

        if not draft_content:
            print("  [DeepSeek-R1] Bước 1: vẫn không soạn được nội dung hợp lệ sau 2 lần, bỏ qua.")
            return None

        print(f"  [DeepSeek-R1] Bước 1 hoàn tất, soạn được {len(draft_content)} ký tự nháp. Đang đóng gói JSON bằng Qwen...")

        # ─── BƯỚC 2: Qwen đóng gói lại nội dung DeepSeek vừa soạn thành đúng JSON schema ───
        # Đây là việc thuần định dạng (không cần suy luận thêm), đúng sở trường Qwen — đã chứng minh
        # ổn định suốt cả ngày nay với response_format=json_object.
        pack_prompt = f"""Dưới đây là 1 bài tập môn {subject} (Chương {chapter}) đã được 1 giáo sư khác soạn thảo. Nhiệm vụ của bạn CHỈ LÀ đóng gói lại đúng nguyên văn nội dung này vào JSON — KHÔNG được tự sáng tác thêm, không được đổi ý nghĩa, chỉ sắp xếp lại đúng nội dung sẵn có vào đúng các trường.

NỘI DUNG BÀI TẬP GỐC:
{draft_content[:6000]}

Trả về ĐÚNG 1 JSON OBJECT (giữ nguyên 100% tiếng Việt, giữ nguyên công thức LaTeX nếu có):
{{
  "id": "{short_s}_C{c_num}_HARD",
  "lesson_number": "{c_num}.9",
  "lesson_name": "<Tên mục, lấy từ nội dung gốc>",
  "topic": "<Tên chuyên đề cụ thể, lấy từ nội dung gốc>",
  "difficulty": "Hard",
  "bloom_level": "Evaluating",
  "question_text": "<Nguyên văn phần ĐỀ BÀI>",
  "correct_answer": "<Nguyên văn phần ĐÁP SỐ>",
  "detailed_solution": "<Nguyên văn phần LỜI GIẢI CHI TIẾT>",
  "scaffolding_steps": [{{"step_number": 1, "hint": "Gợi ý", "step_detail": "Chi tiết bước 1"}}]
}}"""

        # Thử tối đa 2 lần: JSON bị cắt cụt giữa chừng là lỗi transient thường gặp — retry rẻ hơn
        # nhiều so với vứt bỏ cả bài Hard đã tốn công soạn thảo tự do ở Bước 1.
        item = None
        for pack_attempt in range(2):
            pack_raw = _call_llm(
                model=LOCAL_MODEL,
                messages=[{"role": "user", "content": pack_prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=8000,
            )
            if not pack_raw or not pack_raw.strip():
                print(f"  [DeepSeek-R1] Bước 2 (Qwen đóng gói JSON, lần {pack_attempt+1}/2): không có phản hồi.")
                continue

            parsed = _parse_llm_json(pack_raw)
            if isinstance(parsed, dict) and (parsed.get("question_text") or parsed.get("question")):
                item = parsed
            elif isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                item = parsed[0]

            if item:
                break
            print(f"  [DeepSeek-R1] Bước 2 (lần {pack_attempt+1}/2): Qwen không đóng gói được JSON hợp lệ.")

        if not item:
            print("  [DeepSeek-R1] Bước 2: vẫn không đóng gói được JSON hợp lệ sau 2 lần, bỏ qua.")
            return None

        q_text = _clean_val(item.get("question_text") or item.get("question"))
        if not q_text or len(q_text) < 15 or _is_placeholder(q_text):
            print("  [DeepSeek-R1] Bước 2: nội dung câu hỏi rỗng/placeholder sau đóng gói, bỏ qua.")
            return None

        print(f"  [DeepSeek-R1] Thành công (2 bước): {q_text[:60]}...")
        return item
    except Exception as e:
        print(f"  [DeepSeek-R1 Error] {e} — quay lại luồng Qwen mặc định.")
        return None


def _generate_fallback_exercises(subject: str, chapter: str, theory_text: str, subject_type: str = None, avoid_topics: list = None) -> list:
    """Hàm tạo bài tập cấp cứu trực tiếp BẬC ĐẠI HỌC phân nhánh chuẩn xác cho cả STEM và SOCIAL khi LLM gặp sự cố."""
    short_s = _generate_short_subject_code(subject)
    m_num = re.search(r'\d+', chapter)
    c_num = m_num.group(0) if m_num else "1"

    if not subject_type:
        subject_type = _classify_subject_type(subject, theory_text=theory_text)

    balanced_theory = _prepare_balanced_theory_context(theory_text, max_chars=8000)

    # Nếu đợt sinh chính (single-pass) đã sinh được vài câu hợp lệ trước khi phải rơi xuống cấp cứu,
    # báo cho model biết để né lặp lại đúng ý tưởng đó (tránh vòng lặp: sinh trùng -> bị lọc -> cấp cứu -> lại trùng).
    avoid_block = ""
    if avoid_topics:
        uniq_topics = list(dict.fromkeys([t for t in avoid_topics if t and len(str(t).strip()) > 3]))[:6]
        if uniq_topics:
            avoid_block = f"""
⚠️ CÁC Ý TƯỞNG ĐÃ DÙNG TRONG ĐỢT SINH TRƯỚC (TUYỆT ĐỐI CẤM LẶP LẠI Ý TƯỞNG/ĐỊNH LÝ/TÌNH HUỐNG NÀY):
{chr(10).join(f'- {t}' for t in uniq_topics)}
BẮT BUỘC khai thác định lý/công thức/tình huống KHÁC HOÀN TOÀN với danh sách trên.
"""

    if subject_type == "SOCIAL":
        prompt = f"""Bạn là Giáo sư / Giảng viên Đại học chuyên ngành biên soạn đề thi chính quy môn {subject}.
Hãy đọc kỹ nội dung giáo trình Chương {c_num} ({chapter}) dưới đây và biên soạn CHÍNH XÁC 5 bài tập tự luận BẬC ĐẠI HỌC (sinh dư 2 câu so với mức cần dùng để có phương án thay thế nếu có câu bị trùng/không đạt chuẩn) CÓ CHIỀU SÂU HỌC THUẬT, BÁM SÁT 100% GIÁO TRÌNH, XOÁY SÂU VÀO BẢN CHẤT LÝ LUẬN & TƯ DUY BIỆN CHỨNG (100% TỰ LUẬN, BÁM SÁT 100% GIÁO TRÌNH). 5 câu phải khai thác 5 Ý TƯỞNG KHÁC NHAU, TUYỆT ĐỐI CẤM 2 câu cùng xoay quanh 1 nguyên lý/tình huống giống nhau:
{avoid_block}
Nội dung giáo trình Chương {c_num}:
{balanced_theory}

══════════════════════════════════════════════════════════════════════
 🎯 TIÊU CHUẨN ĐỀ THI NHÁNH SOCIAL (LÝ LUẬN / XÃ HỘI / KINH TẾ / LUẬT / QUẢN TRỊ / NHÂN VĂN):
══════════════════════════════════════════════════════════════════════
0. NGUYÊN TẮC 'CLOSED-BOOK' (TUYỆT ĐỐI CẤM LẤY CHỦ ĐỀ NGOÀI ĐOẠN GIÁO TRÌNH DƯỚI ĐÂY):
   - BẠN BẮT BUỘC PHẢI ĐỌC QUÉT TOÀN BỘ ĐOẠN GIÁO TRÌNH DƯỚI ĐÂY VÀ CHỈ BIÊN SOẠN BÀI TẬP DỰA TRÊN 100% CÁC NGUYÊN LÝ, QUY LUẬT, PHẠM TRÙ VÀ VẤN ĐỀ LÝ LUẬN CÓ MẶT TRONG ĐOẠN VĂN BẢN DƯỚI ĐÂY.
   - TUYỆT ĐỐI CẤM đưa các bài toán/chủ đề/kiến thức của các chương khác hoặc MÔN HỌC KHÁC vào đề (ví dụ: nếu môn học không phải Toán/Vật lý thì CẤM tuyệt đối đưa bài toán giải phương trình, tính toán vật lý, đạo hàm/tích phân vào đề dù chỉ để minh hoạ).
   - Nếu bạn không tìm đủ ý tưởng MỚI bám sát giáo trình, HÃY SINH ÍT CÂU HƠN thay vì lấy kiến thức phổ thông chung chung ngoài giáo trình để lấp đầy số lượng — số lượng ít nhưng đúng chủ đề LUÔN TỐT HƠN đủ số lượng nhưng lạc đề.
1. ĐỀ BÀI TỰ LUẬN BẬC ĐẠI HỌC CỤ THỂ, SÂU SẮC (TUYỆT ĐỐI CẤM CÂU HỎI MẪU KHUNG RỖNG):
   - TUYỆT ĐỐI CẤM mọi câu hỏi chung chung, rỗng tuếch kiểu mẫu như: 'Một tình huống cụ thể...', 'Vận dụng lý thuyết để chẩn đoán...', 'Đề xuất giải pháp...', 'Một bối cảnh...'.
   - BẮT BUỘC PHẢI TỰ SOẠN CÂU HỎI CHI TIẾT VÀ TỰ XÂY DỰNG MỘT TÌNH HUỐNG/BỐI CẢNH THỰC TẾ CỤ THỂ (dài 3-5 dòng, nêu rõ chủ thể, sự kiện, hiện tượng, xung đột/mâu thuẫn thực tế) rồi mới đặt câu hỏi phân tích.
   - TUYỆT ĐỐI CẤM các câu hỏi thuộc lòng định nghĩa đơn thuần cấp phổ thông (CẤM 'Nêu định nghĩa X', 'X là gì').
   - TUYỆT ĐỐI CẤM câu hỏi hoặc đáp án kết thúc bằng dấu chấm kép '..' hoặc ba chấm '...'.

2. PHÂN HOÁ 3 MỨC ĐỘ RÕ RỆT (XOÁY SÂU VÀO BẢN CHẤT LÝ THUYẾT MÔN HỌC):
► CÂU 1 (DỄ - Easy | Bloom: Understanding / Mức điểm 5.0 - 6.0):
  - Bản chất: Đặt câu hỏi lý luận chuyên sâu làm sáng tỏ nội hàm bản chất, nguồn gốc và ý nghĩa phương pháp luận của 1 nguyên lý / quy luật / phạm trù cốt lõi ở 1/3 PHẦN ĐẦU giáo trình.
  - Cấu trúc: Nêu rõ khái niệm cần phân tích và yêu cầu giải thích ý nghĩa phương pháp luận đối với nhận thức hoặc hoạt động thực tiễn.
  - Đáp án: Trình bày đầy đủ luận điểm trung tâm và ý nghĩa phương pháp luận (từ 2-3 câu hoàn chỉnh, không cụt lửng).

► CÂU 2 (TRUNG BÌNH - Medium | Bloom: Applying / Mức điểm 7.0 - 8.0):
  - Bản chất: Xây dựng một tình huống thực tiễn sinh động (Case Study) dài 3-5 dòng ở 1/3 PHẦN GIỮA giáo trình về kinh tế, văn hóa, quản lý, khoa học hoặc đời sống.
  - Cấu trúc: Gồm 2 ý a), b) liên kết logic:
    * a) Vận dụng nguyên lý/quy luật [Tên nguyên lý cụ thể trong giáo trình] để phân tích bản chất và chỉ ra nguyên nhân gốc rễ của vấn đề trong tình huống.
    * b) Đề xuất 2-3 giải pháp hoặc nguyên tắc hành động cụ thể dựa trên ý nghĩa phương pháp luận đã học.
  - Đáp án: Trình bày chi tiết, mạch lạc từng ý a), b).

► CÂU 3 (KHÓ - Hard | Bloom: Evaluating / Creating / Mức điểm 9.0 - 10.0) — ĐỈNH CAO PHẢN BIỆN HỌC THUẬT & MÂU THUẪN HỆ THỐNG:
  - Bản chất: BÀI TẬP TƯ DUY PHẢN BIỆN CAO CẤP, GIẢI PHẪU MÂU THUẪN HỆ THỐNG VĨ MÔ ở 1/3 PHẦN CUỐI giáo trình. Đặt ra một nhận định phiến diện/sai lầm hoặc một mâu thuẫn biện chứng phức tạp.
  - Cấu trúc: Chia thành 2-3 ý a), b), c) chặt chẽ:
    * a) Phân tích cơ sở lý luận và mâu thuẫn biện chứng giữa các mặt đối lập trong vấn đề.
    * b) Phản biện sắc bén, chỉ ra tính phiến diện hoặc sai lầm của quan điểm đối lập dựa trên phương pháp luận của môn học.
    * c) Luận giải và đề xuất giải pháp chiến lược dài hạn có cơ sở lý luận vững chắc.
  - Đáp án: Trình bày sắc sảo, toàn diện từng ý a), b), c).

BẮT BUỘC TRẢ VỀ ĐÚNG MỘT JSON OBJECT:
{{
  "questions": [
    {{
      "id": "{short_s}_C{c_num}_01",
      "lesson_number": "{c_num}.1",
      "lesson_name": "<Tên mục THẬT ở phần đầu chương>",
      "topic": "<Tên chuyên đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "thought_process": "<AI tự nháp phân tích, thiết lập công thức/luận điểm và tính toán/kiểm chứng kết quả>",
      "question_text": "<Nội dung câu hỏi lý luận chuyên sâu và yêu cầu phân tích phương pháp luận hoàn chỉnh>",
      "full_answer": "<Luận điểm cốt lõi và kết luận phương pháp luận hoàn chỉnh 2-3 câu>",
      "detailed_solution": "<Lời giải và luận giải chi tiết từng bước bằng Tiếng Việt>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý", "step_detail": "Chi tiết bước 1"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_02",
      "lesson_number": "{c_num}.2",
      "lesson_name": "<Tên mục THẬT ở phần giữa chương>",
      "topic": "<Tên chuyên đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "<AI tự nháp biến đổi trung gian, giải phương trình và tự kiểm chứng>",
      "question_text": "<Mô tả bối cảnh tình huống thực tế chi tiết 3-5 câu>\\na) <Yêu cầu chẩn đoán nguyên nhân theo nguyên lý cụ thể>\\nb) <Yêu cầu đề xuất giải pháp cụ thể>",
      "full_answer": "a) <Chẩn đoán nguyên nhân cốt lõi đầy đủ>; b) <Giải pháp cụ thể đầy đủ>",
      "detailed_solution": "<Lời giải phân tích tình huống chi tiết từng bước bằng Tiếng Việt>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_03",
      "lesson_number": "{c_num}.3",
      "lesson_name": "<Tên mục THẬT ở phần cuối chương>",
      "topic": "<Tên chuyên đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "thought_process": "<AI tự nháp biện luận chuyên sâu, giải phẫu mâu thuẫn/chứng minh định lý>",
      "question_text": "<Mô tả bối cảnh mâu thuẫn hệ thống vĩ mô hoặc quan điểm cần phản biện>\\na) <Yêu cầu giải phẫu mâu thuẫn biện chứng>\\nb) <Yêu cầu phản biện quan điểm đối lập>\\nc) <Yêu cầu định hướng chiến lược>",
      "full_answer": "a) <Kết luận giải phẫu mâu thuẫn>; b) <Luận điểm phản biện chính>; c) <Định hướng chiến lược>",
      "detailed_solution": "<Phân tích và luận giải toàn diện chi tiết từng bước bằng Tiếng Việt>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}},
        {{"step_number": 3, "hint": "Gợi ý ý c", "step_detail": "Chi tiết bước 3"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_04",
      "lesson_number": "{c_num}.2",
      "lesson_name": "<Tên mục THẬT ở phần giữa chương, KHÁC câu 2>",
      "topic": "<Tên chuyên đề THẬT KHÁC câu 2, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "<AI tự nháp biến đổi trung gian KHÁC câu 2, giải phương trình và tự kiểm chứng>",
      "question_text": "<Mô tả bối cảnh tình huống thực tế KHÁC câu 2, chi tiết 3-5 câu>\\na) <Yêu cầu chẩn đoán nguyên nhân theo nguyên lý cụ thể>\\nb) <Yêu cầu đề xuất giải pháp cụ thể>",
      "full_answer": "a) <Chẩn đoán nguyên nhân cốt lõi đầy đủ>; b) <Giải pháp cụ thể đầy đủ>",
      "detailed_solution": "<Lời giải phân tích tình huống chi tiết từng bước bằng Tiếng Việt>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_05",
      "lesson_number": "{c_num}.3",
      "lesson_name": "<Tên mục THẬT ở phần cuối chương, KHÁC câu 3>",
      "topic": "<Tên chuyên đề THẬT KHÁC câu 3, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "thought_process": "<AI tự nháp biện luận chuyên sâu KHÁC câu 3, giải phẫu mâu thuẫn/chứng minh định lý>",
      "question_text": "<Mô tả bối cảnh mâu thuẫn hệ thống vĩ mô KHÁC câu 3 hoặc quan điểm cần phản biện>\\na) <Yêu cầu giải phẫu mâu thuẫn biện chứng>\\nb) <Yêu cầu phản biện quan điểm đối lập>\\nc) <Yêu cầu định hướng chiến lược>",
      "full_answer": "a) <Kết luận giải phẫu mâu thuẫn>; b) <Luận điểm phản biện chính>; c) <Định hướng chiến lược>",
      "detailed_solution": "<Phân tích và luận giải toàn diện chi tiết từng bước bằng Tiếng Việt>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}},
        {{"step_number": 3, "hint": "Gợi ý ý c", "step_detail": "Chi tiết bước 3"}}
      ]
    }}
  ]
}}"""
    else:
        stem_specific_directive = _get_dynamic_stem_directive(subject, chapter)

        prompt = f"""Bạn là Giáo sư / Giảng viên Đại học chuyên ngành biên soạn đề thi chính quy môn {subject}.
Hãy đọc kỹ nội dung giáo trình Chương {c_num} ({chapter}) dưới đây và biên soạn CHÍNH XÁC 5 bài tập tự luận BẬC ĐẠI HỌC (sinh dư 2 câu so với mức cần dùng để có phương án thay thế nếu có câu bị trùng/không đạt chuẩn) CÓ KHOẢNG CÁCH PHÂN HOÁ RÕ RỆT GIỮA 3 MỨC ĐỘ, XOÁY SÂU VÀO BẢN CHẤT LÝ THUYẾT & TÍNH CHUYÊN MÔN CỦA MÔN HỌC (100% TỰ LUẬN, BÁM SÁT 100% GIÁO TRÌNH). 5 câu phải dùng 5 ĐỊNH LÝ/CÔNG THỨC/THUẬT TOÁN KHÁC NHAU, TUYỆT ĐỐI CẤM 2 câu cùng xoay quanh 1 tính chất/định lý giống nhau:
{avoid_block}
Nội dung giáo trình Chương {c_num}:
{balanced_theory}

══════════════════════════════════════════════════════════════════════
 🎯 TIÊU CHUẨN ĐỀ THI NHÁNH STEM (KỸ THUẬT / TOÁN / TỰ NHIÊN / CNTT / CÔNG NGHỆ):
══════════════════════════════════════════════════════════════════════
0. NGUYÊN TẮC 'CLOSED-BOOK': Nếu bạn không tìm đủ ý tưởng MỚI bám sát đúng chuyên đề của chương này trong giáo trình, HÃY SINH ÍT CÂU HƠN thay vì lấy kiến thức phổ thông chung chung ngoài giáo trình (như giải phương trình bậc hai/ba đại số phổ thông, bài toán Vật lý cơ bản rơi tự do/ma sát...) để lấp đầy số lượng — số lượng ít nhưng đúng chủ đề LUÔN TỐT HƠN đủ số lượng nhưng lạc đề.
1. BẮT BUỘC 100% CẢ 5 CÂU HỎI PHẢI RÚT RA TỪ ĐÚNG CHUYÊN MÔN VÀ KIẾN THỨC CỦA CHƯƠNG {c_num} ({chapter}) TRONG GIÁO TRÌNH DƯỚI ĐÂY.
2. TUYỆT ĐỐI CẤM TRỘN LẪN KIẾN THỨC CỦA MÔN HỌC / NGÀNH KHÁC:
   - Môn học đang biên soạn là {subject}. 100% câu hỏi và bài tập BẮT BUỘC chỉ sử dụng đúng các khái niệm, đối tượng, định nghĩa, công thức, thuật toán và mô hình chuyên môn xuất hiện trong giáo trình của môn {subject}.
   - TUYỆT ĐỐI CẤM đưa kiến thức, bài toán của môn học khác vào đề (ví dụ: nếu không phải môn Cơ học/Vật lý thì CẤM đưa bài toán chuyển động/vận tốc/ma sát/rơi tự do; nếu không phải môn Kinh tế thì CẤM đưa bài toán chi phí/lợi nhuận doanh nghiệp; nếu không phải môn Đại số thì CẤM đưa bài toán giải phương trình bậc hai/ba đại số phổ thông).
3. ĐỀ BÀI 100% HỌC THUẬT CHUYÊN SÂU & HÀN LÂM THUẦN TÚY (GIẢM TỐI THIỂU BỐI CẢNH THỰC TẾ):
   - Đề bài phải đi thẳng vào giả thiết khoa học, công thức, biểu thức, cấu trúc dữ liệu, thuật toán, ma trận hoặc mô hình chuyên môn của giáo trình.
   - TUYỆT ĐỐI CẤM mọi bài toán đố có lời văn đóng vai thực tế giả tạo (như "Một kỹ sư...", "Một nhà thiết kế...", "Một công ty sản xuất...", "Một máy móc...", "Một doanh nghiệp...", "Một bể nước...", "Bài toán chi phí...").
   - TUYỆT ĐỐI CẤM mọi câu bình luận, giải thích ngoài lề hoặc câu đệm siêu dữ liệu (meta-text) như: "Bài toán này liên quan đến...", "Bài toán này yêu cầu...", "Câu hỏi này nhằm kiểm tra...", "Dưới đây là...", "Bài toán tập trung vào...".
4. TÊN BÀI TẬP (topic/exerciseName) PHẢI LÀ TÊN CHUYÊN ĐỀ HỌC THUẬT:
   - Chỉ ghi tên nội dung chuyên môn LẤY ĐÚNG TỪ ĐOẠN GIÁO TRÌNH {chapter} Ở TRÊN (tên định lý/công thức/thuật toán/mục cụ thể xuất hiện trong tài liệu) — TUYỆT ĐỐI KHÔNG dùng tên chuyên đề của lĩnh vực khác dù quen thuộc đến đâu (nếu giáo trình không nói về Giải tích thì cấm dùng 'chuỗi Fourier', 'biến đổi Laplace'; nếu không phải Vật lý thì cấm dùng 'chuyển động', 'định luật bảo toàn năng lượng'...).
   - TUYỆT ĐỐI CẤM thêm các cụm từ thừa như 'trong môn {subject}', 'thuộc {subject}'.
{stem_specific_directive}

2. PHÂN HOÁ 3 MỨC ĐỘ (XOÁY SÂU VÀO BẢN CHẤT LÝ THUYẾT MÔN HỌC):
► CÂU 1 (DỄ - Easy | Bloom: Understanding / Mức điểm 5.0 - 6.0):
  - Bản chất: Áp dụng trực tiếp 1 định nghĩa / công thức / định lý / thuật toán cơ bản xuất hiện ở 1/3 PHẦN ĐẦU giáo trình.
  - Cấu trúc: Cho đối tượng/dữ kiện cụ thể, yêu cầu thực hiện tính toán, khảo sát hoặc xác định tính chất cơ bản trong 1-2 bước.
  - Đáp án: Kết quả/đáp số hoặc biểu thức rút gọn ngắn gọn, rõ ràng.

► CÂU 2 (TRUNG BÌNH - Medium | Bloom: Applying / Mức điểm 7.0 - 8.0):
  - Bản chất: Vận dụng kết hợp 2-3 khái niệm, công thức hoặc kỹ thuật liên kết ở 1/3 PHẦN GIỮA giáo trình để giải quyết bài toán đa bước.
  - Cấu trúc: Chia thành 2 ý a), b) liên kết logic (ví dụ: biến đổi/tính toán trung gian ở ý a và giải quyết mục tiêu chính hoặc phân tích mối liên hệ ở ý b).
  - Đáp án: a) Đáp số/kết luận ý a; b) Đáp số/kết luận ý b.

► CÂU 3 (KHÓ - Hard | Bloom: Evaluating / Creating / Mức điểm 9.0 - 10.0) — ĐỈNH CAO HỌC THUẬT, XOÁY SÂU VÀO LÝ THUYẾT CHUYÊN SÂU:
  - Bản chất: BÀI TOÁN TƯ DUY TRỪU TƯỢNG BẬC CAO, KHAI THÁC SÂU BẢN CHẤT LÝ THUYẾT ở 1/3 PHẦN CUỐI giáo trình.
  - TUYỆT ĐỐI CẤM: Cấm các bài toán tính toán cơ bắp đơn giản lặp lại mà không có chiều sâu lý thuyết!
  - YÊU CẦU ĐẶC TRƯNG (chọn hướng phù hợp nhất với nội dung giáo trình môn học):
    * Khảo sát/biện luận điều kiện tồn tại, tính ổn định, sự hội tụ, tính khả vi, không gian nghiệm hoặc trạng thái tới hạn khi chứa tham số thực.
    * HOẶC Chứng minh một tính chất, mệnh đề, hệ quả lý thuyết hoặc thiết lập mối quan hệ định lượng/định tính giữa các khái niệm cốt lõi trong giáo trình.
    * HOẶC Phân tích, đánh giá giới hạn áp dụng, độ phức tạp, điều kiện tối ưu hoặc xử lý ràng buộc phi tuyến/điều kiện biên phức tạp của môn học.
    * HOẶC Khảo sát trạng thái tới hạn, biến thiên đại lượng vật lý, định luật bảo toàn, thiết lập phương trình vi phân chuyển động / cân bằng năng lượng theo bản chất giáo trình.
  - Cấu trúc: Gồm 2-3 ý a), b), c) phân tầng suy luận lý thuyết chặt chẽ.
  - Đáp án: a) Kết luận biện luận/chứng minh ý a; b) Kết quả ý b; c) Kết luận ý c.

BẮT BUỘC TRẢ VỀ ĐÚNG MỘT JSON OBJECT:
{{
  "questions": [
    {{
      "id": "{short_s}_C{c_num}_01",
      "lesson_number": "{c_num}.1",
      "lesson_name": "<Tên mục THẬT ở phần đầu chương>",
      "topic": "<Tên chủ đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "thought_process": "<AI tự nháp phân tích, thiết lập công thức/luận điểm và tính toán/kiểm chứng kết quả>",
      "question_text": "Giả thiết và yêu cầu trực tiếp câu 1...",
      "full_answer": "Đáp số / Kết quả câu 1",
      "detailed_solution": "Lời giải chi tiết câu 1...",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý", "step_detail": "Chi tiết bước 1"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_02",
      "lesson_number": "{c_num}.2",
      "lesson_name": "<Tên mục THẬT ở phần giữa chương>",
      "topic": "<Tên chủ đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "<AI tự nháp biến đổi trung gian, giải phương trình và tự kiểm chứng>",
      "question_text": "Giả thiết câu 2...\\na) Yêu cầu ý a...\\nb) Yêu cầu ý b...",
      "full_answer": "a) Kết quả ý a; b) Kết quả ý b",
      "detailed_solution": "Lời giải chi tiết câu 2...",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_03",
      "lesson_number": "{c_num}.3",
      "lesson_name": "<Tên mục THẬT ở phần cuối chương>",
      "topic": "<Tên chủ đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "thought_process": "<AI tự nháp biện luận chuyên sâu, giải phẫu mâu thuẫn/chứng minh định lý>",
      "question_text": "Giả thiết câu 3 xoáy sâu vào bản chất lý thuyết...\\na) Yêu cầu ý a...\\nb) Yêu cầu ý b...\\nc) Yêu cầu ý c...",
      "full_answer": "a) Kết luận ý a; b) Kết luận ý b; c) Kết luận ý c",
      "detailed_solution": "Lời giải chi tiết và chứng minh chặt chẽ câu 3...",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}},
        {{"step_number": 3, "hint": "Gợi ý ý c", "step_detail": "Chi tiết bước 3"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_04",
      "lesson_number": "{c_num}.2",
      "lesson_name": "<Tên mục THẬT ở phần giữa chương, KHÁC câu 2>",
      "topic": "<Tên chủ đề THẬT KHÁC câu 2, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "<AI tự nháp biến đổi trung gian KHÁC câu 2, giải nghiệm và tự kiểm chứng>",
      "question_text": "Giả thiết câu 4 KHÁC câu 2...\\na) Yêu cầu ý a...\\nb) Yêu cầu ý b...",
      "full_answer": "a) Đáp số ý a; b) Đáp số ý b",
      "detailed_solution": "Lời giải chi tiết từng bước câu 4...",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_05",
      "lesson_number": "{c_num}.3",
      "lesson_name": "<Tên mục THẬT ở phần cuối chương, KHÁC câu 3>",
      "topic": "<Tên chủ đề THẬT KHÁC câu 3, KHÔNG chép nguyên văn mẫu này>",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "thought_process": "<AI tự nháp biện luận chuyên sâu KHÁC câu 3, giải phẫu mâu thuẫn/chứng minh định lý>",
      "question_text": "Giả thiết câu 5 KHÁC câu 3, xoáy sâu vào bản chất lý thuyết...\\na) Yêu cầu ý a...\\nb) Yêu cầu ý b...\\nc) Yêu cầu ý c...",
      "full_answer": "a) Kết luận ý a; b) Kết luận ý b; c) Kết luận ý c",
      "detailed_solution": "Lời giải chi tiết và chứng minh chặt chẽ câu 5...",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}},
        {{"step_number": 3, "hint": "Gợi ý ý c", "step_detail": "Chi tiết bước 3"}}
      ]
    }}
  ]
}}"""
    system_content = f"Bạn là Giáo sư Đại học chuyên ngành biên soạn đề thi chính quy môn {subject}."
    if subject_type == "SOCIAL":
        system_content += f" QUY TẮC BẮT BUỘC: 100% CẢ 5 CÂU HỎI PHẢI RÚT RA TỪ ĐÚNG CHUYÊN MÔN {chapter}, KHAI THÁC CHIỀU SÂU LÝ LUẬN VÀ THỰC TIỄN. BẮT BUỘC trả về đúng định dạng JSON."
    else:
        system_content += f" QUY TẮC BẮT BUỘC: 100% CẢ 5 CÂU HỎI PHẢI RÚT RA TỪ ĐÚNG CHUYÊN MÔN {chapter} VÀ ĐI THẲNG VÀO HỌC THUẬT HÀN LÂM THUẦN TÚY. TUYỆT ĐỐI CẤM MỌI CÂU ĐỐ BỐI CẢNH THỰC TẾ. BẮT BUỘC trả về đúng định dạng JSON."

    # Thử tối đa 2 lần: JSON bị cắt cụt giữa chừng là lỗi transient thường gặp — đây là tầng cấp cứu
    # cuối cùng trước khi cả yêu cầu thất bại hoàn toàn (0 câu), nên retry ở đây đặc biệt đáng giá.
    for attempt in range(2):
        try:
            raw = _call_llm(
                model=LOCAL_MODEL,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
                max_tokens=10000  # Sinh 5 câu (trước là 3) - tránh JSON bị cắt cụt giữa chừng
            )
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            if "</think>" in raw:
                raw = raw.split("</think>")[-1].strip()
            parsed = _parse_llm_json(raw)

            if isinstance(parsed, dict) and parsed.get("questions"):
                temp_list = parsed["questions"]
            elif isinstance(parsed, list):
                temp_list = parsed
            else:
                temp_list = []

            if temp_list:
                final_list = []
                for q in temp_list:
                    if not _is_duplicate_question(q, final_list, subject_type=subject_type or "STEM"):
                        final_list.append(q)
                return final_list

            print(f"  [Fallback Exercise Generator] Lần {attempt+1}/2: JSON rỗng/lỗi, "
                  + ("thử lại..." if attempt == 0 else "bỏ cuộc."))
        except Exception as e:
            print(f"  [Fallback Exercise Generator Error] (lần {attempt+1}/2): {e}")
    return []


# Tầng cứu hộ cuối cùng (trích xuất thô từ giáo trình, không qua AI) — ĐÃ TẮT: thà trả về ít câu hơn
# còn hơn độn boilerplate. Đổi thành True nếu muốn bật lại (xem điểm gọi ở generate_from_theory).
ENABLE_TEXTBOOK_DIRECT_FALLBACK = False

# THỬ NGHIỆM: tắt cảnh báo "cấm lặp lại chủ đề cũ" khỏi prompt Single-Pass — xem giải thích tại nơi
# dùng. Đổi thành True để bật lại nếu thử nghiệm cho thấy không hiệu quả (xem điểm gọi ở generate_from_theory).
AVOID_TOPICS_IN_PROMPT = False


def _extract_exercises_directly_from_textbook(theory_text: str, subject: str, chapter: str, subject_type: str = "STEM") -> list:
    """
    Bộ trích xuất và chuyển đổi bài tập trực tiếp từ các ví dụ / định lý / bài toán có sẵn trong giáo trình.
    Đảm bảo 100% bám sát giáo trình, tuyệt đối không bị ảo giác và KHÔNG BAO GIỜ bị 0 câu hỏi!
    """
    short_s = _generate_short_subject_code(subject)
    m_num = re.search(r'\d+', chapter)
    c_num = m_num.group(0) if m_num else "1"
    
    results = []
    diff_levels = [("Easy", "Understanding"), ("Medium", "Applying"), ("Hard", "Evaluating")]

    # 1. Tìm các khối "Ví dụ ... Lời giải ..." thực sự (chỉ tìm trong phạm vi ngắn, không vượt qua đề mục #)
    pattern = r'(?:^|\n)(?:#+\s*)?(?:Ví dụ|Vi dụ|Ví dụ\s*\d+|Bài toán|Bài tập)\s*[:.\-–—]?\s*([^\n#]{5,200}(?:\n(?!#)[^\n]{1,200}){1,15}?)(?=\n(?:#+\s*)?(?:Lời giải|Giải|Chứng minh|Hướng dẫn giải)\s*[:.\-–—]?)\n(?:#+\s*)?(?:Lời giải|Giải|Chứng minh|Hướng dẫn giải)\s*[:.\-–—]?\s*([^\n#]{5,200}(?:\n(?!#)[^\n]{1,200}){1,25}?)(?=\n(?:#+\s*)?(?:Ví dụ|Vi dụ|Bài toán|Bài tập|Định lý|Định nghĩa|#+\s*\d+|\Z))'
    matches = list(re.finditer(pattern, theory_text, flags=re.IGNORECASE))

    for m in matches:
        q_raw = m.group(1).strip()
        ans_raw = m.group(2).strip()
        
        q_clean = _clean_latex_string(_clean_question_text(q_raw))
        ans_clean = _clean_latex_string(ans_raw)
        
        # Bắt buộc đề bài từ 35 đến 1800 ký tự và lời giải từ 15 đến 3500 ký tự (chống dump toàn bộ giáo trình)
        if not (35 <= len(q_clean) <= 1800) or not (15 <= len(ans_clean) <= 3500) or _is_placeholder(q_clean):
            continue
            
        # Bắt buộc câu hỏi phải có từ khóa hỏi / mệnh đề bài toán (không phải đoạn văn bản lý thuyết thuần túy)
        has_question_intent = any(kw in q_clean.lower() for kw in [
            "hãy", "tính", "tìm", "chứng minh", "xác định", "khảo sát", "biện luận", "viết", "cho biết", 
            "bao nhiêu", "?", "\\?", "cho một", "xét một", "giả sử", "chuyển động theo", "độ lớn", "phương trình"
        ])
        if not has_question_intent:
            continue

        q_words = q_clean.split()
        if q_words and q_words[-1].lower().rstrip(".,:;?") in ["để", "là", "và", "hoặc", "của", "với", "cho", "trong", "tại", "như", "một", "các", "những"]:
            continue
        ans_words = ans_clean.split()
        if ans_words and ans_words[-1].lower().rstrip(".,:;?") in ["để", "là", "và", "hoặc", "của", "với", "cho", "trong", "tại", "như", "một", "các", "những"]:
            continue
            
        is_disc, _ = _validate_subject_discipline_integrity(q_clean, q_clean[:40], subject)
        if not is_disc:
            continue
            
        first_line = q_clean.splitlines()[0].strip()
        clean_first = re.sub(r'^(?:[a-dA-D]\)|\d+[\.)]|Ví dụ\s*\d*[:.\-]?)\s*', '', first_line).strip()
        topic = clean_first[:60].rstrip(".:,")
        m_top = re.match(r'^(?:Cho|Xét|Trong|Hãy|Tính|Giải|Phân tích|Nêu|Dịch|Biểu diễn|Chứng minh|Khảo sát)\s+([^:,.?!]{4,50})', clean_first)
        if m_top:
            raw_top = m_top.group(1).strip()
            topic = raw_top[0].upper() + raw_top[1:]
        
        diff_tuple = diff_levels[min(len(results), len(diff_levels) - 1)]
        
        # Trích xuất kết luận / đáp án ngắn gọn
        ans_summary = ans_clean
        lines = [l.strip() for l in ans_clean.splitlines() if l.strip()]
        for l in reversed(lines):
            l_low = l.lower()
            if any(k in l_low for k in ["vậy", "kết quả", "kết luận", "đáp số", "=", "do đó", "như vậy"]):
                ans_summary = l
                break
        if len(ans_summary) > 200:
            ans_summary = lines[0] if lines else ans_clean[:200]
        
        results.append({
            "id": f"{short_s}_C{c_num}_{len(results)+1:02d}",
            "lesson_number": f"{c_num}.{len(results)+1}",
            "lesson_name": chapter,
            "topic": _clean_topic_name(topic, subject),
            "difficulty": diff_tuple[0],
            "bloom_level": diff_tuple[1],
            "question_text": q_clean,
            "full_answer": ans_summary,
            "detailed_solution": ans_clean,
            "scaffolding_steps": [{"step_number": 1, "hint": "Xem định nghĩa và phương pháp giải trong giáo trình", "step_detail": "Thực hiện giải theo các bước chuẩn"}],
            "common_mistakes": ["Không áp dụng đúng định nghĩa hoặc biến đổi sai dấu"]
        })
        if len(results) >= 5:
            break

    # 2. Nếu không tìm thấy ví dụ bài toán, trích xuất câu hỏi tự luận theo từng mục con ngắn gọn (tối đa 250 ký tự)
    if len(results) < 3:
        sections = re.findall(r'(?:^|\n)(?:#+\s*)?(\d+\.\d+(?:\.\d+)?\s*[^\n]+)\n+([^#]{80,400})', theory_text)
        for sec_title, sec_content in sections:
            if len(results) >= 3:
                break
            sec_clean = sec_content.strip()
            if len(sec_clean) < 60:
                continue
            
            diff_tuple = diff_levels[min(len(results), len(diff_levels) - 1)]
            clean_top = re.sub(r'^\d+\.\d+(?:\.\d+)?\s*[:.\-]?\s*', '', sec_title).strip()
            top_name = _clean_topic_name(clean_top, subject)
            
            if subject_type == "SOCIAL":
                q_text = f"Dựa trên nội dung chuyên đề '{top_name}' trong giáo trình môn {subject}:\n1. Hãy phân tích cơ sở lý luận và nội dung bản chất của vấn đề trên.\n2. Rút ra ý nghĩa phương pháp luận và vận dụng vào thực tiễn nhận thức hoặc hoạt động thực tế."
                ans_text = f"1. Nội dung cốt lõi: {sec_clean[:200]}...\n2. Ý nghĩa phương pháp luận: Vận dụng đúng quy luật, gắn lý luận với thực tiễn."
            else:
                q_text = f"Dựa trên kiến thức về chuyên đề '{top_name}' trong giáo trình môn {subject}:\n{sec_clean[:200]}...\nHãy phân tích bản chất lý thuyết, chứng minh hoặc trình bày phương pháp giải quyết cho nội dung trên."
                ans_text = f"Lời giải và phân tích bản chất cho chuyên đề {top_name}: {sec_clean[:180]}..."

            results.append({
                "id": f"{short_s}_C{c_num}_{len(results)+1:02d}",
                "lesson_number": f"{c_num}.{len(results)+1}",
                "lesson_name": chapter,
                "topic": top_name,
                "difficulty": diff_tuple[0],
                "bloom_level": diff_tuple[1],
                "question_text": q_text,
                "full_answer": ans_text,
                "detailed_solution": f"Lời giải chi tiết dựa trên giáo trình:\n{sec_clean}",
                "scaffolding_steps": [{"step_number": 1, "hint": "Đọc kỹ định nghĩa trong mục", "step_detail": "Trình bày luận điểm"}],
                "common_mistakes": ["Nắm chưa vững định nghĩa"]
            })

    return results


# ----------------------------------------------------------------
# PROMPT NHÁNH 1: STEM
# ----------------------------------------------------------------
_DEEPSEEK_QA_STEM = """Bạn là một Giáo sư / Giảng viên Đại học biên soạn đề thi cấp Đại học.
Nhiệm vụ: Đọc NỘI DUNG LÝ THUYẾT GIÁO TRÌNH môn {subject} dưới đây và sinh ra CHÍNH XÁC 3 bài tập tự luận BẮT BUỘC BÁM SÁT 100% GIÁO TRÌNH, XOÁY SÂU VÀO BẢN CHẤT LÝ THUYẾT & TÍNH CHUYÊN MÔN CỦA MÔN HỌC.
Môn học: {subject} (Khối ngành Kỹ thuật / Công nghệ / Khoa học tự nhiên / Máy tính / Kỹ thuật công nghệ).

══════════════════════════════════════════════════════════════════════
 🎯 TIÊU CHUẨN ĐỀ THI NHÁNH STEM:
══════════════════════════════════════════════════════════════════════
1. ĐỀ BÀI TRỰC TIẾP, CHUYÊN MÔN HỌC THUẬT & TUYỆT ĐỐI KHÔNG CÂU CHỮ THỪA:
   - Đề bài phải đi thẳng vào giả thiết, mô hình, dữ kiện hoặc biểu thức chuyên môn của bài học.
   - TUYỆT ĐỐI CẤM mọi câu bình luận, giải thích ngoài lề hoặc câu đệm siêu dữ liệu (meta-text) như: "Bài toán này liên quan đến...", "Bài toán này yêu cầu...", "Câu hỏi này nhằm kiểm tra...", "Dưới đây là...", "Bài toán tập trung vào...".
   - TUYỆT ĐỐI CẤM bài toán đố có lời văn thực tế đóng vai giả tạo (như "Một kỹ sư...", "Một nhà thiết kế...", "Một công ty...").
   - TUYỆT ĐỐI CẤM trắc nghiệm (CẤM "Khẳng định nào đúng?", CẤM đáp án A, B, C, D).

2. PHÂN HOÁ 3 MỨC ĐỘ (XOÁY SÂU VÀO BẢN CHẤT LÝ THUYẾT MÔN HỌC):
► CÂU 1 (DỄ - Easy | Bloom: Understanding / Mức điểm 5.0 - 6.0):
  - Bản chất: Áp dụng trực tiếp 1 định nghĩa / công thức / định lý / thuật toán cơ bản xuất hiện ở 1/3 PHẦN ĐẦU giáo trình.
  - Cấu trúc: Cho đối tượng/dữ kiện cụ thể, yêu cầu thực hiện tính toán, khảo sát hoặc xác định tính chất cơ bản trong 1-2 bước.
  - Đáp án: Kết quả/đáp số hoặc biểu thức rút gọn ngắn gọn, rõ ràng.

► CÂU 2 (TRUNG BÌNH - Medium | Bloom: Applying / Mức điểm 7.0 - 8.0):
  - Bản chất: Vận dụng kết hợp 2-3 khái niệm, công thức hoặc kỹ thuật liên kết ở 1/3 PHẦN GIỮA giáo trình để giải quyết bài toán đa bước.
  - Cấu trúc: Chia thành 2 ý a), b) liên kết logic (ví dụ: biến đổi/tính toán trung gian ở ý a và giải quyết mục tiêu chính hoặc phân tích mối liên hệ ở ý b).
  - Đáp án: a) Đáp số/kết luận ý a; b) Đáp số/kết luận ý b.

► CÂU 3 (KHÓ - Hard | Bloom: Evaluating / Creating / Mức điểm 9.0 - 10.0) — ĐỈNH CAO HỌC THUẬT, XOÁY SÂU VÀO LÝ THUYẾT CHUYÊN SÂU:
  - Bản chất: BÀI TOÁN TƯ DUY TRỪU TƯỢNG BẬC CAO, KHAI THÁC SÂU BẢN CHẤT LÝ THUYẾT ở 1/3 PHẦN CUỐI giáo trình.
  - TUYỆT ĐỐI CẤM: Cấm các bài toán tính toán cơ bắp đơn giản lặp lại mà không có chiều sâu lý thuyết!
  - YÊU CẦU ĐẶC TRƯNG (chọn hướng phù hợp nhất với nội dung giáo trình môn học):
    * Khảo sát/biện luận điều kiện tồn tại, tính ổn định, sự hội tụ, tính khả vi, không gian nghiệm hoặc trạng thái tới hạn khi chứa tham số thực.
    * HOẶC Chứng minh một tính chất, mệnh đề, hệ quả lý thuyết hoặc thiết lập mối quan hệ định lượng/định tính giữa các khái niệm cốt lõi trong giáo trình.
    * HOẶC Phân tích, đánh giá giới hạn áp dụng, độ phức tạp, điều kiện tối ưu hoặc xử lý ràng buộc phi tuyến/điều kiện biên phức tạp của môn học.
    * HOẶC Khảo sát trạng thái tới hạn, biến thiên đại lượng vật lý, định luật bảo toàn, thiết lập phương trình vi phân chuyển động / cân bằng năng lượng theo bản chất giáo trình.
  - Cấu trúc: Gồm 2-3 ý a), b), c) phân tầng suy luận lý thuyết chặt chẽ.
  - Đáp án: a) Kết luận biện luận/chứng minh ý a; b) Kết quả ý b; c) Kết luận ý c.

Cấu trúc JSON mong muốn:
{{
  "questions": [
    {{
      "id": "EX_001",
      "lesson_number": "Mã bài/mục thực tế ở phần đầu văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần đầu văn bản",
      "topic": "Tên chủ đề bài toán môn {subject} (Phần đầu)",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "thought_process": "<AI tự nháp phân tích, thiết lập công thức/luận điểm và tính toán/kiểm chứng kết quả>",
      "question_text": "Giả thiết và yêu cầu trực tiếp câu 1...",
      "correct_answer": "Đáp số / Kết quả câu 1",
      "detailed_explanation": "Lời giải câu 1 chi tiết từng bước bằng Tiếng Việt."
    }},
    {{
      "id": "EX_002",
      "lesson_number": "Mã bài/mục thực tế ở phần giữa văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần giữa văn bản",
      "topic": "Tên chủ đề bài toán kỹ thuật môn {subject} (Phần giữa)",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "<AI tự nháp biến đổi trung gian, giải phương trình và tự kiểm chứng>",
      "question_text": "Giả thiết câu 2...\\na) Yêu cầu ý a...\\nb) Yêu cầu ý b...",
      "correct_answer": "a) Kết quả ý a; b) Kết quả ý b",
      "detailed_explanation": "Lời giải câu 2 chi tiết từng bước bằng Tiếng Việt."
    }},
    {{
      "id": "EX_003",
      "lesson_number": "Mã bài/mục thực tế ở phần cuối văn bản",
      "lesson_name": "Tên bài/tiêu đề mục thực tế ở phần cuối văn bản",
      "topic": "Tên chủ đề tư duy lý thuyết chuyên sâu môn {subject} (Phần cuối)",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "thought_process": "<AI tự nháp biện luận chuyên sâu, giải phẫu mâu thuẫn/chứng minh định lý>",
      "question_text": "Giả thiết câu 3 xoáy sâu vào bản chất lý thuyết...\\na) Yêu cầu ý a...\\nb) Yêu cầu ý b...\\nc) Yêu cầu ý c...",
      "correct_answer": "a) Kết luận ý a; b) Kết luận ý b; c) Kết luận ý c",
      "detailed_explanation": "Lời giải câu 3 chi tiết và chứng minh chặt chẽ từng bước bằng Tiếng Việt."
    }}
  ]
}}

Nội dung lý thuyết giáo trình môn {subject}:
{content}

BẮT BUỘC TRẢ VỀ CÂU TRẢ LỜI GỒM 3 CÂU HỎI TỰ LUẬN SOẠN 100% BẰNG TIẾNG VIỆT THEO CẤU TRÚC TRÊN.
"""

_QWEN_GENERATE_SCAFFOLD_PROMPT = """Bạn là một giáo sư sư phạm xuất sắc.
Dưới đây là NỘI DUNG LÝ THUYẾT GIÁO TRÌNH và nội dung bài tập / suy luận do DeepSeek vừa khởi tạo.

==================================================
 ⛔ QUY TẮC BẮT BUỘC: 100% TỰ LUẬN - TUYỆT ĐỐI CẤM TRẮC NGHIỆM
==================================================
1. BẮT BUỘC TRẢ VỀ ĐÚNG 3 BÀI TẬP TỰ LUẬN RIÊNG BIỆT TRONG MẢNG "data" (TÍNH TOÁN / PHÂN TÍCH / XỬ LÝ TÌNH HUỐNG / THIẾT KẾ / CHỨNG MINH THEO ĐẶC THÙ MÔN HỌC).
   - Phần tử 1 (Bài 1): Độ khó Easy - Bloom: Understanding.
   - Phần tử 2 (Bài 2): Độ khó Medium - Bloom: Applying.
   - Phần tử 3 (Bài 3): Độ khó Hard - Bloom: Evaluating.
2. TUYỆT ĐỐI CẤM copy các câu mào đầu hội thoại (như 'Dựa trên nội dung giáo trình...', 'Dưới đây là ba câu hỏi...'), VÀ TUYỆT ĐỐI CẤM các câu bình luận ngoài lề (như 'Bài toán này liên quan đến...', 'Bài toán này yêu cầu...', 'Câu hỏi này nhằm...'). Trường `question_text` BẮT BUỘC chỉ chứa trực tiếp giả thiết và yêu cầu bài toán.
3. NẾU DỮ LIỆU CỦA DEEPSEEK CÓ TRÓT LẪN DẠNG TRẮC NGHIỆM ("Khẳng định nào đúng?", "dưới đây là khẳng định đúng?"), BẠN BẮT BUỘC PHẢI CHUYỂN HÓA NÓ THÀNH BÀI TẬP TỰ LUẬN HOÀN CHỈNH: Yêu cầu sinh viên giải chi tiết, tính toán hoặc phân tích đưa ra kết luận.
4. TUYỆT ĐỐI CẤM `full_answer` là chữ cái "A", "B", "C", "D" hoặc câu chữ chung chung. `full_answer` BẮT BUỘC là ĐÁP SỐ / KẾT QUẢ TÍNH TOÁN HOẶC KẾT LUẬN CỐT LÕI NGẮN GỌN.
5. BẮT BUỘC dịch 100% sang Tiếng Việt chuẩn mực.
6. Trong trường `detailed_solution`: Viết LỜI GIẢI CHI TIẾT từng bước thật cặn kẽ, đầy đủ lập luận/biến đổi.
7. TẠO KỊCH BẢN SOCRATIC ĐỈNH CAO (scaffolding_steps): Gồm 3-5 bước gợi mở CÓ CHIỀU SÂU. Không đưa ngay đáp án mà phải dắt dẫn sinh viên đi từ việc phân tích đề bài, áp dụng công thức/nguyên lý lý thuyết, đến giải quyết từng phần của bài toán. Mỗi bước có 'hint' và 'step_detail'.
8. ĐÓNG GÓI kết quả vào mảng JSON chuẩn theo format bên dưới.

QUY TẮC JSON QUAN TRỌNG:
- BẮT BUỘC sao chép CHÍNH XÁC trường "id" từ danh sách câu hỏi gốc (nếu có).
- Dùng double-backslash cho LaTeX (ví dụ: "\\frac").

Cấu trúc JSON bắt buộc:
{{
  "data": [
    {{
      "id": "<id_goc_1>",
      "topic": "<ten_chu_de_thuc_te_phan_dau>",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "thought_process": "<AI tự nháp phân tích, thiết lập công thức/luận điểm và tính toán/kiểm chứng kết quả>",
      "question_text": "<noi_dung_bai_toan_1_tu_luan_tieng_viet_bat_dau_truc_tiep>",
      "full_answer": "<dap_so_hoac_ket_luan_ngan_gon_1>",
      "detailed_solution": "<loi_giai_chi_tiet_tung_buoc_1>",
      "scaffolding_steps": [
        {{ "step_number": 1, "hint": "Gợi ý", "step_detail": "Chi tiết" }}
      ],
      "common_mistakes": [ "Sai lầm 1" ]
    }},
    {{
      "id": "<id_goc_2>",
      "topic": "<ten_chu_de_thuc_te_phan_giua>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "<AI tự nháp biến đổi trung gian, giải phương trình và tự kiểm chứng>",
      "question_text": "<noi_dung_bai_toan_2_tu_luan_tieng_viet_bat_dau_truc_tiep>",
      "full_answer": "<dap_so_hoac_ket_luan_ngan_gon_2>",
      "detailed_solution": "<loi_giai_chi_tiet_tung_buoc_2>",
      "scaffolding_steps": [
        {{ "step_number": 1, "hint": "Gợi ý", "step_detail": "Chi tiết" }}
      ],
      "common_mistakes": [ "Sai lầm 1" ]
    }},
    {{
      "id": "<id_goc_3>",
      "topic": "<ten_chu_de_thuc_te_phan_cuoi>",
      "difficulty": "Hard",
      "bloom_level": "Evaluating",
      "thought_process": "<AI tự nháp biện luận chuyên sâu, giải phẫu mâu thuẫn/chứng minh định lý>",
      "question_text": "<noi_dung_bai_toan_3_tu_luan_tieng_viet_bat_dau_truc_tiep>",
      "full_answer": "<dap_so_hoac_ket_luan_ngan_gon_3>",
      "detailed_solution": "<loi_giai_chi_tiet_tung_buoc_3>",
      "scaffolding_steps": [
        {{ "step_number": 1, "hint": "Gợi ý", "step_detail": "Chi tiết" }}
      ],
      "common_mistakes": [ "Sai lầm 1" ]
    }}
  ]
}}

Nội dung lý thuyết (Dùng để đối chiếu):
{theory_context}

Nội dung bài tập / suy luận từ DeepSeek:
{qa_json}

NHẤT ĐỊNH PHẢI TRẢ VỀ KẾT QUẢ DƯỚI DẠNG JSON.
"""


@router.post("/generate-from-theory", response_model=GenerateFromTheoryResponse)
async def generate_from_theory(req: GenerateFromTheoryRequest):
    try:
        safe_subj = _get_default_folder_name(req.subject)
        safe_chap = _get_default_folder_name(req.chapter)
        # 1. TÌM FILE VÀ TRÍCH XUẤT NỘI DUNG LÝ THUYẾT CHÍNH XÁC (Loại bỏ file mục lục/lời nói đầu rác)
        rag_input_dir = _resolve_rag_input_dir(req.subject, req.course_name or "")
        m_num = re.search(r'\d+', safe_chap)
        chap_num = m_num.group(0) if m_num else ""
        
        # Trích xuất keyword tên chương để dò tìm file theo ngữ nghĩa (chống lỗi đánh số chương sai lệch,
        # ví dụ khi file trên đĩa bị OCR/tách lệch số so với số chương thật trong DB).
        # Ưu tiên tối đa: tên chương THẬT lấy từ DB (Chapter.chapterName) do Spring Boot gửi lên qua req.chapter_title —
        # đáng tin cậy hơn hẳn việc tự đoán từ mã "chuong_4" (không mang thông tin ngữ nghĩa gì).
        if req.chapter_title and req.chapter_title.strip():
            chapter_title_kw = req.chapter_title.strip().lower()
        else:
            m_title = re.search(r'[:.\-]\s*(.+)', req.chapter)
            if m_title:
                chapter_title_kw = m_title.group(1).strip().lower()
            else:
                # Loại bỏ các từ "Chương X", "Bài X" (có dấu hoặc không dấu) để lấy keyword lõi
                chapter_title_kw = re.sub(r'^(?:ch[uư]+[oơ]*ng|b[aà]i|ph[aầ]n)\s*\d*[_\s]*', '', req.chapter, flags=re.IGNORECASE).strip().lower()

        theory_content, target_file = _load_chapter_theory_text(rag_input_dir, safe_chap, chap_num, chapter_title_kw)
        if not theory_content or not target_file:
            raise HTTPException(status_code=404, detail=f"Khong tim thay noi dung ly thuyet cho chuong {req.chapter} mon {req.subject} trong {rag_input_dir}")

        print(f"[Multi-Agent] Found theory file: {target_file} (loaded {len(theory_content)} chars)")
        
        # 1.1 Đọc các bài tập đã có trong ngân hàng để chống trùng lặp chéo giữa các lần sinh
        question_bank_dir = os.path.join(settings.BASE_DIR, "prompts", safe_subj, "question_bank")
        json_path = os.path.join(question_bank_dir, f"{safe_chap}.json")
        existing_bank_questions = []
        existing_bank_topics = []
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    old_json = json.load(f)
                    old_qs = old_json.get("questions", []) if isinstance(old_json, dict) else old_json
                    if isinstance(old_qs, list):
                        for q in old_qs:
                            if isinstance(q, dict):
                                qt = q.get("question_text") or q.get("question")
                                tp = q.get("topic") or q.get("exerciseName")
                                if qt:
                                    existing_bank_questions.append(str(qt))
                                if tp:
                                    existing_bank_topics.append(str(tp))
            except Exception as e:
                print(f"  [Bank Reader Warning] Không thể đọc question_bank cũ: {e}")

        # Chuẩn bị context cân bằng toàn diện 3 phần (Đầu - Giữa - Cuối) của giáo trình
        # Tự động xoay chuyển phân đoạn (offset_phase) khi sinh nhiều lần để AI khám phá các mục mới
        offset_phase = (len(existing_bank_questions) // 3) % 4
        theory_balanced = _prepare_balanced_theory_context(theory_content, max_chars=15000, offset_phase=offset_phase)
        
        # Ngăn chặn việc truyền file rỗng/quá ngắn vào AI (gây ra lỗi JSON rỗng)
        if len(theory_balanced.strip()) < 150:
            err_msg = f"Nội dung file lý thuyết ({target_file}) quá ngắn (chỉ có {len(theory_balanced)} ký tự). File này có thể là file test. Vui lòng cung cấp file giáo trình có nội dung đầy đủ để AI có thể trích xuất bài tập."
            print(f"[Multi-Agent] THẤT BẠI: {err_msg}")
            raise HTTPException(status_code=400, detail=err_msg)

        display_subject = _get_clean_subject_display_name(req.subject, target_file=target_file, theory_text=theory_balanced, course_name=req.course_name or "")
        short_s = _generate_short_subject_code(display_subject or req.subject)
        c_num = chap_num if chap_num else "1"
        subject_type = _classify_subject_type(display_subject, target_file=target_file, theory_text=theory_balanced)
        
        chap_title = _extract_chapter_title_from_text(theory_content)
        display_chapter_name = f"{req.chapter}: {chap_title}" if chap_title else req.chapter
        print(f"[Multi-Agent] Môn '{display_subject}' -> nhánh {subject_type} | Chương: {display_chapter_name} | ID Prefix: {short_s}_C{c_num} | Đợt sinh #{offset_phase + 1} (Đã có {len(existing_bank_questions)} câu)")

        # THỬ NGHIỆM: tắt cảnh báo "cấm lặp lại chủ đề cũ" trong prompt sinh chính (Single-Pass).
        # Giả thuyết: đây là 1 ràng buộc ÂM TÍNH nữa chồng lên các ràng buộc đã có (bám giáo trình,
        # đúng định dạng, đủ độ khó...) — với model 14B, càng nhiều ràng buộc "cấm" cùng lúc càng dễ
        # khiến model buông đúng ràng buộc quan trọng nhất (bám giáo trình) để cố thỏa các cái khác.
        # Trùng lặp đã có bộ lọc riêng đáng tin cậy (_is_duplicate_question) xử lý sau, không cần model
        # tự nhớ/tự né trước. Đổi AVOID_TOPICS_IN_PROMPT = True để bật lại nếu thử nghiệm không hiệu quả.
        existing_warning = ""
        if AVOID_TOPICS_IN_PROMPT and existing_bank_topics:
            unique_tops = list(set([t for t in existing_bank_topics if len(t) > 3]))[:6]
            if unique_tops:
                existing_warning = f"""
══════════════════════════════════════════════════════════════════════
 ⚠️ CÁC CHỦ ĐỀ ĐÃ CÓ TRONG NGÂN HÀNG (TUYỆT ĐỐI CẤM TRÙNG LẶP / CẤM LẶP LẠI SỐ LIỆU):
- Các chủ đề đã biên soạn: {', '.join(unique_tops)}
- YÊU CẦU: BẮT BUỘC biên soạn các bài tập MỚI HOÀN TOÀN, khai thác các công thức/mục kiến thức KHÁC trong giáo trình dưới đây!
══════════════════════════════════════════════════════════════════════
"""

        if subject_type == "SOCIAL":
            gen_prompt = f"""Bạn là Giáo sư / Giảng viên Đại học chuyên ngành biên soạn đề thi chính quy môn {display_subject}.
Nhiệm vụ: Đọc kỹ tài liệu giáo trình {display_chapter_name} dưới đây và biên soạn 3 bài tập tự luận BẬC ĐẠI HỌC (1 Easy, 2 Medium — sinh dư 1 câu Medium so với mức cần dùng để có phương án thay thế nếu 1 câu bị bộ lọc loại/trùng lặp; câu Hard sẽ do một mô hình chuyên biệt khác đảm nhiệm riêng, KHÔNG thuộc phạm vi ở đây) CÓ CHIỀU SÂU HỌC THUẬT, BÁM SÁT 100% GIÁO TRÌNH, XOÁY SÂU VÀO BẢN CHẤT LÝ LUẬN & TƯ DUY BIỆN CHỨNG. BẮT BUỘC 3 câu phải khai thác 3 Ý TƯỞNG/KHÍA CẠNH HOÀN TOÀN KHÁC NHAU của chương, TUYỆT ĐỐI CẤM 2 câu bất kỳ cùng xoay quanh 1 nguyên lý/tình huống giống nhau:
{existing_warning}

══════════════════════════════════════════════════════════════════════
 🎯 QUY TẮC BÁM SÁT CHỦ ĐỀ CHƯƠNG HỌC (GROUNDING TỐI THƯỢNG):
══════════════════════════════════════════════════════════════════════
1. BẮT BUỘC 100% CÁC CÂU HỎI PHẢI RÚT RA TỪ ĐÚNG CHUYÊN MÔN VÀ KIẾN THỨC CỦA {display_chapter_name} TRONG ĐOẠN VĂN BẢN GIÁO TRÌNH DƯỚI ĐÂY.
2. NGUYÊN TẮC 'CLOSED-BOOK' & CHỐNG THIÊN KIẾN VÍ DỤ:
   - BẠN BẮT BUỘC PHẢI ĐỌC QUÉT TOÀN BỘ ĐOẠN GIÁO TRÌNH DƯỚI ĐÂY VÀ CHỈ BIÊN SOẠN DỰA TRÊN 100% CÁC NGUYÊN LÝ, QUY LUẬT, PHẠM TRÙ VÀ VẤN ĐỀ LÝ LUẬN CÓ MẶT TRONG ĐOẠN VĂN BẢN DƯỚI ĐÂY.
   - TUYỆT ĐỐI CẤM đưa các học thuyết của các chương/môn học khác vào bài tập nếu đoạn văn bản dưới đây không đề cập.
   - Nếu bạn không tìm đủ ý tưởng MỚI bám sát giáo trình, HÃY SINH ÍT CÂU HƠN thay vì lấy kiến thức phổ thông chung chung ngoài giáo trình để lấp đầy số lượng — số lượng ít nhưng đúng chủ đề LUÔN TỐT HƠN đủ số lượng nhưng lạc đề.
3. ĐỀ BÀI TỰ LUẬN BẬC ĐẠI HỌC CỤ THỂ, SÂU SẮC (TUYỆT ĐỐI CẤM CÂU HỎI MẪU KHUNG RỖNG):
   - BẮT BUỘC PHẢI TỰ SOẠN CÂU HỎI CHI TIẾT VÀ TỰ XÂY DỰNG MỘT TÌNH HUỐNG/BỐI CẢNH THỰC TẾ CỤ THỂ (dài 3-5 dòng, nêu rõ chủ thể, sự kiện, hiện tượng, xung đột/mâu thuẫn thực tế) rồi mới đặt câu hỏi phân tích.
   - TUYỆT ĐỐI CẤM các câu hỏi thuộc lòng định nghĩa đơn thuần cấp phổ thông.

══════════════════════════════════════════════════════════════════════
 🧠 NGUYÊN TẮC CHAIN-OF-THOUGHT (TỰ NHÁP & LẬP LUẬN BIỆN CHỨNG TRƯỚC KHI KẾT LUẬN):
══════════════════════════════════════════════════════════════════════
- Trong trường `thought_process`: AI BẮT BUỘC phải thực hiện quá trình tự nháp và suy luận từng bước:
  1. Xác định đúng nguyên lý, quy luật, phạm trù lý luận trong giáo trình được vận dụng.
  2. Phân tích giải phẫu mâu thuẫn biện chứng hoặc liên hệ thực tiễn một cách logic, đa chiều.
  3. Tự phản biện, kiểm tra lại tính chặt chẽ của lập luận trước khi kết xuất `correct_answer` và `detailed_solution`.

══════════════════════════════════════════════════════════════════════
 🎯 TIÊU CHUẨN PHÂN HOÁ 2 MỨC ĐỘ (XOÁY SÂU VÀO BẢN CHẤT LÝ THUYẾT MÔN HỌC — MỨC HARD DO MÔ HÌNH KHÁC ĐẢM NHIỆM RIÊNG):
══════════════════════════════════════════════════════════════════════
► CÂU 1 (DỄ - Easy | Bloom: Understanding / Mức điểm 5.0 - 6.0): Đặt câu hỏi lý luận chuyên sâu làm sáng tỏ nội hàm bản chất ở 1/3 PHẦN ĐẦU giáo trình {display_chapter_name}.
► CÂU 2 (TRUNG BÌNH - Medium | Bloom: Applying / Mức điểm 7.0 - 8.0): Xây dựng Case Study tình huống thực tiễn sinh động dài 3-5 dòng ở 1/3 PHẦN GIỮA giáo trình {display_chapter_name}.
► CÂU 3 (TRUNG BÌNH - Medium, ứng viên dự phòng | Bloom: Applying / Mức điểm 7.0 - 8.0): Xây dựng Case Study tình huống thực tiễn sinh động dài 3-5 dòng KHÁC HOÀN TOÀN CÂU 2 ở 1/3 PHẦN CUỐI giáo trình {display_chapter_name}.

══════════════════════════════════════════════════════════════════════
 📖 NỘI DUNG GIÁO TRÌNH {display_chapter_name} (ĐỌC KỸ ĐOẠN NÀY ĐỂ BIÊN SOẠN BÀI TẬP):
══════════════════════════════════════════════════════════════════════
{theory_balanced}

══════════════════════════════════════════════════════════════════════
 BẮT BUỘC TRẢ VỀ ĐÚNG MỘT JSON OBJECT CÓ MẢNG "questions" GỒM 3 BÀI TẬP (BÁM SÁT 100% ĐOẠN GIÁO TRÌNH TRÊN, MỖI CÂU 1 Ý TƯỞNG RIÊNG BIỆT):
{{
  "questions": [
    {{
      "id": "{short_s}_C{c_num}_01",
      "lesson_number": "{c_num}.1",
      "lesson_name": "<Tên mục THẬT ở phần đầu chương>",
      "topic": "<Tên chuyên đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "theory_reference": "<Tên nguyên lý / phạm trù cụ thể trong giáo trình trên>",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "thought_process": "1. Neo lý thuyết: [Tên nguyên lý/phạm trù trong giáo trình trên]. 2. Luận điểm cốt lõi... 3. Kiểm chứng tính logic...",
      "question_text": "<Nội dung câu hỏi lý luận chuyên sâu và yêu cầu phân tích phương pháp luận hoàn chỉnh>",
      "correct_answer": "<Luận điểm cốt lõi và kết luận phương pháp luận hoàn chỉnh 2-3 câu>",
      "detailed_solution": "<Lời giải và luận giải chi tiết từng bước bằng Tiếng Việt>",
      "scaffolding_steps": [{{"step_number": 1, "hint": "Gợi ý", "step_detail": "Chi tiết bước 1"}}]
    }},
    {{
      "id": "{short_s}_C{c_num}_02",
      "lesson_number": "{c_num}.2",
      "lesson_name": "<Tên mục THẬT ở phần giữa chương>",
      "topic": "<Tên chuyên đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "theory_reference": "<Tên nguyên lý / quy luật cụ thể trong giáo trình trên>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "1. Neo lý thuyết: [Tên quy luật trong giáo trình]. 2. Phân tích tình huống... 3. Đề xuất giải pháp...",
      "question_text": "<Mô tả bối cảnh tình huống thực tế chi tiết 3-5 câu>\\na) <Yêu cầu chẩn đoán nguyên nhân theo nguyên lý cụ thể>\\nb) <Yêu cầu đề xuất giải pháp cụ thể>",
      "correct_answer": "a) <Chẩn đoán nguyên nhân cốt lõi đầy đủ>; b) <Giải pháp cụ thể đầy đủ>",
      "detailed_solution": "<Lời giải phân tích tình huống chi tiết từng bước bằng Tiếng Việt>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_03",
      "lesson_number": "{c_num}.3",
      "lesson_name": "<Tên mục THẬT ở phần cuối chương>",
      "topic": "<Tên chuyên đề THẬT, KHÁC HOÀN TOÀN CÂU 2, KHÔNG chép nguyên văn mẫu này>",
      "theory_reference": "<Tên nguyên lý / quy luật cụ thể trong giáo trình trên, KHÁC CÂU 2>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "1. Neo lý thuyết: [Tên quy luật trong giáo trình]. 2. Phân tích tình huống... 3. Đề xuất giải pháp...",
      "question_text": "<Mô tả bối cảnh tình huống thực tế chi tiết 3-5 câu, KHÁC HOÀN TOÀN CÂU 2>\\na) <Yêu cầu chẩn đoán nguyên nhân theo nguyên lý cụ thể>\\nb) <Yêu cầu đề xuất giải pháp cụ thể>",
      "correct_answer": "a) <Chẩn đoán nguyên nhân cốt lõi đầy đủ>; b) <Giải pháp cụ thể đầy đủ>",
      "detailed_solution": "<Lời giải phân tích tình huống chi tiết từng bước bằng Tiếng Việt>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}}
      ]
    }}
  ]
}}"""
        else:
            stem_specific_directive = _get_dynamic_stem_directive(display_subject, display_chapter_name)

            gen_prompt = f"""Bạn là Giáo sư / Giảng viên Đại học chuyên ngành biên soạn đề thi chính quy môn {display_subject}.
Nhiệm vụ: Biên soạn 3 bài tập tự luận BẬC ĐẠI HỌC (1 Easy, 2 Medium — sinh dư 1 câu Medium so với mức cần dùng để có phương án thay thế nếu 1 câu bị bộ lọc loại/trùng lặp; câu Hard sẽ do một mô hình chuyên biệt khác đảm nhiệm riêng, KHÔNG thuộc phạm vi ở đây) CÓ KHOẢNG CÁCH PHÂN HOÁ RÕ RỆT, XOÁY SÂU VÀO BẢN CHẤT LÝ THUYẾT & TÍNH CHUYÊN MÔN CỦA {display_chapter_name}. BẮT BUỘC 3 câu phải dùng 3 ĐỊNH LÝ/CÔNG THỨC/THUẬT TOÁN KHÁC NHAU, TUYỆT ĐỐI CẤM 2 câu bất kỳ cùng xoay quanh 1 tính chất/định lý giống nhau:
{existing_warning}

══════════════════════════════════════════════════════════════════════
 🎯 QUY TẮC BÁM SÁT CHỦ ĐỀ CHƯƠNG HỌC (GROUNDING TỐI THƯỢNG):
══════════════════════════════════════════════════════════════════════
1. BẮT BUỘC 100% CÁC CÂU HỎI PHẢI RÚT RA TỪ ĐÚNG CHUYÊN MÔN VÀ KIẾN THỨC CỦA {display_chapter_name} TRONG ĐOẠN VĂN BẢN GIÁO TRÌNH DƯỚI ĐÂY.
2. NGUYÊN TẮC 'CLOSED-BOOK' (TUYỆT ĐỐI CẤM LẤY CHỦ ĐỀ NGOÀI ĐOẠN GIÁO TRÌNH DƯỚI ĐÂY):
   - BẠN BẮT BUỘC PHẢI ĐỌC QUÉT TOÀN BỘ ĐOẠN GIÁO TRÌNH DƯỚI ĐÂY VÀ CHỈ BIÊN SOẠN BÀI TẬP DỰA TRÊN 100% CÁC ĐỀ MỤC, ĐỊNH NGHĨA, ĐỊNH LÝ, CÔNG THỨC, THUẬT TOÁN VÀ MÔ HÌNH THỰC TẾ XUẤT HIỆN TRONG TÀI LIỆU DƯỚI ĐÂY.
   - TUYỆT ĐỐI CẤM đưa các bài toán/chủ đề của các chương khác hoặc môn học khác vào đề!
   - Nếu bạn không tìm đủ ý tưởng MỚI bám sát giáo trình, HÃY SINH ÍT CÂU HƠN thay vì lấy kiến thức phổ thông chung chung ngoài giáo trình để lấp đầy số lượng — số lượng ít nhưng đúng chủ đề LUÔN TỐT HƠN đủ số lượng nhưng lạc đề.
3. QUY TẮC ĐỒNG BỘ ĐỀ BÀI VÀ ĐÁP ÁN (BẮT BUỘC 100%):
   - Nếu đề bài là câu hỏi đơn (không chia ý a, b) -> Trường 'question_text' là câu hỏi trực tiếp, và trường 'correct_answer' BẮT BUỘC chỉ là một đáp số/kết luận duy nhất (TUYỆT ĐỐI CẤM tự thêm nhãn a, b hay câu đệm như 'b) Chi tiết tính toán').
   - Nếu đề bài là câu hỏi đa bước (gồm các ý a, b) -> Trường 'question_text' BẮT BUỘC phải ghi rõ ràng 'a) <Yêu cầu ý a>\\nb) <Yêu cầu ý b>' và trường 'correct_answer' BẮT BUỘC tương ứng chính xác 'a) <Đáp số ý a>; b) <Đáp số ý b>'.
4. QUY TẮC 100% TIẾNG VIỆT CHUẨN MỰC (TUYỆT ĐỐI CẤM KÝ TỰ CHỮ HÁN / TIẾNG TRUNG):
   - TUYỆT ĐỐI CẤM để sót ký tự chữ Hán/tiếng Trung hoặc ngoại ngữ trong toàn bộ đề bài, đáp án và lời giải. Toàn bộ thuật ngữ phải dùng Tiếng Việt chuẩn mực.
5. ĐỀ BÀI BẮT BUỘC CÓ DỮ LIỆU ĐẦU VÀO ĐỊNH LƯỢNG / BÀI TẬP TÍNH TOÁN CỤ THỂ (TUYỆT ĐỐI CẤM HỎI LÝ THUYẾT TRÌNH BÀY SUÔNG):
   - Đề bài BẮT BUỘC phải cho BỘ DỮ LIỆU ĐẦU VÀO CỤ THỂ, LẤY ĐÚNG LOẠI ĐỐI TƯỢNG XUẤT HIỆN TRONG ĐOẠN GIÁO TRÌNH {display_chapter_name} Ở DƯỚI (ví dụ: nếu giáo trình nói về ma trận thì cho ma trận số cụ thể, nếu nói về đồ thị thì cho đồ thị có trọng số cụ thể, nếu nói về mạch điện thì cho thông số mạch cụ thể...). TUYỆT ĐỐI CẤM mặc định dùng hàm số bậc nhất/bậc hai trừu tượng kiểu f(x)=ax+b nếu giáo trình KHÔNG nói về hàm số — đó là dạng bài phổ thông, KHÔNG PHẢI đối tượng chuyên môn của {display_chapter_name}.
   - TUYỆT ĐỐI CẤM các câu hỏi lý thuyết trình bày/giải thích vẹt (CẤM: 'Hãy giải thích cách hoạt động của...', 'So sánh hiệu quả của...', 'Nêu ưu nhược điểm của...', 'Trình bày khái niệm...').
   - 100% bài tập STEM phải là bài toán giải quyết vấn đề, tính toán các bước, giải ra đáp số/phương án tối ưu hoặc chứng minh định lý/tính chất cụ thể!
6. TÍNH ĐỘC LẬP & ĐA DẠNG GIỮA CÁC CÂU HỎI (TUYỆT ĐỐI CẤM TRÙNG LẶP DẠNG BÀI):
   - 2 câu hỏi BẮT BUỘC phải khai thác 2 MỤC/DẠNG BÀI TOÁN KHÁC NHAU của chương {display_chapter_name}. TUYỆT ĐỐI CẤM lặp lại cùng một bài toán, cùng một định lý hay cùng một thuật toán cho nhiều câu!
7. ĐỀ BÀI PHẢI CÓ ĐỦ NGỮ CẢNH HỌC THUẬT (KHÔNG PHẢI CÂU LỆNH TRẦN TRỤI 1 DÒNG):
   - TRƯỚC khi nêu yêu cầu tính toán, BẮT BUỘC mở đầu bằng 1-2 câu mô tả rõ đối tượng/hệ thống/mô hình đang xét và Ý NGHĨA hoặc VAI TRÒ của nó trong chuyên đề {display_chapter_name} (ví dụ: hệ thống này dùng để làm gì, thuộc dạng bài toán nào, tại sao đáng quan tâm) — KHÔNG chỉ liệt kê trần trụi "Cho X. Tính Y." mà không có câu dẫn nhập nào.
   - LƯU Ý: đây KHÔNG phải yêu cầu thêm bối cảnh thực tế đóng vai giả tạo (mục 3 ở TIÊU CHUẨN ĐỀ THI vẫn cấm "Một kỹ sư...", "Một công ty..." như cũ) — mà là thêm 1-2 CÂU DẪN NHẬP HỌC THUẬT THUẦN TÚY (định nghĩa bối cảnh toán học/kỹ thuật của đối tượng) trước khi đưa ra giả thiết số liệu và yêu cầu cụ thể.
8. QUY TẮC BỔ SUNG THEO CHUYÊN NGÀNH:
{stem_specific_directive}

══════════════════════════════════════════════════════════════════════
 🧠 NGUYÊN TẮC CHAIN-OF-THOUGHT (TỰ NHÁP & KIỂM CHỨNG TỔNG QUÁT CHO MỌI MÔN STEM):
══════════════════════════════════════════════════════════════════════
- Trong trường `thought_process`: AI BẮT BUỘC phải thực hiện toàn bộ quá trình suy luận nháp chuyên môn cặn kẽ trước khi đưa ra kết luận:
  1. Phân tích các dữ kiện, giả thiết khoa học, đối tượng kỹ thuật hoặc ràng buộc chuyên môn của bài toán.
  2. Xác định và thiết lập đúng định luật, định lý, công thức toán học, thuật toán, cấu trúc dữ liệu, cơ chế kỹ thuật hoặc mô hình nguyên lý tương ứng từ giáo trình {display_chapter_name}.
  3. Thực hiện từng bước biến đổi logic chuyên môn (tính toán công thức, thay số, mô phỏng luồng xử lý/thuật toán hoặc chứng minh).
  4. Tự kiểm chứng lại tính chính xác của kết quả, điều kiện biên, tính hợp lệ logic và đơn vị đo lường (nếu có) trước khi kết xuất `correct_answer` và `detailed_solution`.

══════════════════════════════════════════════════════════════════════
 🎯 TIÊU CHUẨN PHÂN HOÁ 2 MỨC ĐỘ (XOÁY SÂU VÀO BẢN CHẤT LÝ THUYẾT MÔN HỌC — MỨC HARD DO MÔ HÌNH KHÁC ĐẢM NHIỆM RIÊNG):
══════════════════════════════════════════════════════════════════════
► CÂU 1 (DỄ - Easy | Bloom: Understanding / Mức điểm 5.0 - 6.0): Áp dụng trực tiếp ĐÚNG 1 định nghĩa / công thức / định lý / thuật toán duy nhất, không cần biến đổi hay kết hợp gì thêm, ở 1/3 PHẦN ĐẦU giáo trình {display_chapter_name}. Mở đầu bằng 1-2 câu giới thiệu ngắn gọn đối tượng/mô hình đang xét (xem mục 7 ở trên) trước khi cho giả thiết số liệu.
► CÂU 2 (TRUNG BÌNH - Medium | Bloom: Applying / Mức điểm 7.0 - 8.0): Vận dụng kết hợp 2-3 khái niệm, công thức hoặc kỹ thuật liên kết ở 1/3 PHẦN GIỮA giáo trình {display_chapter_name} để giải bài toán đa bước. Mở đầu bằng 1-2 câu giới thiệu ngắn gọn đối tượng/mô hình đang xét (xem mục 7 ở trên) trước khi cho giả thiết số liệu.
► CÂU 3 (TRUNG BÌNH - Medium, ứng viên dự phòng | Bloom: Applying / Mức điểm 7.0 - 8.0): Vận dụng kết hợp 2-3 khái niệm/công thức/kỹ thuật KHÁC HOÀN TOÀN CÂU 2, ở 1/3 PHẦN CUỐI giáo trình {display_chapter_name}. Mở đầu bằng 1-2 câu giới thiệu ngắn gọn đối tượng/mô hình đang xét (xem mục 7 ở trên) trước khi cho giả thiết số liệu.

══════════════════════════════════════════════════════════════════════
 📖 NỘI DUNG GIÁO TRÌNH {display_chapter_name} (ĐỌC KỸ ĐOẠN NÀY ĐỂ BIÊN SOẠN BÀI TẬP):
══════════════════════════════════════════════════════════════════════
{theory_balanced}

══════════════════════════════════════════════════════════════════════
 BẮT BUỘC TRẢ VỀ ĐÚNG MỘT JSON OBJECT CÓ MẢNG "questions" GỒM 3 BÀI TẬP (BÁM SÁT 100% ĐOẠN GIÁO TRÌNH TRÊN, MỖI CÂU 1 DẠNG BÀI RIÊNG BIỆT):
{{
  "questions": [
    {{
      "id": "{short_s}_C{c_num}_01",
      "lesson_number": "{c_num}.1",
      "lesson_name": "<Tên mục THẬT ở phần đầu chương>",
      "topic": "<Tên chuyên đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "theory_reference": "<Tên mục / Định nghĩa / Công thức cụ thể trong giáo trình trên>",
      "difficulty": "Easy",
      "bloom_level": "Understanding",
      "thought_process": "1. Neo lý thuyết: [Tên mục/công thức trong giáo trình trên]. 2. Dữ kiện bài toán... 3. Nháp giải và thay số... 4. Tự kiểm chứng kết quả...",
      "question_text": "<Noi_dung_de_bai_tu_luan_1_cau_don_bat_dau_truc_tiep_gia_thiet>",
      "correct_answer": "<Dap_so_hoac_ket_luan_don_1>",
      "detailed_solution": "<Loi_giai_chi_tiet_tung_buoc_1>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý", "step_detail": "Chi tiết bước 1"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_02",
      "lesson_number": "{c_num}.2",
      "lesson_name": "<Tên mục THẬT ở phần giữa chương>",
      "topic": "<Tên chuyên đề THẬT, KHÔNG chép nguyên văn mẫu này>",
      "theory_reference": "<Tên định lý / thuật toán cụ thể trong giáo trình trên>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "1. Neo lý thuyết: [Tên thuật toán/công thức trong giáo trình trên]. 2. Biến đổi trung gian... 3. Giải nghiệm... 4. Kiểm chứng...",
      "question_text": "<Gia_thiet_bai_2>\\na) <Yeu_cau_y_a>\\nb) <Yeu_cau_y_b>",
      "correct_answer": "a) <Dap_so_y_a>; b) <Dap_so_y_b>",
      "detailed_solution": "<Loi_giai_chi_tiet_tung_buoc_2>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}}
      ]
    }},
    {{
      "id": "{short_s}_C{c_num}_03",
      "lesson_number": "{c_num}.3",
      "lesson_name": "<Tên mục THẬT ở phần cuối chương>",
      "topic": "<Tên chuyên đề THẬT, KHÁC HOÀN TOÀN CÂU 2, KHÔNG chép nguyên văn mẫu này>",
      "theory_reference": "<Tên định lý / thuật toán cụ thể trong giáo trình trên, KHÁC CÂU 2>",
      "difficulty": "Medium",
      "bloom_level": "Applying",
      "thought_process": "1. Neo lý thuyết: [Tên thuật toán/công thức trong giáo trình trên]. 2. Biến đổi trung gian... 3. Giải nghiệm... 4. Kiểm chứng...",
      "question_text": "<Gia_thiet_bai_3_khac_hoan_toan_bai_2>\\na) <Yeu_cau_y_a>\\nb) <Yeu_cau_y_b>",
      "correct_answer": "a) <Dap_so_y_a>; b) <Dap_so_y_b>",
      "detailed_solution": "<Loi_giai_chi_tiet_tung_buoc_3>",
      "scaffolding_steps": [
        {{"step_number": 1, "hint": "Gợi ý ý a", "step_detail": "Chi tiết bước 1"}},
        {{"step_number": 2, "hint": "Gợi ý ý b", "step_detail": "Chi tiết bước 2"}}
      ]
    }}
  ]
}}"""

        final_list = []
        system_content = f"Bạn là Giáo sư Đại học chuyên ngành biên soạn đề thi chính quy môn {display_subject}."
        if subject_type == "SOCIAL":
            system_content += f" QUY TẮC BẮT BUỘC: 100% CÁC CÂU HỎI PHẢI BÁM SÁT {display_chapter_name}, XOÁY SÂU VÀO BẢN CHẤT LÝ LUẬN, XÂY DỰNG TÌNH HUỐNG THỰC TẾ VÀ TƯ DUY BIỆN CHỨNG. TUYỆT ĐỐI CẤM HỎI VẸT ĐỊNH NGHĨA ĐƠN THUẦN. BẮT BUỘC trả về đúng định dạng JSON."
        else:
            system_content += f" QUY TẮC BẮT BUỘC: 100% CÁC CÂU HỎI PHẢI LÀ BÀI TOÁN TÍNH TOÁN / MÔ PHỎNG / TỐI ƯU HÓA / CHỨNG MINH CÓ SỐ LIỆU ĐẦU VÀO CỤ THỂ TỪ {display_chapter_name}. TUYỆT ĐỐI CẤM MỌI CÂU HỎI LÝ THUYẾT TRÌNH BÀY / HỎI VẸT (CẤM: 'Cho biết khái niệm...', 'Nêu định nghĩa...', 'Giải thích cách hoạt động...', 'So sánh hiệu quả...'). BẮT BUỘC trả về đúng định dạng JSON."

        # Thử tối đa 2 lần: JSON bị cắt cụt giữa chừng (lỗi transient của model/kết nối) khá thường gặp,
        # và thường CHỈ CẦN gọi lại là qua — retry 1 lần rẻ hơn nhiều so với rơi thẳng xuống Fallback
        # Generator (vốn có prompt yếu hơn, dễ lạc đề như đã phát hiện qua test thực tế).
        for attempt in range(2):
            try:
                print(f"  -> Đang gọi mô hình AI ({LOCAL_MODEL}) sinh tập ứng viên 3 bài tập Easy/Medium/Medium-dự phòng (Single-Pass, lần {attempt+1}/2) — câu Hard do DeepSeek đảm nhiệm riêng...")
                raw_gen = _call_llm(
                    model=LOCAL_MODEL,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": gen_prompt}
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    max_tokens=10000  # Giữ dư so với mặc định 8192 để tránh JSON bị cắt cụt giữa chừng
                )
                parsed_gen = _parse_llm_json(raw_gen)
                if isinstance(parsed_gen, list):
                    final_list = parsed_gen
                elif isinstance(parsed_gen, dict) and parsed_gen.get("questions"):
                    final_list = parsed_gen["questions"]
                elif isinstance(parsed_gen, dict) and parsed_gen.get("data"):
                    final_list = parsed_gen["data"]
            except Exception as e:
                print(f"  [Primary Generator Warning] Lỗi khi gọi mô hình chính (lần {attempt+1}/2): {e}")

            if final_list:
                break
            elif attempt == 0:
                print("  [Primary Generator Warning] Không lấy được câu hỏi hợp lệ nào (JSON lỗi/rỗng), thử gọi lại lần 2...")

        # Nếu mô hình chính chưa đủ 2 câu (Easy/Medium), kích hoạt bộ sinh bổ sung cấp cứu
        if len(final_list) < 2:
            print(f"  [Fallback Generator] Kích hoạt tạo bổ sung bài tập cấp cứu cho {display_subject} ({display_chapter_name})...")
            fb_items = _generate_fallback_exercises(display_subject, display_chapter_name, theory_balanced, subject_type=subject_type)
            for fb in fb_items:
                if len(final_list) >= 2:
                    break
                if str(fb.get("difficulty", "")).strip().lower() == "hard":
                    continue  # Câu Hard do DeepSeek đảm nhiệm riêng bên dưới, không lấy từ đây
                final_list.append(fb)

        # Kết hợp kết quả để trả về cho Spring Boot lưu DB, đồng thời inject dữ liệu vào final_list
        db_exercises = []
        clean_final_list = []
        
        for idx, item in enumerate(final_list, start=1):
            if isinstance(item, str):
                final_item = {"question_text": item, "topic": f"Bài tập {display_subject} {idx}", "full_answer": "Xem chi tiết lời giải"}
            elif isinstance(item, dict):
                final_item = item
            else:
                continue

            # 1. Ưu tiên lấy dữ liệu trực tiếp từ Stage 2 (do Qwen 2.5 đã phân loại & dịch thuật)
            raw_diff = _clean_val(final_item.get("difficulty"))
            raw_bloom = _clean_val(final_item.get("bloom_level"))
            topic = _clean_val(final_item.get("topic")) or _clean_val(final_item.get("exerciseName")) or _clean_val(final_item.get("title"))
            question_text = _clean_val(final_item.get("question_text")) or _clean_val(final_item.get("question")) or _clean_val(final_item.get("questionText"))
            
            # Đáp án đúng: ưu tiên lấy kết quả cuối cùng (full_answer hoặc correct_answer)
            correct_answer = (_clean_val(final_item.get("full_answer")) or _clean_val(final_item.get("correct_answer"))
                              or _clean_val(final_item.get("answer")) or _clean_val(final_item.get("general_solution")))
            detailed_sol = _clean_val(final_item.get("detailed_solution")) or _clean_val(final_item.get("detailed_explanation"))
            lesson_num = _clean_val(final_item.get("lesson_number"))
            lesson_nam = _clean_val(final_item.get("lesson_name"))

            # Phục hồi question_text từ general_solution khi Qwen trả sai format
            if not question_text and final_item.get("general_solution"):
                gen_sol_str = _clean_val(final_item.get("general_solution"))
                if len(gen_sol_str) > 20:
                    first_sentence = gen_sol_str.split('\n')[0].strip()
                    if len(first_sentence) > 15 and not first_sentence.lower().startswith("để giải"):
                        question_text = first_sentence

            # 2. Xử lý kịch bản sư phạm và bước gợi ý
            scaffolding = final_item.get("scaffolding_steps") or []
            if not isinstance(scaffolding, list):
                scaffolding = []
            if (not correct_answer or _is_placeholder(correct_answer)) and scaffolding:
                last_step = scaffolding[-1]
                if isinstance(last_step, dict):
                    correct_answer = _clean_val(last_step.get("step_detail")) or _clean_val(last_step.get("hint"))

            # Nếu sau khi thử phục hồi từ scaffolding vẫn không có đáp án thật (vẫn rỗng/placeholder
            # như "Xem chi tiết lời giải", "Chứng minh thành công"...) -> LOẠI BỎ cả câu hỏi, không
            # chấp nhận với đáp án giả (trước đây bị âm thầm thay bằng "Chưa có đáp án" và vẫn cho qua).
            if not correct_answer or _is_placeholder(correct_answer):
                print(f"  [Placeholder Guard] Loại câu hỏi có đáp án rỗng/giả: {correct_answer!r}")
                continue

            # Lọc nghiêm ngặt: Bỏ qua hoàn toàn các câu mào đầu / lời chào của AI
            q_str = str(question_text or "").strip()
            lines = [l.strip() for l in q_str.splitlines() if l.strip()]
            if lines:
                clean_lines = []
                skip_hdr = True
                for l in lines:
                    l_low = l.lower()
                    if skip_hdr and (l_low.startswith("dựa trên") or l_low.startswith("dưới đây là") or l_low.startswith("sau đây là") or l_low.startswith("đây là") or l.startswith("---") or l.startswith("===")):
                        continue
                    skip_hdr = False
                    clean_lines.append(l)
                if clean_lines:
                    question_text = "\n".join(clean_lines).strip()
                else:
                    # Toàn bộ nội dung câu hỏi chỉ là câu chào mào đầu -> Bỏ qua câu rác này
                    continue

            # Kiểm tra câu hỏi có hợp lệ (độ dài >= 15 ký tự và không phải placeholder)
            q_lower = str(question_text).lower().strip()
            if not question_text or len(q_lower) < 15 or _is_placeholder(question_text):
                continue
            if q_lower.startswith("dựa trên nội dung giáo trình") and ("?" not in q_lower and "=" not in q_lower and "$" not in q_lower):
                continue

            # Chuyển đổi triệt để nếu câu hỏi trót dính câu từ trắc nghiệm sang bài tập tự luận hoàn chỉnh
            trac_nghiem_patterns = [
                r"[,\s]*dưới đây là khẳng định đúng\??",
                r"[,\s]*khẳng định nào sau đây là đúng\??",
                r"[,\s]*mệnh đề nào sau đây là đúng\??",
                r"[,\s]*mệnh đề nào đúng\??",
                r"[,\s]*chọn câu đúng\??",
                r"[,\s]*chọn đáp án đúng\??"
            ]
            for pat in trac_nghiem_patterns:
                if re.search(pat, question_text, flags=re.IGNORECASE):
                    question_text = re.sub(pat, "", question_text, flags=re.IGNORECASE).strip()
                    if not question_text.endswith(".") and not question_text.endswith("?") and not question_text.endswith(":"):
                        question_text += "."
                    question_text += f" Hãy phân tích chi tiết và đưa ra lời giải đầy đủ cho bài toán môn {display_subject} trên."

            # Lọc bỏ triệt để ký tự tiếng Trung, trích dẫn tài liệu tham khảo hoặc văn bản rác
            question_text = _clean_question_text(question_text)
            if not question_text or len(question_text) < 15:
                print(f"  [Garbage Filter] Bỏ qua câu hỏi không hợp lệ / chứa trích dẫn sách / tiếng Trung rác: {question_text}")
                continue

            # Chuẩn hóa các thuật ngữ toán học tiếng Anh sót lại sang Tiếng Việt chuẩn mực
            question_text = _clean_math_vietnamese(question_text)
            correct_answer = _clean_math_vietnamese(correct_answer)
            detailed_sol = _clean_math_vietnamese(detailed_sol)
            topic = _clean_math_vietnamese(str(topic))

            # Đồng bộ hóa 100% Đề bài và Đáp án (loại bỏ đáp án fake a, b khi đề bài là câu đơn) & Dọn sạch CJK
            question_text, correct_answer, detailed_sol = _harmonize_question_and_answer(question_text, correct_answer, detailed_sol)
            topic = _clean_cjk_and_foreign_artifacts(str(topic))

            # Kiểm tra chống trùng lặp chéo giữa các lần sinh (Cross-batch & Intra-batch Deduplication)
            existing_questions = [ex.question for ex in db_exercises]
            all_known_questions = existing_questions + existing_bank_questions
            if _is_duplicate_question(question_text, all_known_questions, subject_type=subject_type) or _has_batch_semantic_collision(question_text, all_known_questions, subject_type=subject_type):
                print(f"  [Anti-Duplicate] Bỏ qua câu hỏi bị trùng lặp với câu đã có: {question_text[:60]}...")
                continue

            # Kiểm tra tính bám sát giáo trình chương (Grounding Filter - Chống ảo giác lẫn chương)
            is_grounded, ground_msg = _validate_in_chapter_grounding(question_text, str(topic), theory_content)
            if not is_grounded:
                print(f"  [Grounding Filter] {ground_msg} (Bỏ qua câu: {question_text[:60]}...)")
                continue

            # Kiểm tra chống ảo giác TỔNG QUÁT (không phụ thuộc danh sách từ khóa cấm theo từng cặp môn)
            is_dyn_grounded, dyn_msg = _validate_dynamic_grounding(question_text, str(topic), theory_content)
            if not is_dyn_grounded:
                print(f"  [Dynamic Grounding Filter] {dyn_msg} (Bỏ qua câu: {question_text[:60]}...)")
                continue

            # Kiểm tra tính toàn vẹn chuyên ngành (Strict Cross-Discipline Quarantine - Chống lẫn chéo môn)
            is_disc, disc_msg = _validate_subject_discipline_integrity(question_text, str(topic), display_subject)
            if not is_disc:
                print(f"  [Discipline Quarantine] {disc_msg} (Bỏ qua câu: {question_text[:60]}...)")
                continue

            # Thẩm định tính học thuật bậc Đại học (Academic Rigor Filter - Chống toán lớp 7 f(x)=2x+1)
            is_rigorous, rigor_msg = _audit_academic_rigor(question_text, str(topic), str(raw_diff), str(raw_bloom), subject_type)
            if not is_rigorous:
                print(f"  [Academic Rigor] {rigor_msg} (Bỏ qua câu: {question_text[:60]}...)")
                continue

            # Nếu phát hiện bài tập còn chứa Tiếng Anh hoặc ngoại ngữ khác, tự động dùng AI dịch lại 100% dựa vào đúng NGỮ CẢNH GIÁO TRÌNH MÔN HỌC
            if _is_english_or_foreign(question_text) or _is_english_or_foreign(str(topic)) or _is_english_or_foreign(str(correct_answer)):
                print(f"  [AI Auto-Translator] Đang tự động dịch bài tập dựa theo đúng ngữ cảnh giáo trình môn học: {topic}")
                translated = _ai_translate_item_with_context(final_item, theory_balanced)
                if translated and isinstance(translated, dict):
                    final_item.update(translated)
                    topic = final_item.get("topic") or final_item.get("exerciseName") or topic
                    question_text = final_item.get("question_text") or final_item.get("question") or question_text
                    correct_answer = final_item.get("full_answer") or final_item.get("correct_answer") or correct_answer
                    detailed_sol = final_item.get("detailed_solution") or final_item.get("detailed_explanation") or detailed_sol

            if not topic or any(str(topic).startswith(prefix) for prefix in ["Chủ đề bài tập", "Bài tập tự luận", "Bài tập Nền tảng", "Bài tập Vận dụng", "Bài tập Nâng cao", "Chủ đề"]):
                if lesson_nam and len(lesson_nam) > 3:
                    topic = lesson_nam
                else:
                    # Trích xuất linh hoạt mệnh đề chủ đề từ câu đầu của đề bài
                    m_top = re.match(r'^(?:Cho|Xét|Trong|Hãy|Tính|Giải|Phân tích|Nêu|Trình bày|Dưới đây|Giả sử)\s+([^:,.?!]{4,60})', question_text)
                    if m_top:
                        raw_top = m_top.group(1).strip()
                        topic = raw_top[0].upper() + raw_top[1:]
                    else:
                        topic = f"Bài tập {display_subject} - Phần {len(db_exercises) + 1}"
            
            # Bác bỏ hoàn toàn đáp án trắc nghiệm A, B, C, D hoặc ký tự đơn
            ans_clean = str(correct_answer or "").lower().rstrip(".").strip()
            if ans_clean in ["a", "b", "c", "d", "đáp án a", "đáp án b", "đáp án c", "đáp án d", "a)", "b)", "c)", "d)"] or (len(ans_clean) == 1 and ans_clean.isalpha()):
                correct_answer = ""

            invalid_ans_set = {
                "", "0", "1", "null", "none", "chưa có đáp án", "tham khao kich ban ai",
                "tham khảo kịch bản ai", "tham khảo kịch bản sư phạm", "tham khao kich ban su pham",
                "đáp án 1", "đáp án 2", "đáp án 3", "a", "b", "c", "d",
                "kết quả chính xác 1", "kết quả chính xác 2", "kết quả chính xác 3",
                "a) kết quả ý a; b) kết quả ý b", "kết quả ý a", "kết quả ý b", "kết luận ý a", "kết luận ý b", "kết luận ý c",
                "xem chi tiết lời giải từng bước trong phần đáp án chi tiết.",
                "xem chi tiết lời giải", "xem chi tiết", "bài toán tự luận bám sát giáo trình.",
                "bài toán tự luận bám sát giáo trình"
            }

            # Trích xuất công thức / kết luận từ lời giải chi tiết (detailed_sol) nếu correct_answer bị thiếu
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
                        # Tìm công thức toán / kết luận trong detailed_sol
                        math_m = re.findall(r'\$([^$]+)\$', detailed_sol)
                        if math_m:
                            correct_answer = f"${math_m[-1]}$"
                        else:
                            sentences = re.split(r'(?<=[.!?])\s+', detailed_sol)
                            non_empty_sent = [s.strip() for s in sentences if len(s.strip()) > 10 and not _is_placeholder(s)]
                            if non_empty_sent:
                                correct_answer = " ".join(non_empty_sent[:2])

            if not correct_answer or _is_placeholder(correct_answer) or str(correct_answer).strip().lower() in invalid_ans_set:
                if detailed_sol and len(detailed_sol) > 10:
                    lines = [l.strip() for l in detailed_sol.splitlines() if l.strip()]
                    correct_answer = lines[-1]
                else:
                    correct_answer = f"Nghiệm và kết quả bài toán môn {display_subject}."
            if not detailed_sol:
                detailed_sol = correct_answer

            # Nếu correct_answer bị lẫn các bước giải bài (dài > 150 ký tự hoặc chứa từ khóa giải bước)
            if len(correct_answer) > 150 and any(kw in correct_answer.lower() for kw in ["đặt ", "bước 1", "bước 2", "phương trình này có thể giải", "để giải", "ta có"]):
                if not detailed_sol or len(detailed_sol) < len(correct_answer):
                    detailed_sol = correct_answer
                # Tìm dòng kết luận / đáp số cuối
                lines = [l.strip() for l in correct_answer.splitlines() if l.strip()]
                res_line = None
                for line in reversed(lines):
                    l_lower = line.lower()
                    if any(kw in l_lower for kw in ["vậy", "kết quả", "kết luận", "đáp số", "nghiệm", "=", "s =", "y =", "z =", "do đó", "từ đó"]):
                        res_line = line
                        break
                if res_line:
                    correct_answer = res_line
                elif lines:
                    correct_answer = lines[-1]

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
            topic = _clean_topic_name(topic, display_subject)

            # Chặn câu hỏi có 'topic'/'lesson_name' là placeholder AI trả nguyên văn từ mẫu prompt
            # (ví dụ "Chủ đề thực tế trong giáo trình", "Tên mục phần đầu...") thay vì tự đặt tên thật —
            # dấu hiệu AI đã cạn ý tưởng và sinh câu hỏi rỗng/chung chung, loại bỏ cả câu ngay tại đây
            # thay vì chỉ chặn ở question_text/đáp án (vốn có thể vẫn "đọc được" dù nội dung vô nghĩa).
            if _is_placeholder(topic) or _is_placeholder(lesson_nam):
                print(f"  [Placeholder Guard] Loại câu hỏi có topic/lesson_name là placeholder: topic={topic!r}, lesson_name={lesson_nam!r}")
                continue

            # Chặn rò rỉ ký tự tiếng Trung (thường gặp ở model suy luận gốc Trung Quốc) lẫn vào đề bài/đáp án —
            # vi phạm luật "100% Tiếng Việt chuẩn mực".
            if _has_cjk_chars(question_text) or _has_cjk_chars(correct_answer) or _has_cjk_chars(detailed_sol):
                print(f"  [CJK Guard] Loại câu hỏi lẫn ký tự tiếng Trung: {question_text!r}")
                continue

            # Chặn rò rỉ tiếng Anh (cũng thường gặp ở DeepSeek-R1) — phát hiện tổng quát qua mật độ ký
            # tự tiếng Việt có dấu, không cần liệt kê từ điển tiếng Anh.
            if _lacks_vietnamese_diacritics(question_text) or _lacks_vietnamese_diacritics(correct_answer) or _lacks_vietnamese_diacritics(detailed_sol):
                print(f"  [Language Guard] Loại câu hỏi lẫn tiếng Anh/ngôn ngữ khác: {question_text!r}")
                continue

            # Chặn câu hỏi STEM 'hỏi vẹt' lý thuyết suông, không có dữ liệu định lượng/công thức cụ thể
            # nào — vi phạm chính luật STEM đã đặt ra trong prompt (BẮT BUỘC có dữ liệu cụ thể, CẤM hỏi
            # lý thuyết trình bày suông) mà model đôi khi không tuân theo.
            if subject_type == "STEM" and _lacks_concrete_stem_data(question_text):
                print(f"  [Rote Question Guard] Loại câu hỏi STEM thiếu dữ liệu cụ thể/hỏi vẹt: {question_text!r}")
                continue

            # Loại bỏ các câu mở đầu lặp lại đề bài theo khuôn mẫu (ví dụ: 'Triết học Mác - Lênin được xem là bước tiến vì...')
            correct_answer = _clean_robotic_answer_prefix(question_text, correct_answer)

            # Chuẩn hóa mã hóa Enum cho Difficulty & Bloom
            diff_enum = _normalize_difficulty(str(raw_diff or "MEDIUM"))
            bloom_enum = _normalize_bloom(str(raw_bloom or "UNDERSTANDING"))

            diff_str = diff_enum.value.capitalize()
            bloom_str = bloom_enum.value.capitalize()

            # Tạo exercise code ngắn gọn <= 15 ký tự (để không bị Spring Boot substring(0, 15) cắt cụt)
            raw_ex_id = _clean_val(final_item.get("id"))
            current_count = len(db_exercises) + 1
            if not raw_ex_id or len(raw_ex_id) > 15:
                short_s = _generate_short_subject_code(display_subject or req.subject)
                c_num = chap_num if chap_num else "1"
                ex_id = f"{short_s}_C{c_num}_{current_count:02d}"
            else:
                ex_id = raw_ex_id

            ordered_item = {
                "id": ex_id,
                "lesson_number": lesson_num or "1.1",
                "lesson_name": lesson_nam or req.chapter,
                "topic": str(topic or f"Bài tập {display_subject}"),
                "theory_reference": str(final_item.get("theory_reference") or ""),
                "difficulty": diff_str,
                "bloom_level": bloom_str,
                "thought_process": str(final_item.get("thought_process") or ""),
                "question_text": str(question_text or "Chưa có nội dung câu hỏi"),
                "full_answer": str(correct_answer or "Chưa có đáp án"),
                "detailed_solution": detailed_sol,
                "scaffolding_steps": final_item.get("scaffolding_steps", []),
                "common_mistakes": final_item.get("common_mistakes", [])
            }

            clean_final_list.append(ordered_item)
            db_exercises.append(ExtractedExercise(
                exerciseCode=ordered_item["id"],
                exerciseName=ordered_item["topic"][:200],
                difficulty=diff_enum,
                bloomLevel=bloom_enum,
                question=ordered_item["question_text"],
                correctAnswer=str(correct_answer)
            ))

            # KHÔNG BREAK SỚM Ở ĐÂY: Phải duyệt hết danh sách LLM trả về (thường là 2 câu Easy/Medium)
            # để đảm bảo cả 2 câu đều được xử lý qua các bộ lọc.

        final_list = clean_final_list

        # 3.0 Câu Hard LUÔN do DeepSeek-R1 (model suy luận) đảm nhiệm riêng — KHÔNG còn là phương án cấp
        # cứu chờ Qwen thất bại nữa. Qwen ở Single-Pass phía trên giờ chỉ còn lo Easy/Medium (đúng sở
        # trường), tách hẳn câu Hard (dạng bài kết hợp nhiều bước/chứng minh Qwen hay làm hời hợt) sang
        # DeepSeek ngay từ đầu để giảm tải thật sự, thay vì chỉ giảm số lượng suông. Có lỗi gì cũng an
        # toàn: hàm tự bắt exception, trả None, luồng cũ (Emergency Generator) vẫn chạy tiếp bình thường.
        has_hard_already = any(ex.difficulty.value == "HARD" for ex in db_exercises)
        if not has_hard_already:
            already_used_topics_ds = [ex.exerciseName for ex in db_exercises] + existing_bank_topics
            ds_item = _generate_hard_exercise_with_deepseek(
                display_subject, display_chapter_name, theory_balanced,
                subject_type=subject_type, avoid_topics=already_used_topics_ds
            )
            if ds_item:
                q_txt = _clean_question_text(str(ds_item.get("question_text") or ""))
                q_txt = _clean_latex_string(_clean_math_vietnamese(q_txt))
                existing_qs = [ex.question for ex in db_exercises]
                all_known_qs = existing_qs + existing_bank_questions
                is_dup = _is_duplicate_question(q_txt, all_known_qs, subject_type=subject_type) or _has_batch_semantic_collision(q_txt, all_known_qs, subject_type=subject_type)
                is_grd, reason_grd = _validate_in_chapter_grounding(q_txt, str(ds_item.get("topic") or ""), theory_content)
                is_dyn_grd, reason_dyn_grd = _validate_dynamic_grounding(q_txt, str(ds_item.get("topic") or ""), theory_content)
                is_disc, reason_disc = _validate_subject_discipline_integrity(q_txt, str(ds_item.get("topic") or ""), display_subject)
                is_placeholder_ds = _is_placeholder(str(ds_item.get("topic") or "")) or _is_placeholder(str(ds_item.get("lesson_name") or ""))
                raw_ans_ds = str(ds_item.get("correct_answer") or ds_item.get("full_answer") or "")
                is_empty_answer_ds = _is_placeholder(raw_ans_ds)
                has_cjk_ds = _has_cjk_chars(q_txt) or _has_cjk_chars(raw_ans_ds) or _has_cjk_chars(ds_item.get("detailed_solution"))
                has_en_ds = (_lacks_vietnamese_diacritics(q_txt) or _lacks_vietnamese_diacritics(raw_ans_ds)
                             or _lacks_vietnamese_diacritics(ds_item.get("detailed_solution")))
                is_rote_ds = subject_type == "STEM" and _lacks_concrete_stem_data(q_txt)
                if (q_txt and len(q_txt) >= 15 and not is_dup and is_grd and is_dyn_grd and is_disc
                        and not is_placeholder_ds and not is_empty_answer_ds and not has_cjk_ds and not has_en_ds and not is_rote_ds):
                    ans_txt = _clean_latex_string(_clean_math_vietnamese(raw_ans_ds))
                    sol_txt = _clean_latex_string(_clean_math_vietnamese(str(ds_item.get("detailed_solution") or ans_txt)))
                    top_txt = _clean_topic_name(_clean_latex_string(_clean_math_vietnamese(str(ds_item.get("topic") or f"Bài tập {display_subject} nâng cao"))), display_subject)
                    short_s_ds = _generate_short_subject_code(display_subject or req.subject)
                    c_num_ds = chap_num if chap_num else "1"
                    ex_id_ds = f"{short_s_ds}_C{c_num_ds}_{len(db_exercises)+1:02d}"
                    db_exercises.append(ExtractedExercise(
                        exerciseCode=ex_id_ds,
                        exerciseName=top_txt[:200],
                        difficulty=_normalize_difficulty("Hard"),
                        bloomLevel=_normalize_bloom("Evaluating"),
                        question=q_txt,
                        correctAnswer=ans_txt
                    ))
                    final_list.append({
                        "id": ex_id_ds,
                        "lesson_number": ds_item.get("lesson_number", "1.9"),
                        "lesson_name": ds_item.get("lesson_name", req.chapter),
                        "topic": top_txt,
                        "difficulty": "Hard",
                        "bloom_level": "Evaluating",
                        "question_text": q_txt,
                        "full_answer": ans_txt,
                        "detailed_solution": sol_txt,
                        "scaffolding_steps": ds_item.get("scaffolding_steps", []),
                        "common_mistakes": ds_item.get("common_mistakes", [])
                    })
                    print(f"  [DeepSeek-R1] Đã thêm 1 câu Hard chất lượng cao vào đề.")
                else:
                    fail_reasons = []
                    if is_dup: fail_reasons.append("TRÙNG")
                    if not is_grd: fail_reasons.append(f"in_chapter_grounding: {reason_grd}")
                    if not is_dyn_grd: fail_reasons.append(f"dynamic_grounding: {reason_dyn_grd}")
                    if not is_disc: fail_reasons.append(f"discipline_integrity: {reason_disc}")
                    if is_placeholder_ds: fail_reasons.append("PLACEHOLDER topic/lesson_name")
                    if is_empty_answer_ds: fail_reasons.append("ĐÁP ÁN RỖNG")
                    if has_cjk_ds: fail_reasons.append("LẪN TIẾNG TRUNG")
                    if has_en_ds: fail_reasons.append("LẪN TIẾNG ANH")
                    if is_rote_ds: fail_reasons.append("HỎI VẸT/THIẾU DỮ LIỆU")
                    if not q_txt or len(q_txt) < 15: fail_reasons.append("QUÁ NGẮN")
                    print(f"  [DeepSeek-R1] Câu sinh ra không qua được bộ lọc, bỏ qua. Lý do: {' | '.join(fail_reasons) or '(không xác định)'}")

        if len(db_exercises) < 3:
            print(f"  [Emergency Generator] Chưa đủ 3 bài tập (hiện có {len(db_exercises)}/3). Đang tự động bổ sung từ lý thuyết {display_chapter_name}...")
            already_used_topics = [ex.exerciseName for ex in db_exercises] + existing_bank_topics
            fallback_items = _generate_fallback_exercises(display_subject, display_chapter_name, theory_balanced, subject_type=subject_type, avoid_topics=already_used_topics)
            if fallback_items:
                for idx, fb in enumerate(fallback_items, start=len(db_exercises)+1):
                    if len(db_exercises) >= 3:
                        break
                    q_txt = str(fb.get("question_text") or fb.get("question") or "Cho dữ kiện bài toán tự luận bám sát giáo trình.")
                    q_txt = _clean_question_text(q_txt)
                    if not q_txt or len(q_txt) < 15:
                        continue
                    q_txt = _clean_latex_string(_clean_math_vietnamese(q_txt))
                    existing_qs = [ex.question for ex in db_exercises]
                    all_known_qs = existing_qs + existing_bank_questions
                    if _is_duplicate_question(q_txt, all_known_qs, subject_type=subject_type) or _has_batch_semantic_collision(q_txt, all_known_qs, subject_type=subject_type):
                        continue
                    is_grd, _ = _validate_in_chapter_grounding(q_txt, str(fb.get("topic") or ""), theory_content)
                    if not is_grd:
                        continue
                    is_dyn_grd, _ = _validate_dynamic_grounding(q_txt, str(fb.get("topic") or ""), theory_content)
                    if not is_dyn_grd:
                        continue
                    is_disc, _ = _validate_subject_discipline_integrity(q_txt, str(fb.get("topic") or ""), display_subject)
                    if not is_disc:
                        continue
                    is_rig, _ = _audit_academic_rigor(q_txt, str(fb.get("topic") or ""), str(fb.get("difficulty", "MEDIUM")), str(fb.get("bloom_level", "UNDERSTANDING")), subject_type)
                    if not is_rig:
                        continue
                    # Chặn câu hỏi cấp cứu có topic/lesson_name là placeholder AI trả nguyên văn từ mẫu
                    # prompt (ví dụ "Chủ đề thực tế trong giáo trình") thay vì tự đặt tên thật — dấu hiệu
                    # model đã cạn ý tưởng sinh nội dung rỗng/chung chung dù question_text vẫn "đọc được".
                    if _is_placeholder(str(fb.get("topic") or "")) or _is_placeholder(str(fb.get("lesson_name") or "")):
                        print(f"  [Placeholder Guard] Loại câu cấp cứu có topic/lesson_name placeholder: {fb.get('topic')!r} / {fb.get('lesson_name')!r}")
                        continue
                    # Đáp án rỗng/giả (ví dụ "Xem chi tiết lời giải", "Chứng minh thành công") -> loại bỏ
                    # cả câu, không âm thầm thay bằng text mặc định như trước đây.
                    raw_ans_fb = str(fb.get("full_answer") or fb.get("correct_answer") or "")
                    if _is_placeholder(raw_ans_fb):
                        print(f"  [Placeholder Guard] Loại câu cấp cứu có đáp án rỗng/giả: {raw_ans_fb!r}")
                        continue
                    if _has_cjk_chars(q_txt) or _has_cjk_chars(raw_ans_fb) or _has_cjk_chars(fb.get("detailed_solution")):
                        print(f"  [CJK Guard] Loại câu cấp cứu lẫn ký tự tiếng Trung.")
                        continue
                    if (_lacks_vietnamese_diacritics(q_txt) or _lacks_vietnamese_diacritics(raw_ans_fb)
                            or _lacks_vietnamese_diacritics(fb.get("detailed_solution"))):
                        print(f"  [Language Guard] Loại câu cấp cứu lẫn tiếng Anh/ngôn ngữ khác.")
                        continue
                    if subject_type == "STEM" and _lacks_concrete_stem_data(q_txt):
                        print(f"  [Rote Question Guard] Loại câu cấp cứu STEM thiếu dữ liệu cụ thể/hỏi vẹt: {q_txt!r}")
                        continue
                    ans_txt = _clean_latex_string(_clean_math_vietnamese(raw_ans_fb))
                    sol_txt = str(fb.get("detailed_solution") or fb.get("detailed_explanation") or ans_txt)
                    sol_txt = _clean_latex_string(_clean_math_vietnamese(sol_txt))
                    top_txt = str(fb.get("topic") or fb.get("exerciseName") or f"Bài tập {display_subject} {len(db_exercises)+1}")
                    top_txt = _clean_latex_string(_clean_math_vietnamese(top_txt))
                    top_txt = _clean_topic_name(top_txt, display_subject)
                    diff_e = _normalize_difficulty(fb.get("difficulty", "MEDIUM"))
                    bloom_e = _normalize_bloom(fb.get("bloom_level", "UNDERSTANDING"))
                    diff_str = diff_e.value.capitalize() if hasattr(diff_e, "value") else str(diff_e).capitalize()
                    bloom_str = bloom_e.value.capitalize() if hasattr(bloom_e, "value") else str(bloom_e).capitalize()

                    short_s = _generate_short_subject_code(display_subject or req.subject)
                    c_num = chap_num if chap_num else "1"
                    ex_id = f"{short_s}_C{c_num}_{len(db_exercises)+1:02d}"
                    
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
                        "difficulty": diff_str,
                        "bloom_level": bloom_str,
                        "question_text": q_txt,
                        "full_answer": ans_txt,
                        "detailed_solution": sol_txt,
                        "scaffolding_steps": fb.get("scaffolding_steps", []),
                        "common_mistakes": fb.get("common_mistakes", [])
                    })

        # 3.2 Bộ cứu hộ trực tiếp từ giáo trình: ĐÃ TẮT theo yêu cầu — tầng này không dùng AI, chỉ bọc
        # nguyên văn đoạn giáo trình vào câu mẫu cứng ("Dựa trên kiến thức về chuyên đề '...'..."), văn
        # phong robot/boilerplate. Thà trả về ÍT CÂU HƠN (nhưng 100% do AI soạn thật) còn hơn độn đủ 3
        # câu bằng nội dung boilerplate. Giữ nguyên hàm _extract_exercises_directly_from_textbook và
        # khối code bên dưới (không xoá) để có thể bật lại nhanh nếu cần, chỉ đổi điều kiện kích hoạt.
        if ENABLE_TEXTBOOK_DIRECT_FALLBACK and len(db_exercises) < 3:
            print(f"  [Textbook Direct Extractor] Chưa đủ 3 câu (hiện có {len(db_exercises)}/3). Đang tự động trích xuất trực tiếp bài toán từ giáo trình {display_chapter_name}...")
            direct_items = _extract_exercises_directly_from_textbook(theory_content, display_subject, display_chapter_name, subject_type=subject_type)
            for fb in direct_items:
                if len(db_exercises) >= 3:
                    break
                q_txt = str(fb.get("question_text") or "")
                if not q_txt or len(q_txt) < 15:
                    continue
                q_txt = _clean_latex_string(_clean_math_vietnamese(q_txt))
                existing_qs = [ex.question for ex in db_exercises]
                all_known_qs = existing_qs + existing_bank_questions
                if _is_duplicate_question(q_txt, all_known_qs, subject_type=subject_type):
                    continue
                ans_txt = str(fb.get("full_answer") or fb.get("correct_answer") or "Xem chi tiết lời giải")
                ans_txt = _clean_latex_string(_clean_math_vietnamese(ans_txt))
                sol_txt = str(fb.get("detailed_solution") or ans_txt)
                sol_txt = _clean_latex_string(_clean_math_vietnamese(sol_txt))
                top_txt = str(fb.get("topic") or f"Bài tập {display_subject} {len(db_exercises)+1}")
                top_txt = _clean_topic_name(top_txt, display_subject)
                diff_e = _normalize_difficulty(fb.get("difficulty", "MEDIUM"))
                bloom_e = _normalize_bloom(fb.get("bloom_level", "UNDERSTANDING"))
                diff_str = diff_e.value.capitalize() if hasattr(diff_e, "value") else str(diff_e).capitalize()
                bloom_str = bloom_e.value.capitalize() if hasattr(bloom_e, "value") else str(bloom_e).capitalize()

                short_s = _generate_short_subject_code(display_subject or req.subject)
                c_num = chap_num if chap_num else "1"
                ex_id = f"{short_s}_C{c_num}_{len(db_exercises)+1:02d}"

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
                    "difficulty": diff_str,
                    "bloom_level": bloom_str,
                    "question_text": q_txt,
                    "full_answer": ans_txt,
                    "detailed_solution": sol_txt,
                    "scaffolding_steps": fb.get("scaffolding_steps", []),
                    "common_mistakes": fb.get("common_mistakes", [])
                })

        if len(db_exercises) == 0:
            err_msg = f"Mô hình AI không trích xuất được bài tập hợp lệ nào. Lý do có thể: AI chỉ sinh ra câu hỏi mẫu (placeholder) do nội dung file không chứa đủ kiến thức chuyên môn. Kích thước file: {len(theory_balanced)} ký tự. File: {target_file}"
            print(f"[Multi-Agent] THẤT BẠI: {err_msg}")
            raise HTTPException(status_code=500, detail=err_msg)

        # Cố định đúng 3 bài tập chất lượng cao (ưu tiên 1 Easy, 1 Medium, 1 Hard)
        if len(db_exercises) > 3:
            easy_idx = [i for i, ex in enumerate(db_exercises) if ex.difficulty.value == "EASY"]
            medium_idx = [i for i, ex in enumerate(db_exercises) if ex.difficulty.value == "MEDIUM"]
            hard_idx = [i for i, ex in enumerate(db_exercises) if ex.difficulty.value == "HARD"]
            
            selected_indices = []
            if easy_idx: selected_indices.append(easy_idx[0])
            if medium_idx: selected_indices.append(medium_idx[0])
            if hard_idx: selected_indices.append(hard_idx[0])
            
            # Nếu chưa đủ 3 câu đại diện các mức khó, lấp đầy bằng các câu còn lại
            for i in range(len(db_exercises)):
                if len(selected_indices) >= 3:
                    break
                if i not in selected_indices:
                    selected_indices.append(i)
                    
            selected_indices.sort()
            db_exercises = [db_exercises[i] for i in selected_indices[:3]]
            final_list = [final_list[i] for i in selected_indices[:3]]

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

            # Chỉ ép nhãn lại khi 3 câu THỰC SỰ có độ sâu Bloom khác biệt nhau ngay từ gốc (AI tự phân hoá
            # được thật). Nếu cả 3 câu vốn dĩ cùng 1 mức Bloom (model không tự phân hoá được), việc ép 1 câu
            # thành "Hard" chỉ là DÁN NHÃN GIẢ lên nội dung thực chất vẫn dễ như nhau — đây chính là nguyên
            # nhân câu "Hard" nhiều khi đọc chẳng thấy khó hơn "Easy" là bao. Trường hợp này giữ nguyên nhãn
            # gốc của AI, không cưỡng ép tạo ra sự phân hoá giả tạo.
            original_priorities = [bloom_priority.get(ex.bloomLevel.value.capitalize(), 1) for ex in db_exercises]
            has_real_spread = len(set(original_priorities)) >= 2

            if not has_real_spread:
                print("  [DiffRebalancer] Bỏ qua — 3 câu có cùng mức Bloom gốc, giữ nguyên nhãn thật của AI thay vì ép phân hoá giả tạo.")
            else:
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
            "subject": display_subject or req.subject,
            "chapter_number": chap_num if chap_num else safe_chap,
            "chapter_name": req.chapter,
            "questions": clean_final_list if clean_final_list else final_list
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


# ENDPOINT: DELETE /v1/exercises/question-bank/{subject}/{chapter}/{exercise_code}
# Xóa 1 câu hỏi khỏi file question_bank JSON trên đĩa của ai_api (nguồn dữ liệu module AI Chat
# (ai_engine.py) đọc trực tiếp) — cần thiết vì khi admin xóa bài tập trên Spring Boot, chỉ xóa được
# hàng trong Postgres (exercise_ai); container spring_api không mount /app/prompts nên không thể tự
# xóa trong file JSON, phải gọi sang endpoint này để ai_api xóa hộ, tránh AI Chat vẫn dùng câu đã xóa.
@router.delete("/question-bank/{subject}/{chapter}/{exercise_code}")
async def delete_question_from_bank(subject: str, chapter: str, exercise_code: str):
    from core.mapping import get_mapped_paths
    mapped_subj, mapped_chap = get_mapped_paths(subject, chapter)
    json_path = os.path.join(settings.BASE_DIR, "prompts", mapped_subj, "question_bank", f"{mapped_chap}.json")

    if not os.path.exists(json_path):
        return {"success": True, "removed": False, "message": f"Không tìm thấy file {json_path}, không có gì để xóa."}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        questions = data.get("questions", []) if isinstance(data, dict) else []
        new_questions = [q for q in questions if str(q.get("id") or "") != exercise_code]
        removed = len(new_questions) != len(questions)
        if removed:
            data["questions"] = new_questions
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return {"success": True, "removed": removed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi xóa câu hỏi khỏi question_bank: {str(e)}")
