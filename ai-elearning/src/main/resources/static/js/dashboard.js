// =====================================================
// DASHBOARD LOGIC - PTIT E-Learning
// =====================================================
(function () {
    const token = localStorage.getItem('ptit_token');
    if (!token || token === 'undefined' || token === 'null' || !token.trim()) {
        localStorage.removeItem('ptit_token');
        localStorage.removeItem('ptit_user');
        window.location.replace('/login.html');
        return;
    }

    let currentUser = null;
    let teachers = []; // Store list of teachers for dropdowns
    let currentSelectedCourseIdForLessons = null;

    // Chart instances for cleanup
    let overviewStudentsChartInstance = null;
    let overviewLevelsChartInstance = null;
    let reportProgressChartInstance = null;
    let reportCompletionChartInstance = null;
    let reportBloomChartInstance = null;

    // Helper to safely extract list from API response (Array, items, or content)
    function getListFromData(data) {
        if (!data) return [];
        if (Array.isArray(data)) return data;
        if (Array.isArray(data.items)) return data.items;
        if (Array.isArray(data.content)) return data.content;
        return [];
    }

    // Helper to safely set element text content
    function safeSetText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function handleAuthError() {
        localStorage.removeItem('ptit_token');
        localStorage.removeItem('ptit_user');
        window.location.replace('/login.html');
    }

    // Initialize Dashboard
    function init() {
        setupTabs();

        // Load cached user profile if present to show initial names
        const cachedUserStr = localStorage.getItem('ptit_user');
        if (cachedUserStr) {
            try {
                currentUser = JSON.parse(cachedUserStr);
                if (currentUser) {
                    safeSetText('dbUserFullName', currentUser.name || currentUser.fullName || 'Quản trị viên');
                    safeSetText('dbUserRole', (currentUser.role === 'ADMIN') ? 'Quản trị viên' : 'Giảng viên');
                    setupRolePermissions();
                }
            } catch (e) { console.error(e); }
        }

        // Setup Logout button
        const logoutBtn = document.getElementById('dbLogoutBtn');
        if (logoutBtn) {
            logoutBtn.onclick = (e) => {
                e.preventDefault();
                localStorage.removeItem('ptit_token');
                localStorage.removeItem('ptit_user');
                window.location.href = 'login.html';
            };
        }

        // Trigger immediate data loading for overview stats, recent courses, and teachers list
        loadOverview();
        loadTeachersList();

        // Fetch current user details from backend to verify token & sync profile asynchronously
        fetch('/api/v1/auth/me', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => {
                if (!res.ok && (res.status === 401 || res.status === 403)) {
                    handleAuthError();
                    return null;
                }
                return res.json();
            })
            .then(resData => {
                if (!resData) return;
                if (resData.success && resData.data) {
                    currentUser = resData.data;
                    currentUser.role = (currentUser.roles && currentUser.roles.length > 0) ? currentUser.roles[0] : 'ADMIN';

                    if (currentUser.role !== 'ADMIN' && currentUser.role !== 'TEACHER') {
                        if (window.showToast) window.showToast('Bạn không có quyền truy cập trang quản trị!', 'warning');
                        window.location.href = 'index.html';
                        return;
                    }

                    localStorage.setItem('ptit_user', JSON.stringify({
                        id: currentUser.id,
                        fullName: currentUser.fullName,
                        name: currentUser.fullName,
                        email: currentUser.email,
                        role: currentUser.role
                    }));

                    safeSetText('dbUserFullName', currentUser.fullName);
                    safeSetText('dbUserRole', currentUser.role === 'ADMIN' ? 'Quản trị viên' : 'Giảng viên');

                    setupRolePermissions();
                } else if (resData && !resData.success) {
                    handleAuthError();
                }
            })
            .catch(err => {
                console.error('Lỗi khi kiểm tra phiên làm việc:', err);
            });
    }

    // Helper to safely set element display style
    function safeSetDisplay(id, displayStyle) {
        const el = document.getElementById(id);
        if (el) el.style.display = displayStyle;
    }

    // Role setup
    function setupRolePermissions() {
        const isAdmin = !currentUser || currentUser.role === 'ADMIN';

        safeSetDisplay('btnCreateCourse', isAdmin ? 'inline-block' : 'none');
        safeSetDisplay('btnCreateLesson', 'inline-block');
        safeSetDisplay('navUsers', isAdmin ? 'flex' : 'none');
        safeSetDisplay('navReports', isAdmin ? 'flex' : 'none');
        safeSetDisplay('navNotifications', 'flex');
        safeSetDisplay('navReviews', isAdmin ? 'flex' : 'none');
        safeSetDisplay('navNews', isAdmin ? 'flex' : 'none');
        safeSetDisplay('navSupport', isAdmin ? 'flex' : 'none');
        safeSetDisplay('adminNotiForms', isAdmin ? 'grid' : 'none');
        safeSetDisplay('statusGroup', isAdmin ? 'block' : 'none');
    }

    // Tab Switcher
    function setupTabs() {
        document.querySelectorAll('.db-nav-item').forEach(item => {
            item.onclick = (e) => {
                try {
                    document.querySelectorAll('.db-nav-item').forEach(b => b.classList.remove('active'));
                    document.querySelectorAll('.db-panel').forEach(c => c.classList.remove('active'));

                    item.classList.add('active');
                    const panelId = item.dataset.panel || item.getAttribute('data-panel');
                    const targetPanel = document.getElementById(panelId);
                    if (targetPanel) {
                        targetPanel.classList.add('active');
                    }

                    // Update Header Title safely
                    const titleEl = document.getElementById('dbTitle');
                    if (titleEl) {
                        titleEl.textContent = item.textContent.trim();
                    }

                    // Load panel-specific data
                    if (panelId === 'overviewPanel') loadOverview();
                    if (panelId === 'coursesPanel') loadCourses();
                    if (panelId === 'lessonsPanel') loadLessonsModule();
                    if (panelId === 'exercisesPanel') loadExercisesModule();
                    if (panelId === 'exercisesAiPanel') loadExercisesAiModule();
                    if (panelId === 'usersPanel') loadUsers();
                    if (panelId === 'reportsPanel') loadReports();
                    if (panelId === 'notificationsPanel') loadNotificationsPanel();
                    if (panelId === 'reviewsPanel') loadReviewsPanel();
                    if (panelId === 'newsPanel') loadNewsModule();
                    if (panelId === 'supportPanel') loadSupportTicketsModule();
                } catch (err) {
                    console.error('Lỗi khi chuyển tab:', err);
                }
            };
        });
    }

    // Overview Panel
    function loadOverview() {
        const fetchCoursesUrl = (token && (!currentUser || currentUser.role === 'ADMIN' || currentUser.role === 'TEACHER')) ? '/api/v1/courses/all?size=50' : '/api/v1/courses?size=50';

        fetch(fetchCoursesUrl, {
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => {
                if (!res.ok) {
                    if (res.status === 401 || res.status === 403) {
                        handleAuthError();
                        return null;
                    }
                    return fetch('/api/v1/courses?size=50').then(r => r.json());
                }
                return res.json();
            })
            .then(resData => {
                if (!resData) return;
                const list = (resData && resData.success) ? getListFromData(resData.data) : [];
                safeSetText('statCourses', list.length);

                const tableBody = document.getElementById('overviewCoursesTable');
                if (tableBody) {
                    if (list.length === 0) {
                        tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-3); padding: 20px;">Chưa có khóa học nào trong hệ thống.</td></tr>`;
                    } else {
                        const recent = list.slice(0, 5);
                        tableBody.innerHTML = recent.map(c => {
                            const statusText = c.isVisible ? 'PUBLISHED' : 'DRAFT';
                            const catText = (c.level === 'BEGINNER' || c.level === 'INTERMEDIATE') ? 'Đại Cương' : 'Chuyên ngành';
                            return `
                        <tr>
                            <td><strong>#${c.id}</strong></td>
                            <td style="font-weight:700;">${c.title}</td>
                            <td>${c.createdByName || 'Chưa phân công'}</td>
                            <td><span class="badge badge-primary">${catText}</span></td>
                            <td><span class="badge ${c.isVisible ? 'badge-primary' : 'badge-info'}">${statusText}</span></td>
                        </tr>`;
                        }).join('');
                    }
                }

                // Aggregate lessons count
                let totalLessons = 0;
                list.forEach(c => {
                    totalLessons += (c.chapterCount || 0);
                });
                safeSetText('statLessons', totalLessons);

                if (window.Chart) {
                    renderOverviewCharts(list);
                }
            })
            .catch(err => {
                console.error(err);
                fetch('/api/v1/courses?size=50')
                    .then(r => r.json())
                    .then(resData => {
                        if (resData && resData.success) {
                            const list = getListFromData(resData.data);
                            safeSetText('statCourses', list.length);
                        }
                    })
                    .catch(e => console.error(e));
            });

        // Fetch courses summary stats
        if (token && (!currentUser || currentUser.role === 'ADMIN')) {
            fetch('/api/v1/reports/courses-summary', {
                headers: token ? { 'Authorization': 'Bearer ' + token } : {}
            })
                .then(res => res.json())
                .then(resData => {
                    if (resData && resData.success && resData.data) {
                        const summary = resData.data;
                        safeSetText('statCourses', summary.totalCourses || 0);
                        safeSetText('statStudents', summary.totalStudents || 0);
                        safeSetText('statEnrollments', summary.totalStudents || 0);
                    }
                })
                .catch(err => console.error('Lỗi tải Courses Summary:', err));
        } else {
            safeSetText('statStudents', '0');
            safeSetText('statEnrollments', '0');
        }
    }

    // Helper to render Overview charts
    function renderOverviewCharts(coursesList) {
        if (!window.Chart) return;
        try {
            if (overviewStudentsChartInstance) overviewStudentsChartInstance.destroy();
            if (overviewLevelsChartInstance) overviewLevelsChartInstance.destroy();

            // 1. Phân bố học viên theo khóa học
            const canvasStudents = document.getElementById('overviewStudentsChart');
            if (canvasStudents) {
                const courseLabels = coursesList.map(c => c.title);
                const studentCounts = coursesList.map(c => c.studentCount || 0);

                overviewStudentsChartInstance = new Chart(canvasStudents.getContext('2d'), {
                    type: 'bar',
                    data: {
                        labels: courseLabels,
                        datasets: [{
                            label: 'Số lượng học viên',
                            data: studentCounts,
                            backgroundColor: 'rgba(122, 19, 24, 0.75)', // PTIT Red
                            borderColor: 'rgba(122, 19, 24, 1)',
                            borderWidth: 1.5,
                            borderRadius: 4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, ticks: { stepSize: 1, precision: 0 } } }
                    }
                });
            }

            // 2. Phân loại cấp độ khóa học
            const canvasLevels = document.getElementById('overviewLevelsChart');
            if (canvasLevels) {
                let daiCuongCount = 0;
                let chuyenNganhCount = 0;
                coursesList.forEach(c => {
                    if (c.level === 'BEGINNER' || c.level === 'INTERMEDIATE') daiCuongCount++;
                    else chuyenNganhCount++;
                });

                overviewLevelsChartInstance = new Chart(canvasLevels.getContext('2d'), {
                    type: 'doughnut',
                    data: {
                        labels: ['Đại cương', 'Chuyên ngành'],
                        datasets: [{
                            data: [daiCuongCount, chuyenNganhCount],
                            backgroundColor: ['rgba(59, 130, 246, 0.8)', 'rgba(139, 92, 246, 0.8)'],
                            borderColor: ['#ffffff', '#ffffff'],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'bottom', labels: { padding: 16, font: { size: 12, weight: '600' } } } }
                    }
                });
            }
        } catch (e) {
            console.error('Lỗi khi vẽ biểu đồ tổng quan:', e);
        }
    }

    // Fetch Teachers List
    function loadTeachersList() {
        if (currentUser && currentUser.role !== 'ADMIN') return;
        fetch('/api/v1/users?size=1000', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData && resData.success) {
                    const users = getListFromData(resData.data).map(u => {
                        u.role = u.roles && u.roles.length > 0 ? u.roles[0] : 'STUDENT';
                        return u;
                    });
                    teachers = users.filter(u => u.role === 'TEACHER');

                    const select = document.getElementById('mcTeacher');
                    if (select) {
                        select.innerHTML = teachers.map(t => `<option value="${t.id}">${t.fullName}</option>`).join('');
                    }
                }
            });
    }

    // Courses Panel
    function loadCourses() {
        fetch('/api/v1/courses/all?size=100', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData && resData.success) {
                    const list = getListFromData(resData.data);
                    const tbody = document.getElementById('coursesTableBody');

                    if (list.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-3);">Không có khóa học nào trong hệ thống.</td></tr>`;
                        return;
                    }

                    tbody.innerHTML = list.map(c => {
                        const isCourseOwner = !currentUser || currentUser.role === 'ADMIN' || (currentUser.role === 'TEACHER' && c.createdById === currentUser.id);
                        const statusText = c.isVisible ? 'PUBLISHED' : 'DRAFT';
                        const fileName = c.lecturePdf ? c.lecturePdf.split('/').pop().replace(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_/, '') : 'Chưa cập nhật';

                        let ocrBadge = '<span class="badge" style="background-color: var(--surface-3); color: var(--text-2);">Không có</span>';
                        if (c.ocrStatus === 'PENDING') ocrBadge = '<span class="badge" style="background-color: var(--primary); color: white;">Đang chờ</span>';
                        else if (c.ocrStatus === 'PROCESSING') ocrBadge = '<span class="badge" style="background-color: #f59e0b; color: white;">Đang xử lý</span>';
                        else if (c.ocrStatus === 'COMPLETED') ocrBadge = '<span class="badge" style="background-color: #10b981; color: white;">Hoàn thành</span>';
                        else if (c.ocrStatus === 'FAILED') ocrBadge = '<span class="badge" style="background-color: #ef4444; color: white;">Lỗi</span>';


                        return `
                    <tr>
                        <td><strong>#${c.id}</strong></td>
                        <td style="font-weight: 700; color: var(--primary);">${c.title}</td>
                        <td style="max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${fileName}">${fileName}</td>
                        <td>${ocrBadge}</td>
                        <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${c.description || ''}</td>
                        <td>${c.createdByName || 'Chưa phân công'}</td>
                        <td>${c.chapterCount || 0} chương</td>
                        <td><span class="badge ${c.isVisible ? 'badge-primary' : 'badge-info'}">${statusText}</span></td>
                        <td>
                            <div class="db-btn-actions">
                                ${(!currentUser || currentUser.role === 'ADMIN') ? `
                                    <button class="btn btn-secondary btn-sm" onclick="editCourse(${c.id})">Sửa</button>
                                    <button class="btn btn-outline-primary btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="deleteCourse(${c.id})">Xóa</button>
                                ` : ''}
                            </div>
                        </td>
                    </tr>`;
                    }).join('');
                }
            })
            .catch(err => console.error(err));
    }

    // Course Creation & Modals
    window.closeCourseModal = () => {
        document.getElementById('courseModal').classList.remove('show');
    };

    // Hàm tự động tạo AI Persona bằng cách gọi Python API
    window.autoGeneratePersona = async () => {
        const title = document.getElementById('mcTitle').value.trim();
        if (!title) {
            alert('Vui lòng nhập Tiêu đề khóa học trước khi tạo Persona AI!');
            return;
        }
        const style = document.getElementById('mcTeachingStyle').value;
        const detail = document.getElementById('mcDetailLevel').value;
        const extra = document.getElementById('mcExtraNotes').value.trim();

        const btn = document.getElementById('btnGeneratePersona');
        btn.textContent = '⏳ Đang tạo...';
        btn.disabled = true;

        try {
            const response = await fetch('http://localhost:8001/v1/persona/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    course_title: title,
                    teaching_style: style,
                    detail_level: detail,
                    extra_notes: extra || null
                })
            });
            const data = await response.json();
            if (data.persona_text) {
                document.getElementById('mcAiPersona').value = data.persona_text;
                document.getElementById('mcAiPersonaHidden').value = data.persona_text;
                document.getElementById('personaPreviewGroup').style.display = 'block';
            } else {
                alert('Không thể tạo Persona. Vui lòng thử lại!');
            }
        } catch (err) {
            alert('Lỗi kết nối tới AI Service. Bạn có thể tự nhập prompt vào ô bên dưới.');
            document.getElementById('personaPreviewGroup').style.display = 'block';
        } finally {
            btn.textContent = 'Tạo Prompt AI Tự Động';
            btn.disabled = false;
        }
    };

    // Sync textarea → hidden input khi người dùng chỉnh sửa thủ công
    document.getElementById('mcAiPersona').addEventListener('input', () => {
        document.getElementById('mcAiPersonaHidden').value = document.getElementById('mcAiPersona').value;
    });

    // Thumbnail image preview khi chọn file
    document.getElementById('mcThumbnailFile').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        if (file.size > 5 * 1024 * 1024) {
            alert('Ảnh quá lớn! Vui lòng chọn ảnh dưới 5MB.');
            e.target.value = '';
            return;
        }
        const reader = new FileReader();
        reader.onload = (ev) => {
            const preview = document.getElementById('thumbnailPreview');
            const placeholder = document.getElementById('thumbnailPlaceholder');
            preview.src = ev.target.result;
            preview.style.display = 'block';
            placeholder.style.display = 'none';
            document.getElementById('thumbnailUploadArea').style.borderColor = '#10b981';
        };
        reader.readAsDataURL(file);
    });

    const btnCreateCourse = document.getElementById('btnCreateCourse');
    if (btnCreateCourse) {
        btnCreateCourse.addEventListener('click', () => {
            document.getElementById('courseForm').reset();
            document.getElementById('modalCourseId').value = '';
            document.getElementById('mcPdfFile').value = '';
            document.getElementById('mcPdfLinkContainer').style.display = 'none';
            document.getElementById('personaPreviewGroup').style.display = 'none';
            document.getElementById('mcAiPersona').value = '';
            document.getElementById('mcAiPersonaHidden').value = '';
            // Reset thumbnail
            document.getElementById('mcThumbnailFile').value = '';
            document.getElementById('thumbnailPreview').style.display = 'none';
            document.getElementById('thumbnailPreview').src = '';
            document.getElementById('thumbnailPlaceholder').style.display = 'block';
            document.getElementById('thumbnailUploadArea').style.borderColor = 'var(--border)';
            document.getElementById('mcThumbnailCurrentLink').style.display = 'none';
            document.getElementById('courseModalTitle').textContent = 'Thêm khóa học mới';
            document.getElementById('courseModal').classList.add('show');
        });
    }

    // Course Form Submit
    document.getElementById('courseForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const cId = document.getElementById('modalCourseId').value;
        const title = document.getElementById('mcTitle').value.trim();
        const desc = document.getElementById('mcDescription').value.trim();
        const cat = document.getElementById('mcCategory').value;
        const thumb = document.getElementById('mcThumbLabel').value.trim();
        const status = document.getElementById('mcStatus').value;

        const payload = {
            title: title,
            description: desc,
            level: cat === 'daicuong' ? 'BEGINNER' : 'ADVANCED',
            thumbnailUrl: thumb,
            isVisible: status === 'PUBLISHED',
            aiPersona: document.getElementById('mcAiPersonaHidden').value.trim() || null
        };

        const method = cId ? 'PUT' : 'POST';
        const url = cId ? `/api/v1/courses/${cId}` : '/api/v1/courses';

        fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(payload)
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const savedCourseId = resData.data.id;

                    const handleVisibilityAndFinish = () => {
                        if (cId && currentUser.role === 'ADMIN') {
                            const isVisible = status === 'PUBLISHED';
                            fetch(`/api/v1/courses/${cId}/visibility?isVisible=${isVisible}`, {
                                method: 'PATCH',
                                headers: {
                                    'Authorization': 'Bearer ' + token
                                }
                            })
                                .then(() => {
                                    closeCourseModal();
                                    loadCourses();
                                });
                        } else {
                            closeCourseModal();
                            loadCourses();
                        }
                    };

                    // Upload thumbnail nếu có chọn file ảnh mới
                    const thumbnailFile = document.getElementById('mcThumbnailFile').files[0];
                    const uploadThumbnailIfNeeded = (afterCallback) => {
                        if (!thumbnailFile) { afterCallback(); return; }
                        const thumbFormData = new FormData();
                        thumbFormData.append('file', thumbnailFile);
                        fetch(`/api/v1/courses/${savedCourseId}/upload-thumbnail`, {
                            method: 'POST',
                            headers: { 'Authorization': 'Bearer ' + token },
                            body: thumbFormData
                        })
                            .then(r => r.json())
                            .then(tRes => {
                                if (!tRes.success) {
                                    console.warn('Cảnh báo: Upload ảnh đại diện thất bại:', tRes.message);
                                }
                                afterCallback();
                            })
                            .catch(err => { console.error(err); afterCallback(); });
                    };

                    const pdfFile = document.getElementById('mcPdfFile').files[0];
                    if (pdfFile) {
                        const submitBtn = document.querySelector('#courseForm button[type="submit"]');
                        if (submitBtn) {
                            submitBtn.disabled = true;
                            submitBtn.textContent = 'Đang xử lý tải lên...';
                        }

                        const formData = new FormData();
                        formData.append('file', pdfFile);

                        const progressDiv = document.getElementById('coursePdfUploadProgress');
                        const progressBar = document.getElementById('coursePdfUploadBar');
                        const progressPercent = document.getElementById('coursePdfPercent');
                        const statusText = document.getElementById('coursePdfStatusText');

                        if (progressDiv) {
                            progressDiv.style.display = 'block';
                            progressBar.style.width = '0%';
                            progressPercent.textContent = '0%';
                            statusText.textContent = 'Đang tải file lên server...';
                        }

                        const xhr = new XMLHttpRequest();
                        xhr.open('POST', `/api/v1/courses/${savedCourseId}/upload-pdf`, true);
                        xhr.setRequestHeader('Authorization', 'Bearer ' + token);

                        xhr.upload.onprogress = (event) => {
                            if (event.lengthComputable && progressDiv) {
                                const percent = Math.round((event.loaded / event.total) * 100);
                                progressBar.style.width = percent + '%';
                                progressPercent.textContent = percent + '%';
                                if (percent === 100) {
                                    statusText.textContent = 'File đã lên server. Đang khởi động AI OCR ngầm...';
                                }
                            }
                        };

                        xhr.onload = () => {
                            if (xhr.status >= 200 && xhr.status < 300) {
                                try {
                                    const uploadResData = JSON.parse(xhr.responseText);
                                    if (!uploadResData.success) {
                                        alert('Cảnh báo: Khóa học đã lưu nhưng tải lên tệp PDF thất bại: ' + uploadResData.message);
                                        if (submitBtn) {
                                            submitBtn.disabled = false;
                                            submitBtn.textContent = 'Lưu khóa học';
                                        }
                                        if (progressDiv) progressDiv.style.display = 'none';
                                        uploadThumbnailIfNeeded(handleVisibilityAndFinish);
                                        return;
                                    }

                                    // FAKE PROGRESS FOR BACKGROUND OCR (UX visual feedback)
                                    if (progressDiv) {
                                        progressBar.style.width = '20%';
                                        progressPercent.textContent = '20%';
                                        statusText.textContent = 'Đang khởi động Model OCR (trên server GPU)...';

                                        let fakeProgress = 20;
                                        const interval = setInterval(() => {
                                            fakeProgress += Math.floor(Math.random() * 15) + 5;
                                            if (fakeProgress < 100) {
                                                progressBar.style.width = fakeProgress + '%';
                                                progressPercent.textContent = fakeProgress + '%';
                                                if (fakeProgress > 60) {
                                                    statusText.textContent = 'Đang xếp hàng đợi xử lý tài liệu...';
                                                }
                                            } else {
                                                clearInterval(interval);
                                                progressBar.style.width = '100%';
                                                progressPercent.textContent = '100%';
                                                statusText.textContent = 'Đã nạp file thành công! AI đang xử lý ngầm.';

                                                setTimeout(() => {
                                                    if (submitBtn) {
                                                        submitBtn.disabled = false;
                                                        submitBtn.textContent = 'Lưu khóa học';
                                                    }
                                                    progressDiv.style.display = 'none';
                                                    uploadThumbnailIfNeeded(handleVisibilityAndFinish);
                                                }, 1500); // Wait 1.5s at 100% before closing
                                            }
                                        }, 400); // 400ms per tick ~ takes about 3 seconds total
                                        return; // Wait for interval to finish
                                    }
                                } catch (e) { }
                            } else {
                                alert('Cảnh báo: Khóa học đã lưu nhưng máy chủ trả về lỗi khi tải tệp PDF.');
                            }

                            if (submitBtn) {
                                submitBtn.disabled = false;
                                submitBtn.textContent = 'Lưu khóa học';
                            }
                            if (progressDiv) progressDiv.style.display = 'none';
                            uploadThumbnailIfNeeded(handleVisibilityAndFinish);
                        };

                        xhr.onerror = () => {
                            console.error('Lỗi mạng khi tải lên file PDF');
                            alert('Cảnh báo: Khóa học đã lưu nhưng tải lên PDF gặp lỗi mạng.');
                            if (submitBtn) {
                                submitBtn.disabled = false;
                                submitBtn.textContent = 'Lưu khóa học';
                            }
                            if (progressDiv) progressDiv.style.display = 'none';
                            uploadThumbnailIfNeeded(handleVisibilityAndFinish);
                        };

                        xhr.send(formData);
                    } else {
                        uploadThumbnailIfNeeded(handleVisibilityAndFinish);
                    }
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            })
            .catch(err => console.error(err));
    });

    window.editCourse = (courseId) => {
        fetch(`/api/v1/courses/${courseId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const c = resData.data;
                    document.getElementById('modalCourseId').value = c.id;
                    document.getElementById('mcTitle').value = c.title;
                    document.getElementById('mcDescription').value = c.description || '';
                    document.getElementById('mcTeacher').value = c.createdById || '';
                    document.getElementById('mcDuration').value = 0;
                    document.getElementById('mcCategory').value = (c.level === 'BEGINNER' || c.level === 'INTERMEDIATE') ? 'daicuong' : 'chuyennganh';
                    document.getElementById('mcThumbLabel').value = c.thumbnailUrl || '';
                    document.getElementById('mcStatus').value = c.isVisible ? 'PUBLISHED' : 'DRAFT';

                    // Điền lại AI Persona nếu có
                    if (c.aiPersona && c.aiPersona.trim()) {
                        document.getElementById('mcAiPersona').value = c.aiPersona;
                        document.getElementById('mcAiPersonaHidden').value = c.aiPersona;
                        document.getElementById('personaPreviewGroup').style.display = 'block';
                    } else {
                        document.getElementById('mcAiPersona').value = '';
                        document.getElementById('mcAiPersonaHidden').value = '';
                        document.getElementById('personaPreviewGroup').style.display = 'none';
                    }

                    document.getElementById('mcPdfFile').value = '';
                    const pdfLinkContainer = document.getElementById('mcPdfLinkContainer');
                    if (c.lecturePdf && c.lecturePdf !== 'null' && c.lecturePdf !== 'undefined') {
                        pdfLinkContainer.style.display = 'block';
                        document.getElementById('mcPdfLink').href = c.lecturePdf;
                    } else {
                        pdfLinkContainer.style.display = 'none';
                    }

                    // Hiển thị ảnh đại diện hiện tại
                    document.getElementById('mcThumbnailFile').value = '';
                    const thumbnailPreview = document.getElementById('thumbnailPreview');
                    const thumbnailPlaceholder = document.getElementById('thumbnailPlaceholder');
                    const thumbnailCurrentLink = document.getElementById('mcThumbnailCurrentLink');
                    if (c.thumbnailUrl && c.thumbnailUrl !== 'null' && c.thumbnailUrl !== 'undefined') {
                        thumbnailPreview.src = c.thumbnailUrl;
                        thumbnailPreview.style.display = 'block';
                        thumbnailPlaceholder.style.display = 'none';
                        document.getElementById('thumbnailUploadArea').style.borderColor = '#10b981';
                        if (c.thumbnailUrl.startsWith('/uploads/')) {
                            thumbnailCurrentLink.style.display = 'block';
                            document.getElementById('mcThumbnailCurrentUrl').href = c.thumbnailUrl;
                        } else {
                            thumbnailCurrentLink.style.display = 'none';
                        }
                    } else {
                        thumbnailPreview.src = '';
                        thumbnailPreview.style.display = 'none';
                        thumbnailPlaceholder.style.display = 'block';
                        document.getElementById('thumbnailUploadArea').style.borderColor = 'var(--border)';
                        thumbnailCurrentLink.style.display = 'none';
                    }

                    document.getElementById('courseModalTitle').textContent = 'Sửa thông tin khóa học';
                    document.getElementById('courseModal').classList.add('show');
                }
            });
    };

    window.deleteCourse = async (courseId) => {
        const ok = await window.showConfirm('Bạn có chắc chắn muốn xóa khóa học này không?');
        if (!ok) return;
        fetch(`/api/v1/courses/${courseId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => {
                if (res.ok) {
                    loadCourses();
                } else {
                    alert('Không thể xóa khóa học đã có học viên đăng ký tiến độ học tập!');
                }
            });
    };

    // Lessons Module
    function loadLessonsModule() {
        fetch('/api/v1/courses/all?size=100', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const courses = getListFromData(resData.data);
                    const selector = document.getElementById('lessonCourseSelector');
                    selector.innerHTML = `<option value="">-- Chọn khóa học quản lý --</option>` +
                        courses.map(c => `<option value="${c.id}">${c.title}</option>`).join('');

                    // If already selected a course, preserve it
                    if (currentSelectedCourseIdForLessons) {
                        selector.value = currentSelectedCourseIdForLessons;
                        loadLessonsTable(currentSelectedCourseIdForLessons);
                    }
                }
            });
    }

    document.getElementById('lessonCourseSelector').addEventListener('change', (e) => {
        const cId = e.target.value;
        currentSelectedCourseIdForLessons = cId;
        if (cId) {
            loadLessonsTable(cId);
        } else {
            document.getElementById('lessonsTableBody').innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-3);">Vui lòng chọn một khóa học phía trên để xem bài giảng.</td></tr>`;
        }
    });

    function loadLessonsTable(courseId) {
        fetch(`/api/v1/courses/${courseId}/chapters`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const lessons = resData.data || [];
                    const tbody = document.getElementById('lessonsTableBody');

                    if (lessons.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-3);">Khóa học này chưa có chương học nào.</td></tr>`;
                        return;
                    }

                    tbody.innerHTML = lessons.map((l, i) => `
                    <tr>
                        <td><strong>${l.chapterNumber || (i + 1)}</strong></td>
                        <td style="font-weight: 700;">${l.chapterName || 'Chương học'}</td>
                        <td>${l.subjectName || ''}</td>
                        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${l.content || ''}</td>
                        <td><span class="badge ${!l.isLocked ? 'badge-primary' : 'badge-info'}">${!l.isLocked ? 'Hoạt động' : 'Khóa'}</span></td>
                        <td>
                            <div class="db-btn-actions">
                                <button class="btn btn-secondary btn-sm" onclick="editLesson(${l.id})">Sửa</button>
                                <button class="btn btn-outline-primary btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="deleteLesson(${l.id})">Xóa</button>
                                <button class="btn btn-primary btn-sm" style="background:#10b981; border-color:#10b981;" onclick="manageExercises(${l.id})">BT Chương</button>
                                <button class="btn btn-primary btn-sm" style="background:#8b5cf6; border-color:#8b5cf6;" onclick="manageExercisesAi(${l.id})">BT AI</button>
                            </div>
                        </td>
                    </tr>`).join('');
                }
            });
    }

    // Lesson Modal Management
    window.closeLessonModal = () => {
        document.getElementById('lessonModal').classList.remove('show');
    };

    const btnCreateLesson = document.getElementById('btnCreateLesson');
    if (btnCreateLesson) {
        btnCreateLesson.addEventListener('click', () => {
            if (!currentSelectedCourseIdForLessons) {
                alert('Vui lòng chọn khóa học trước khi thêm chương học!');
                return;
            }
            document.getElementById('lessonForm').reset();
            document.getElementById('modalLessonId').value = '';
            document.getElementById('lessonModalTitle').textContent = 'Thêm chương học mới';
            document.getElementById('lessonModal').classList.add('show');
        });
    }

    document.getElementById('lessonForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const lId = document.getElementById('modalLessonId').value;
        const title = document.getElementById('mlTitle').value.trim();
        const text = document.getElementById('mlTextContent').value.trim();
        const order = parseInt(document.getElementById('mlOrderIndex').value) || 1;
        const subjectName = document.getElementById('mlSubjectName').value.trim();
        const chapterNum = parseInt(document.getElementById('mlChapterNumber').value) || 1;
        const isLocked = document.getElementById('mlIsLocked').value === 'true';

        const payload = {
            subjectName: subjectName,
            chapterNumber: chapterNum,
            chapterName: title,
            content: text ? text : null,
            orderIndex: order,
            isLocked: isLocked
        };

        const fetchUrl = lId ? `/api/v1/chapters/${lId}` : `/api/v1/courses/${currentSelectedCourseIdForLessons}/chapters`;
        const method = lId ? 'PUT' : 'POST';

        fetch(fetchUrl, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(payload)
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    closeLessonModal();
                    loadLessonsTable(currentSelectedCourseIdForLessons);
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            });
    });

    window.editLesson = (lessonId) => {
        fetch(`/api/v1/chapters/${lessonId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const l = resData.data;
                    document.getElementById('modalLessonId').value = l.id;
                    document.getElementById('mlTitle').value = l.chapterName || '';
                    document.getElementById('mlSubjectName').value = l.subjectName || '';
                    document.getElementById('mlChapterNumber').value = l.chapterNumber || 1;
                    document.getElementById('mlTextContent').value = l.content || '';
                    document.getElementById('mlOrderIndex').value = l.orderIndex || 1;
                    document.getElementById('mlIsLocked').value = l.isLocked ? 'true' : 'false';

                    document.getElementById('lessonModalTitle').textContent = 'Sửa thông tin chương học';
                    document.getElementById('lessonModal').classList.add('show');
                }
            });
    };

    window.deleteLesson = async (lessonId) => {
        const ok = await window.showConfirm('Bạn có chắc chắn muốn xóa chương học này không? Cảnh báo: tất cả bài tập thuộc chương học cũng sẽ bị xóa!');
        if (!ok) return;
        fetch(`/api/v1/chapters/${lessonId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => {
                if (res.ok) {
                    loadLessonsTable(currentSelectedCourseIdForLessons);
                } else {
                    alert('Không thể xóa chương học này.');
                }
            });
    };

    // --- EXERCISES & AI EXERCISES MANAGEMENT PANELS ---
    let currentSelectedCourseIdForExercises = null;
    let currentSelectedChapterIdForExercises = null;
    let currentSelectedCourseIdForExercisesAi = null;
    let currentSelectedChapterIdForExercisesAi = null;

    window.closeExerciseModal = () => {
        document.getElementById('exerciseModal').classList.remove('show');
    };
    window.closeExerciseAiModal = () => {
        document.getElementById('exerciseAiModal').classList.remove('show');
    };
    window.closeExerciseAiPdfUploadModal = () => {
        document.getElementById('exerciseAiPdfUploadModal').classList.remove('show');
    };
    window.openExerciseAiPdfUploadModal = () => {
        const courseSelect = document.getElementById('exerciseAiCourseSelector');
        const chapterSelect = document.getElementById('exerciseAiChapterSelector');

        if (!currentSelectedChapterIdForExercisesAi) {
            alert('Vui lòng chọn khóa học và chương học trước khi tải PDF bài tập AI!');
            return;
        }

        const courseTitle = courseSelect.options[courseSelect.selectedIndex].text;
        const chapterTitle = chapterSelect.options[chapterSelect.selectedIndex].text;

        document.getElementById('exerciseAiPdfUploadForm').reset();
        document.getElementById('uploadExerciseAiPdfCourseTitle').value = courseTitle;
        document.getElementById('uploadExerciseAiPdfChapterTitle').value = chapterTitle;
        document.getElementById('exerciseAiPdfUploadProgress').style.display = 'none';
        document.getElementById('exerciseAiPdfUploadBar').style.width = '0%';
        document.getElementById('exerciseAiPdfPercent').textContent = '0%';
        document.getElementById('exerciseAiPdfStatusText').textContent = 'Đang tải file lên...';

        document.getElementById('exerciseAiPdfUploadModal').classList.add('show');
    };

    // --- BT CHƯƠNG PANEL ---
    function loadExercisesModule() {
        fetch('/api/v1/courses/all?size=100', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const courses = getListFromData(resData.data);
                    const selector = document.getElementById('exerciseCourseSelector');
                    selector.innerHTML = `<option value="">-- Chọn khóa học --</option>` +
                        courses.map(c => `<option value="${c.id}">${c.title}</option>`).join('');

                    if (currentSelectedCourseIdForExercises) {
                        selector.value = currentSelectedCourseIdForExercises;
                        loadExerciseChapters(currentSelectedCourseIdForExercises);
                    }
                }
            });
    }

    function loadExerciseChapters(courseId, selectChapterId = null) {
        fetch(`/api/v1/courses/${courseId}/chapters`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const chapters = resData.data || [];
                    const selector = document.getElementById('exerciseChapterSelector');
                    selector.innerHTML = `<option value="">-- Chọn chương học --</option>` +
                        chapters.map(ch => `<option value="${ch.id}">Chương ${ch.chapterNumber}: ${ch.chapterName}</option>`).join('');

                    if (selectChapterId) {
                        selector.value = selectChapterId;
                        currentSelectedChapterIdForExercises = selectChapterId;
                        loadExercisesPanelTable(selectChapterId);
                    } else if (currentSelectedChapterIdForExercises) {
                        selector.value = currentSelectedChapterIdForExercises;
                        loadExercisesPanelTable(currentSelectedChapterIdForExercises);
                    } else {
                        document.getElementById('btnCreateExercisePanel').style.display = 'none';
                        document.getElementById('exercisePanelTableBody').innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Vui lòng chọn chương học để xem bài tập.</td></tr>`;
                    }
                }
            });
    }

    function loadExercisesPanelTable(chapterId) {
        document.getElementById('btnCreateExercisePanel').style.display = 'inline-block';
        fetch(`/api/v1/chapters/${chapterId}/exercises`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                const tbody = document.getElementById('exercisePanelTableBody');
                if (resData.success && resData.data && resData.data.length > 0) {
                    tbody.innerHTML = resData.data.map(ex => `
                    <tr>
                        <td><strong>${ex.exerciseCode || ''}</strong></td>
                        <td>${ex.exerciseName || ''}</td>
                        <td><span class="badge badge-info">${ex.difficulty}</span></td>
                        <td><span class="badge badge-primary">${ex.bloomLevel}</span></td>
                        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${ex.question || ''}</td>
                        <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${ex.correctAnswer || ''}</td>
                        <td>
                            <div class="db-btn-actions">
                                <button class="btn btn-secondary btn-sm" onclick="editExercise(${ex.id})">Sửa</button>
                                <button class="btn btn-outline-primary btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="deleteExercise(${ex.id})">Xóa</button>
                            </div>
                        </td>
                    </tr>`).join('');
                } else {
                    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Chưa có bài tập nào cho chương này.</td></tr>`;
                }
            });
    }

    // --- BT AI PANEL ---
    function loadExercisesAiModule() {
        fetch('/api/v1/courses/all?size=100', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const courses = getListFromData(resData.data);
                    const selector = document.getElementById('exerciseAiCourseSelector');
                    selector.innerHTML = `<option value="">-- Chọn khóa học --</option>` +
                        courses.map(c => `<option value="${c.id}">${c.title}</option>`).join('');

                    if (currentSelectedCourseIdForExercisesAi) {
                        selector.value = currentSelectedCourseIdForExercisesAi;
                        loadExerciseAiChapters(currentSelectedCourseIdForExercisesAi);
                    }
                }
            });
    }

    function loadExerciseAiChapters(courseId, selectChapterId = null) {
        fetch(`/api/v1/courses/${courseId}/chapters`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const chapters = resData.data || [];
                    const selector = document.getElementById('exerciseAiChapterSelector');
                    selector.innerHTML = `<option value="">-- Chọn chương học --</option>` +
                        chapters.map(ch => `<option value="${ch.id}">Chương ${ch.chapterNumber}: ${ch.chapterName}</option>`).join('');

                    if (selectChapterId) {
                        selector.value = selectChapterId;
                        currentSelectedChapterIdForExercisesAi = selectChapterId;
                        loadExercisesAiPanelTable(selectChapterId);
                    } else if (currentSelectedChapterIdForExercisesAi) {
                        selector.value = currentSelectedChapterIdForExercisesAi;
                        loadExercisesAiPanelTable(currentSelectedChapterIdForExercisesAi);
                    } else {
                        document.getElementById('btnCreateExerciseAiPanel').style.display = 'none';
                        document.getElementById('exerciseAiPanelTableBody').innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Vui lòng chọn chương học để xem bài tập AI.</td></tr>`;
                    }
                }
            });
    }

    function loadExercisesAiPanelTable(chapterId) {
        document.getElementById('btnCreateExerciseAiPanel').style.display = 'inline-block';
        fetch(`/api/v1/chapters/${chapterId}/exercises-ai`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                const tbody = document.getElementById('exerciseAiPanelTableBody');
                if (resData.success && resData.data && resData.data.length > 0) {
                    tbody.innerHTML = resData.data.map(ex => `
                    <tr>
                        <td><strong>${ex.exerciseCode || ''}</strong></td>
                        <td>${ex.exerciseName || ''}</td>
                        <td><span class="badge badge-info">${ex.difficulty}</span></td>
                        <td><span class="badge badge-primary">${ex.bloomLevel}</span></td>
                        <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${ex.question || ''}</td>
                        <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${ex.correctAnswer || ''}</td>
                        <td>
                            <div class="db-btn-actions">
                                <button class="btn btn-secondary btn-sm" onclick="editExerciseAi(${ex.id})">Sửa</button>
                                <button class="btn btn-outline-primary btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="deleteExerciseAi(${ex.id})">Xóa</button>
                            </div>
                        </td>
                    </tr>`).join('');
                } else {
                    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Chưa có bài tập AI nào cho chương này.</td></tr>`;
                }
            });
    }

    // --- BIND SELECTORS AND CREATE BUTTONS ---
    document.getElementById('exerciseCourseSelector').addEventListener('change', (e) => {
        const cId = e.target.value;
        currentSelectedCourseIdForExercises = cId;
        currentSelectedChapterIdForExercises = null;
        if (cId) {
            loadExerciseChapters(cId);
        } else {
            document.getElementById('exerciseChapterSelector').innerHTML = `<option value="">-- Chọn chương học --</option>`;
            document.getElementById('btnCreateExercisePanel').style.display = 'none';
            document.getElementById('exercisePanelTableBody').innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Vui lòng chọn khóa học và chương học phía trên để xem danh sách bài tập.</td></tr>`;
        }
    });

    document.getElementById('exerciseChapterSelector').addEventListener('change', (e) => {
        const chId = e.target.value;
        currentSelectedChapterIdForExercises = chId;
        if (chId) {
            loadExercisesPanelTable(chId);
        } else {
            document.getElementById('btnCreateExercisePanel').style.display = 'none';
            document.getElementById('exercisePanelTableBody').innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Vui lòng chọn chương học để xem bài tập.</td></tr>`;
        }
    });

    document.getElementById('exerciseAiCourseSelector').addEventListener('change', (e) => {
        const cId = e.target.value;
        currentSelectedCourseIdForExercisesAi = cId;
        currentSelectedChapterIdForExercisesAi = null;
        if (cId) {
            loadExerciseAiChapters(cId);
        } else {
            document.getElementById('exerciseAiChapterSelector').innerHTML = `<option value="">-- Chọn chương học --</option>`;
            document.getElementById('btnCreateExerciseAiPanel').style.display = 'none';
            document.getElementById('exerciseAiPanelTableBody').innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Vui lòng chọn khóa học và chương học phía trên để xem danh sách bài tập AI.</td></tr>`;
        }
    });

    document.getElementById('exerciseAiChapterSelector').addEventListener('change', (e) => {
        const chId = e.target.value;
        currentSelectedChapterIdForExercisesAi = chId;
        if (chId) {
            loadExercisesAiPanelTable(chId);
        } else {
            document.getElementById('btnCreateExerciseAiPanel').style.display = 'none';
            document.getElementById('exerciseAiPanelTableBody').innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Vui lòng chọn chương học để xem bài tập AI.</td></tr>`;
        }
    });

    // BT Chương Add new click
    document.getElementById('btnCreateExercisePanel').addEventListener('click', () => {
        document.getElementById('exerciseForm').reset();
        document.getElementById('modalExerciseId').value = '';
        document.getElementById('modalExerciseChapterId').value = currentSelectedChapterIdForExercises;
        document.getElementById('exerciseModalTitle').textContent = 'Thêm bài tập mới';
        document.getElementById('exerciseModal').classList.add('show');
    });

    // BT AI Add new click
    document.getElementById('btnCreateExerciseAiPanel').addEventListener('click', () => {
        document.getElementById('exerciseAiForm').reset();
        document.getElementById('modalExerciseAiId').value = '';
        document.getElementById('modalExerciseAiChapterId').value = currentSelectedChapterIdForExercisesAi;
        document.getElementById('exerciseAiModalTitle').textContent = 'Thêm bài tập AI mới';
        document.getElementById('exerciseAiModal').classList.add('show');
    });

    // BT AI PDF Upload click
    document.getElementById('btnUploadExerciseAiPdfPanel').addEventListener('click', () => {
        openExerciseAiPdfUploadModal();
    });

    // BT AI Auto Generate click
    document.getElementById('btnAutoGenerateExerciseAi').addEventListener('click', async () => {
        if (!currentSelectedChapterIdForExercisesAi) {
            alert('Vui lòng chọn khóa học và chương học trước!');
            return;
        }
        
        const okAI = await window.showConfirm('AI (DeepSeek + Qwen) sẽ đọc lý thuyết và tự động sinh bài tập. Quá trình này có thể mất 30-60 giây. Bạn có muốn tiếp tục?');
        if (okAI) {
            const btn = document.getElementById('btnAutoGenerateExerciseAi');
            const originalText = btn.innerHTML;
            btn.disabled = true;

            // Mở Modal Loading
            const loadingModal = document.getElementById('aiLoadingModal');
            const progressBar = document.getElementById('aiLoadingBar');
            const progressPercent = document.getElementById('aiLoadingPercent');
            const statusTitle = document.getElementById('aiLoadingTitle');
            
            statusTitle.textContent = 'AI đang xử lý...';
            progressBar.style.width = '0%';
            progressPercent.textContent = '0%';
            loadingModal.classList.add('show');
            
            // Giả lập thanh tiến trình chạy đều đến 95% trong 45s
            let progress = 0;
            const progressInterval = setInterval(() => {
                if (progress < 95) {
                    progress += 2; // Tăng 2% mỗi giây -> khoảng 47s là tới 94%
                    progressBar.style.width = progress + '%';
                    progressPercent.textContent = progress + '%';
                }
            }, 1000);
            
            fetch(`/api/v1/chapters/${currentSelectedChapterIdForExercisesAi}/exercises-ai/generate-auto`, {
                method: 'POST',
                headers: { 'Authorization': 'Bearer ' + token }
            })
            .then(res => res.json().then(data => ({ ok: res.ok, status: res.status, data })))
            .then(({ ok, status, data }) => {
                clearInterval(progressInterval);
                btn.innerHTML = originalText;
                btn.disabled = false;
                
                if (ok && data.success) {
                    progressBar.style.width = '100%';
                    progressPercent.textContent = '100%';
                    statusTitle.textContent = 'Sinh bài tập thành công!';
                    
                    setTimeout(() => {
                        loadingModal.classList.remove('show');
                        alert('✅ Sinh bài tập AI thành công!');
                        loadExercisesAiPanelTable(currentSelectedChapterIdForExercisesAi);
                    }, 500);
                } else {
                    loadingModal.classList.remove('show');
                    // Lấy message lỗi từ nhiều field có thể có
                    const errMsg = data.message || data.detail || data.error || JSON.stringify(data);
                    alert('❌ Lỗi khi gọi AI Service sinh bài tập: ' + status + ' - ' + errMsg);
                }
            })
            .catch(err => {
                clearInterval(progressInterval);
                loadingModal.classList.remove('show');
                btn.innerHTML = originalText;
                btn.disabled = false;
                console.error(err);
                alert('❌ Lỗi kết nối khi sinh bài tập AI: ' + err.message);
            });
        }
    });

    // --- DEEP LINKS / REDIRECTS FROM LESSONS ---
    window.manageExercises = (chapterId) => {
        fetch(`/api/v1/chapters/${chapterId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const chapter = resData.data;
                    currentSelectedCourseIdForExercises = chapter.courseId;
                    currentSelectedChapterIdForExercises = chapter.id;

                    // Switch sidebar item to active
                    document.querySelectorAll('.db-nav-item').forEach(b => b.classList.remove('active'));
                    document.querySelectorAll('.db-panel').forEach(c => c.classList.remove('active'));

                    const navEx = document.getElementById('navExercises');
                    navEx.classList.add('active');
                    document.getElementById('exercisesPanel').classList.add('active');
                    document.getElementById('dbTitle').textContent = navEx.textContent;

                    // Load selectors and select values
                    fetch('/api/v1/courses?size=100', {
                        headers: { 'Authorization': 'Bearer ' + token }
                    })
                        .then(r => r.json())
                        .then(cData => {
                            if (cData.success) {
                                const courses = getListFromData(cData.data);
                                const selector = document.getElementById('exerciseCourseSelector');
                                selector.innerHTML = `<option value="">-- Chọn khóa học --</option>` +
                                    courses.map(c => `<option value="${c.id}">${c.title}</option>`).join('');
                                selector.value = currentSelectedCourseIdForExercises;

                                loadExerciseChapters(currentSelectedCourseIdForExercises, currentSelectedChapterIdForExercises);
                            }
                        });
                }
            });
    };

    window.manageExercisesAi = (chapterId) => {
        fetch(`/api/v1/chapters/${chapterId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const chapter = resData.data;
                    currentSelectedCourseIdForExercisesAi = chapter.courseId;
                    currentSelectedChapterIdForExercisesAi = chapter.id;

                    // Switch sidebar item to active
                    document.querySelectorAll('.db-nav-item').forEach(b => b.classList.remove('active'));
                    document.querySelectorAll('.db-panel').forEach(c => c.classList.remove('active'));

                    const navExAi = document.getElementById('navExercisesAi');
                    navExAi.classList.add('active');
                    document.getElementById('exercisesAiPanel').classList.add('active');
                    document.getElementById('dbTitle').textContent = navExAi.textContent;

                    // Load selectors and select values
                    fetch('/api/v1/courses?size=100', {
                        headers: { 'Authorization': 'Bearer ' + token }
                    })
                        .then(r => r.json())
                        .then(cData => {
                            if (cData.success) {
                                const courses = getListFromData(cData.data);
                                const selector = document.getElementById('exerciseAiCourseSelector');
                                selector.innerHTML = `<option value="">-- Chọn khóa học --</option>` +
                                    courses.map(c => `<option value="${c.id}">${c.title}</option>`).join('');
                                selector.value = currentSelectedCourseIdForExercisesAi;

                                loadExerciseAiChapters(currentSelectedCourseIdForExercisesAi, currentSelectedChapterIdForExercisesAi);
                            }
                        });
                }
            });
    };

    // --- FORM ACTIONS AND CRUD IMPLEMENTATION ---
    function parseOptionsFromQuestion(rawQ) {
        if (!rawQ) return { q: '', a: '', b: '', c: '', d: '' };
        const optionRegex = /(?:^|\n|\s*)([A-D])[\.\:\)]\s*([^\n]+)/gi;
        const matches = [...rawQ.matchAll(optionRegex)];

        if (matches.length >= 2) {
            const firstIndex = rawQ.search(/(?:^|\n|\s*)[A-D][\.\:\)]/i);
            const q = firstIndex > 0 ? rawQ.substring(0, firstIndex).trim() : rawQ.trim();
            const opts = {};
            matches.forEach(m => {
                opts[m[1].toUpperCase()] = m[2].trim();
            });
            return {
                q: q,
                a: opts['A'] || '',
                b: opts['B'] || '',
                c: opts['C'] || '',
                d: opts['D'] || ''
            };
        }
        return { q: rawQ, a: '', b: '', c: '', d: '' };
    }

    document.getElementById('exerciseForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const exId = document.getElementById('modalExerciseId').value;
        const chapterId = document.getElementById('modalExerciseChapterId').value;
        const code = document.getElementById('meCode').value.trim();
        const name = document.getElementById('meName').value.trim();
        const difficulty = document.getElementById('meDifficulty').value;
        const bloom = document.getElementById('meBloom').value;

        const qText = document.getElementById('meQuestion').value.trim();
        const optA = document.getElementById('meOptA').value.trim();
        const optB = document.getElementById('meOptB').value.trim();
        const optC = document.getElementById('meOptC').value.trim();
        const optD = document.getElementById('meOptD').value.trim();
        const correct = document.getElementById('meCorrect').value;

        const fullQuestion = `${qText}\nA. ${optA}\nB. ${optB}\nC. ${optC}\nD. ${optD}`;

        const payload = {
            exerciseCode: code,
            exerciseName: name,
            difficulty: difficulty,
            bloomLevel: bloom,
            question: fullQuestion,
            correctAnswer: correct
        };

        const fetchUrl = exId ? `/api/v1/exercises/${exId}` : `/api/v1/chapters/${chapterId}/exercises`;
        const method = exId ? 'PUT' : 'POST';

        fetch(fetchUrl, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(payload)
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    closeExerciseModal();
                    loadExercisesPanelTable(currentSelectedChapterIdForExercises);
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            });
    });

    window.editExercise = (exId) => {
        fetch(`/api/v1/exercises/${exId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const ex = resData.data;
                    document.getElementById('modalExerciseId').value = ex.id;
                    document.getElementById('modalExerciseChapterId').value = ex.chapterId || currentSelectedChapterIdForExercises;
                    document.getElementById('meCode').value = ex.exerciseCode || '';
                    document.getElementById('meName').value = ex.exerciseName || '';
                    document.getElementById('meDifficulty').value = ex.difficulty || 'EASY';
                    document.getElementById('meBloom').value = ex.bloomLevel || 'REMEMBERING';

                    const parsed = parseOptionsFromQuestion(ex.question || '');
                    document.getElementById('meQuestion').value = parsed.q;
                    document.getElementById('meOptA').value = parsed.a;
                    document.getElementById('meOptB').value = parsed.b;
                    document.getElementById('meOptC').value = parsed.c;
                    document.getElementById('meOptD').value = parsed.d;

                    document.getElementById('meCorrect').value = ex.correctAnswer ? ex.correctAnswer.trim().toUpperCase() : 'A';

                    document.getElementById('exerciseModalTitle').textContent = 'Sửa bài tập trắc nghiệm cuối chương';
                    document.getElementById('exerciseModal').classList.add('show');
                }
            });
    };

    window.deleteExercise = async (exId) => {
        const ok = await window.showConfirm('Bạn có chắc chắn muốn xóa bài tập này không?');
        if (!ok) return;
        fetch(`/api/v1/exercises/${exId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => {
                if (res.ok) {
                    loadExercisesPanelTable(currentSelectedChapterIdForExercises);
                } else {
                    alert('Không thể xóa bài tập này.');
                }
            });
    };

    // AI Form Actions
    document.getElementById('exerciseAiForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const exId = document.getElementById('modalExerciseAiId').value;
        const chapterId = document.getElementById('modalExerciseAiChapterId').value;
        const code = document.getElementById('meAiCode').value.trim();
        const name = document.getElementById('meAiName').value.trim();
        const difficulty = document.getElementById('meAiDifficulty').value;
        const bloom = document.getElementById('meAiBloom').value;
        const question = document.getElementById('meAiQuestion').value.trim();
        const correct = document.getElementById('meAiCorrect').value.trim();

        const payload = {
            exerciseCode: code,
            exerciseName: name,
            difficulty: difficulty,
            bloomLevel: bloom,
            question: question,
            correctAnswer: correct
        };

        const fetchUrl = exId ? `/api/v1/exercises-ai/${exId}` : `/api/v1/chapters/${chapterId}/exercises-ai`;
        const method = exId ? 'PUT' : 'POST';

        fetch(fetchUrl, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(payload)
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    closeExerciseAiModal();
                    loadExercisesAiPanelTable(currentSelectedChapterIdForExercisesAi);
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            });
    });

    // AI PDF Upload Form Submit Action
    document.getElementById('exerciseAiPdfUploadForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const chapterId = currentSelectedChapterIdForExercisesAi;
        const fileInput = document.getElementById('exerciseAiPdfFile');
        if (fileInput.files.length === 0) {
            alert('Vui lòng chọn một file PDF chứa câu hỏi và đáp án');
            return;
        }

        const file = fileInput.files[0];
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
            alert('Chỉ chấp nhận file định dạng PDF');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        const progressDiv = document.getElementById('exerciseAiPdfUploadProgress');
        const progressBar = document.getElementById('exerciseAiPdfUploadBar');
        const progressPercent = document.getElementById('exerciseAiPdfPercent');
        const statusText = document.getElementById('exerciseAiPdfStatusText');

        progressDiv.style.display = 'block';
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        statusText.textContent = 'Đang tải file lên...';

        // Use XMLHttpRequest to track upload progress and handle wait time
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `/api/v1/chapters/${chapterId}/exercises-ai/import-pdf`, true);
        xhr.setRequestHeader('Authorization', 'Bearer ' + token);

        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                progressBar.style.width = (percent * 0.3) + '%'; // Reserve some percentage for AI processing
                progressPercent.textContent = Math.round(percent * 0.3) + '%';
                if (percent === 100) {
                    statusText.textContent = 'AI đang phân tích và tự dịch câu hỏi (có thể mất 10-30s)...';
                    // Start a slow dummy animation for AI processing phase from 30% to 95%
                    let aiProgress = 30;
                    const interval = setInterval(() => {
                        if (aiProgress < 95) {
                            aiProgress += 2;
                            progressBar.style.width = aiProgress + '%';
                            progressPercent.textContent = aiProgress + '%';
                        } else {
                            clearInterval(interval);
                        }
                    }, 1000);
                    xhr.onreadystatechange = () => {
                        if (xhr.readyState === 4) {
                            clearInterval(interval);
                        }
                    };
                }
            }
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                const resData = JSON.parse(xhr.responseText);
                if (resData.success) {
                    progressBar.style.width = '100%';
                    progressPercent.textContent = '100%';
                    statusText.textContent = 'Hoàn thành!';
                    setTimeout(() => {
                        alert('AI đã dịch và nhập bài tập từ PDF thành công!');
                        closeExerciseAiPdfUploadModal();
                        loadExercisesAiPanelTable(chapterId); // Refresh table
                    }, 500);
                } else {
                    alert('Lỗi: ' + resData.message);
                    progressDiv.style.display = 'none';
                }
            } else {
                let errorMsg = 'AI phân tích thất bại. Vui lòng kiểm tra lại file hoặc dịch vụ AI.';
                try {
                    const resData = JSON.parse(xhr.responseText);
                    if (resData && resData.message) {
                        errorMsg = resData.message;
                    }
                } catch (err) { }
                alert('Lỗi: ' + errorMsg);
                progressDiv.style.display = 'none';
            }
        };

        xhr.onerror = () => {
            alert('Lỗi kết nối khi tải lên file.');
            progressDiv.style.display = 'none';
        };

        xhr.send(formData);
    });

    window.syncExercisesToAITutor = async () => {
        const chapterId = currentSelectedChapterIdForExercisesAi;
        if (!chapterId) {
            alert('Vui lòng chọn một chương học để đồng bộ bài tập');
            return;
        }

        const okSync = await window.showConfirm('Hệ thống sẽ đồng bộ toàn bộ bài tập AI của chương này sang AI Tutor. Việc này sử dụng AI để tự động sinh giáo án Socratic và có thể mất 1-3 phút. Bạn có muốn tiếp tục?');
        if (!okSync) return;

        const btn = document.getElementById('btnSyncExerciseAi');
        const originalText = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Đang đồng bộ (1-3 phút)...';

        fetch(`/api/v1/chapters/${chapterId}/exercises-ai/sync`, {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                btn.disabled = false;
                btn.textContent = originalText;
                if (resData.success) {
                    alert('Đồng bộ bài tập sang AI Tutor thành công! Học sinh đã có thể làm các bài tập này.');
                } else {
                    alert('Lỗi đồng bộ: ' + (resData.message || 'Lỗi không xác định'));
                }
            })
            .catch(err => {
                btn.disabled = false;
                btn.textContent = originalText;
                alert('Lỗi kết nối khi đồng bộ bài tập');
                console.error(err);
            });
    };

    window.editExerciseAi = (exId) => {
        fetch(`/api/v1/exercises-ai/${exId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const ex = resData.data;
                    document.getElementById('modalExerciseAiId').value = ex.id;
                    document.getElementById('modalExerciseAiChapterId').value = ex.chapterId || currentSelectedChapterIdForExercisesAi;
                    document.getElementById('meAiCode').value = ex.exerciseCode || '';
                    document.getElementById('meAiName').value = ex.exerciseName || '';
                    document.getElementById('meAiDifficulty').value = ex.difficulty || 'EASY';
                    document.getElementById('meAiBloom').value = ex.bloomLevel || 'REMEMBERING';
                    document.getElementById('meAiQuestion').value = ex.question || '';
                    document.getElementById('meAiCorrect').value = '';

                    document.getElementById('exerciseAiModalTitle').textContent = 'Sửa thông tin bài tập AI';
                    document.getElementById('exerciseAiModal').classList.add('show');
                }
            });
    };

    window.deleteExerciseAi = async (exId) => {
        const ok = await window.showConfirm('Bạn có chắc chắn muốn xóa bài tập AI này không?');
        if (!ok) return;
        fetch(`/api/v1/exercises-ai/${exId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => {
                if (res.ok) {
                    loadExercisesAiPanelTable(currentSelectedChapterIdForExercisesAi);
                } else {
                    alert('Không thể xóa bài tập AI này.');
                }
            });
    };

    // Users Panel (Admin only)
    function loadUsers() {
        if (currentUser && currentUser.role !== 'ADMIN') return;
        fetch('/api/v1/users?size=1000', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const users = getListFromData(resData.data).map(u => {
                        u.role = u.roles && u.roles.length > 0 ? u.roles[0] : 'STUDENT';
                        u.username = u.email ? u.email.split('@')[0] : '';
                        return u;
                    });
                    const tbody = document.getElementById('usersTableBody');

                    tbody.innerHTML = users.map(u => `
                    <tr>
                        <td><strong>#${u.id}</strong></td>
                        <td>${u.username}</td>
                        <td style="font-weight: 700;">${u.fullName}</td>
                        <td>${u.email}</td>
                        <td>
                            <select onchange="changeUserRole(${u.id}, this.value)" class="form-control" style="width:130px; font-size: 13px; height: 32px; padding: 4px 8px;">
                                <option value="STUDENT" ${u.role === 'STUDENT' ? 'selected' : ''}>Student</option>
                                <option value="TEACHER" ${u.role === 'TEACHER' ? 'selected' : ''}>Teacher</option>
                                <option value="ADMIN" ${u.role === 'ADMIN' ? 'selected' : ''}>Admin</option>
                            </select>
                        </td>
                        <td>
                            <span class="badge ${u.isActive ? 'badge-primary' : 'badge-info'}">${u.isActive ? 'Hoạt động' : 'Bị Khóa'}</span>
                        </td>
                        <td>
                            <div class="db-btn-actions">
                                <button class="btn btn-secondary btn-sm" onclick="toggleUserStatus(${u.id}, ${u.isActive})">
                                    ${u.isActive ? 'Khóa' : 'Kích hoạt'}
                                </button>
                                <button class="btn btn-outline-primary btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="deleteUser(${u.id})">Xóa</button>
                            </div>
                        </td>
                    </tr>`).join('');
                }
            });
    }

    window.changeUserRole = (userId, newRole) => {
        let roleId = 2; // STUDENT
        if (newRole === 'ADMIN') roleId = 0;
        if (newRole === 'TEACHER') roleId = 1;

        fetch(`/api/v1/users/${userId}/roles`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({ roleIds: [roleId] })
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    loadUsers();
                } else {
                    alert('Lỗi khi đổi vai trò: ' + resData.message);
                }
            });
    };

    window.toggleUserStatus = (userId, currentStatus) => {
        fetch(`/api/v1/users/${userId}/status?isActive=${!currentStatus}`, {
            method: 'PATCH',
            headers: {
                'Authorization': 'Bearer ' + token
            }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    loadUsers();
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            });
    };

    window.deleteUser = async (userId) => {
        const ok = await window.showConfirm('Bạn có chắc chắn muốn xóa thành viên này?');
        if (!ok) return;
        fetch(`/api/v1/users/${userId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => {
                if (res.ok) {
                    loadUsers();
                } else {
                    alert('Không thể xóa người dùng này.');
                }
            });
    };

    // Reports Panel
    function loadReports() {
        if (currentUser && currentUser.role !== 'ADMIN') return;
        fetch('/api/v1/courses?size=100', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const list = getListFromData(resData.data);
                    // Sắp xếp các khóa học theo số lượng học viên giảm dần
                    list.sort((a, b) => (b.studentCount || 0) - (a.studentCount || 0));

                    const tbody = document.getElementById('reportsTableBody');
                    if (list.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-3);">Không có dữ liệu báo cáo.</td></tr>`;
                        return;
                    }

                    tbody.innerHTML = list.map(r => `
                    <tr>
                        <td><strong>#${r.id}</strong></td>
                        <td style="font-weight: 700; color: var(--primary);">${r.title}</td>
                        <td>${r.createdByName || 'Chưa phân công'}</td>
                        <td><strong>${r.studentCount || 0}</strong> học viên đăng ký học</td>
                    </tr>`).join('');
                }
            })
            .catch(err => console.error(err));

        // Tải dữ liệu tiến độ và độ khó bài tập để vẽ biểu đồ
        if (window.Chart) {
            Promise.all([
                fetch('/api/v1/reports/progress', { headers: { 'Authorization': 'Bearer ' + token } }).then(r => r.json()),
                fetch('/api/v1/reports/exercise-difficulty', { headers: { 'Authorization': 'Bearer ' + token } }).then(r => r.json())
            ])
                .then(([progressData, difficultyData]) => {
                    if (progressData.success && difficultyData.success) {
                        renderReportCharts(progressData.data, difficultyData.data);
                    }
                })
                .catch(err => console.error('Lỗi khi tải dữ liệu báo cáo vẽ biểu đồ:', err));
        }
    }

    // Helper to render Report charts
    function renderReportCharts(progressList, difficultyList) {
        if (reportProgressChartInstance) reportProgressChartInstance.destroy();
        if (reportCompletionChartInstance) reportCompletionChartInstance.destroy();
        if (reportBloomChartInstance) reportBloomChartInstance.destroy();

        // 1. Tiến độ học tập trung bình
        const courseLabels = progressList.map(p => p.courseTitle);
        const avgProgressValues = progressList.map(p => p.avgProgress || 0);

        const ctxProgress = document.getElementById('reportProgressChart').getContext('2d');
        reportProgressChartInstance = new Chart(ctxProgress, {
            type: 'bar',
            data: {
                labels: courseLabels,
                datasets: [{
                    label: 'Tiến độ trung bình (%)',
                    data: avgProgressValues,
                    backgroundColor: 'rgba(59, 130, 246, 0.75)', // Blue
                    borderColor: 'rgba(59, 130, 246, 1)',
                    borderWidth: 1.5,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { stepSize: 20 }
                    }
                }
            }
        });

        // 2. Tỷ lệ hoàn thành khóa học (Grouped Bar Chart)
        const totalStudentsValues = progressList.map(p => p.totalStudents || 0);
        const completedCountValues = progressList.map(p => p.completedCount || 0);

        const ctxCompletion = document.getElementById('reportCompletionChart').getContext('2d');
        reportCompletionChartInstance = new Chart(ctxCompletion, {
            type: 'bar',
            data: {
                labels: courseLabels,
                datasets: [
                    {
                        label: 'Tổng học viên',
                        data: totalStudentsValues,
                        backgroundColor: 'rgba(148, 163, 184, 0.8)', // slate
                        borderRadius: 4
                    },
                    {
                        label: 'Đã hoàn thành (>= 100%)',
                        data: completedCountValues,
                        backgroundColor: 'rgba(16, 185, 129, 0.8)', // green
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1, precision: 0 }
                    }
                }
            }
        });

        // 3. Tỷ lệ làm đúng theo mức độ Bloom (Horizontal Bar Chart)
        const bloomTranslations = {
            'REMEMBERING': 'Nhớ (Remembering)',
            'UNDERSTANDING': 'Hiểu (Understanding)',
            'APPLYING': 'Áp dụng (Applying)',
            'ANALYZING': 'Phân tích (Analyzing)',
            'EVALUATING': 'Đánh giá (Evaluating)',
            'CREATING': 'Sáng tạo (Creating)'
        };

        const bloomLabels = difficultyList.map(d => bloomTranslations[d.bloomLevel] || d.bloomLevel);
        const successRates = difficultyList.map(d => d.avgSuccessRate || 0);

        const ctxBloom = document.getElementById('reportBloomChart').getContext('2d');
        reportBloomChartInstance = new Chart(ctxBloom, {
            type: 'bar',
            data: {
                labels: bloomLabels,
                datasets: [{
                    label: 'Tỷ lệ làm đúng (%)',
                    data: successRates,
                    backgroundColor: 'rgba(139, 92, 246, 0.75)', // Purple
                    borderColor: 'rgba(139, 92, 246, 1)',
                    borderWidth: 1.5,
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y', // Makes it horizontal
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { stepSize: 20 }
                    }
                }
            }
        });
    }



    // PDF Upload Modal Handlers
    window.openPdfUploadModal = (courseId, courseTitle, currentPdf) => {
        document.getElementById('pdfUploadForm').reset();
        document.getElementById('uploadPdfCourseId').value = courseId;
        document.getElementById('uploadPdfCourseTitle').value = courseTitle;

        const label = document.getElementById('pdfCurrentFileLabel');
        if (currentPdf && currentPdf !== 'null' && currentPdf !== 'undefined') {
            label.innerHTML = `File hiện tại: <a href="${currentPdf}" target="_blank" style="color: var(--primary);">Xem PDF</a>`;
        } else {
            label.textContent = 'Khóa học này chưa có file bài giảng PDF.';
        }

        document.getElementById('pdfUploadProgress').style.display = 'none';
        document.getElementById('pdfUploadModal').classList.add('show');
    };

    window.closePdfUploadModal = () => {
        document.getElementById('pdfUploadModal').classList.remove('show');
    };

    document.getElementById('pdfUploadForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const courseId = document.getElementById('uploadPdfCourseId').value;
        const fileInput = document.getElementById('pdfFile');
        if (fileInput.files.length === 0) {
            alert('Vui lòng chọn một file PDF');
            return;
        }

        const file = fileInput.files[0];
        if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
            alert('Chỉ chấp nhận file định dạng PDF');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        const progressDiv = document.getElementById('pdfUploadProgress');
        const progressBar = document.getElementById('pdfUploadBar');
        const progressPercent = document.getElementById('pdfUploadPercent');

        progressDiv.style.display = 'block';
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';

        // Use XMLHttpRequest to track progress
        const xhr = new XMLHttpRequest();
        xhr.open('POST', `/api/v1/courses/${courseId}/upload-pdf`, true);
        xhr.setRequestHeader('Authorization', 'Bearer ' + token);

        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable) {
                const percent = Math.round((event.loaded / event.total) * 100);
                progressBar.style.width = percent + '%';
                progressPercent.textContent = percent + '%';
            }
        };

        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                const resData = JSON.parse(xhr.responseText);
                if (resData.success) {
                    alert('Tải lên file bài giảng PDF thành công!');
                    closePdfUploadModal();
                    loadCourses(); // Refresh courses list
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            } else {
                alert('Tải lên thất bại. Vui lòng kiểm tra dung lượng file hoặc kết nối.');
            }
            progressDiv.style.display = 'none';
        };

        xhr.onerror = () => {
            alert('Lỗi kết nối khi tải lên file.');
            progressDiv.style.display = 'none';
        };

        xhr.send(formData);
    });

    // ==========================================
    // NOTIFICATIONS PANEL MANAGEMENT
    // ==========================================
    function loadNotificationsPanel() {
        // 1. Tải hộp thư thông báo cá nhân
        fetch('/api/v1/notifications?size=100', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                const tbody = document.getElementById('panelNotificationsTableBody');
                if (resData.success) {
                    const notifications = getListFromData(resData.data);
                    if (notifications.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-3);">Không có thông báo nào.</td></tr>`;
                        return;
                    }
                    tbody.innerHTML = notifications.map(n => {
                        const statusText = n.isRead ? '<span class="badge badge-primary">Đã đọc</span>' : '<span class="badge badge-info">Chưa đọc</span>';
                        const dateText = new Date(n.createdAt).toLocaleString('vi-VN');
                        return `
                    <tr>
                        <td><strong>#${n.id}</strong></td>
                        <td><span class="badge badge-primary">${n.type}</span></td>
                        <td style="max-width: 300px; word-wrap: break-word; white-space: normal;">${n.message}</td>
                        <td>${dateText}</td>
                        <td>${statusText}</td>
                        <td>
                            <div class="db-btn-actions">
                                ${!n.isRead ? `<button class="btn btn-secondary btn-sm" onclick="markPanelNotiRead(${n.id})">Đã đọc</button>` : ''}
                                <button class="btn btn-outline-primary btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="deletePanelNoti(${n.id})">Xóa</button>
                            </div>
                        </td>
                    </tr>`;
                    }).join('');
                } else {
                    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-3);">Không thể tải thông báo. Lỗi: ${resData.message}</td></tr>`;
                }
            })
            .catch(err => {
                console.error(err);
                document.getElementById('panelNotificationsTableBody').innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-3);">Lỗi kết nối khi tải thông báo.</td></tr>`;
            });

        // 2. Nếu là ADMIN, tải danh sách khóa học cho dropdown Broadcast
        if (!currentUser || currentUser.role === 'ADMIN') {
            fetch('/api/v1/courses/all?size=100', {
                headers: { 'Authorization': 'Bearer ' + token }
            })
                .then(res => res.json())
                .then(resData => {
                    if (resData.success) {
                        const courses = getListFromData(resData.data);
                        const scopeSelector = document.getElementById('pbNotiScope');
                        if (scopeSelector) {
                            scopeSelector.innerHTML = '<option value="all">Toàn bộ người dùng hệ thống</option>' +
                                courses.map(c => `<option value="${c.id}">Học viên khóa học: ${c.title}</option>`).join('');
                        }
                    }
                })
                .catch(err => console.error('Lỗi tải danh sách khóa học cho scope:', err));
        }
    }

    // Các hàm phụ trợ cho Notifications Panel
    window.markPanelNotiRead = (notiId) => {
        fetch(`/api/v1/notifications/${notiId}/read`, {
            method: 'PATCH',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    loadNotificationsPanel();
                    if (typeof loadNotifications === 'function') loadNotifications(); // Sync client drawer if header exists
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            });
    };

    window.deletePanelNoti = async (notiId) => {
        const ok = await window.showConfirm('Bạn có chắc chắn muốn xóa thông báo này?');
        if (!ok) return;
        fetch(`/api/v1/notifications/${notiId}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => {
                if (res.ok) {
                    loadNotificationsPanel();
                    if (typeof loadNotifications === 'function') loadNotifications();
                } else {
                    alert('Không thể xóa thông báo này.');
                }
            });
    };

    // Đăng ký sự kiện submit form gửi thông báo
    document.getElementById('panelDirectNotiForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const recipientsRaw = document.getElementById('pdNotiRecipients').value;
        const targetUserIds = recipientsRaw.split(',').map(id => parseInt(id.trim())).filter(id => !isNaN(id));
        if (targetUserIds.length === 0) {
            alert('Vui lòng nhập ít nhất một mã người nhận hợp lệ!');
            return;
        }
        const type = document.getElementById('pdNotiType').value;
        const message = document.getElementById('pdNotiMessage').value.trim();

        fetch('/api/v1/notifications', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({
                message: message,
                type: type,
                targetUserIds: targetUserIds
            })
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    alert('Gửi thông báo cá nhân thành công!');
                    document.getElementById('panelDirectNotiForm').reset();
                    loadNotificationsPanel();
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            })
            .catch(err => {
                console.error(err);
                alert('Lỗi kết nối khi gửi thông báo.');
            });
    });

    document.getElementById('panelBroadcastNotiForm').addEventListener('submit', (e) => {
        e.preventDefault();
        const scope = document.getElementById('pbNotiScope').value;
        const message = document.getElementById('pbNotiMessage').value.trim();
        const courseId = scope === 'all' ? null : parseInt(scope);

        fetch('/api/v1/notifications/broadcast', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({
                message: message,
                courseId: courseId
            })
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    alert('Phát thông báo thành công!');
                    document.getElementById('panelBroadcastNotiForm').reset();
                    loadNotificationsPanel();
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            })
            .catch(err => {
                console.error(err);
                alert('Lỗi kết nối khi phát thông báo.');
            });
    });

    document.getElementById('btnMarkAllReadPanel').addEventListener('click', () => {
        fetch('/api/v1/notifications/read-all', {
            method: 'PATCH',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    loadNotificationsPanel();
                    if (typeof loadNotifications === 'function') loadNotifications();
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            });
    });

    // ==========================================
    // REVIEWS PANEL MANAGEMENT (ADMIN ONLY)
    // ==========================================
    function loadReviewsPanel() {
        if (currentUser && currentUser.role !== 'ADMIN') return;
        fetch('/api/v1/reviews?size=100', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                const tbody = document.getElementById('panelReviewsTableBody');
                if (resData.success) {
                    const reviews = getListFromData(resData.data);
                    if (reviews.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-3);">Không có đánh giá nào trên hệ thống.</td></tr>`;
                        return;
                    }
                    tbody.innerHTML = reviews.map(r => {
                        const stars = '★'.repeat(r.rating) + '☆'.repeat(5 - r.rating);
                        const isVisibleVal = r.isVisible !== undefined ? r.isVisible : true;
                        const statusBadge = isVisibleVal ? '<span class="badge badge-primary">Hiển thị</span>' : '<span class="badge badge-info">Đang ẩn</span>';
                        const dateText = new Date(r.createdAt).toLocaleString('vi-VN');
                        return `
                    <tr>
                        <td><strong>#${r.id}</strong></td>
                        <td style="font-weight: 600; color: var(--primary);">${r.courseTitle || ('Khóa học #' + r.courseId)}</td>
                        <td>${r.userFullName || 'Học viên'}</td>
                        <td style="color: #f59e0b; font-size: 16px;">${stars}</td>
                        <td style="max-width: 300px; word-wrap: break-word; white-space: normal;">${r.comment || ''}</td>
                        <td>${dateText}</td>
                        <td>${statusBadge}</td>
                        <td>
                            <div class="db-btn-actions">
                                <button class="btn btn-secondary btn-sm" onclick="togglePanelReviewVisibility(${r.id}, ${isVisibleVal})">
                                    ${isVisibleVal ? 'Ẩn đi' : 'Hiển thị'}
                                </button>
                                <button class="btn btn-outline-primary btn-sm" style="color: #ef4444; border-color: #ef4444;" onclick="deletePanelReview(${r.id})">Xóa</button>
                            </div>
                        </td>
                    </tr>`;
                    }).join('');
                } else {
                    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-3);">Không thể tải đánh giá. Lỗi: ${resData.message}</td></tr>`;
                }
            })
            .catch(err => {
                console.error(err);
                document.getElementById('panelReviewsTableBody').innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-3);">Lỗi kết nối khi tải đánh giá.</td></tr>`;
            });
    }

    window.togglePanelReviewVisibility = (reviewId, currentVisibility) => {
        fetch(`/api/v1/reviews/${reviewId}/visibility?isVisible=${!currentVisibility}`, {
            method: 'PATCH',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    loadReviewsPanel();
                } else {
                    alert('Lỗi khi cập nhật trạng thái hiển thị: ' + resData.message);
                }
            });
    };

    window.deletePanelReview = async (reviewId) => {
        const ok = await window.showConfirm('Bạn có chắc chắn muốn xóa đánh giá này?');
        if (!ok) return;
        fetch(`/api/v1/reviews/${reviewId}/admin`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => {
                if (res.ok) {
                    loadReviewsPanel();
                } else {
                    alert('Không thể xóa đánh giá này.');
                }
            });
    };

    // =====================================================
    // NEWS MANAGEMENT MODULE
    // =====================================================
    let cachedNewsList = [];

    function loadNewsModule() {
        fetch('/api/v1/news', {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                const tbody = document.getElementById('newsTableBody');
                if (resData.success) {
                    cachedNewsList = resData.data || [];
                    if (cachedNewsList.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Chưa có tin tức nào. Bấm nút "+ Đăng tin tức mới" để thêm.</td></tr>`;
                        return;
                    }

                    const catMap = {
                        'academy': 'Tin Học viện',
                        'student': 'Hoạt động sinh viên',
                        'tech': 'Khoa học công nghệ',
                        'admission': 'Tuyển sinh'
                    };

                    tbody.innerHTML = cachedNewsList.map(item => {
                        const dateStr = item.createdAt ? new Date(item.createdAt).toLocaleDateString('vi-VN') : '---';
                        const catLabel = catMap[item.category] || item.category;
                        const spotlightBadge = item.isSpotlight
                            ? `<span class="badge badge-primary" style="background:#7a1318; color:#fff;">Tiêu điểm (Spotlight)</span>`
                            : `<span class="badge badge-secondary" style="background:#f1f5f9; color:#64748b;">Tin thường</span>`;

                        return `
                        <tr>
                            <td><strong>#${item.id}</strong></td>
                            <td><img src="${item.imageUrl}" alt="${item.title}" style="width:48px; height:32px; object-fit:cover; border-radius:4px;"></td>
                            <td style="max-width:280px; font-weight:700; color:var(--text-1);">${item.title}</td>
                            <td><span class="badge badge-info">${catLabel}</span></td>
                            <td>${spotlightBadge}</td>
                            <td>${dateStr}</td>
                            <td>
                                <div class="db-btn-actions">
                                    <button class="btn btn-secondary btn-sm" onclick="editNews(${item.id})">Sửa</button>
                                    <button class="btn btn-outline-primary btn-sm" style="color:#ef4444; border-color:#ef4444;" onclick="deleteNews(${item.id})">Xóa</button>
                                </div>
                            </td>
                        </tr>`;
                    }).join('');
                } else {
                    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Không thể tải danh sách tin tức.</td></tr>`;
                }
            })
            .catch(err => {
                console.error(err);
                document.getElementById('newsTableBody').innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-3);">Lỗi kết nối khi tải tin tức.</td></tr>`;
            });
    }

    window.openNewsModal = () => {
        document.getElementById('newsModalTitle').textContent = 'Đăng Tin Tức Mới';
        document.getElementById('newsForm').reset();
        document.getElementById('newsId').value = '';
        document.getElementById('newsModal').style.display = 'flex';
    };

    window.closeNewsModal = () => {
        document.getElementById('newsModal').style.display = 'none';
    };

    window.saveNews = (e) => {
        e.preventDefault();
        const newsId = document.getElementById('newsId').value;
        const payload = {
            title: document.getElementById('newsTitle').value.trim(),
            category: document.getElementById('newsCategory').value,
            imageUrl: document.getElementById('newsImageUrl').value.trim(),
            summary: document.getElementById('newsSummary').value.trim(),
            content: document.getElementById('newsContent').value.trim(),
            isSpotlight: document.getElementById('newsIsSpotlight').checked
        };

        const url = newsId ? `/api/v1/news/${newsId}` : '/api/v1/news';
        const method = newsId ? 'PUT' : 'POST';

        fetch(url, {
            method: method,
            headers: {
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    alert(newsId ? 'Cập nhật tin tức thành công!' : 'Đăng tin tức mới thành công!');
                    window.closeNewsModal();
                    loadNewsModule();
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            })
            .catch(err => {
                console.error(err);
                alert('Có lỗi xảy ra khi lưu tin tức.');
            });
    };

    window.editNews = (id) => {
        const item = cachedNewsList.find(n => n.id === id);
        if (!item) return;

        document.getElementById('newsModalTitle').textContent = `Chỉnh Sửa Tin Tức #${item.id}`;
        document.getElementById('newsId').value = item.id;
        document.getElementById('newsTitle').value = item.title || '';
        document.getElementById('newsCategory').value = item.category || 'academy';
        document.getElementById('newsImageUrl').value = item.imageUrl || '';
        document.getElementById('newsSummary').value = item.summary || '';
        document.getElementById('newsContent').value = item.content || '';
        document.getElementById('newsIsSpotlight').checked = !!item.isSpotlight;

        document.getElementById('newsModal').style.display = 'flex';
    };

    window.deleteNews = async (id) => {
        const ok = await window.showConfirm('Bạn có chắc chắn muốn xóa tin tức này khỏi hệ thống?');
        if (!ok) return;

        fetch(`/api/v1/news/${id}`, {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    alert('Xóa tin tức thành công!');
                    loadNewsModule();
                } else {
                    alert('Lỗi khi xóa tin tức: ' + resData.message);
                }
            })
            .catch(err => {
                console.error(err);
                alert('Có lỗi xảy ra khi xóa tin tức.');
            });
    };

    // ===== SUPPORT TICKETS MODULE =====
    window.loadSupportTicketsModule = function () {
        fetch('/api/v1/support-tickets', {
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => res.json())
            .then(resData => {
                const tbody = document.getElementById('supportTicketsTableBody');
                if (!tbody) return;

                if (resData && resData.success && resData.data) {
                    const list = resData.data;
                    if (list.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding:24px; color: var(--text-3);">Chưa có yêu cầu hỗ trợ nào từ sinh viên.</td></tr>`;
                        return;
                    }

                    tbody.innerHTML = list.map(t => {
                        const isResolved = t.status === 'RESOLVED';
                        const statusBadge = isResolved 
                            ? `<span class="badge badge-success">ĐÃ XỬ LÝ</span>` 
                            : `<span class="badge badge-warning" style="background:#fef3c7; color:#d97706; padding:3px 8px; border-radius:4px; font-weight:700; font-size:11px;">CHỜ XỬ LÝ</span>`;

                        const formattedTime = t.createdAt ? new Date(t.createdAt).toLocaleString('vi-VN') : 'Vừa xong';

                        return `
                        <tr>
                            <td><strong>#${t.id}</strong></td>
                            <td style="font-weight:700;">${t.studentName}</td>
                            <td><a href="mailto:${t.studentEmail}" style="color:var(--primary); font-weight:600;">${t.studentEmail}</a></td>
                            <td><span class="badge badge-info">${t.problemType || 'Hỗ trợ'}</span></td>
                            <td style="max-width:280px; white-space:pre-wrap; font-size:13px;">${t.message}</td>
                            <td style="font-size:12.5px; color:var(--text-3);">${formattedTime}</td>
                            <td>${statusBadge}</td>
                            <td>
                                ${!isResolved ? `
                                <button class="btn btn-primary btn-sm" onclick="resolveSupportTicket(${t.id})" style="border-radius:6px; font-weight:700; background:#10b981; border-color:#10b981;">
                                    Đã xử lý
                                </button>` : `<span style="font-size:12px; color:#10b981; font-weight:700;">Hoàn tất</span>`}
                            </td>
                        </tr>`;
                    }).join('');
                }
            })
            .catch(err => console.error(err));
    };

    window.resolveSupportTicket = async function (id) {
        const ok = await window.showConfirm('Xác nhận đánh dấu yêu cầu này đã được hỗ trợ xử lý xong?');
        if (!ok) return;

        fetch(`/api/v1/support-tickets/${id}/resolve`, {
            method: 'PATCH',
            headers: token ? { 'Authorization': 'Bearer ' + token } : {}
        })
            .then(res => res.json())
            .then(resData => {
                if (resData && resData.success) {
                    alert('Đã cập nhật trạng thái yêu cầu hỗ trợ thành công!');
                    loadSupportTicketsModule();
                } else {
                    alert('Cập nhật thất bại: ' + (resData.message || 'Lỗi hệ thống'));
                }
            })
            .catch(err => console.error(err));
    };

    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        init();
    } else {
        document.addEventListener('DOMContentLoaded', init);
    }
})();
