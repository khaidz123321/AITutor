        // =====================================================
// AI CHAT PAGE - FASTAPI INTEGRATION
// =====================================================
(function () {
    // 1. CẤU HÌNH ĐỊA CHỈ BACKEND (FastAPI của Khải)
    // Nếu trong router.py dùng prefix, nhớ đổi thành "http://127.0.0.1:8000/api/chat"
    const API_BASE_URL = "http://127.0.0.1:8000/chat"; 

    // Lấy thông tin môn học và chương từ URL (VD: ?id=1&ch=0)
    const params    = new URLSearchParams(window.location.search);
    const courseId  = parseInt(params.get('id')) || 1; 
    const chapterIdx = parseInt(params.get('ch')) || 0;

    // =====================================================
    // 2. DỮ LIỆU MÔN HỌC (Giải tích 1 & Triết học Mác-Lênin)
    // =====================================================
    const COURSE_NAMES = {
        1: "Giải tích 1",
        2: "Triết học Mác - Lênin"
    };

    const CHAPTERS = {
        1: [
            'Giới hạn của dãy số', 
            'Hàm số một biến số', 
            'Đạo hàm và vi phân', 
            'Phép tính tích phân', 
            'Lí thuyết chuỗi'
        ],
        2: [
            'Triết học và vai trò của triết học trong đời sống xã hội',
            'Chủ nghĩa duy vật biện chứng',
            'Chủ nghĩa duy vật lịch sử'
        ],
        default: ['Nội dung đang cập nhật']
    };

    // Xác định dữ liệu cho phiên học hiện tại
    const courseTitle = COURSE_NAMES[courseId] || "Môn học PTIT";
    const chapters = CHAPTERS[courseId] || CHAPTERS.default;
    const safeChapterIdx = (chapterIdx >= 0 && chapterIdx < chapters.length) ? chapterIdx : 0;
    const currentChapter = chapters[safeChapterIdx];

    const SUGGESTIONS = [
        'Giải thích khái niệm cơ bản',
        'Cho tôi một ví dụ minh họa',
        'Hướng dẫn giải bài tập'
    ];

    let isTyping = false;

    // ==========================================
    // 3. KHỞI TẠO BÀI HỌC VÀ GỌI API /INIT
    // ==========================================
    async function init() {
        // Cập nhật giao diện (Header, Title, Back button)
        document.title = `Gia sư AI: ${currentChapter} - PTIT`;
        document.getElementById('chatCourseName').textContent = courseTitle;
        document.getElementById('chatChapterName').textContent = currentChapter;
        document.getElementById('backBtn').href = `course-detail.html?id=${courseId}`;

        // Vẽ Sidebar danh sách chương
        document.getElementById('chatChapters').innerHTML = chapters.map((ch, i) => `
            <a href="ai-chat.html?id=${courseId}&ch=${i}" class="session-card ${i === safeChapterIdx ? 'active' : ''}" style="display:block;text-decoration:none;margin-bottom:8px;">
                <div class="session-title" style="font-size:13px;">Chương ${i + 1}: ${ch}</div>
                <span class="status-badge ${i < safeChapterIdx ? '' : i === safeChapterIdx ? 'pending' : 'locked'}" style="margin-top:4px;">
                    ${i < safeChapterIdx ? 'Hoàn thành' : i === safeChapterIdx ? 'Đang học' : 'Chưa học'}
                </span>
            </a>`).join('');

        // Cập nhật nút gợi ý
        document.getElementById('quickSuggestions').innerHTML =
            SUGGESTIONS.map(s => `<button class="suggestion-chip" onclick="sendSuggestion('${s}')">${s}</button>`).join('');

        // Gọi Backend lấy câu chào mừng
        showTyping(); // Hiện dấu 3 chấm
        try {
            // Thay đổi URL sao cho khớp với biến môn học và chương của Khải
            const response = await fetch(`${API_BASE_URL}/init?subject=${encodeURIComponent(courseTitle)}&chapter=${encodeURIComponent(currentChapter)}`);
            const data = await response.json();
            
            removeTyping(); // Tắt dấu 3 chấm
            
            // 1. NẾU CÓ LỊCH SỬ -> VẼ LẠI TOÀN BỘ
            if (data.history && data.history.length > 0) {
                data.history.forEach(item => {
                    // Chuyển đổi role cho khớp với hàm appendMessage (user/ai)
                    const role = item.role === 'user' ? 'user' : 'ai';
                    appendMessage(role, item.content);
                });
            } 
            // 2. NẾU KHÔNG CÓ LỊCH SỬ -> IN RA CÂU CHÀO
            else if (data.reply) {
                appendMessage('ai', data.reply);
            }

            // Lưu lại ID bài tập đang làm
            if (data.question_id) {
                currentQuestionId = data.question_id;
            }

        } catch (error) {
            console.error("Lỗi khởi tạo:", error);
            removeTyping();
            appendMessage('ai', 'Lỗi kết nối máy chủ. Vui lòng thử lại sau.');
        }
    }

    // ==========================================
    // 4. HIỂN THỊ TIN NHẮN (RENDER MARKDOWN & MATHJAX)
    // ==========================================
    function appendMessage(type, text) {
        const container = document.getElementById('chatMessages');
        const isUser    = type === 'user';
        const label     = isUser ? 'Tôi' : 'AI';
        const div       = document.createElement('div');
        div.className   = `msg-row ${type}`;
        
        // Nếu là AI thì dịch Markdown sang HTML (để in đậm, xuống dòng). User thì in thường.
        let contentHTML = text;
        if (!isUser && typeof marked !== 'undefined') {
            contentHTML = marked.parse(text);
        }

        div.innerHTML   = `
            <div class="msg-avatar ${type}">${label}</div>
            <div class="msg-bubble">${contentHTML}</div>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;

        // Báo cho MathJax biết có nội dung mới để vẽ công thức Toán
        if (!isUser && window.MathJax) {
            setTimeout(() => {
                MathJax.typesetPromise([div]);
            }, 50);
        }
    }

    // ==========================================
    // 5. GỬI TIN NHẮN LÊN BACKEND (API CHAT)
    // ==========================================
    async function sendMessage(text) {
        if (!text.trim() || isTyping) return;
        isTyping = true;
        
        appendMessage('user', text);
        document.getElementById('chatInput').value = '';
        document.getElementById('chatInput').style.height = 'auto';
        document.getElementById('sendBtn').disabled = true;
        document.getElementById('quickSuggestions').style.display = 'none';

        showTyping();

        try {
            // Lưu ý: Kiểm tra router.py xem có phải đổi '/' thành '/chat' không
            const response = await fetch(`${API_BASE_URL}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    subject: courseTitle,
                    chapter: currentChapter,
                    message: text
                })
            });

            const data = await response.json();
            removeTyping();
            
            const aiReply = data.reply || data.response || "Hệ thống AI xử lý lỗi định dạng.";
            appendMessage('ai', aiReply);

        } catch (error) {
            console.error("Lỗi gửi Chat:", error);
            removeTyping();
            appendMessage('ai', 'Hệ thống đang bận hoặc gián đoạn kết nối. Vui lòng thử lại sau.');
        } finally {
            isTyping = false;
            document.getElementById('sendBtn').disabled = false;
        }
    }

    // ==========================================
    // 6. CÁC HÀM TIỆN ÍCH UI
    // ==========================================
    function showTyping() {
        const container = document.getElementById('chatMessages');
        const div       = document.createElement('div');
        div.className   = 'msg-row ai';
        div.id          = 'typingIndicator';
        div.innerHTML   = `
            <div class="msg-avatar ai">AI</div>
            <div class="typing-indicator">
                <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
            </div>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    function removeTyping() { document.getElementById('typingIndicator')?.remove(); }
    window.sendSuggestion = (text) => sendMessage(text);

    // ==========================================
    // 7. KHỞI CHẠY KHI TẢI XONG TRANG
    // ==========================================
    document.addEventListener('DOMContentLoaded', () => {
        const chatForm = document.getElementById('chatForm');
        const input    = document.getElementById('chatInput');

        // BƯỚC 1: PHẢI CHẶN RELOAD TRƯỚC (Bất kể API có lỗi hay không)
        if (chatForm) {
            chatForm.addEventListener('submit', (e) => {
                e.preventDefault(); 
                if (input) sendMessage(input.value.trim());
            });
        }

        // BƯỚC 2: GẮN SỰ KIỆN PHÍM ENTER
        if (input) {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault(); // Chặn form submit mặc định
                    sendMessage(input.value.trim());
                }
            });

            // Tự giãn nở ô nhập liệu
            input.addEventListener('input', () => {
                input.style.height = 'auto';
                input.style.height = Math.min(input.scrollHeight, 120) + 'px';
            });
        }

        // BƯỚC 3: GỌI INIT CUỐI CÙNG VÀ BỌC TRONG TRY-CATCH
        // Việc gọi init ở cuối giúp đảm bảo các Listener ở trên đã được gắn thành công
        (async () => {
            try {
                await init();
            } catch (err) {
                console.warn("Init gặp lỗi nhưng hệ thống chat vẫn hoạt động:", err);
            }
        })();
    });
})();