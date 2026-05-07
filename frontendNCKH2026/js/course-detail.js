// =====================================================
// COURSE DETAIL PAGE - No emoji
// =====================================================
(function () {
    const CHAPTERS_DATA = {
        1: ['Giới hạn và liên tục', 'Đạo hàm và vi phân', 'Tích phân bất định', 'Tích phân xác định', 'Ứng dụng tích phân'],
        2: ['Vật chất và ý thức', 'Phép biện chứng duy vật', 'Chủ nghĩa duy vật lịch sử', 'Kinh tế chính trị Mác-Lênin'],
        3: ['Giới thiệu về AI', 'Tìm kiếm và suy diễn', 'Machine Learning cơ bản', 'Mạng nơ-ron nhân tạo', 'Xử lý ngôn ngữ tự nhiên', 'Thị giác máy tính'],
        4: ['Cú pháp Python', 'Hàm và module', 'Lập trình hướng đối tượng', 'Xử lý file và I/O', 'Thư viện NumPy & Pandas', 'Dự án thực hành', 'Web scraping', 'Flask API'],
        5: ['Mô hình OSI & TCP/IP', 'Địa chỉ IP và Subnet', 'Giao thức định tuyến', 'Bảo mật mạng', 'Mạng không dây', 'Cloud Networking', 'Network Labs'],
        6: ['Từ vựng IT cơ bản', 'Đọc tài liệu kỹ thuật', 'Viết email chuyên nghiệp', 'Thuyết trình kỹ thuật', 'Interview skills'],
        7: ['Arrays & Linked Lists', 'Stacks & Queues', 'Trees & Graphs', 'Sorting Algorithms', 'Searching Algorithms', 'Dynamic Programming', 'Greedy Algorithms', 'String Algorithms', 'Practice Problems'],
        8: ['Cơ học Newton', 'Dao động và sóng', 'Nhiệt động lực học', 'Điện từ học', 'Quang học', 'Vật lý hiện đại'],
    };

    const LEARN_ITEMS = {
        1: ['Hiểu và tính giới hạn hàm số', 'Tính đạo hàm thành thạo', 'Giải tích phân bất định', 'Áp dụng tích phân xác định', 'Giải phương trình vi phân đơn giản', 'Vận dụng vào bài toán thực tế'],
        2: ['Nắm vững triết học Mác-Lênin', 'Hiểu phép biện chứng duy vật', 'Phân tích quy luật xã hội', 'Vận dụng tư tưởng vào thực tiễn', 'Tư duy biện chứng', 'Hiểu kinh tế chính trị cơ bản'],
        3: ['Hiểu các khái niệm AI cơ bản', 'Triển khai thuật toán tìm kiếm', 'Xây dựng mô hình ML đơn giản', 'Hiểu cách hoạt động của mạng nơ-ron', 'Làm việc với dữ liệu văn bản', 'Ứng dụng AI vào bài toán thực tế'],
        default: ['Nắm vững kiến thức lý thuyết', 'Làm bài tập thực hành', 'Hỏi đáp với AI gia sư', 'Theo dõi tiến độ học tập', 'Ôn tập theo từng chương', 'Chuẩn bị thi cử hiệu quả'],
    };

    const REVIEWS = [
        { name: 'Nguyễn Minh Tú', rating: 5, text: 'Khóa học rất hay, AI gia sư giải thích rõ ràng và dễ hiểu. Tôi đã hiểu được nhiều khái niệm khó nhờ hệ thống này.' },
        { name: 'Trần Thị Lan', rating: 5, text: 'Nội dung bám sát chương trình PTIT, ôn thi rất hiệu quả. Giao diện đẹp, dễ sử dụng.' },
        { name: 'Lê Quốc Hùng', rating: 4, text: 'Tốt hơn mong đợi! AI phản hồi nhanh và chính xác. Mong có thêm nhiều bài tập thực hành hơn.' },
    ];

    function init() {
        const params = new URLSearchParams(window.location.search);
        const id = parseInt(params.get('id')) || 1;
        const course = COURSES.find(c => c.id === id) || COURSES[0];
        const chapters = CHAPTERS_DATA[course.id] || CHAPTERS_DATA[1];
        const learnItems = LEARN_ITEMS[course.id] || LEARN_ITEMS.default;
        const progress = 47; // Demo progress

        document.title = `${course.title} - PTIT E-Learning`;

        // Hero
        document.getElementById('detailHero').innerHTML = `
            <div style="position:relative;z-index:2;">
                <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
                    <span class="badge" style="background:rgba(255,255,255,.15);color:#fff;">${course.categoryLabel}</span>
                    <span class="badge" style="background:rgba(255,255,255,.15);color:#fff;">${course.level}</span>
                </div>
                <div class="detail-hero-title">${course.title}</div>
                <div class="detail-hero-meta">
                    <span>${chapters.length} chương</span>
                    <span>${course.instructor}</span>
                    <span>${course.rating} / 5 &nbsp;(${course.ratingCount.toLocaleString()} đánh giá)</span>
                </div>
                <p class="detail-hero-desc">${course.description}</p>
                <a href="ai-chat.html?id=${course.id}" class="btn" style="background:#fff;color:var(--primary);font-weight:700;margin-top:8px;">
                    Hỏi gia sư AI ngay
                </a>
            </div>`;

        // Learn grid
        document.getElementById('learnGrid').innerHTML =
            learnItems.map(item => `<div class="learn-item">${item}</div>`).join('');

        // Course desc
        document.getElementById('courseDesc').textContent =
            course.description + ' Khóa học được thiết kế phù hợp với chương trình đào tạo tại PTIT, giúp sinh viên nắm vững kiến thức lý thuyết và kỹ năng thực hành. Tích hợp AI gia sư sẵn sàng giải đáp mọi thắc mắc 24/7.';

        // Chapters
        document.getElementById('chaptersCount').textContent = `${chapters.length} chương`;
        document.getElementById('chapterCountBadge').textContent = `${chapters.length} chương`;
        document.getElementById('chapterList').innerHTML = chapters.map((ch, i) => `
            <div class="chapter-item">
                <div class="chapter-header" onclick="toggleChapter(this)">
                    <div>
                        <div class="chapter-num">Chương ${i + 1}</div>
                        <div class="chapter-name">${ch}</div>
                    </div>
                    <svg class="chapter-toggle" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                </div>
                <div class="chapter-body">
                    <div class="lesson-item">
                        <span class="lesson-status ${i < 2 ? 'done' : ''}">Bài giảng lý thuyết</span>
                        ${i < 2 ? '<span class="done-tag">Hoàn thành</span>' : ''}
                    </div>
                    <div class="lesson-item">
                        <span class="lesson-status ${i < 2 ? 'done' : ''}">Hỏi đáp AI gia sư</span>
                        ${i < 2 ? '<span class="done-tag">Hoàn thành</span>' : ''}
                    </div>
                    <div class="lesson-item"><span class="lesson-status">Bài tập ôn tập</span></div>
                </div>
            </div>`).join('');

        // Reviews
        document.getElementById('reviewsSection').innerHTML = `
            <div style="background:var(--bg-white);border:1px solid var(--border);border-radius:var(--radius-lg);padding:28px;">
                <div style="display:flex;gap:32px;align-items:center;margin-bottom:24px;padding-bottom:24px;border-bottom:1px solid var(--border);">
                    <div style="text-align:center;min-width:100px;">
                        <div style="font-size:52px;font-weight:900;color:var(--primary);line-height:1;">${course.rating}</div>
                        <div style="font-size:13px;color:var(--text-3);margin-top:4px;">${course.ratingCount.toLocaleString()} đánh giá</div>
                    </div>
                    <div style="font-size:14px;color:var(--text-3);line-height:1.8;">
                        Xếp hạng trung bình từ sinh viên PTIT tham gia khóa học này.<br>
                        <strong style="color:var(--text-1);">98%</strong> sinh viên đánh giá khóa học đáp ứng hoặc vượt kỳ vọng.
                    </div>
                </div>
                ${REVIEWS.map(r => `
                <div style="padding:20px 0;border-bottom:1px solid var(--border-light);">
                    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
                        <div style="width:40px;height:40px;background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;flex-shrink:0;">
                            ${r.name.split(' ').map(w=>w[0]).join('').slice(0,2)}
                        </div>
                        <div>
                            <div style="font-weight:700;font-size:14px;">${r.name}</div>
                            <div style="font-size:12px;color:#f59e0b;">${'★'.repeat(r.rating)}</div>
                        </div>
                    </div>
                    <p style="font-size:14px;color:var(--text-2);line-height:1.7;">${r.text}</p>
                </div>`).join('')}
            </div>`;

        // Sidebar
        document.getElementById('sidebarMeta').innerHTML = `
            <li><span>Số chương</span><strong>${chapters.length} chương</strong></li>
            <li><span>Giảng viên</span><strong>${course.instructor}</strong></li>
            <li><span>Cấp độ</span><strong>${course.level}</strong></li>
            <li><span>Danh mục</span><strong>${course.categoryLabel}</strong></li>`;

        document.getElementById('sidebarProgress').style.display = 'block';
        document.getElementById('progressPct').textContent = progress + '%';
        document.getElementById('progressFill').style.width = progress + '%';

        document.getElementById('startBtn').href = `ai-chat.html?id=${course.id}`;
        document.getElementById('startBtn').textContent = progress > 0 ? 'Tiếp tục học' : 'Bắt đầu học';

        document.getElementById('sidebarChapters').innerHTML = chapters.map((ch, i) => `
            <a href="ai-chat.html?id=${course.id}&ch=${i}" class="session-card ${i === 2 ? 'active' : ''}" style="display:block;text-decoration:none;">
                <div class="session-title">Chương ${i + 1}: ${ch}</div>
                <span class="status-badge ${i < 2 ? '' : i === 2 ? 'pending' : 'locked'}">
                    ${i < 2 ? 'Hoàn thành' : i === 2 ? 'Đang học' : 'Chưa học'}
                </span>
            </a>`).join('');
    }

    window.toggleChapter = function (header) {
        header.classList.toggle('open');
        header.nextElementSibling.classList.toggle('open');
    };

    document.addEventListener('DOMContentLoaded', () => {
        init();
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
            });
        });
    });
})();
