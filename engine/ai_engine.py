from core.config import settings
import os 
import json 
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import HumanMessage, AIMessage

class AItutor:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            api_key = settings.GOOGLE_API_KEY,
            model = settings.MODEL_NAME,
            temperature = settings.TEMPERATURE
        )
        # lưu trữ 5 lượt hỏi đáp
        self.window_size = 10 
    
    def load_persona(self, subject: str) -> str:
        """
        Tự động tìm file persona dựa theo biến (subject).
        --- ĐỌC CÁC QUY TẮC SƯ PHẠM ---
        """
        persona_path = os.path.join(settings.BASE_DIR, "prompts", subject, "assignment_persona.txt")
        try: 
            with open(persona_path, "r", encoding = "utf-8") as f:
                return f.read()
        except FileNotFoundError:
            print("Lỗi không tìm file Assignment")
            return "Bạn là Gia sư AI. Hãy hướng dẫn sinh viên tận tình, tuyệt đối không giải hộ toàn bộ đáp án."
        
    def load_question_data(self, subject: str, chapter: str):
        """
        Tự động tìm file JSON bài tập dựa trên 2 biến: môn học và chương.
        --- LẤY NỘI DUNG CÂU HỎI + TRẢ LỜI ---
        """
        json_path = os.path.join(settings.BASE_DIR, "prompts", subject, "question_bank", f"{chapter}.json")
        try:
            with open(json_path, "r", encoding = "utf-8") as f:
                data = json.load(f)
                return json.dumps(data, ensure_ascii=False)
        except FileNotFoundError:
            print("Lỗi không  tìm thấy file JSON")
            return "Dữ liệu bài tập đang bị lỗi hệ thống."
    
    def get_response(self, subject: str, chapter: str, user_message: str, chat_history: list, scaffold_instruction: str, rag_context: str) -> str:
        """
        Hàm xử lý: Trộn Prompt, ghép lịch sử chat và trả về câu trả lời.
        """
        # nạp dữ liệu + ngữ cảnh
        persona_text = self.load_persona(subject)
        json_context = self.load_question_data(subject, chapter)

        # xây dựng prompt
        system_template = SystemMessagePromptTemplate.from_template(
            "SYSTEM PERSONA:\n{persona}\n\n"
            "PEDAGOGICAL GUIDANCE (SCAFFOLDING):\n{scaffold_instruction}\n\n"
            "REFERENCE KNOWLEDGE (RAG):\n{rag_context}\n\n"
            "ASSIGNMENT DATA:\n{context}\n\n"
            "STRICT OPERATIONAL RULES:\n"
            "1. INTENT RECOGNITION:\n"
            "   - If the student asks for 'theory', 'concepts', or 'reference materials': Be generous and detailed. Use the REFERENCE KNOWLEDGE (RAG) to explain and provide relevant snippets to help them learn.\n"
            "   - If the student is working on an 'exercise' or 'assignment': Strictly follow the SCAFFOLDING guidance. Do NOT provide the final answer. Provide hints for the current step or ask leading questions to help them think.\n"
            
            "2. TONE & ENCOURAGEMENT:\n"
            "   - Always maintain a supportive and motivating academic tone. Use phrases like 'You're on the right track!', 'Great effort, let's look at this part again', or 'Keep going, you're almost there!'\n"
            "   - Never just say 'No' or 'I can't'. Always pivot to a helpful hint or a piece of theory from the documents.\n"
            
            "3. ACADEMIC INTEGRITY:\n"
            "   - Bridge theory to practice. Tell the student: 'According to the PTIT textbook, [concept] is defined as... How can we apply this to your current problem?'\n"
            "   - Ensure that the student remains the primary problem-solver.\n"
            
            "4. RESPONSE LANGUAGE: You MUST communicate with the student entirely in VIETNAMESE."
        )
        human_template = HumanMessagePromptTemplate.from_template("{user_input}")

        chat_prompt = ChatPromptTemplate.from_messages([
            system_template,
            MessagesPlaceholder(variable_name = "chat_history"),
            human_template
        ])

        # tạo pipeline xử lí
        chain = chat_prompt | self.llm 

        # xử lí lịch sử chat cắt ngắn
        # Tự động cắt bỏ các tin nhắn cũ, chỉ giữ lại số lượng bằng window_size
        trimmed_history = chat_history[-self.window_size:] if len(chat_history) > self.window_size else chat_history

        # Goi AI
        response = chain.invoke({
            "persona": persona_text,
            "scaffold_instruction": scaffold_instruction,
            "rag_context": rag_context,
            "context": json_context,
            "chat_history": trimmed_history,
            "user_input": user_message
        })

        return response.content