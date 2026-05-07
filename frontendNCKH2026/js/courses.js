// =====================================================
// COURSES PAGE LOGIC
// =====================================================
(function () {
    let activeCat   = 'all';
    let activeLevel = 'all';
    let searchQuery = '';
    let sortBy      = 'popular';

    function getFiltered() {
        let list = [...COURSES];
        if (activeCat   !== 'all') list = list.filter(c => c.category === activeCat);
        if (activeLevel !== 'all') list = list.filter(c => c.level === activeLevel);
        if (searchQuery) {
            const q = searchQuery.toLowerCase();
            list = list.filter(c =>
                c.title.toLowerCase().includes(q) ||
                c.instructor.toLowerCase().includes(q) ||
                c.categoryLabel.toLowerCase().includes(q)
            );
        }
        if (sortBy === 'rating')  list.sort((a, b) => b.rating - a.rating);
        if (sortBy === 'popular') list.sort((a, b) => b.ratingCount - a.ratingCount);
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
                if (!cats[c.categoryLabel]) cats[c.categoryLabel] = [];
                cats[c.categoryLabel].push(c);
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

        renderOutput();

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
                if (filterType === 'level') activeLevel = val;
                renderOutput();
            });
        });

        document.getElementById('resetFilter')?.addEventListener('click', () => {
            activeCat = 'all'; activeLevel = 'all'; searchQuery = '';
            document.getElementById('courseSearch').value = '';
            document.querySelectorAll('.filter-option').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.val === 'all');
            });
            renderOutput();
        });
    });
})();
