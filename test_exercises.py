import asyncio
import sys
import os

# Cấu hình môi trường giả lập
os.environ["DEEPSEEK_MODEL"] = "mock-deepseek"
os.environ["OLLAMA_MODEL"] = "mock-qwen"

sys.path.append(r"d:\Project\AITutor\AI")

from schemas.exercise import GenerateFromTheoryRequest
from controller.endpoints import exercises

# MOCK LLM
def mock_call_llm(model: str, messages: list, temperature: float, response_format: dict = None) -> str:
    print(f"[MOCK LLM] Model: {model}")
    if "deepseek" in model:
        # Giả lập DeepSeek trả về JSON rỗng hoặc chỉ có tag <think>
        return "<think>Tôi không thể xử lý</think>\n"
    elif "qwen" in model:
        # Giả lập Qwen fallback sinh JSON
        return """
        {
          "data": [
            {
              "id": "COURSE_1_001",
              "difficulty": "Easy",
              "bloom_level": "Understanding",
              "question_text": "Dưới đây là bài toán: 1 + 1 bằng bao nhiêu?",
              "correct_answer": "2",
              "detailed_explanation": "Vì 1 thêm 1 là 2."
            }
          ]
        }
        """
    return "{}"

exercises._call_llm = mock_call_llm

async def main():
    req = GenerateFromTheoryRequest(
        subject="course_1",
        chapter="chuong_1"
    )
    
    # Tạo mock file lý thuyết
    os.makedirs(r"d:\Project\AITutor\AI\data\rag_input\course_1", exist_ok=True)
    with open(r"d:\Project\AITutor\AI\data\rag_input\course_1\test_giai_tich_1_chuong_1_chuong_1_chuong_1.txt", "w", encoding="utf-8") as f:
        f.write("# CHƯƠNG 1\nNội dung lý thuyết test.")

    try:
        res = await exercises.generate_from_theory(req)
        print("SUCCESS:", res)
    except Exception as e:
        print("FAILED WITH EXCEPTION:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
