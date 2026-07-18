"""
Quản lý tiến trình học tập.
Task: Đọc cấu trúc JSON của bài tập, theo dõi sinh viên đang ở bước nào 
và tạo Chỉ thị (Instruction) nghiêm ngặt để điều phối AI.
"""

import json 
from sqlalchemy.orm import Session

class LearningScaffold:
    def __init__(self, db: Session = None):
        # Giữ lại connection db để sau này dùng cho việc cập nhật Activity (Tiến độ)
        self.db = db
    
    def get_current_instruction(self, current_step: int, question_data: str) -> str:
        """
        Trích xuất thông tin Bước hiện tại từ JSON và tạo "Mật thư" dặn dò AI.
        
        Args:
            current_step (int): Bước hiện tại mà sinh viên đang làm (lấy từ DB).
            question_data (str): Chuỗi JSON chứa duy nhất 1 bài tập hiện tại.
            
        Returns:
            str: Câu lệnh hướng dẫn (Instruction) để nhúng vào System Prompt của AI.
        """
        try:
            # 1. Chuyển chuỗi JSON thành Dictionary của Python
            data = json.loads(question_data) 
            
            # Khắc phục triệt để Vấn đề 8: Dùng đúng key "scaffolding_steps"
            scaffolding_steps = data.get("scaffolding_steps", [])
            
            # 2. Tìm khối dữ liệu của bước hiện tại
            target_step = next((s for s in scaffolding_steps if s.get("step_number") == current_step), None)

            # Nếu không tìm thấy bước (ví dụ sinh viên đã làm xong bước cuối cùng)
            if not target_step:
                return "STATUS: The student has completed all steps of this problem. Summarize the key takeaways, praise their effort, and ask if they are ready for the next problem."
            
            # 3. Trích xuất Mục tiêu (step_detail) và Gợi ý (hint)
            step_detail = target_step.get("step_detail", "Require the student to complete the current step.")
            hint = target_step.get("hint", "No specific hint available. Ask guiding questions to encourage student reasoning.")

            # 4. Đóng gói thành Chỉ thị Sư phạm (Instruction) bằng Tiếng Anh
            instruction_to_ai = (
                f"--- CURRENT STATE & OBJECTIVE ---\n"
                f"The student is currently working on Step {current_step}.\n"
                f"Target Objective for this step: '{step_detail}'\n\n"
                
                f"--- TUTORING DIRECTIVES & BEHAVIOR ---\n"
                f"1. EVALUATE SEMANTICALLY: Analyze the student's input to see if it mathematically or logically satisfies the Target Objective. Accept variations in wording or equivalent mathematical expressions.\n"
                f"2. GUIDE, DO NOT SOLVE: You are a Socratic tutor. If the student is stuck, incorrect, or asks for help, use this hint: '{hint}'. Formulate your response as a leading question or a conceptual nudge. NEVER give the final answer, complete formula, or direct calculation for this step.\n"
                f"3. STRICT STEP ISOLATION: Focus 100% on Step {current_step}. Absolutely DO NOT mention, preview, or hint at any subsequent steps. Keep the student's cognitive load focused on the current task.\n"
                f"4. ERROR HANDLING: If the student makes a mistake, gently point out the specific area they need to re-evaluate instead of just saying 'wrong'. (e.g., 'Check the sign on the second term').\n"
                f"5. FORMATTING: Always use standard LaTeX formatting for mathematical symbols and equations (e.g., use $x^2 + y^2$ for inline math, and $$...$$ for standalone display equations).\n"
                f"6. TONE: Maintain a supportive, encouraging, and academically professional tone. Validate their effort."
            )

            return instruction_to_ai

        except json.JSONDecodeError:
            return "SYSTEM ERROR: Corrupt or invalid JSON data. Please inform the student."
        except Exception as e:
            print(f"Scaffolding Error: {str(e)}")
            return "Guide the student to solve the problem step by step slowly."