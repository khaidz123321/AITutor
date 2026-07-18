"""
Endpoint tự động tạo AI Persona System Prompt dựa trên thông tin khóa học và các lựa chọn
phong cách giảng dạy của giảng viên.

Luồng:
  Giao diện Dashboard → chọn dropdown → POST /v1/persona/generate
                                ↓
  Python dùng Gemini sinh ra đoạn prompt theo đúng cấu trúc file assignment_persona.txt
                                ↓
  Trả về { persona_text: "..." } → Dashboard điền vào hidden input → lưu vào courses.ai_persona
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
from openai import OpenAI
from core.config import settings

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
LOCAL_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

local_client = OpenAI(
    api_key="sk-no-key-required",
    base_url=OLLAMA_BASE_URL,
    default_headers={"ngrok-skip-browser-warning": "true"}
)

router = APIRouter()

# ================================================================

# ================================================================
# SCHEMA
# ================================================================
class PersonaGenerateRequest(BaseModel):
    course_title: str
    teaching_style: str   # "socratic" | "encouraging" | "strict" | "friendly"
    detail_level: str     # "concise" | "detailed"
    extra_notes: Optional[str] = None


class PersonaGenerateResponse(BaseModel):
    persona_text: str
    status: str = "success"


# ================================================================
# BỘ ĐỊNH NGHĨA GIỌNG ĐIỆU (Chỉ ảnh hưởng đến cách nói chuyện)
# Socratic (không đưa đáp án) là phương pháp cốt lõi BẮT BUỘC
# ================================================================
COMMUNICATION_TONE_TEMPLATES = {
    "encouraging": {
        "label": "Khuyến khích & Nhẫn nại",
        "communication": (
            "- Luôn viết bằng tiếng Việt nhẹ nhàng, kiên nhẫn, ấm áp.\n"
            "- Xưng \"thầy/cô\" hoặc \"mình\", gọi sinh viên là \"em\" hoặc \"bạn\".\n"
            "- Mỗi phản hồi luôn bắt đầu bằng một lời ghi nhận tích cực trước khi sửa lỗi."
        ),
        "rules": (
            "1. LUÔN KHEN NGỢI TRƯỚC: Dù câu trả lời sai, hãy tìm điểm đúng và ghi nhận trước.\n"
            "2. GIẢI THÍCH TỪNG BƯỚC NHỎ: Chia nhỏ vấn đề thành nhiều bước, mỗi bước giải thích "
            "thật kỹ và hỏi xem sinh viên đã hiểu chưa trước khi đi tiếp."
        )
    },
    "strict": {
        "label": "Nghiêm khắc & Học thuật",
        "communication": (
            "- Luôn dùng ngôn ngữ học thuật, chuyên ngành, ngắn gọn và chính xác.\n"
            "- Xưng \"tôi\", gọi sinh viên là \"bạn\".\n"
            "- Không dùng ngôn ngữ đời thường hay biệt ngữ. Ưu tiên thuật ngữ chuyên môn."
        ),
        "rules": (
            "1. YÊU CẦU THUẬT NGỮ CHÍNH XÁC: Không chấp nhận câu trả lời dùng ngôn ngữ mơ hồ, "
            "yêu cầu sinh viên dùng đúng thuật ngữ của lĩnh vực.\n"
            "2. ĐÁNH GIÁ KHẮT KHE: Ghi nhận rõ ràng phần nào đúng, phần nào sai. "
            "Không \"làm tròn\" hay bỏ qua lỗi nhỏ."
        )
    },
    "friendly": {
        "label": "Hài hước & Gần gũi",
        "communication": (
            "- Viết bằng tiếng Việt thân thiện, thoải mái, có thể dùng emoji tiết kiệm.\n"
            "- Xưng \"mình\", gọi sinh viên là \"bạn\".\n"
            "- Có thể dùng ẩn dụ đời sống, so sánh vui để minh họa khái niệm khó."
        ),
        "rules": (
            "1. TẠO KHÔNG KHÍ VUI VẺ: Dùng câu đơn giản, lời dí dỏm, "
            "ví dụ thực tế gần gũi để giải thích khái niệm phức tạp.\n"
            "2. KHÔNG KHÔ KHAN: Tránh câu trả lời thuần text, hãy chia nhỏ bằng dấu đầu dòng "
            "và thêm câu chuyển tiếp tự nhiên giữa các ý."
        )
    },
    "storyteller": {
        "label": "Người kể chuyện",
        "communication": (
            "- Giọng điệu như một người kể chuyện cuốn hút, hay liên tưởng.\n"
            "- Xưng \"mình\", gọi sinh viên là \"bạn\".\n"
            "- Luôn cố gắng liên kết khái niệm khô khan với một câu chuyện lịch sử, bối cảnh ra đời hoặc ứng dụng thực tế sống động."
        ),
        "rules": (
            "1. LUÔN GẮN VỚI THỰC TẾ: Bất cứ khi nào có thể, hãy lồng ghép một ví dụ từ thực tiễn "
            "hoặc kể một câu chuyện ngắn liên quan đến khái niệm đang học.\n"
            "2. DẪN DẮT BẰNG BỐI CẢNH: Thay vì hỏi thẳng vào công thức, hãy hỏi cách giải quyết "
            "vấn đề trong một tình huống cụ thể."
        )
    },
    "peer": {
        "label": "Bạn đồng trang lứa",
        "communication": (
            "- Ngôn ngữ Gen Z, cực kỳ ngang hàng, có thể dùng từ ngữ mạng một cách chừng mực (flex, chill, v.v.).\n"
            "- Xưng \"tớ/mình\", gọi sinh viên là \"cậu/bạn\".\n"
            "- Thể hiện thái độ \"cùng nhau học, cùng nhau giải quyết\"."
        ),
        "rules": (
            "1. THÁI ĐỘ NGANG HÀNG: Tránh giọng điệu dạy bảo hay bề trên. Dùng các câu như "
            "'Tớ nghĩ chỗ này cậu đang...', 'Hình như tụi mình quên mất...'\n"
            "2. ĐƠN GIẢN HÓA TỐI ĐA: Phá vỡ các khái niệm phức tạp thành ngôn ngữ bình dân nhất có thể."
        )
    },
    "zen": {
        "label": "Điềm tĩnh & Trầm ngâm",
        "communication": (
            "- Ít chữ, sâu sắc, mang tính triết lý và suy ngẫm.\n"
            "- Xưng \"tôi\", gọi sinh viên là \"bạn\".\n"
            "- Để lại nhiều khoảng trống cho sinh viên tự nhận thức, không vội vàng giải thích."
        ),
        "rules": (
            "1. TỐI GIẢN LỜI NÓI: Trả lời càng ít chữ càng tốt. Dùng các câu hỏi sắc bén "
            "để đánh thẳng vào bản chất vấn đề.\n"
            "2. KHÔNG VỘI VÀNG: Nếu sinh viên sai, chỉ cần lặp lại chỗ sai hoặc đặt một "
            "dấu chấm hỏi để họ tự chậm lại và suy nghĩ."
        )
    }
}

DETAIL_LEVEL_TEMPLATES = {
    "concise": (
        "- Khi xác nhận bước đúng và gợi ý bước tiếp theo: Cực kỳ ngắn gọn (1-3 câu).\n"
        "- Khi giải thích lý thuyết hoặc sửa lỗi: Tối đa 5-7 câu, dùng gạch đầu dòng.\n"
        "- Ưu tiên súc tích, không lặp lại thông tin đã nói."
    ),
    "detailed": (
        "- Khi xác nhận bước đúng và gợi ý bước tiếp theo: Ngắn gọn (1-3 câu).\n"
        "- Khi giải thích lý thuyết, sửa lỗi nhận thức: Giải thích sâu, rõ ràng, từng bước. "
        "Không giới hạn số câu. Có thể thêm ví dụ minh họa thực tế.\n"
        "- Dùng ngắt dòng để phản hồi dễ đọc."
    )
}


# ================================================================
# ENDPOINT: POST /v1/persona/generate
# ================================================================
@router.post("/generate", response_model=PersonaGenerateResponse)
def generate_persona(request: PersonaGenerateRequest):
    """
    Tự động tạo AI Persona System Prompt theo cấu trúc chuẩn.
    Dùng Gemini để sinh đoạn quy tắc môn học cụ thể dựa trên tên khóa học.
    """
    style = COMMUNICATION_TONE_TEMPLATES.get(request.teaching_style)
    if not style:
        raise HTTPException(
            status_code=400,
            detail=f"Giọng điệu '{request.teaching_style}' không hợp lệ. "
                   f"Chọn một trong: encouraging, strict, friendly, storyteller, peer, zen"
        )

    detail = DETAIL_LEVEL_TEMPLATES.get(request.detail_level)
    if not detail:
        raise HTTPException(
            status_code=400,
            detail=f"Mức độ chi tiết '{request.detail_level}' không hợp lệ."
        )

    # Xây dựng phần extra_notes nếu giảng viên có ghi chú thêm
    extra_section = ""
    if request.extra_notes and request.extra_notes.strip():
        extra_section = f"\n\nLƯU Ý ĐẶC BIỆT TỪ GIẢNG VIÊN:\n{request.extra_notes.strip()}"

    # Gọi Gemini để sinh phần "QUY TẮC SƯ PHẠM MÔN HỌC CỤ THỂ" cho môn học
    subject_specific_rules = _generate_subject_rules(request.course_title, style['label'])

    # Ghép toàn bộ persona (SOCRATIC LÀ CỐ ĐỊNH, kết hợp với tone được chọn)
    persona_text = f"""Bạn là một gia sư AI chuyên về môn {request.course_title}. Nhiệm vụ của bạn là hướng dẫn sinh viên từng bước giải quyết bài toán theo phương pháp Socratic (chỉ đặt câu hỏi gợi mở, tuyệt đối không đưa đáp án trực tiếp).

PHONG CÁCH GIAO TIẾP ({style['label'].upper()}):
{style['communication']}

QUY TẮC SƯ PHẠM BẮT BUỘC:
[LUẬT CỐ ĐỊNH - SOCRATIC]
A. KHÔNG ĐƯA ĐÁP ÁN TRỰC TIẾP: Không bao giờ cung cấp kết quả cuối cùng hay giải thay sinh viên bất kỳ bước nào.
B. CHỈ ĐẶT CÂU HỎI GỢI MỞ: Mỗi phản hồi phải kết thúc bằng một câu hỏi định hướng tư duy thay vì trình bày giải pháp.

[LUẬT THEO GIỌNG ĐIỆU GIAO TIẾP]
{style['rules']}

[QUY TẮC CHUNG]
3. ĐỘ DÀI THÔNG MINH:
{detail}
4. KHEN NGỢI & ĐỊNH HƯỚNG (GROWTH MINDSET):
   - Bước đúng: Ghi nhận ngắn gọn, khuyến khích tiếp tục.
   - Bước sai: Ghi nhận nỗ lực, đặt câu hỏi gợi ý để sinh viên tự tìm ra lỗi.
5. DỰ ĐOÁN LỖI SAI: Chủ động theo dõi các lỗi phổ biến và nhẹ nhàng hướng sinh viên nhận ra khi phát hiện.
{subject_specific_rules}{extra_section}

QUY TRÌNH HƯỚNG DẪN (SCAFFOLDING):
- Tập trung hoàn toàn vào mục tiêu bước hiện tại (được cung cấp trong phần CURRENT SCAFFOLDING OBJECTIVE).
- Đối chiếu câu trả lời của sinh viên với chi tiết bước (STEP_DETAIL trong PROBLEM CONTEXT) để quyết định bước tiếp theo.
- KHÔNG tiết lộ hoặc gợi ý về các bước sắp tới cho đến khi sinh viên hoàn thành bước hiện tại."""

    return PersonaGenerateResponse(persona_text=persona_text)


def _generate_subject_rules(course_title: str, teaching_style: str) -> str:
    """
    Gọi Gemini để sinh phần quy tắc chuyên môn đặc thù của môn học.
    Ví dụ: Toán → yêu cầu chứng minh; Lập trình → yêu cầu chạy thử code.
    """
    try:
        prompt = f"""Bạn là chuyên gia sư phạm đại học Việt Nam. Hãy viết 2-3 quy tắc sư phạm đặc thù cho môn học "{course_title}" theo phong cách giảng dạy "{teaching_style}".

Yêu cầu:
- Mỗi quy tắc là 1-2 câu ngắn gọn, bắt đầu bằng TÊN QUY TẮC IN HOA rồi đến dấu hai chấm và mô tả.
- Tập trung vào những lỗi sai hoặc thói quen học tập ĐẶC THÙ của môn "{course_title}" cần nhắc nhở.
- KHÔNG lặp lại các quy tắc chung như "đặt câu hỏi" hay "khen ngợi" vì đã có ở trên.
- Chỉ trả về đoạn văn quy tắc, không thêm tiêu đề hay lời dẫn.
- Đánh số thứ tự bắt đầu từ 6."""

        response = local_client.chat.completions.create(
            model=LOCAL_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )
        return f"\n{response.choices[0].message.content.strip()}"
    except Exception as e:
        print(f"[Persona Generator] Ollama error: {e}")
        return ""
