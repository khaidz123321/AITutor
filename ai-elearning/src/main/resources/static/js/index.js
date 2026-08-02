// =====================================================
// SHARED COURSE DATA + UTILITIES (no emoji)
// =====================================================
(function() {
    const userStr = localStorage.getItem('ptit_user');
    if (userStr) {
        try {
            const user = JSON.parse(userStr);
            if (user && (user.role === 'ADMIN' || user.role === 'TEACHER')) {
                window.location.href = 'dashboard.html';
            }
        } catch (e) {
            console.error(e);
        }
    }
})();
const COURSES = [];

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
    const cId = course.courseId || course.id;
    const cThumbLabel = course.thumbLabel || 'Course';
    const cCategoryLabel = course.category === 'daicuong' ? 'Đại Cương' : 'Chuyên ngành';
    const cChapters = course.chapterCount || 0;

    const isChuyenNganh = course.category === 'chuyennganh';
    const gradient = isChuyenNganh 
        ? 'linear-gradient(135deg, #3d0507, #54090c)' 
        : 'linear-gradient(135deg, #54090c, #7a1318)';

    const hasImage = course.thumbnailUrl && course.thumbnailUrl !== 'null' && course.thumbnailUrl !== 'undefined' && course.thumbnailUrl.trim() !== '';

    return `
    <div class="course-card" data-id="${cId}" style="border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; display: flex; flex-direction: column; background: #fff; transition: transform var(--transition), box-shadow var(--transition); box-shadow: var(--shadow-sm);">
        <a href="course-detail.html?id=${cId}">
            <div class="card-thumb" style="aspect-ratio: 16/9; background:${gradient}; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; color: rgba(255,255,255,.2); font-size: 80px; font-weight: 900; letter-spacing: -3px; border-radius: var(--radius-lg) var(--radius-lg) 0 0;">
                ${hasImage ? `<img src="${course.thumbnailUrl}" alt="${course.title}" style="width:100%; height:100%; object-fit:cover; position:absolute; inset:0; z-index:1;" onerror="this.style.display='none'">` : ''}
                ${cThumbLabel}
            </div>
        </a>
        <div class="card-body" style="padding: 20px; display: flex; flex-direction: column; flex: 1;">
            <div style="margin-bottom: 12px;">
                <span class="badge" style="background: #fdf4f4; color: #7a1318; border: 1px solid rgba(122, 19, 24, 0.15); padding: 3px 10px; border-radius: var(--radius-sm); font-size: 11px; font-weight: 700;">${cCategoryLabel}</span>
            </div>
            
            <div style="display:flex; align-items:center; gap:16px; font-size:12.5px; color:var(--text-3); margin-bottom:12px;">
                <span style="display:inline-flex; align-items:center; gap:4px; font-weight: 600;">
                    ${cChapters} Chương học
                </span>
            </div>
            
            <a href="course-detail.html?id=${cId}" style="text-decoration:none;">
                <h3 class="card-title" style="font-size: 15px; font-weight: 800; color: #111827; margin: 0 0 16px; line-height: 1.4; min-height: 42px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-family: var(--font);">${course.title}</h3>
            </a>
            
            ${enrolled
                ? `<a href="course-detail.html?id=${cId}" style="display: flex; align-items: center; justify-content: center; width: 100%; padding: 9px; background: #fdf4f4; color: #7a1318; border: 1px solid rgba(122,19,24,0.2); font-weight: 700; border-radius: var(--radius); font-size: 13px; text-decoration: none; transition: all 0.2s; margin-top: auto; font-family: var(--font);">Tiếp tục học</a>`
                : `<a href="course-detail.html?id=${cId}" style="display: flex; align-items: center; justify-content: center; width: 100%; padding: 9px; background: #7a1318; color: #ffffff; font-weight: 700; border-radius: var(--radius); font-size: 13px; text-decoration: none; transition: all 0.2s; margin-top: auto; font-family: var(--font);">Xem thông tin khóa học</a>`
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

function initHeroSlider() {
    const slider = document.getElementById('heroSlider');
    if (!slider) return;

    const slides = slider.querySelectorAll('.slide');
    const prevBtn = document.getElementById('sliderPrevBtn');
    const nextBtn = document.getElementById('sliderNextBtn');
    const dotsContainer = document.getElementById('sliderDots');

    if (!slides.length) return;

    let currentIndex = 0;
    let timer = null;
    const intervalTime = 3000; // Tự động chuyển ảnh sau mỗi 3 giây

    // Động hóa việc tạo chấm tròn navigation (Dots)
    if (dotsContainer) {
        dotsContainer.innerHTML = '';
        slides.forEach((_, idx) => {
            const dot = document.createElement('div');
            dot.className = `slider-dot ${idx === 0 ? 'active' : ''}`;
            dot.addEventListener('click', () => {
                goToSlide(idx);
                startAutoPlay();
            });
            dotsContainer.appendChild(dot);
        });
    }

    function updateDots() {
        if (!dotsContainer) return;
        const dots = dotsContainer.querySelectorAll('.slider-dot');
        dots.forEach((dot, idx) => {
            dot.classList.toggle('active', idx === currentIndex);
        });
    }

    function goToSlide(index) {
        slides[currentIndex].classList.remove('active');
        currentIndex = (index + slides.length) % slides.length;
        slides[currentIndex].classList.add('active');
        updateDots();
    }

    function nextSlide() {
        goToSlide(currentIndex + 1);
    }

    function prevSlide() {
        goToSlide(currentIndex - 1);
    }

    function startAutoPlay() {
        stopAutoPlay();
        timer = setInterval(nextSlide, intervalTime);
    }

    function stopAutoPlay() {
        if (timer) clearInterval(timer);
    }

    if (prevBtn) prevBtn.addEventListener('click', () => { prevSlide(); startAutoPlay(); });
    if (nextBtn) nextBtn.addEventListener('click', () => { nextSlide(); startAutoPlay(); });

    // Dừng auto-play khi người dùng rê chuột vào banner slider
    const container = slider.closest('.hero-slider-container');
    if (container) {
        container.addEventListener('mouseenter', stopAutoPlay);
        container.addEventListener('mouseleave', startAutoPlay);
    }

    startAutoPlay();
}

// =====================================================
// HOMEPAGE INIT
// =====================================================
document.addEventListener('DOMContentLoaded', () => {
    initHeroSlider();

    document.getElementById('heroSearch')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') doSearch();
    });

    const token = localStorage.getItem('ptit_token');
    const headers = token ? { 'Authorization': 'Bearer ' + token } : {};

    fetch('/api/v1/courses?status=PUBLISHED&size=50', { headers })
    .then(res => {
        if (res.status === 401) {
            return { success: false, data: { items: [] } };
        }
        return res.json();
    })
    .then(resData => {
        let actualCourses = [];
        if (resData.success) {
            actualCourses = (resData.data.items || []).map(c => {
                c.category = (c.level === 'BEGINNER' || c.level === 'INTERMEDIATE') ? 'daicuong' : 'chuyennganh';
                return c;
            });
        }
        const grid = document.getElementById('featuredCourses');
        if (grid) {
            if (actualCourses.length > 0) {
                const featured = actualCourses.slice(0, 4);
                grid.innerHTML = featured.map(c => renderCourseCard(c)).join('');
            } else {
                grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-3); padding: 40px 0;">Đăng nhập để xem các khóa học nổi bật của chúng tôi.</div>`;
            }
        }
    })
    .catch(err => {
        console.error(err);
        const grid = document.getElementById('featuredCourses');
        if (grid) grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-3); padding: 40px 0;">Vui lòng đăng nhập để khám phá các khóa học.</div>`;
    });
});
