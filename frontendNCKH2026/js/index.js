// =====================================================
// SHARED COURSE DATA + UTILITIES (no emoji)
// =====================================================
const COURSES = [
    {
        id: 1, title: 'Giải tích 1',
        category: 'daicuong', categoryLabel: 'Đại Cương',
        level: 'Cơ bản', chapters: 5,
        instructor: 'GV. Nguyễn Văn A',
        rating: 4.8, ratingCount: 342,
        thumb: null, thumbLabel: 'GT1', color: '#7a1318',
        description: 'Nền tảng giải tích toán học: giới hạn, đạo hàm, tích phân và ứng dụng.'
    },
    {
        id: 2, title: 'Triết học Mác-Lênin',
        category: 'daicuong', categoryLabel: 'Đại Cương',
        level: 'Cơ bản', chapters: 4,
        instructor: 'GV. Trần Thị B',
        rating: 4.5, ratingCount: 218,
        thumb: null, thumbLabel: 'TH', color: '#1a4a7a',
        description: 'Các nguyên lý cơ bản của chủ nghĩa Mác-Lênin và vận dụng vào thực tiễn.'
    },
    {
        id: 3, title: 'Nhập môn Trí tuệ nhân tạo',
        category: 'chuyennganh', categoryLabel: 'Chuyên ngành',
        level: 'Trung cấp', chapters: 6,
        instructor: 'GV. Lê Văn C',
        rating: 4.9, ratingCount: 487,
        thumb: null, thumbLabel: 'AI', color: '#1a5c2e',
        description: 'Khám phá các khái niệm AI, Machine Learning và Deep Learning từ căn bản.'
    },
    {
        id: 4, title: 'Lập trình Python',
        category: 'chuyennganh', categoryLabel: 'Chuyên ngành',
        level: 'Cơ bản', chapters: 8,
        instructor: 'GV. Phạm Thị D',
        rating: 4.7, ratingCount: 395,
        thumb: null, thumbLabel: 'Py', color: '#1a3a7a',
        description: 'Lập trình Python từ cơ bản đến nâng cao: OOP, thư viện phổ biến và dự án thực tế.'
    },
    {
        id: 5, title: 'Mạng máy tính',
        category: 'chuyennganh', categoryLabel: 'Chuyên ngành',
        level: 'Trung cấp', chapters: 7,
        instructor: 'GV. Hoàng Văn E',
        rating: 4.6, ratingCount: 201,
        thumb: null, thumbLabel: 'MMT', color: '#4a1a7a',
        description: 'Kiến trúc mạng, giao thức TCP/IP, bảo mật mạng và các công nghệ hiện đại.'
    },
    {
        id: 6, title: 'Tiếng Anh chuyên ngành',
        category: 'chuyennganh', categoryLabel: 'Chuyên ngành',
        level: 'Trung cấp', chapters: 5,
        instructor: 'GV. Nguyễn Thị F',
        rating: 4.4, ratingCount: 156,
        thumb: null, thumbLabel: 'EN', color: '#7a4a1a',
        description: 'Từ vựng và kỹ năng Tiếng Anh chuyên ngành CNTT và Viễn thông.'
    },
    {
        id: 7, title: 'Cấu trúc dữ liệu và Giải thuật',
        category: 'chuyennganh', categoryLabel: 'Chuyên ngành',
        level: 'Trung cấp', chapters: 9,
        instructor: 'GV. Đỗ Văn G',
        rating: 4.8, ratingCount: 312,
        thumb: null, thumbLabel: 'DSA', color: '#2a5a1a',
        description: 'Các cấu trúc dữ liệu cơ bản và giải thuật quan trọng cho lập trình viên.'
    },
    {
        id: 8, title: 'Vật lý đại cương',
        category: 'daicuong', categoryLabel: 'Đại Cương',
        level: 'Cơ bản', chapters: 6,
        instructor: 'GV. Bùi Thị H',
        rating: 4.3, ratingCount: 189,
        thumb: null, thumbLabel: 'VL', color: '#5a2a1a',
        description: 'Cơ học, điện từ học, quang học và nhiệt động lực học.'
    }
];

// =====================================================
// RENDER HELPERS
// =====================================================
function renderStars(rating) {
    const full = Math.floor(rating);
    const stars = [];
    for (let i = 1; i <= 5; i++) {
        if (i <= full) stars.push('<span style="color:#f59e0b;">&#9733;</span>');
        else stars.push('<span style="color:#d1d5db;">&#9733;</span>');
    }
    return stars.join('');
}

function renderCourseCard(course, enrolled = false) {
    return `
    <div class="course-card" data-id="${course.id}">
        <a href="course-detail.html?id=${course.id}">
            <div class="card-thumb" style="background:linear-gradient(135deg,${course.color},${course.color}aa)">
                ${course.thumb ? `<img src="${course.thumb}" alt="${course.title}">` : course.thumbLabel}
            </div>
        </a>
        <div class="card-body">
            <div style="display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap;">
                <span class="badge badge-primary">${course.categoryLabel}</span>
                <span class="badge badge-info">${course.level}</span>
            </div>
            <a href="course-detail.html?id=${course.id}" style="text-decoration:none;">
                <h3 class="card-title">${course.title}</h3>
            </a>
            <div class="card-instructor">${course.instructor}</div>
            <div class="rating" style="margin-bottom:8px;">
                <span class="rating-score">${course.rating}</span>
                <span>${renderStars(course.rating)}</span>
                <span class="rating-count">(${course.ratingCount.toLocaleString()})</span>
            </div>
            <div class="card-meta">${course.chapters} chương &bull; Miễn phí</div>
            ${enrolled
                ? `<a href="course-detail.html?id=${course.id}" class="btn btn-primary btn-block" style="margin-top:auto;">Tiếp tục học</a>`
                : `<a href="course-detail.html?id=${course.id}" class="btn btn-outline-primary btn-block" style="margin-top:auto;">Học ngay</a>`
            }
        </div>
    </div>`;
}

function showToast(msg, type = 'success') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3500);
}

// =====================================================
// ANIMATED COUNTER
// =====================================================
function animateCounters() {
    document.querySelectorAll('[data-target]').forEach(el => {
        const target = parseInt(el.dataset.target);
        const duration = 1800;
        const step = target / (duration / 16);
        let current = 0;
        const suffix = target === 98 ? '%' : '+';
        const timer = setInterval(() => {
            current = Math.min(current + step, target);
            el.textContent = Math.floor(current).toLocaleString() + suffix;
            if (current >= target) clearInterval(timer);
        }, 16);
    });
}

function doSearch() {
    const val = document.getElementById('heroSearch')?.value?.trim();
    if (val) window.location.href = `courses.html?search=${encodeURIComponent(val)}`;
}

// =====================================================
// HOMEPAGE INIT
// =====================================================
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('heroSearch')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') doSearch();
    });

    const featured = [...COURSES].sort((a, b) => b.ratingCount - a.ratingCount).slice(0, 4);
    const grid = document.getElementById('featuredCourses');
    if (grid) grid.innerHTML = featured.map(c => renderCourseCard(c)).join('');

    const observer = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) { animateCounters(); observer.disconnect(); }
        });
    }, { threshold: 0.3 });
    const statsBar = document.querySelector('.stats-bar');
    if (statsBar) observer.observe(statsBar);
});
