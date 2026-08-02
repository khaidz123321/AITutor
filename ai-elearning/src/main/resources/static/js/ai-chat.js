// =====================================================
// AI CHAT PAGE - No emoji
// =====================================================
(function () {
    const params = new URLSearchParams(window.location.search);
    const courseId = parseInt(params.get('id')) || 1;
    const activeLessonId = parseInt(params.get('les')) || 0;

    let isTyping = false;
    let currentCourse = null;
    let enrolledData = null;
    let lessons = [];
    let activeLesson = null;

    const MATH_TEMPLATES = [
        { label: '√', latex: '\\sqrt{}', offset: 6 },
        { label: 'x²', latex: '^{}', offset: 2 },
        { label: 'xᵢ', latex: '_{}', offset: 2 },
        { label: '½', latex: '\\frac{}{}', offset: 6 },
        { label: 'log', latex: '\\log_{}{}', offset: 6 },
        { label: 'π', latex: '\\pi', offset: 3 },
        { label: 'sin', latex: '\\sin{}', offset: 5 },
        { label: 'cos', latex: '\\cos{}', offset: 5 },
        { label: 'tan', latex: '\\tan{}', offset: 5 },
        { label: '∑', latex: '\\sum_{}^{}', offset: 7 },
        { label: '∫', latex: '\\int_{}^{}', offset: 7 },
        { label: '∞', latex: '\\infty', offset: 7 },
        { label: 'α', latex: '\\alpha', offset: 6 },
        { label: 'β', latex: '\\beta', offset: 5 },
        { label: 'θ', latex: '\\theta', offset: 6 }
    ];

    function isCursorInMathBlock(textarea) {
        const pos = textarea.selectionStart;
        const textBefore = textarea.value.substring(0, pos);
        const dollarCount = (textBefore.match(/\$/g) || []).length;
        return dollarCount % 2 !== 0;
    }

    function insertMathTemplate(textarea, template) {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const value = textarea.value;
        const selectedText = value.substring(start, end);
        
        const inMath = isCursorInMathBlock(textarea);
        let latex = template.latex;
        let offset = template.offset;
        
        if (selectedText.length > 0 && latex.endsWith('}')) {
            if (latex.endsWith('{}')) {
                latex = latex.substring(0, latex.length - 2) + '{' + selectedText + '}';
                offset = latex.length;
            }
        }
        
        let textToInsert = latex;
        let finalOffset = offset;
        
        if (!inMath) {
            textToInsert = '$' + latex + '$';
            finalOffset = offset + 1;
        }
        
        const newValue = value.substring(0, start) + textToInsert + value.substring(end);
        textarea.value = newValue;
        
        const newCursorPos = start + finalOffset;
        textarea.focus();
        textarea.setSelectionRange(newCursorPos, newCursorPos);
        
        textarea.dispatchEvent(new Event('input'));
    }

    function updateMathPreview() {
        const input = document.getElementById('chatInput');
        const previewContainer = document.getElementById('mathPreviewContainer');
        const previewContent = document.getElementById('mathPreview');
        if (!input || !previewContainer || !previewContent) return;

        const val = input.value;
        if (val.trim() && (val.includes('$') || val.includes('\\') || val.includes('^') || val.includes('_'))) {
            previewContainer.style.display = 'block';
            previewContent.textContent = val;
            
            if (window.renderMathInElement) {
                window.renderMathInElement(previewContent, {
                    delimiters: [
                        {left: '$$', right: '$$', display: true},
                        {left: '$', right: '$', display: false},
                        {left: '\\(', right: '\\)', display: false},
                        {left: '\\[', right: '\\]', display: true}
                    ],
                    throwOnError: false
                });
            }
        } else {
            previewContainer.style.display = 'none';
        }
    }

    const AI_RESPONSES = [
        'Đây là câu hỏi hay! Để giải thích rõ hơn, chúng ta cần xem xét từng bước một.',
        'Bạn đang hỏi về một chủ đề quan trọng trong bài học. Về cơ bản, khái niệm này được hiểu như sau...',
        'Câu hỏi của bạn liên quan đến phần cốt lõi của chương học. Hãy để tôi phân tích từ đầu nhé.',
        'Rất vui được hỗ trợ! Dựa trên nội dung chương này, tôi sẽ giải thích theo từng bước để bạn dễ hiểu hơn.',
        'Đây là điểm mà nhiều sinh viên thường nhầm lẫn. Hãy để tôi làm rõ từng phần một.',
    ];

    const SUGGESTIONS = [
        'Giải thích khái niệm cơ bản',
        'Cho tôi một ví dụ minh họa',
        'Hướng dẫn giải bài tập',
        'Ôn lại nội dung trước',
        'Bài tập thực hành',
    ];

    async function init() {
        const token = localStorage.getItem('ptit_token');
        if (!token) {
            alert('Vui lòng đăng nhập để truy cập phòng học Trợ lý AI PTIT!');
            window.location.href = 'login.html';
            return;
        }

        // Fetch course detail to populate lessons
        fetch(`/api/v1/courses/${courseId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
        .then(res => res.json())
        .then(resData => {
            if (resData && resData.success) {
                currentCourse = resData.data;

                // Fetch chapters for the course
                fetch(`/api/v1/courses/${courseId}/chapters`, {
                    headers: { 'Authorization': 'Bearer ' + token }
                })
                .then(r => r.json())
                .then(chapData => {
                    if (chapData && chapData.success) {
                        lessons = chapData.data || [];
                    } else {
                        lessons = [];
                    }

                    // Select active lesson
                    activeLesson = lessons.find(l => l.id === activeLessonId) || lessons[0];

                    // Fetch user learning profile for this course (Auto-enroll if missing)
                    fetch(`/api/v1/learning-profiles/me?courseId=${currentCourse.id}`, {
                        headers: { 'Authorization': 'Bearer ' + token }
                    })
                    .then(r => r.json())
                    .then(enrData => {
                        if (enrData && enrData.success && enrData.data) {
                            enrolledData = enrData.data;
                            renderChat();
                        } else {
                            // Auto-enroll user silently
                            fetch(`/api/v1/courses/${currentCourse.id}/enroll`, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'Authorization': 'Bearer ' + token
                                },
                                body: JSON.stringify({})
                            })
                            .then(r => r.json())
                            .then(autoRes => {
                                if (autoRes && autoRes.success && autoRes.data) {
                                    enrolledData = autoRes.data;
                                }
                                renderChat();
                            })
                            .catch(() => {
                                renderChat();
                            });
                        }
                    })
                    .catch(() => {
                        renderChat();
                    });
                })
                .catch(err => {
                    console.error(err);
                    renderChat();
                });
            }
        })
        .catch(err => {
            console.error(err);
        });
    }

    function renderExercisePanel() {
        if (!activeLesson) return;

        const activeIdx = lessons.findIndex(l => l.id === activeLesson.id);
        const chapterNum = activeIdx >= 0 ? (activeIdx + 1) : 1;
        const activeTitle = activeLesson.chapterName || 'Chương học';

        const barTitle = document.getElementById('exerciseBarTitle');
        if (barTitle) barTitle.textContent = `Bài tập Chương ${chapterNum}: ${activeTitle}`;

        const btnStart = document.getElementById('btnStartExercise');
        if (btnStart) {
            btnStart.href = `exercise.html?courseId=${courseId}&chapterId=${activeLesson.id}`;
        }

        const requiredPct = Math.round(((activeIdx + 1) / lessons.length) * 100);
        const isCompleted = enrolledData ? (enrolledData.progressPercent >= requiredPct) : false;

        const badge = document.getElementById('exerciseStatusBadge');
        if (badge) {
            badge.className = `exercise-status-badge ${isCompleted ? 'completed' : 'pending'}`;
            badge.textContent = isCompleted ? 'Đã hoàn thành' : 'Chưa làm';
        }
    }

    function renderChat() {
        if (!currentCourse || !activeLesson) return;

        const activeTitle = activeLesson.chapterName || 'Chương học';
        document.title = `Gia sư AI: ${activeTitle} - PTIT`;
        document.getElementById('chatCourseName').textContent = currentCourse.title;
        document.getElementById('chatChapterName').textContent = activeTitle;
        document.getElementById('backBtn').href = `course-detail.html?id=${courseId}`;

        // Render exercise panel on the right
        renderExercisePanel();

        // Sidebar lessons
        document.getElementById('chatChapters').innerHTML = lessons.map((les, i) => {
            const requiredPct = Math.round(((i + 1) / lessons.length) * 100);
            const isCompleted = enrolledData ? (enrolledData.progressPercent >= requiredPct) : false;
            const isActive = les.id === activeLesson.id;
            return `
            <a href="ai-chat.html?id=${courseId}&les=${les.id}" class="session-card ${isActive ? 'active' : ''}" style="display:block;text-decoration:none;margin-bottom:8px;">
                <div class="session-title" style="font-size:13px;">Chương ${i + 1}: ${les.chapterName || 'Chương học'}</div>
                <span class="status-badge ${isCompleted ? '' : 'pending'}" style="margin-top:4px;">
                    ${isCompleted ? 'Hoàn thành' : 'Đang học'}
                </span>
            </a>`;
        }).join('');

        document.getElementById('quickSuggestions').innerHTML =
            SUGGESTIONS.map(s => `<button class="suggestion-chip" onclick="sendSuggestion('${s}')">${s}</button>`).join('');

        // Welcome message
        const welcome = `Chào bạn! Tôi là <strong>Gia sư AI PTIT</strong>, rất vui được đồng hành cùng bạn học môn <strong>${currentCourse.title}</strong>. Hiện tại chúng ta đang ở chương <strong>${activeTitle}</strong>. Hãy đặt bất kỳ câu hỏi nào về bài học, tôi sẽ giải thích chi tiết cho bạn!`;

        // Clear old welcomes
        document.getElementById('chatMessages').innerHTML = '';
        appendMessage('ai', welcome);

        // Fetch session history from API
        const token = localStorage.getItem('ptit_token');
        fetch(`/api/v1/ai/chat/history?chapterId=${activeLesson.id}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
        .then(res => res.json())
        .then(resData => {
            if (resData && resData.success && resData.data && resData.data.messages) {
                const chatHistory = resData.data.messages;
                chatHistory.forEach(msg => {
                    const type = msg.role === 'USER' ? 'user' : 'ai';
                    appendMessage(type, msg.content);
                });
            }
        })
        .catch(err => {
            console.error('Fetch chat history error:', err);
        });
    }

    /**
     * Map ký tự Unicode toán học đặc biệt → LaTeX tương đương.
     * Mục đích: tránh font bị thiếu glyph hiển thị thành □ hoặc ký tự lạ.
     * KaTeX sẽ render những ký tự này đẹp hơn nhiều.
     */
    const UNICODE_TO_LATEX = {
        // Logic
        '∧': '\\wedge', '∨': '\\vee', '¬': '\\neg', '⊕': '\\oplus',
        '→': '\\rightarrow', '←': '\\leftarrow', '↔': '\\leftrightarrow',
        '⇒': '\\Rightarrow', '⇐': '\\Leftarrow', '⇔': '\\Leftrightarrow',
        '⊤': '\\top', '⊥': '\\bot',
        // Set theory
        '∈': '\\in', '∉': '\\notin', '∋': '\\ni',
        '∅': '\\emptyset', '∪': '\\cup', '∩': '\\cap',
        '⊂': '\\subset', '⊃': '\\supset', '⊆': '\\subseteq', '⊇': '\\supseteq',
        '∖': '\\setminus',
        // Quantifiers
        '∀': '\\forall', '∃': '\\exists', '∄': '\\nexists',
        // Arrows
        '↦': '\\mapsto', '↗': '\\nearrow', '↘': '\\searrow',
        // Comparison
        '≤': '\\leq', '≥': '\\geq', '≠': '\\neq', '≈': '\\approx',
        '≡': '\\equiv', '≢': '\\not\\equiv', '≪': '\\ll', '≫': '\\gg',
        '∝': '\\propto',
        // Arithmetic/Calculus
        '∞': '\\infty', '∂': '\\partial', '∇': '\\nabla',
        '∑': '\\sum', '∏': '\\prod', '∫': '\\int', '∬': '\\iint',
        '±': '\\pm', '∓': '\\mp', '×': '\\times', '÷': '\\div',
        '√': '\\sqrt{}', '∘': '\\circ', '⋅': '\\cdot',
        // Greek (nếu nằm ngoài $...$)
        'α': '\\alpha', 'β': '\\beta', 'γ': '\\gamma', 'δ': '\\delta',
        'ε': '\\varepsilon', 'ζ': '\\zeta', 'η': '\\eta', 'θ': '\\theta',
        'λ': '\\lambda', 'μ': '\\mu', 'ν': '\\nu', 'ξ': '\\xi',
        'π': '\\pi', 'ρ': '\\rho', 'σ': '\\sigma', 'τ': '\\tau',
        'φ': '\\varphi', 'χ': '\\chi', 'ψ': '\\psi', 'ω': '\\omega',
        'Γ': '\\Gamma', 'Δ': '\\Delta', 'Θ': '\\Theta', 'Λ': '\\Lambda',
        'Ξ': '\\Xi', 'Π': '\\Pi', 'Σ': '\\Sigma', 'Φ': '\\Phi',
        'Ψ': '\\Psi', 'Ω': '\\Omega',
    };

    // Regex khớp tất cả các ký tự trong map trên
    const UNICODE_SYMBOL_REGEX = new RegExp(
        '[' + Object.keys(UNICODE_TO_LATEX).join('').replace(/[\]\\^-]/g, '\\$&') + ']',
        'g'
    );

    /**
     * Quét text bên ngoài $...$ và $$...$$, bọc từng ký tự toán học đặc biệt
     * vào $...$  để KaTeX render thay vì để browser dùng font (dễ bị thiếu glyph).
     */
    function sanitizeUnicodeSymbols(text) {
        // Tách thành các segment: [ngoài-math, trong-math, ngoài-math, ...]
        const segments = [];
        let last = 0;
        // Tìm tất cả $$ ... $$ và $ ... $
        const mathRe = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g;
        let m;
        while ((m = mathRe.exec(text)) !== null) {
            // Đoạn text thường trước khối math
            if (m.index > last) {
                segments.push({ type: 'text', val: text.slice(last, m.index) });
            }
            // Đoạn math — giữ nguyên
            segments.push({ type: 'math', val: m[0] });
            last = m.index + m[0].length;
        }
        // Phần cuối còn lại
        if (last < text.length) {
            segments.push({ type: 'text', val: text.slice(last) });
        }

        // Chỉ xử lý các segment text
        return segments.map(seg => {
            if (seg.type === 'math') return seg.val;
            // Thay từng ký tự đặc biệt bằng $\latex$
            return seg.val.replace(UNICODE_SYMBOL_REGEX, ch => {
                const latex = UNICODE_TO_LATEX[ch];
                return latex ? `$${latex}$` : ch;
            });
        }).join('');
    }

    /**
     * Chuyển đổi Markdown -> HTML an toàn.
     * Bảo vệ $...$ và $$...$$ khỏi bị marked.js làm hỏng.
     */
    function markdownToHtml(text) {
        if (!window.marked) return text;

        // Bước 0: Chuẩn hoá ký tự Unicode toán học → $LaTeX$ (tránh lỗi font)
        text = sanitizeUnicodeSymbols(text);

        // Bước 1: Tạm thời thay thế các khối toán học bằng placeholder
        const mathBlocks = [];
        // Ưu tiên $$ trước $
        text = text.replace(/\$\$([\s\S]+?)\$\$/g, (match) => {
            mathBlocks.push(match);
            return `%%MATH_BLOCK_${mathBlocks.length - 1}%%`;
        });
        text = text.replace(/\$([^$\n]+?)\$/g, (match) => {
            mathBlocks.push(match);
            return `%%MATH_BLOCK_${mathBlocks.length - 1}%%`;
        });

        // Bước 2: Chạy marked để parse Markdown
        marked.setOptions({
            breaks: true,      // \n -> <br>
            gfm: true,         // GitHub Flavored Markdown
            pedantic: false
        });
        let html = marked.parse(text);

        // Bước 3: Khôi phục các khối toán học
        html = html.replace(/%%MATH_BLOCK_(\d+)%%/g, (_, i) => mathBlocks[parseInt(i)]);

        return html;
    }


    function appendMessage(type, rawText) {
        const container = document.getElementById('chatMessages');
        const isUser    = type === 'user';
        const label     = isUser ? 'Tôi' : 'AI';
        const div       = document.createElement('div');
        div.className   = `msg-row ${type}`;

        // Người dùng: hiển thị plain text (không render markdown)
        // AI: parse Markdown -> HTML
        const contentHtml = isUser
            ? rawText.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>')
            : markdownToHtml(rawText);

        div.innerHTML   = `
            <div class="msg-avatar ${type}">${label}</div>
            <div class="msg-bubble markdown-body">${contentHtml}</div>`;
        container.appendChild(div);

        // Render math equations in bubble using KaTeX
        const bubble = div.querySelector('.msg-bubble');
        if (window.renderMathInElement && bubble) {
            window.renderMathInElement(bubble, {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\(', right: '\\)', display: false},
                    {left: '\\[', right: '\\]', display: true}
                ],
                throwOnError: false
            });
        }

        container.scrollTop = container.scrollHeight;
    }

    function showTyping() {
        const container = document.getElementById('chatMessages');
        const div       = document.createElement('div');
        div.className   = 'msg-row ai';
        div.id          = 'typingIndicator';
        div.innerHTML   = `
            <div class="msg-avatar ai">AI</div>
            <div class="typing-indicator">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>`;
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    function removeTyping() { document.getElementById('typingIndicator')?.remove(); }

    function getAIResponse(question) {
        const resp = AI_RESPONSES[Math.floor(Math.random() * AI_RESPONSES.length)];
        const kw   = question.split(' ').slice(0, 4).join(' ');
        return resp + ` Cụ thể với <strong>"${kw}"</strong>, bạn có thể tham khảo thêm các ví dụ trong phần tài liệu của chương này.`;
    }

    function sendMessage(text) {
        if (!text.trim() || isTyping) return;
        isTyping = true;
        appendMessage('user', text);
        document.getElementById('chatInput').value = '';
        document.getElementById('chatInput').style.height = 'auto';
        const previewContainer = document.getElementById('mathPreviewContainer');
        if (previewContainer) previewContainer.style.display = 'none';
        document.getElementById('sendBtn').disabled = true;
        document.getElementById('quickSuggestions').style.display = 'none';

        showTyping();

        const token = localStorage.getItem('ptit_token');
        fetch('/api/v1/ai/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({
                chapterId: activeLesson.id,
                question: text
            })
        })
        .then(res => res.json())
        .then(resData => {
            removeTyping();
            if (resData.success) {
                appendMessage('ai', resData.data.content);
            } else {
                appendMessage('ai', 'Lỗi từ hệ thống AI: ' + resData.message);
            }
            isTyping = false;
            document.getElementById('sendBtn').disabled = false;
        })
        .catch(err => {
            console.error(err);
            removeTyping();
            appendMessage('ai', 'Không thể kết nối tới Gia sư AI. Vui lòng thử lại sau.');
            isTyping = false;
            document.getElementById('sendBtn').disabled = false;
        });
    }

    window.sendSuggestion = (text) => sendMessage(text);

    document.addEventListener('DOMContentLoaded', () => {
        init();

        const input = document.getElementById('chatInput');

        document.getElementById('chatForm').addEventListener('submit', e => {
            e.preventDefault();
            sendMessage(input.value.trim());
        });

        // Gán sự kiện cho các nút trên thanh công cụ toán học
        const mathToolbar = document.getElementById('mathToolbar');
        if (mathToolbar && input) {
            mathToolbar.querySelectorAll('.math-btn').forEach(btn => {
                btn.addEventListener('click', e => {
                    const idx = parseInt(e.target.getAttribute('data-template-idx'));
                    const template = MATH_TEMPLATES[idx];
                    if (template) {
                        insertMathTemplate(input, template);
                    }
                });
            });
        }

        input.addEventListener('input', () => {
            input.style.height = 'auto';
            input.style.height = Math.min(input.scrollHeight, 120) + 'px';
            updateMathPreview();
        });

        input.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(input.value.trim());
            }
        });
    });
})();
