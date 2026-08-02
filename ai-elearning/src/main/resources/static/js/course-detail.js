(function () {
    let currentCourse = null;
    let enrolledData = null;

    async function init() {
        const params = new URLSearchParams(window.location.search);
        const courseId = parseInt(params.get('id')) || 1;
        const token = localStorage.getItem('ptit_token');

        try {
            // 1. Fetch course details
            const res = await fetch(`/api/v1/courses/${courseId}`, {
                headers: token ? { 'Authorization': 'Bearer ' + token } : {}
            });

            if (!res || !res.ok) {
                throw new Error('Course fetch failed');
            }

            const resData = await res.json();
            if (resData && resData.success) {
                currentCourse = resData.data;
                document.title = `${currentCourse.title} - PTIT E-Learning`;

                // 2. Fetch course chapters
                try {
                    const r = await fetch(`/api/v1/courses/${courseId}/chapters`, {
                        headers: token ? { 'Authorization': 'Bearer ' + token } : {}
                    });
                    const chapData = await r.json();
                    if (chapData && chapData.success) {
                        currentCourse.chapters = chapData.data || [];
                    } else {
                        currentCourse.chapters = [];
                    }
                } catch (e) {
                    currentCourse.chapters = [];
                }

                // 3. Fetch user learning profile for this course (Auto-enroll if not enrolled yet)
                try {
                    const profileRes = await fetch(`/api/v1/learning-profiles/me?courseId=${currentCourse.id}`, {
                        headers: token ? { 'Authorization': 'Bearer ' + token } : {}
                    });
                    const enrData = await profileRes.json();
                    if (enrData && enrData.success && enrData.data) {
                        enrolledData = enrData.data;
                    } else if (token) {
                        // Auto-enroll student seamlessly
                        const autoRes = await fetch(`/api/v1/courses/${currentCourse.id}/enroll`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer ' + token
                            },
                            body: JSON.stringify({})
                        });
                        const autoData = await autoRes.json();
                        if (autoData && autoData.success && autoData.data) {
                            enrolledData = autoData.data;
                        }
                    }
                } catch (e) {
                    console.error('Learning profile error:', e);
                }

                renderDetails();
            }
        } catch (err) {
            console.error('Fetch course error:', err);
        }
    }

    function renderDetails() {
        if (!currentCourse) return;

        const lessons = currentCourse.chapters || [];

        // Hero
        const isDaiCuong = currentCourse.level === 'BEGINNER' || currentCourse.level === 'INTERMEDIATE';
        document.getElementById('detailHero').innerHTML = `
            <div style="position:relative;z-index:2;">
                <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
                    <span class="badge" style="background:rgba(255,255,255,.15);color:#fff;">${isDaiCuong ? 'Đại Cương' : 'Chuyên ngành'}</span>
                </div>
                <div class="detail-hero-title">${currentCourse.title}</div>
                <div class="detail-hero-meta">
                    <span>${lessons.length} chương</span>
                    <span>${currentCourse.createdByName || 'GV. PTIT'}</span>
                </div>
                <p class="detail-hero-desc">${currentCourse.description || 'Chưa có mô tả chi tiết cho khóa học này.'}</p>
                <a href="ai-chat.html?id=${currentCourse.id}" class="btn" style="background:#fff;color:var(--primary);font-weight:700;margin-top:8px;">
                    Hỏi gia sư AI ngay
                </a>
            </div>`;

        // Learn grid - display only if learnItems exist from backend
        const learnGrid = document.getElementById('learnGrid');
        const learnTitle = document.getElementById('learnTitle');
        if (currentCourse.learnItems && Array.isArray(currentCourse.learnItems) && currentCourse.learnItems.length > 0) {
            if (learnTitle) learnTitle.style.display = 'block';
            if (learnGrid) {
                learnGrid.style.display = 'grid';
                learnGrid.innerHTML = currentCourse.learnItems.map(item => `<div class="learn-item">${item}</div>`).join('');
            }
        } else {
            if (learnTitle) learnTitle.style.display = 'none';
            if (learnGrid) learnGrid.style.display = 'none';
        }

        // Course desc
        document.getElementById('courseDesc').textContent =
            currentCourse.description || 'Chưa có mô tả chi tiết cho khóa học này.';

        // Render PDF lecture preview if available
        const pdfSection = document.getElementById('pdfLectureSection');
        if (currentCourse.lecturePdf && currentCourse.lecturePdf !== 'null' && currentCourse.lecturePdf !== 'undefined') {
            pdfSection.style.display = 'block';
            document.getElementById('pdfIframe').src = currentCourse.lecturePdf;
            document.getElementById('pdfDownloadLink').href = currentCourse.lecturePdf;
            
            let fileName = 'tai-lieu-bai-giang.pdf';
            const parts = currentCourse.lecturePdf.split('/');
            const base = parts[parts.length - 1];
            if (base.includes('_')) {
                fileName = decodeURIComponent(base.substring(base.indexOf('_') + 1));
            } else {
                fileName = decodeURIComponent(base);
            }
            document.getElementById('pdfFileName').textContent = fileName;
        } else {
            pdfSection.style.display = 'none';
        }

        // Curriculum
        document.getElementById('chaptersCount').textContent = `${lessons.length} chương`;
        document.getElementById('chapterCountBadge').textContent = `${lessons.length} chương`;

        document.getElementById('chapterList').innerHTML = lessons.map((les, i) => {
            const requiredPct = Math.round(((i + 1) / lessons.length) * 100);
            const isCompleted = enrolledData ? (enrolledData.progressPercent >= requiredPct) : false;
            
            let exerciseHTML = '';
            if (enrolledData) {
                if (les.isLocked) {
                    exerciseHTML = `<div style="margin-top:12px; color:var(--text-3); font-size:13px; font-style:italic;">Bài tập chương này bị khóa cho đến khi hoàn thành chương trước.</div>`;
                } else if (isCompleted) {
                    exerciseHTML = `<div style="background:#f0fdf4; border:1px solid #bbf7d0; color:#16a34a; padding:12px; border-radius:8px; margin-top:12px; font-size:13px; font-weight:600;">Bạn đã hoàn thành toàn bộ bài tập của chương này!</div>`;
                } else {
                    exerciseHTML = `<div class="exercise-container" id="ex-container-${les.id}" style="margin-top:12px;">Đang tải bài tập...</div>`;
                }
            }

            return `
            <div class="chapter-item">
                <div class="chapter-header open" onclick="toggleChapter(this)">
                    <div>
                        <div class="chapter-num">Chương ${i + 1}</div>
                        <div class="chapter-name">${les.chapterName || 'Chương học'}</div>
                    </div>
                    <svg class="chapter-toggle" xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
                </div>
                <div class="chapter-body open" style="display:block; padding: 16px 20px;">
                    <p style="font-size: 14px; color: var(--text-2); margin-bottom: 12px; line-height: 1.6;">${les.content || ''}</p>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; border-top: 1px solid var(--border-light); padding-top: 12px; margin-bottom:8px;">
                        <span class="status-badge ${isCompleted ? '' : 'pending'}">${isCompleted ? 'Đã hoàn thành' : 'Chưa hoàn thành'}</span>
                    </div>
                    ${exerciseHTML}
                </div>
            </div>`;
        }).join('');

        if (enrolledData) {
            lessons.forEach((les, i) => {
                const requiredPct = Math.round(((i + 1) / lessons.length) * 100);
                const isCompleted = enrolledData ? (enrolledData.progressPercent >= requiredPct) : false;
                if (!les.isLocked && !isCompleted) {
                    loadChapterExercise(les.id);
                }
            });
        }

        // Load reviews dynamically
        loadReviews();

        // Sidebar Info
        document.getElementById('sidebarMeta').innerHTML = `
            <li><span>Số chương</span><strong>${lessons.length} chương</strong></li>
            <li><span>Giảng viên</span><strong>${currentCourse.createdByName || 'GV. PTIT'}</strong></li>
            <li><span>Danh mục</span><strong>${isDaiCuong ? 'Đại Cương' : 'Chuyên ngành'}</strong></li>`;

        const startBtn = document.getElementById('startBtn');
        if (enrolledData) {
            // Display actual progress
            document.getElementById('sidebarProgress').style.display = 'block';
            const pct = Math.round(enrolledData.progressPercent || 0);
            document.getElementById('progressPct').textContent = pct + '%';
            document.getElementById('progressFill').style.width = pct + '%';

            startBtn.href = `ai-chat.html?id=${currentCourse.id}`;
            startBtn.innerHTML = `&#9654; Tiếp tục học`;
            startBtn.onclick = null;
        } else {
            // Not enrolled -> Click "Bắt đầu học" to silently enroll
            document.getElementById('sidebarProgress').style.display = 'none';
            startBtn.href = `#`;
            startBtn.innerHTML = `&#9654; Bắt đầu học `;
            startBtn.onclick = (e) => {
                e.preventDefault();
                enrollCourseSilent();
            };
        }

        // Quick access lessons in sidebar
        document.getElementById('sidebarChapters').innerHTML = lessons.map((les, i) => {
            const requiredPct = Math.round(((i + 1) / lessons.length) * 100);
            const isCompleted = enrolledData ? (enrolledData.progressPercent >= requiredPct) : false;
            return `
            <a href="${enrolledData ? `ai-chat.html?id=${currentCourse.id}&les=${les.id}` : '#'}" class="session-card" style="display:block;text-decoration:none;" onclick="${!enrolledData ? 'alert(\'Vui lòng nhấp nút Bắt đầu học phía trên trước khi chọn bài!\'); return false;' : ''}">
                <div class="session-title">Chương ${i + 1}: ${les.chapterName || 'Chương học'}</div>
                <span class="status-badge ${isCompleted ? '' : 'pending'}">
                    ${isCompleted ? 'Hoàn thành' : 'Chưa học'}
                </span>
            </a>`;
        }).join('');
    }

    function enrollCourseSilent() {
        const token = localStorage.getItem('ptit_token');
        if (!token) return;

        fetch(`/api/v1/courses/${currentCourse.id}/enroll`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({})
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    showToast('Đã mở khóa học tập miễn phí! Chúc bạn học tốt.');
                    setTimeout(() => { init(); }, 800);
                } else {
                    alert('Lỗi khi mở khóa học: ' + resData.message);
                }
            })
            .catch(err => {
                console.error(err);
                alert('Lỗi kết nối khi đăng ký học.');
            });
    }

    function loadChapterExercise(chapterId) {
        const token = localStorage.getItem('ptit_token');
        fetch(`/api/v1/chapters/${chapterId}/exercises/next`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
        .then(res => {
            if (res.status === 404) {
                return { success: true, data: null };
            }
            return res.json();
        })
        .then(resData => {
            const container = document.getElementById(`ex-container-${chapterId}`);
            if (!container) return;

            if (resData && resData.success && resData.data) {
                const ex = resData.data;
                container.innerHTML = `
                <div style="background:#f9fafb; border:1px solid #e5e7eb; padding:16px; border-radius:8px;">
                    <div style="font-weight:700; font-size:13px; color:#c12026; margin-bottom:8px; display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                        <span>Bài tập ${ex.exerciseCode || ''}: ${ex.exerciseName || 'Luyện tập'}</span>
                        <span class="badge" style="background:#fdf2f2; color:#c12026; font-size:11px; padding:2px 8px; border-radius:4px;">${ex.difficulty}</span>
                        <span class="badge" style="background:#f0fdf4; color:#16a34a; font-size:11px; padding:2px 8px; border-radius:4px;">${ex.bloomLevel}</span>
                    </div>
                    <div style="font-size:13.5px; color:var(--text-2); margin-bottom:12px; line-height:1.5;">${ex.question}</div>
                    <div style="display:flex; gap:8px; max-width:400px;">
                        <input type="text" id="ans-input-${ex.id}" class="form-control" style="font-size:13px; padding:8px 12px; height:36px;" placeholder="Nhập đáp án của bạn...">
                        <button onclick="submitExerciseAnswer(${ex.id}, ${chapterId})" class="btn btn-primary" style="font-size:13px; height:36px; padding:0 16px; min-width:80px;">Nộp bài</button>
                    </div>
                    <div id="ex-msg-${ex.id}" style="font-size:13px; margin-top:8px; font-weight:600; display:none;"></div>
                </div>`;
            } else {
                container.innerHTML = `<div style="background:#f0fdf4; border:1px solid #bbf7d0; color:#16a34a; padding:12px; border-radius:8px; font-size:13px; font-weight:600;">Chương học này không có bài tập bắt buộc.</div>`;
            }
        })
        .catch(err => {
            console.error('Load exercise error:', err);
            const container = document.getElementById(`ex-container-${chapterId}`);
            if (container) {
                container.innerHTML = `<div style="color:var(--text-3); font-size:13px;">Không thể tải bài tập.</div>`;
            }
        });
    }

    window.submitExerciseAnswer = function (exerciseId, chapterId) {
        const ansInput = document.getElementById(`ans-input-${exerciseId}`);
        const msgDiv = document.getElementById(`ex-msg-${exerciseId}`);
        if (!ansInput || !ansInput.value.trim()) return;

        const answer = ansInput.value.trim();
        const token = localStorage.getItem('ptit_token');

        msgDiv.style.display = 'block';
        msgDiv.style.color = 'var(--text-3)';
        msgDiv.textContent = 'Đang nộp câu trả lời...';

        fetch(`/api/v1/exercises/${exerciseId}/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({ answer: answer })
        })
        .then(res => res.json())
        .then(resData => {
            if (resData && resData.success) {
                const result = resData.data;
                if (result.isCorrect) {
                    msgDiv.style.color = '#16a34a';
                    msgDiv.textContent = (result.message || 'Chính xác!');
                    showToast('Chúc mừng! Đáp án chính xác.');
                    setTimeout(() => {
                        init();
                    }, 1500);
                } else {
                    msgDiv.style.color = '#ef4444';
                    msgDiv.textContent = '✗ ' + (result.message || 'Đáp án chưa đúng. Hãy thử lại.');
                }
            } else {
                msgDiv.style.color = '#ef4444';
                msgDiv.textContent = 'Lỗi nộp bài: ' + resData.message;
            }
        })
        .catch(err => {
            console.error(err);
            msgDiv.style.color = '#ef4444';
            msgDiv.textContent = 'Lỗi kết nối khi nộp câu trả lời.';
        });
    };

    function updateLearningProgress(newProgress) {
        const token = localStorage.getItem('ptit_token');
        fetch('/api/v1/learning-profiles/me/progress', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({ courseId: enrolledData.courseId || currentCourse.id, progressPercent: newProgress })
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    showToast('Tuyệt vời! Đã ghi nhận hoàn thành bài học.');
                    setTimeout(() => { init(); }, 800);
                } else {
                    alert('Lỗi: ' + resData.message);
                }
            })
            .catch(err => {
                console.error(err);
                alert('Không thể ghi nhận hoàn thành bài học.');
            });
    }

    function loadReviews() {
        const token = localStorage.getItem('ptit_token');
        fetch(`/api/v1/courses/${currentCourse.id}/reviews?size=100`, {
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(res => res.json())
            .then(resData => {
                if (resData && resData.success) {
                    const reviewsPage = resData.data;
                    const reviews = reviewsPage.items || [];
                    renderReviewsList(reviews);
                }
            })
            .catch(err => {
                console.error('Fetch reviews error:', err);
                document.getElementById('reviewsSection').innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-3);">Không thể tải đánh giá. Vui lòng thử lại.</div>';
            });
    }

    function renderReviewsList(reviews) {
        let avgRating = 0;
        if (reviews.length > 0) {
            const sum = reviews.reduce((acc, r) => acc + r.rating, 0);
            avgRating = (sum / reviews.length).toFixed(1);
        } else {
            avgRating = '0.0';
        }

        let reviewsHTML = `
            <div style="background:var(--bg-white);border:1px solid var(--border);border-radius:var(--radius-lg);padding:28px;width:100%;box-sizing:border-box;">
                <div style="display:flex;gap:32px;align-items:center;margin-bottom:24px;padding-bottom:24px;border-bottom:1px solid var(--border);">
                    <div style="text-align:center;min-width:100px;">
                        <div style="font-size:52px;font-weight:900;color:var(--primary);line-height:1;">${avgRating}</div>
                        <div style="font-size:13px;color:var(--text-3);margin-top:4px;">${reviews.length} đánh giá</div>
                    </div>
                    <div style="font-size:14px;color:var(--text-3);line-height:1.8;">
                        Xếp hạng trung bình từ sinh viên PTIT tham gia khóa học này.<br>
                        ${reviews.length > 0 ? `Có <strong style="color:var(--text-1);">${reviews.filter(r => r.rating >= 4).length}</strong> đánh giá tích cực (từ 4-5 sao).` : 'Chưa có xếp hạng cho khóa học này.'}
                    </div>
                </div>
        `;

        if (reviews.length === 0) {
            reviewsHTML += `
                <div style="text-align:center;padding:40px 0;color:var(--text-3);">
                    Khóa học này chưa có đánh giá nào. Hãy là người đầu tiên đánh giá!
                </div>
            `;
        } else {
            reviewsHTML += reviews.map(r => {
                const initials = r.studentName ? r.studentName.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() : 'SV';
                const starsStr = '★'.repeat(r.rating) + '☆'.repeat(5 - r.rating);
                return `
                <div style="padding:20px 0;border-bottom:1px solid var(--border-light);">
                    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
                        <div style="width:40px;height:40px;background:linear-gradient(135deg,var(--primary),var(--primary-dark));color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;flex-shrink:0;">${initials}</div>
                        <div>
                            <div style="font-weight:700;font-size:14px;">${r.studentName || 'Sinh viên PTIT'}</div>
                            <div style="font-size:12px;color:#f59e0b;">${starsStr}</div>
                        </div>
                    </div>
                    <p style="font-size:14px;color:var(--text-2);line-height:1.7;">${r.comment || 'Không có bình luận.'}</p>
                </div>`;
            }).join('');
        }

        // Add review form if enrolled and student
        const user = JSON.parse(localStorage.getItem('ptit_user') || '{}');
        if (enrolledData && user.role === 'STUDENT') {
            reviewsHTML += `
                <div style="margin-top:32px;padding-top:24px;border-top:1.5px solid var(--border);">
                    <h4 style="font-size:16px;font-weight:700;margin-bottom:16px;">Gửi đánh giá của bạn</h4>
                    <form id="reviewSubmitForm" style="display:flex;flex-direction:column;gap:12px;">
                        <div style="display:flex;align-items:center;gap:8px;">
                            <span style="font-size:14px;font-weight:600;color:var(--text-2);">Đánh giá sao:</span>
                            <div class="star-rating-select" style="display:flex;gap:4px;font-size:20px;cursor:pointer;color:#d1d5db;">
                                <span class="star-select-item" data-val="1" style="color:#f59e0b;">★</span>
                                <span class="star-select-item" data-val="2" style="color:#f59e0b;">★</span>
                                <span class="star-select-item" data-val="3" style="color:#f59e0b;">★</span>
                                <span class="star-select-item" data-val="4" style="color:#f59e0b;">★</span>
                                <span class="star-select-item" data-val="5" style="color:#f59e0b;">★</span>
                            </div>
                            <input type="hidden" id="reviewRatingInput" value="5">
                        </div>
                        <div>
                            <textarea id="reviewCommentInput" class="form-control" rows="3" placeholder="Nhập nhận xét của bạn về khóa học này..." style="resize:vertical;" required></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary" style="align-self:flex-start;">Gửi đánh giá</button>
                    </form>
                </div>
            `;
        }

        reviewsHTML += `</div>`;
        document.getElementById('reviewsSection').innerHTML = reviewsHTML;

        // Add events for review submit form and star rating select
        if (enrolledData && user.role === 'STUDENT') {
            const starSelectItems = document.querySelectorAll('.star-select-item');
            const ratingInput = document.getElementById('reviewRatingInput');
            starSelectItems.forEach(item => {
                item.addEventListener('click', () => {
                    const rating = parseInt(item.dataset.val);
                    ratingInput.value = rating;
                    starSelectItems.forEach(star => {
                        const starVal = parseInt(star.dataset.val);
                        if (starVal <= rating) {
                            star.style.color = '#f59e0b';
                        } else {
                            star.style.color = '#d1d5db';
                        }
                    });
                });
            });

            const form = document.getElementById('reviewSubmitForm');
            form.addEventListener('submit', (e) => {
                e.preventDefault();
                submitReview();
            });
        }
    }

    function submitReview() {
        const rating = parseInt(document.getElementById('reviewRatingInput').value);
        const comment = document.getElementById('reviewCommentInput').value.trim();
        const token = localStorage.getItem('ptit_token');

        fetch(`/api/v1/courses/${currentCourse.id}/reviews`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({ rating, comment })
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    showToast('Đã gửi đánh giá thành công! Cảm ơn ý kiến của bạn.');
                    loadReviews();
                } else {
                    alert('Lỗi gửi đánh giá: ' + resData.message);
                }
            })
            .then(null, err => {
                console.error('Submit review error:', err);
                alert('Lỗi kết nối khi gửi đánh giá.');
            });
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
