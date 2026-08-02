// =====================================================
// STUDENT DASHBOARD LOGIC - Sidebar Edition
// =====================================================
(function () {
    const token = localStorage.getItem('ptit_token');
    if (!token) {
        window.location.href = 'login.html';
        return;
    }
    const userStr = localStorage.getItem('ptit_user');
    let currentUser = null;

    if (userStr) {
        try { currentUser = JSON.parse(userStr); } catch (e) {}
    }

    function init() {
        if (currentUser) {
            document.getElementById('dbUserFullName').textContent = currentUser.name || 'Sinh viên PTIT';
            document.getElementById('dbUserRole').textContent = (currentUser.email || 'sinhvien@ptit.edu.vn');
        }

        const logoutBtn = document.getElementById('dbLogoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', (e) => {
                e.preventDefault();
                localStorage.removeItem('ptit_token');
                localStorage.removeItem('ptit_user');
                window.location.href = 'index.html';
            });
        }

        setupTabs();
        loadStudentOverview();
    }

    function setupTabs() {
        document.querySelectorAll('.db-nav-item').forEach(item => {
            item.addEventListener('click', () => {
                document.querySelectorAll('.db-nav-item').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.db-panel').forEach(c => c.classList.remove('active'));

                item.classList.add('active');
                const panelId = item.dataset.panel;
                const targetPanel = document.getElementById(panelId);
                if (targetPanel) targetPanel.classList.add('active');

                document.getElementById('dbTitle').textContent = item.textContent.replace(/[^\p{L}\s]/gu, '').trim();

                if (panelId === 'overviewPanel') loadStudentOverview();
                if (panelId === 'coursesPanel') loadStudentCourses();
                if (panelId === 'exercisesAiPanel') loadStudentAttempts();
                if (panelId === 'progressPanel') loadStudentGrades();
                if (panelId === 'notificationsPanel') loadStudentNotifications();
            });
        });
    }

    function createCircularProgressRing(pct) {
        const r = 18;
        const circ = 2 * Math.PI * r;
        const offset = circ * (1 - pct / 100);
        return `
        <div style="display:flex; align-items:center; gap:10px;">
            <svg width="44" height="44" viewBox="0 0 44 44" style="flex-shrink:0;">
                <circle cx="22" cy="22" r="${r}" stroke="#e2e8f0" stroke-width="4.5" fill="none"/>
                <circle cx="22" cy="22" r="${r}" stroke="#7a1318" stroke-width="4.5" stroke-dasharray="${circ.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}" stroke-linecap="round" fill="none" transform="rotate(-90 22 22)"/>
                <text x="22" y="26" font-size="10.5" font-weight="800" fill="#0f172a" text-anchor="middle">${pct}%</text>
            </svg>
            <span style="font-size:13px; font-weight:700; color:var(--text-1);">${pct}% Hoàn thành</span>
        </div>`;
    }

    function renderCoursesTable(containerId, list) {
        const targetElem = document.getElementById(containerId);
        if (!targetElem) return;

        if (!list || list.length === 0) {
            targetElem.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-3); padding: 24px;">Chưa có dữ liệu khóa học.</td></tr>`;
            return;
        }

        targetElem.innerHTML = list.map((c, idx) => {
            const pct = Math.round(c.progressPercent || 0);
            const catText = (c.level === 'BEGINNER' || c.level === 'INTERMEDIATE') ? 'Đại Cương' : 'Chuyên Ngành';
            return `
            <tr>
                <td><strong>#${c.id || (idx + 1)}</strong></td>
                <td><strong>${c.title}</strong></td>
                <td>${c.createdByName || 'Giảng viên PTIT'}</td>
                <td><span class="badge badge-primary">${catText}</span></td>
                <td>${createCircularProgressRing(pct)}</td>
                <td>
                    <a href="course-detail.html?id=${c.id || 1}" class="btn btn-secondary btn-sm" style="font-weight:700; white-space:nowrap;">Vào học ➔</a>
                </td>
            </tr>`;
        }).join('');
    }

    function renderAttemptsTable(attempts) {
        const tbody = document.getElementById('studentAttemptsTableBody');
        if (!tbody) return;

        if (!attempts || attempts.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:24px; color:var(--text-3);">Chưa có bài tập AI nào được nộp.</td></tr>`;
            return;
        }

        tbody.innerHTML = attempts.map(a => `
            <tr>
                <td><strong>#${a.attemptId}</strong></td>
                <td style="font-weight:700; color:var(--text-1);">${a.exerciseTitle}</td>
                <td><span class="badge badge-info">${a.courseName}</span></td>
                <td>${a.attemptedAt}</td>
                <td><strong style="color:${a.isCorrect ? '#10b981' : '#ef4444'};">${a.score}</strong></td>
                <td><span class="badge ${a.isCorrect ? 'badge-success' : 'badge-danger'}">${a.status}</span></td>
            </tr>
        `).join('');
    }

    function loadStudentOverview() {
        fetch('/api/v1/student/dashboard-summary', {
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => res.json())
            .then(resData => {
                if (resData && resData.success && resData.data) {
                    const data = resData.data;

                    if (document.getElementById('statCourses')) document.getElementById('statCourses').textContent = data.totalCourses || 0;
                    if (document.getElementById('statProgress')) document.getElementById('statProgress').textContent = (data.avgProgress || 0) + '%';
                    if (document.getElementById('statHours')) document.getElementById('statHours').textContent = data.hoursStudied || 0;
                    if (document.getElementById('statQuiz')) document.getElementById('statQuiz').textContent = data.passedAttemptsRatio || '0/0';

                    if (data.courses) {
                        renderCoursesTable('overviewCoursesTable', data.courses.slice(0, 4));
                    }
                    if (data.attempts && data.attempts.length > 0) {
                        renderAttemptsTable(data.attempts);
                    }
                } else {
                    fetchFallbackCourses();
                }
                renderStudentChart();
            })
            .catch(err => {
                console.error(err);
                fetchFallbackCourses();
                renderStudentChart();
            });
    }

    function fetchFallbackCourses() {
        fetch('/api/v1/courses/all?size=50', {
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => res.json())
            .then(resData => {
                let items = [];
                if (resData && resData.success && resData.data) {
                    items = Array.isArray(resData.data) ? resData.data : (resData.data.items || resData.data.content || []);
                }
                renderCoursesTable('overviewCoursesTable', items.slice(0, 4));
            })
            .catch(err => {
                renderCoursesTable('overviewCoursesTable', []);
            });
    }

    function loadStudentCourses() {
        fetch('/api/v1/student/dashboard-summary', {
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => res.json())
            .then(resData => {
                if (resData && resData.success && resData.data && resData.data.courses) {
                    renderCoursesTable('studentCoursesTableBody', resData.data.courses);
                } else {
                    fetchFallbackCoursesForCoursesTab();
                }
            })
            .catch(err => fetchFallbackCoursesForCoursesTab());
    }

    function fetchFallbackCoursesForCoursesTab() {
        fetch('/api/v1/courses/all?size=50', {
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => res.json())
            .then(resData => {
                let items = [];
                if (resData && resData.success && resData.data) {
                    items = Array.isArray(resData.data) ? resData.data : (resData.data.items || resData.data.content || []);
                }
                renderCoursesTable('studentCoursesTableBody', items);
            })
            .catch(err => renderCoursesTable('studentCoursesTableBody', []));
    }

    function loadStudentAttempts() {
        fetch('/api/v1/student/dashboard-summary', {
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => res.json())
            .then(resData => {
                if (resData && resData.success && resData.data && resData.data.attempts) {
                    renderAttemptsTable(resData.data.attempts);
                }
            })
            .catch(err => console.error(err));
    }

    function loadStudentGrades() {
        fetch('/api/v1/student/dashboard-summary', {
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => res.json())
            .then(resData => {
                if (resData && resData.success && resData.data && resData.data.courses) {
                    const courses = resData.data.courses;
                    document.getElementById('studentGradeTableBody').innerHTML = courses.map(c => `
                        <tr>
                            <td><strong>${c.title}</strong></td>
                            <td>${c.totalChapters || 10} bài</td>
                            <td><span class="badge badge-primary">${c.completedChapters || 0} bài</span></td>
                            <td><strong style="color:#7a1318;">${(c.progressPercent * 0.1).toFixed(1)} / 10</strong></td>
                            <td><span class="badge ${c.progressPercent >= 80 ? 'badge-success' : 'badge-info'}">${c.progressPercent >= 80 ? 'XUẤT SẮC' : (c.progressPercent >= 65 ? 'GIỎI' : 'KHÁ')}</span></td>
                        </tr>
                    `).join('');
                }
            })
            .catch(err => console.error(err));
    }

    function loadStudentNotifications() {
        fetch('/api/v1/notifications', {
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => res.json())
            .then(resData => {
                const list = (resData && resData.success && resData.data && resData.data.content) ? resData.data.content : [];
                const container = document.getElementById('studentNotificationsList');
                if (!container) return;

                if (list.length === 0) {
                    container.innerHTML = `<div style="text-align:center; padding:24px; color:var(--text-3);">Không có thông báo mới nào từ hệ thống.</div>`;
                    return;
                }

                container.innerHTML = list.map(n => `
                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:16px;">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <strong style="font-size:14px; color:var(--text-1);">${n.type || 'HỆ THỐNG'}</strong>
                            <span style="font-size:12px; color:var(--text-3);">${n.createdAt || 'Mới'}</span>
                        </div>
                        <div style="font-size:13.5px; color:var(--text-2);">${n.message}</div>
                    </div>
                `).join('');
            })
            .catch(err => console.error(err));
    }

    function renderStudentChart() {
        const ctxLine = document.getElementById('overviewChart');
        if (ctxLine && window.Chart) {
            new Chart(ctxLine, {
                type: 'line',
                data: {
                    labels: ['Thứ 2', 'Thứ 3', 'Thứ 4', 'Thứ 5', 'Thứ 6', 'Thứ 7', 'Chủ nhật'],
                    datasets: [{
                        label: 'Thời lượng học (Giờ)',
                        data: [3.5, 5.0, 4.2, 6.8, 5.5, 8.0, 9.0],
                        borderColor: '#7a1318',
                        backgroundColor: 'rgba(122, 19, 24, 0.08)',
                        fill: true,
                        tension: 0.35,
                        borderWidth: 3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } }
                }
            });
        }

        const ctxDoughnut = document.getElementById('progressDoughnutChart');
        if (ctxDoughnut && window.Chart) {
            new Chart(ctxDoughnut, {
                type: 'doughnut',
                data: {
                    labels: ['Đã hoàn thành', 'Đang học', 'Chưa bắt đầu'],
                    datasets: [{
                        data: [65, 25, 10],
                        backgroundColor: ['#7a1318', '#fbbf24', '#e2e8f0'],
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11, weight: '600' } } }
                    },
                    cutout: '72%'
                }
            });
        }
    }

    document.addEventListener('DOMContentLoaded', init);
})();
