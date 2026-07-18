"""
Script restore dau tieng Viet + sua loi nhan dang ky tu OCR bang LLM.
- Chay SAU clean_data.py va clean_rag_input.py (da don rac cau truc).
- Xoay vong 4 provider: Cerebras -> Groq -> OpenRouter -> Gemini.
- Co checkpoint o muc CHUNK (khong phai chi file) -> dung giua chung
  chay lai se tiep tuc dung tu chunk bi dang, khong mat tien do.
- BAT BUOC giu nguyen cong thuc toan hoc ($...$, \\frac, \\sqrt, ^, _ ...).

Cach dung:
    cd D:\\Project\\AITutor\\AI
    python ProcessData\\clean\\clean_ocr_with_llm.py
"""

import json
import os
import re
import sys
import time
from dotenv import load_dotenv

# Duong dan goc toi thu muc AI (file nam trong ProcessData/clean/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAG_INPUT_DIR   = os.path.join(BASE_DIR, "data", "rag_input")
CHECKPOINT_FILE = os.path.join(os.path.dirname(__file__), "clean_ocr_checkpoint.json")

load_dotenv(os.path.join(BASE_DIR, ".env"))
sys.stdout.reconfigure(encoding="utf-8")

# ─── Khoi tao clients ────────────────────────────────────────────────────────
from openai import OpenAI

def _get_local_client() -> OpenAI:
    """
    Tạo OpenAI client mỗi lần gọi để đọc OLLAMA_BASE_URL mới nhất từ env.
    Tránh phải restart server khi đổi URL ngrok trong .env.
    """
    load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    return OpenAI(
        api_key="sk-no-key-required",
        base_url=base_url,
        default_headers={"ngrok-skip-browser-warning": "true"}
    )

def _get_model() -> str:
    load_dotenv(os.path.join(BASE_DIR, ".env"), override=True)
    return os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# ─── Config ────────────────────────────────────────────────────────────────────
CHUNK_SIZE    = 1500   # ky tu moi chunk gui cho LLM (du ngu canh, khong qua dai)
CHUNK_OVERLAP = 0      # KHONG overlap — moi chunk doc lap, ghep lai theo thu tu

SYSTEM_PROMPT = """You are an expert in correcting Vietnamese text that has OCR errors, extracted from university textbooks (Mathematics / Philosophy).

TASK: Restore Vietnamese diacritics, fix character recognition errors, and reconstruct broken sentences in the text below.

MANDATORY RULES:
1. PRESERVE 100% of all mathematical notation: $...$, \\frac, \\sqrt, ^, _, variables, LaTeX formulas. DO NOT touch any mathematical symbol whatsoever.
2. PRESERVE the heading structure (#, ##, ###...) and section numbering (1.1.2....). MERGE broken words that belong to the same sentence into a single line. REMOVE unnatural line breaks within a sentence.
3. ONLY restore Vietnamese diacritics and fix character recognition errors in REGULAR TEXT (not formulas).
   Example: "S6 phuc" -> "Số phức", "tap so thuc" -> "tập số thực", "dinh nghia" -> "định nghĩa".
4. DO NOT add, remove, paraphrase, or summarize content. Only fix spelling/diacritic errors and reconstruct lines.
5. DO NOT add explanations, markdown code blocks, or any text outside the corrected content.
6. If a passage is already spelled correctly, leave it unchanged — do not over-correct.

Return ONLY the restored text content, nothing else."""


# ─── Checkpoint ────────────────────────────────────────────────────────────────
def load_checkpoint(subject: str = "global"):
    checkpoint_file = os.path.join(RAG_INPUT_DIR, subject, f"clean_ocr_checkpoint_{subject}.json") if subject != "global" else CHECKPOINT_FILE
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[CHECKPOINT] Tiep tuc cho {subject} - da xong {len(data.get('done_files', []))} files, "
              f"{len(data.get('partial', {}))} file dang do dang")
        data["_checkpoint_file"] = checkpoint_file
        return data
    return {"done_files": [], "partial": {}, "_checkpoint_file": checkpoint_file}

def save_checkpoint(data):
    checkpoint_file = data.get("_checkpoint_file", CHECKPOINT_FILE)
    os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)
    with open(checkpoint_file, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in data.items() if k != "_checkpoint_file"}, f, ensure_ascii=False, indent=2)


# ─── Chunking — cat theo doan van (paragraph) de khong vo cau ──────────────────
def chunk_text(text: str, size: int = CHUNK_SIZE) -> list:
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 2 <= size:
            current = current + "\n\n" + p if current else p
        else:
            if current:
                chunks.append(current)
            # Doan qua dai, cat cung theo size
            if len(p) > size:
                for i in range(0, len(p), size):
                    chunks.append(p[i:i + size])
                current = ""
            else:
                current = p
    if current:
        chunks.append(current)
    return chunks


# ─── Goi tung provider ─────────────────────────────────────────────────────────
def call_local_llm(text: str) -> str:
    client = _get_local_client()  # Đọc URL mới nhất từ .env mỗi lần gọi
    model  = _get_model()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        max_tokens=4000,
        temperature=0.1,
        stream=True
    )
    full_text = ""
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            full_text += content
    return full_text.strip()

# ─── Hau xu ly output ──────────────────────────────────────────────────────────
def strip_wrapper(text: str) -> str:
    """Xoa markdown code block neu LLM lo boc ```...``` quanh ket qua."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()

def strip_thinking(text: str) -> str:
    """Xóa phần <think>...</think> mà reasoning model (qwen3) đôi khi leak ra."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()

# ─── Clean 1 chunk voi local LLM ──────────────────────────────────────
def clean_chunk(chunk: str) -> str:
    if len(chunk.strip()) < 20:
        return chunk  # chunk qua ngan (dong trong, separator) -> giu nguyen

    for attempt in range(3): # Thử lại tối đa 3 lần nếu lỗi
        try:
            result = call_local_llm(chunk)
            result = strip_wrapper(result)
            result = strip_thinking(result)
            
            # Reject cứng nếu vẫn còn sót tag <think> (bị cắt giữa chừng, không đóng được)
            if "<think>" in result or "</think>" in result:
                print(f"\n  [INVALID] Còn sót thẻ <think>, thử lại...", end=" ")
                continue
            
            # Đếm số chữ cái và số thực tế (bỏ qua khoảng trắng, dấu chấm, ký tự đặc biệt)
            an_chunk = len(re.sub(r'[^\w\s]', '', chunk.replace('\n', '').replace(' ', '')))
            an_result = len(re.sub(r'[^\w\s]', '', result.replace('\n', '').replace(' ', '')))
            
            # Kết quả hợp lệ nếu nội dung chữ/số đạt ít nhất 30% so với gốc
            if result and (an_result > an_chunk * 0.3 or len(result) > len(chunk) * 0.5):
                print(f"[Ollama OK]", end=" ", flush=True)
                return result
            else:
                print(f"\n  [WARN] Kết quả trả về quá ngắn! (len_an={an_result}/{an_chunk}). Nội dung: {result[:100]}...", end=" ")
        except Exception as e:
            err = str(e)
            print(f"\n  [ERROR] {err[:60]}. Thu lai lan {attempt+1}...", end=" ")
            time.sleep(1)
            continue

    print("\n  [FAILED] Giu nguyen chunk goc sau 3 lan thu")
    return chunk


# ─── Xu ly 1 file ──────────────────────────────────────────────────────────────
def process_file(filepath: str, file_key: str, checkpoint: dict):
    with open(filepath, "r", encoding="utf-8") as f:
        original = f.read()

    chunks = chunk_text(original)
    total = len(chunks)

    # Lay tien do da co (neu dang do dang)
    partial = checkpoint["partial"].get(file_key, {"cleaned_chunks": [], "next_index": 0})
    cleaned_chunks = partial["cleaned_chunks"]
    start_index    = partial["next_index"]

    print(f"  Tong chunks: {total} | Da xong: {start_index}")

    for i in range(start_index, total):
        print(f"  Chunk {i+1}/{total}...", end=" ", flush=True)
        cleaned = clean_chunk(chunks[i])
        cleaned_chunks.append(cleaned)
        print("OK")

        # Luu checkpoint sau MOI chunk — dam bao khong mat tien do
        checkpoint["partial"][file_key] = {
            "cleaned_chunks": cleaned_chunks,
            "next_index": i + 1
        }
        save_checkpoint(checkpoint)

    # Ghep lai va ghi de file goc
    final_text = "\n\n".join(cleaned_chunks)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(final_text)

    # Danh dau file da hoan thanh, xoa partial
    checkpoint["done_files"].append(file_key)
    if file_key in checkpoint["partial"]:
        del checkpoint["partial"][file_key]
    save_checkpoint(checkpoint)

    print(f"  => Da ghi de file sach: {os.path.basename(filepath)}")


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("  CLEAN OCR BANG LLM - Khoi phuc dau tieng Viet")
    print("=" * 65)

    checkpoint = load_checkpoint()

    import glob
    txt_files = sorted(glob.glob(os.path.join(RAG_INPUT_DIR, "**", "*.txt"), recursive=True))

    if not txt_files:
        print("Khong tim thay file .txt nao trong", RAG_INPUT_DIR)
        return

    print(f"\nTim thay {len(txt_files)} file can xu ly\n")

    for filepath in txt_files:
        file_key = os.path.relpath(filepath, RAG_INPUT_DIR).replace("\\", "/")

        if file_key in checkpoint["done_files"]:
            print(f"[SKIP] {file_key} — da xong")
            continue

        print(f"\n[FILE] {file_key}")
        process_file(filepath, file_key, checkpoint)

    # Xoa checkpoint khi tat ca da xong
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print("\n" + "=" * 65)
    print("  HOAN THANH! Toan bo file da duoc khoi phuc dau tieng Viet.")
    print("  -> Chay reindex_rag.py de nap lai du lieu sach vao Vector DB.")
    print("=" * 65)


if __name__ == "__main__":
    main()