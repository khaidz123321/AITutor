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
        ? 'linear-gradient(135deg, #3d0709, #c12026)' 
        : 'linear-gradient(135deg, #7a1318, #c12026)';

    return `
    <div class="course-card" data-id="${cId}" style="border: 1.5px solid #f3f4f6; border-radius: 16px; overflow: hidden; display: flex; flex-direction: column; background: #fff; transition: transform var(--transition), box-shadow var(--transition); box-shadow: 0 4px 20px rgba(0,0,0,0.04);">
        <a href="course-detail.html?id=${cId}">
            <div class="card-thumb" style="aspect-ratio: 16/9; background:${gradient}; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; color: rgba(255,255,255,.15); font-size: 80px; font-weight: 900; letter-spacing: -3px; border-radius: 16px 16px 0 0;">
                ${cThumbLabel}
            </div>
        </a>
        <div class="card-body" style="padding: 20px; display: flex; flex-direction: column; flex: 1;">
            <div style="margin-bottom: 12px;">
                <span class="badge" style="background: #fff5f5; color: #c12026; padding: 4px 12px; border-radius: 100px; font-size: 11px; font-weight: 700; text-transform: none; letter-spacing: 0;">${cCategoryLabel}</span>
            </div>
            
            <div style="display:flex; align-items:center; gap:16px; font-size:12.5px; color:var(--text-3); margin-bottom:12px;">
                <span style="display:inline-flex; align-items:center; gap:4px; font-weight: 600;">
                    <svg style="color: #c12026;" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
                    ${cChapters} ChÆ°Æ¡ng há»c
                </span>
                <span style="display:inline-flex; align-items:center; gap:4px; font-weight: 600;">
                    <svg style="color: #c12026;" xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>
                    1023 học viên
                </span>
            </div>
            
            <a href="course-detail.html?id=${cId}" style="text-decoration:none;">
                <h3 class="card-title" style="font-size: 15px; font-weight: 800; color: #111827; margin: 0 0 16px; line-height: 1.4; min-height: 42px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-family: var(--font);">${course.title}</h3>
            </a>
            
            ${enrolled
                ? `<a href="course-detail.html?id=${cId}" style="display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 10px; background: #fdf2f2; color: #c12026; font-weight: 700; border-radius: 8px; font-size: 13.5px; text-decoration: none; transition: background 0.2s; margin-top: auto; font-family: var(--font);">Tiếp tục học &nearr;</a>`
                : `<a href="course-detail.html?id=${cId}" style="display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 10px; background: #fdf2f2; color: #c12026; font-weight: 700; border-radius: 8px; font-size: 13.5px; text-decoration: none; transition: background 0.2s; margin-top: auto; font-family: var(--font);">Học ngay &nearr;</a>`
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

    const observer = new IntersectionObserver(entries => {
        entries.forEach(e => {
            if (e.isIntersecting) { animateCounters(); observer.disconnect(); }
        });
    }, { threshold: 0.3 });
    const statsBar = document.querySelector('.stats-bar');
    if (statsBar) observer.observe(statsBar);
});
