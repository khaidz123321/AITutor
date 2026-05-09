from core.config import settings
import os 
import json 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from schemas.evaluation import StudentEvaluation
from core.mapping import get_mapped_paths

class AItutor:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            api_key = settings.GOOGLE_API_KEY,
            model = settings.MODEL_NAME,
            temperature = settings.TEMPERATURE
        )
        # lưu trữ 2 lượt hỏi đáp
        self.window_size = 10
    
    def get_first_question_id(self, subject: str, chapter: str) -> str:
        """
        Tự động mở file JSON của môn/chương tương ứng và lấy ID của bài tập đầu tiên.
        """
        mapped_subj, mapped_chap = get_mapped_paths(subject, chapter)
        
        json_path = os.path.join(settings.BASE_DIR, "prompts", mapped_subj, "question_bank", f"{mapped_chap}.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                questions = data.get("questions", [])
                if questions:
                    return questions[0]["id"]
        except Exception as e:
            print(f"Error finding first question: {str(e)}")
        # Fallback
        return "GT1_C1_001" if subject == "Giải tích 1" else "TRIET_C1_001"
    
    def load_persona(self, subject: str) -> str:
        """Tự động tìm file persona dựa theo bộ dịch Mapping"""
        # Gọi bộ dịch (vì persona không cần chapter nên truyền chuỗi rỗng)
        mapped_subj, _ = get_mapped_paths(subject, "") 
        
        persona_path = os.path.join(settings.BASE_DIR, "prompts", mapped_subj, "assignment_persona.txt")
        try: 
            with open(persona_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print(f"Lỗi không tìm file Assignment cho môn: {mapped_subj}")
            return "You are an AI Tutor. Guide the student step-by-step with patience."
        
    def load_question_data(self, subject: str, chapter: str, question_id: str):
        """
        Chỉ load đúng 1 bài tập đang làm thay vì bê cả chương.
        Tiết kiệm 90% Token và giúp AI không bị nhầm lẫn kịch bản.
        """
        mapped_subj, mapped_chap = get_mapped_paths(subject, chapter)
        
        json_path = os.path.join(settings.BASE_DIR, "prompts", mapped_subj, "question_bank", f"{mapped_chap}.json")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for question in data.get("questions", []):
                    if question["id"] == question_id:
                        return json.dumps(question, ensure_ascii=False)
                return "SYSTEM ERROR: Question ID not found."
        except FileNotFoundError:
            return f"SYSTEM ERROR: File {mapped_chap}.json not found in {mapped_subj}."
        
    def get_initial_question(self, subject: str, chapter: str, question_id: str) -> str:
        """
        Trích xuất đề bài từ JSON và tạo câu chào mừng sinh viên bắt đầu làm bài.
        Dùng cho Endpoint /init của API.
        """
        json_data = self.load_question_data(subject, chapter, question_id)

        # Nếu hàm load_question_data trả về thông báo lỗi (SYSTEM ERROR)
        if "SYSTEM ERROR" in json_data:
            return "Hệ thống đang bảo trì dữ liệu bài tập này. Bạn vui lòng quay lại sau nhé!"

        try:
            # Parse JSON để lấy nội dung câu hỏi
            data = json.loads(json_data)
            question_text = data.get("question_text", "Không tìm thấy nội dung câu hỏi.")

            welcome_message = (
                f"Chào bạn! Chúng ta cùng bắt đầu giải bài toán này nhé:\n\n"
                f"**Đề bài:** {question_text}\n\n"
                f"Bạn đã có ý tưởng nào để bắt đầu chưa? Hãy cho tôi biết suy nghĩ của bạn nhé."
            )
            return welcome_message
            
        except json.JSONDecodeError:
            return "Lỗi hệ thống: Dữ liệu bài tập không hợp lệ. Vui lòng báo cáo với quản trị viên."
    
    def get_response(self, subject: str, chapter: str, user_message: str, chat_history: list, scaffold_instruction: str, rag_context: str, question_id: str) -> str:
        """
        Hàm xử lý Single-Agent: 
        Vừa đánh giá (Evaluate) vừa sinh câu trả lời (Generate) trong 1 lần gọi API duy nhất.
        """
        # 1. Nạp dữ liệu + ngữ cảnh
        persona_text = self.load_persona(subject)
        json_context = self.load_question_data(subject, chapter, question_id)

        # 2. Xử lý lịch sử chat cắt ngắn
        trimmed_history = chat_history[-self.window_size:] if len(chat_history) > self.window_size else chat_history

        # 3. Khởi tạo LLM với Structured Output ép kiểu theo StudentEvaluation
        structured_llm = self.llm.with_structured_output(StudentEvaluation)

        # 4. Thiết lập System Prompt hợp nhất
        system_prompt = (
            "## ROLE & PERSONA\n"
            "{persona}\n\n"
            "## PROBLEM CONTEXT (Question Bank & Steps)\n"
            "{json_context}\n\n"
            "## RETRIEVED KNOWLEDGE (RAG)\n"
            "{rag_context}\n\n"
            "## CURRENT SCAFFOLDING OBJECTIVE\n"
            "{scaffold_instruction}\n\n"
            "## YOUR TASK — TWO STEPS IN ONE RESPONSE\n"
            "**Step 1 — Diagnose** (Internal reasoning, invisible to the student):\n"
            "Analyze the student's input and classify:\n"
            "- cognitive_state: Must be one of [STEP_CORRECT, PROBLEM_COMPLETED, INCOMPLETE, "
            "CALCULATION_ERROR, CONCEPTUAL_ERROR, VAGUE_OR_OFFTOPIC, REQUEST_HINT, REQUEST_THEORY, REVEAL_ANSWER]\n"
            "- emotion_state: Must be one of [NEUTRAL, FRUSTRATED, LACK_CONFIDENCE]\n\n"
            "FRUSTRATION CONTROL RULE: If the chat history shows the student has been stuck, provided incorrect answers, or shown continuous confusion for 3 or more consecutive attempts on the current step, you MUST set cognitive_state to 'REVEAL_ANSWER'.\n\n"
            "**Step 2 — Respond** (Based on the diagnosis):\n"
            "1. STEP_CORRECT → Briefly praise the student and seamlessly guide them to the next logical sub-step.\n"
            "2. PROBLEM_COMPLETED → Congratulate them, summarize the key takeaways, and conclude the problem.\n"
            "3. INCOMPLETE → Explicitly acknowledge the correct portion, then ask a probing question to extract the missing condition or step.\n"
            "4. CALCULATION_ERROR → Point out the general area of the mistake (e.g., signs, arithmetic rules). DO NOT fix it for them.\n"
            "5. CONCEPTUAL_ERROR → Use [RAG_CONTEXT] and common mistakes to formulate a Socratic question that exposes their misunderstanding.\n"
            "6. VAGUE_OR_OFFTOPIC → Gently redirect the student's focus back to the current scaffolding objective.\n"
            "7. REQUEST_HINT → Provide a minimal, indirect hint to spark their thinking without giving away the exact operation.\n"
            "8. REQUEST_THEORY → Provide a clear, detailed explanation using [RAG_CONTEXT], then connect it back to the current problem.\n\n"
            "**Emotion Handling**: If the emotion_state is FRUSTRATED or LACK_CONFIDENCE, you MUST begin your `response` with an empathetic, encouraging sentence.\n\n"
            "9. REVEAL_ANSWER → DO NOT ask any more questions. Extract the correct solution from the [PROBLEM CONTEXT] for the current step, explain it clearly to the student, comfort them so they don't feel discouraged, and gently guide them to the next step.\n\n"
            "## CONSTRAINTS\n"
            "- The `response` field MUST be written entirely in natural, fluent VIETNAMESE.\n"
            "- Limit the `response` to a MAXIMUM of 4 sentences (Smart Brevity).\n"
            "- Use Markdown and LaTeX ($) for all mathematical formulas and expressions.\n"
            "- NEVER reveal the final answer or do the computation for the student (UNLESS the cognitive_state is REVEAL_ANSWER. In that case, you are ALLOWED and REQUIRED to reveal the answer)."        )

        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{user_input}")
        ])

        # 5. Lắp ghép Chain và gọi API đúng 1 lần
        chain = chat_prompt | structured_llm
        eval_result = chain.invoke({
            "persona": persona_text,
            "json_context": json_context,
            "rag_context": rag_context,
            "scaffold_instruction": scaffold_instruction,
            "chat_history": trimmed_history,
            "user_input": user_message
        })
        return eval_result