// =====================================================
// COURSES PAGE LOGIC
// =====================================================
(function () {
    let activeCat   = 'all';
    let searchQuery = '';
    let sortBy      = 'popular';
    let DB_COURSES  = []; // Array to store courses fetched from backend

    function getFiltered() {
        let list = [...DB_COURSES];
        if (activeCat   !== 'all') list = list.filter(c => c.category === activeCat);
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            list = list.filter(c =>
                c.title.toLowerCase().includes(q) ||
                (c.teacherName && c.teacherName.toLowerCase().includes(q)) ||
                (c.category && c.category.toLowerCase().includes(q))
            );
        }
        if (sortBy === 'rating')  {
            // Backend doesn't have rating yet, so we use dummy sort
        }
        if (sortBy === 'az')      list.sort((a, b) => a.title.localeCompare(b.title));
        return list;
    }

    function renderOutput() {
        const list   = getFiltered();
        const output = document.getElementById('courseOutput');
        const count  = document.getElementById('coursesCount');
        if (!output) return;

        count.innerHTML = `<strong>${list.length}</strong> khóa học`;

        if (list.length === 0) {
            output.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">--</div>
                <h3>Không tìm thấy khóa học</h3>
                <p>Thử thay đổi bộ lọc hoặc từ khóa tìm kiếm.</p>
            </div>`;
            return;
        }

        if (activeCat === 'all' && !searchQuery) {
            const cats = {};
            list.forEach(c => {
                const label = c.category === 'daicuong' ? 'Đại Cương' : 'Chuyên ngành';
                if (!cats[label]) cats[label] = [];
                cats[label].push(c);
            });
            output.innerHTML = Object.entries(cats).map(([label, courses]) => `
                <h2 class="category-label">${label} <span>${courses.length} khóa học</span></h2>
                <div class="course-grid" style="margin-bottom:12px;">
                    ${courses.map(c => renderCourseCard(c)).join('')}
                </div>
            `).join('');
        } else {
            output.innerHTML = `<div class="course-grid">${list.map(c => renderCourseCard(c)).join('')}</div>`;
        }
    }

    function fetchCourses() {
        const token = localStorage.getItem('ptit_token');
        if (!token) {
            window.location.href = 'login.html';
            return;
        }

        fetch('/api/v1/courses?status=PUBLISHED&size=100', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
        .then(res => {
            if (res.status === 401) {
                localStorage.removeItem('ptit_token');
                window.location.href = 'login.html';
                return;
            }
            return res.json();
        })
        .then(resData => {
            if (resData && resData.success) {
                DB_COURSES = (resData.data.items || []).map(c => {
                    c.category = (c.level === 'BEGINNER' || c.level === 'INTERMEDIATE') ? 'daicuong' : 'chuyennganh';
                    return c;
                });
                renderOutput();
            }
        })
        .catch(err => {
            console.error(err);
            const output = document.getElementById('courseOutput');
            if (output) output.innerHTML = `<div style="text-align:center; padding: 40px; color: var(--text-3);">Không thể tải danh sách khóa học. Vui lòng thử lại.</div>`;
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        const params = new URLSearchParams(window.location.search);
        if (params.get('search')) {
            searchQuery = params.get('search');
            const inp = document.getElementById('courseSearch');
            if (inp) inp.value = searchQuery;
        }
        if (params.get('cat')) {
            activeCat = params.get('cat');
            document.querySelectorAll('[data-filter="cat"]').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.val === activeCat);
            });
        }

        fetchCourses();

        document.getElementById('courseSearch')?.addEventListener('input', e => {
            searchQuery = e.target.value.trim();
            renderOutput();
        });

        document.getElementById('sortSelect')?.addEventListener('change', e => {
            sortBy = e.target.value;
            renderOutput();
        });

        document.querySelectorAll('.filter-option').forEach(btn => {
            btn.addEventListener('click', () => {
                const filterType = btn.dataset.filter;
                const val = btn.dataset.val;
                document.querySelectorAll(`[data-filter="${filterType}"]`).forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                if (filterType === 'cat')   activeCat   = val;
                renderOutput();
            });
        });

        document.getElementById('resetFilter')?.addEventListener('click', () => {
            activeCat = 'all'; searchQuery = '';
            document.getElementById('courseSearch').value = '';
            document.querySelectorAll('.filter-option').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.val === 'all');
            });
            renderOutput();
        });
    });
})();
