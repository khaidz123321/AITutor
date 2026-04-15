import streamlit as st
from engine.rag_service import RAGService
from engine.ai_engine import AItutor # Import bộ não chính thức của bạn
from langchain_core.messages import HumanMessage, AIMessage
from core.config import settings

# 1. Cấu hình trang chuẩn PTIT
st.set_page_config(page_title="Gia sư AI - PTIT Academic", page_icon="🎓", layout="wide")

# 2. Khởi tạo dịch vụ (Dùng cache để giữ trạng thái bộ não)
@st.cache_resource
def init_services():
    # Khởi tạo RAG để tìm tài liệu và AItutor làm bộ não xử lý
    rag = RAGService()
    tutor = AItutor()
    return rag, tutor

rag_service, ai_tutor = init_services()

# 3. Sidebar quản lý môn học và chương
st.sidebar.title("📚 Kho tri thức PTIT")
subject = st.sidebar.selectbox(
    "Chọn môn học:",
    ["giai_tich_1", "triet_hoc_maclenin"]
)

# Thêm chọn chương vì ai_engine cần biến này để nạp bài tập JSON
chapter = st.sidebar.selectbox(
    "Chọn chương đang học:",
    ["chuong_1", "chuong_2", "chuong_3"]
)

if st.sidebar.button("Xóa lịch sử trò chuyện"):
    st.session_state.messages = []
    st.rerun()

# 4. Giao diện Chat chính
st.title(f"🎓 Gia sư AI: {subject.replace('_', ' ').title()}")
st.info(f"Chào Khải! Tôi là gia sư {subject}. Hãy hỏi tôi bất cứ điều gì về {chapter.replace('_', ' ')}.")

# Khởi tạo bộ nhớ tin nhắn Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = []

# Hiển thị các tin nhắn cũ
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. Xử lý câu hỏi và kết nối Não bộ
if prompt := st.chat_input("Nhập câu hỏi hoặc yêu cầu bài tập..."):
    # Hiển thị tin nhắn người dùng
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Gia sư đang tra cứu giáo trình và chuẩn bị phản hồi..."):
            
            # BƯỚC 1: Lấy ngữ cảnh từ kho tri thức PDF (RAG)
            context = rag_service.query_context(subject=subject, query=prompt)
            
            # BƯỚC 2: Chuyển đổi lịch sử chat từ Streamlit (dict) sang LangChain (Object)
            # ĐÂY LÀ CHÌA KHÓA FIX LỖI MẤT TRÍ NHỚ
            chat_history_objs = []
            for m in st.session_state.messages[:-1]: # Lấy các câu trước câu vừa hỏi
                if m["role"] == "user":
                    chat_history_objs.append(HumanMessage(content=m["content"]))
                else:
                    chat_history_objs.append(AIMessage(content=m["content"]))

            # BƯỚC 3: Gọi trực tiếp bộ não AItutor của bạn
            # Không cần gọi llm.invoke ở đây nữa, ai_engine sẽ lo hết
            try:
                # Bạn có thể điều chỉnh scaffold_instruction tùy theo mục đích demo
                scaffold_instruction = (
                    "Student requires support. Implement SCAFFOLDING rules: For practice problems, offer ONLY a hint for the first step without giving the solution. For conceptual or theoretical queries, provide a comprehensive and detailed explanation."
                )
                
                answer = ai_tutor.get_response(
                    subject=subject,
                    chapter=chapter,
                    user_message=prompt,
                    chat_history=chat_history_objs,
                    scaffold_instruction=scaffold_instruction,
                    rag_context=context
                )
                
                st.markdown(answer)
                # Lưu câu trả lời vào lịch sử
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                st.error(f"Lỗi kết nối bộ não AI: {str(e)}")