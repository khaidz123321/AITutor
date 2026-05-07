import streamlit as st
from engine.rag_service import RAGService
from engine.ai_engine import AItutor 
from engine.scaffolding import LearningScaffold # Import thêm Thầy Giáo Vụ
from langchain_core.messages import HumanMessage, AIMessage
from core.config import settings

# 1. Cấu hình trang chuẩn PTIT
st.set_page_config(page_title="Gia sư AI - PTIT Academic", page_icon="🎓", layout="wide")

# 2. Khởi tạo dịch vụ (Dùng cache để giữ trạng thái bộ não)
@st.cache_resource
def init_services():
    rag = RAGService()
    tutor = AItutor()
    # Khởi tạo Scaffolding không cần DB cho bản demo
    scaffold = LearningScaffold(db=None) 
    return rag, tutor, scaffold

rag_service, ai_tutor, scaffold_manager = init_services()

# --- KHỞI TẠO STATE MANAGEMENT (BỘ NHỚ TẠM) ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_step" not in st.session_state:
    st.session_state.current_step = 1

# Hàm tự động reset bộ nhớ khi người dùng đổi Môn học hoặc Chương
def reset_learning_session():
    st.session_state.messages = []
    st.session_state.current_step = 1

# 3. Sidebar quản lý hệ thống
st.sidebar.title("📚 Kho tri thức PTIT")
subject = st.sidebar.selectbox(
    "Chọn môn học:",
    ["giai_tich_1", "triet_hoc_maclenin", "lap_trinh_c++"],
    on_change=reset_learning_session # Tự động xóa chat khi đổi môn
)

chapter = st.sidebar.selectbox(
    "Chọn chương đang học:",
    ["chuong_1", "chuong_2", "chuong_3"],
    on_change=reset_learning_session # Tự động xóa chat khi đổi chương
)

# TỰ ĐỘNG GÁN ID KHỚP VỚI MÔN HỌC
if subject == "giai_tich_1":
    # Ổ khóa và Chìa khóa đã khớp nhau 100%
    st.session_state.current_question_id = "GT1_C1_1.1_001" 
elif subject == "triet_hoc_maclenin":
    st.session_state.current_question_id = "TRIET_C3_3.1_001"
else:
    st.session_state.current_question_id = "CPP_001"

st.sidebar.markdown("---")
# Hiển thị tiến độ trực quan trên thanh bên
st.sidebar.success(f"**📍 Tiến độ hiện tại: Bước {st.session_state.current_step}**")
st.sidebar.info(f"**📝 Đang giải bài:** {st.session_state.current_question_id}")
st.sidebar.markdown("---")

# Reset thủ công phiên học
if st.sidebar.button("🔄 Bắt đầu bài mới / Xóa lịch sử"):
    reset_learning_session()
    st.rerun()

# 4. Giao diện Chat chính
st.title(f"🎓 Gia sư AI: {subject.replace('_', ' ').title()}")
st.info(f"Chào Khải! Tôi là gia sư {subject}. Hãy cùng giải quyết bài tập nhé.")

# Hiển thị các tin nhắn cũ
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. Xử lý câu hỏi và kết nối Toàn bộ Hệ thống
if prompt := st.chat_input("Nhập câu trả lời hoặc hỏi gợi ý..."):
    # Hiển thị tin nhắn người dùng
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Gia sư đang phân tích câu trả lời..."):
            
            # BƯỚC 1: Lấy ngữ cảnh RAG (Đã có thuật toán lọc rác)
            context = rag_service.query_context(subject=subject, query=prompt)
            
            # BƯỚC 2: Load dữ liệu bài tập và lấy Mật thư Scaffolding
            question_data = ai_tutor.load_question_data(
                subject=subject, 
                chapter=chapter, 
                question_id=st.session_state.current_question_id
            )
            scaffold_instruction = scaffold_manager.get_current_instruction(
                current_step=st.session_state.current_step,
                question_data=question_data
            )
            
            # BƯỚC 3: Chuyển đổi lịch sử chat
            chat_history_objs = []
            for m in st.session_state.messages[:-1]: 
                if m["role"] == "user":
                    chat_history_objs.append(HumanMessage(content=m["content"]))
                else:
                    chat_history_objs.append(AIMessage(content=m["content"]))

            # BƯỚC 4: Gọi não bộ AItutor (Đã truyền đủ tham số và xử lý Object)
            try:
                eval_result = ai_tutor.get_response(
                    subject=subject,
                    chapter=chapter,
                    question_id=st.session_state.current_question_id,
                    user_message=prompt,
                    chat_history=chat_history_objs,
                    scaffold_instruction=scaffold_instruction,
                    rag_context=context
                )
                
                if eval_result:
                    ai_reply = eval_result.response
                    new_step = eval_result.next_step
                    
                    st.markdown(ai_reply)
                    
                    # Lưu lịch sử chat
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                    
                    # CẬP NHẬT TIẾN ĐỘ: Nếu AI phán qua bước, cập nhật lên giao diện
                    if new_step != st.session_state.current_step:
                        st.session_state.current_step = new_step
                        st.rerun() # Tải lại trang để cập nhật con số bên Sidebar
                        
                else:
                    st.warning("Hệ thống đang bận. Vui lòng thử lại.")
                
            except Exception as e:
                st.error(f"Lỗi hệ thống: {str(e)}")