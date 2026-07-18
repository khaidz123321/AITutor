// =====================================================
// EXERCISE LOGIC - Dedicated Premium System
// =====================================================
(function () {
    const params = new URLSearchParams(window.location.search);
    const courseId = parseInt(params.get('courseId'));
    const chapterId = parseInt(params.get('chapterId'));
    const token = localStorage.getItem('ptit_token');

    if (!token) {
        window.location.href = 'login.html';
        return;
    }

    if (!courseId || !chapterId) {
        alert('Thiếu thông tin khóa học hoặc chương học!');
        window.location.href = 'index.html';
        return;
    }

    // State Variables
    let currentCourse = null;
    let currentChapter = null;
    let chaptersList = [];
    let exercisesList = [];
    let activeExercise = null;
    let enrolledData = null;
    let activeChapterIndex = -1;

    // Set up back button dynamically
    document.getElementById('backToChatBtn').href = `ai-chat.html?id=${courseId}&les=${chapterId}`;

    // Initialize Page
    function init() {
        // 1. Fetch Course Detail
        const p1 = fetch(`/api/v1/courses/${courseId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(res => res.json());

        // 2. Fetch Chapter Detail
        const p2 = fetch(`/api/v1/chapters/${chapterId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(res => res.json());

        // 3. Fetch Course Chapters List
        const p3 = fetch(`/api/v1/courses/${courseId}/chapters`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(res => res.json());

        // 4. Fetch User Learning Profile
        const p4 = fetch(`/api/v1/learning-profiles/me?courseId=${courseId}`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(res => res.json());

        Promise.all([p1, p2, p3, p4])
            .then(([courseRes, chapRes, listRes, profileRes]) => {
                if (courseRes.success) currentCourse = courseRes.data;
                if (chapRes.success) currentChapter = chapRes.data;
                if (listRes.success) chaptersList = listRes.data || [];
                if (profileRes.success) enrolledData = profileRes.data;

                if (!currentCourse || !currentChapter) {
                    alert('Không tìm thấy thông tin bài học.');
                    window.location.href = 'index.html';
                    return;
                }

                // Render Header details
                document.getElementById('courseNameText').textContent = currentCourse.title;
                document.getElementById('chapterNameText').textContent = currentChapter.chapterName;

                // Find active chapter index
                activeChapterIndex = chaptersList.findIndex(c => c.id === chapterId);

                // Determine if this chapter is already completed
                const requiredPct = Math.round(((activeChapterIndex + 1) / chaptersList.length) * 100);
                const isChapterCompleted = enrolledData && (enrolledData.progressPercent >= requiredPct);

                if (isChapterCompleted) {
                    // Already completed! Show celebration screen immediately
                    showCelebration(true);
                } else {
                    // Not completed yet, fetch exercises
                    loadExercises();
                }
            })
            .catch(err => {
                console.error('Initialization error:', err);
                alert('Có lỗi xảy ra khi tải dữ liệu bài học.');
            });
    }

    // Load exercises list and find next unsolved one
    function loadExercises() {
        // Fetch all exercises to calculate progress count
        const pList = fetch(`/api/v1/chapters/${chapterId}/exercises`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(res => res.json());

        // Fetch next unsolved exercise
        const pNext = fetch(`/api/v1/chapters/${chapterId}/exercises/next`, {
            headers: { 'Authorization': 'Bearer ' + token }
        }).then(res => {
            if (res.status === 404) {
                return { success: true, data: null };
            }
            return res.json();
        });

        Promise.all([pList, pNext])
            .then(([listRes, nextRes]) => {
                if (listRes.success) exercisesList = listRes.data || [];
                if (nextRes.success) activeExercise = nextRes.data;

                if (exercisesList.length === 0) {
                    // No exercises in this chapter, trigger completion celebration
                    showCelebration(false);
                    return;
                }

                if (!activeExercise) {
                    // No active exercise means all exercises are solved
                    showCelebration(true);
                } else {
                    renderExercise();
                }
            })
            .catch(err => {
                console.error('Load exercises error:', err);
                document.getElementById('exQuestionText').textContent = 'Không thể tải câu hỏi bài tập. Vui lòng thử lại sau.';
            });
    }

    // Render active exercise question
    function renderExercise() {
        if (!activeExercise) return;

        // Find index of active exercise in list to compute progress
        const activeIndex = exercisesList.findIndex(ex => ex.id === activeExercise.id);
        const solvedCount = activeIndex >= 0 ? activeIndex : 0;
        const pct = Math.round((solvedCount / exercisesList.length) * 100);

        // Update progress bar
        document.getElementById('progressPercentageText').textContent = `${pct}%`;
        document.getElementById('progressBarFill').style.width = `${pct}%`;
        document.getElementById('progressSummaryText').textContent = `Đã hoàn thành ${solvedCount}/${exercisesList.length} câu hỏi.`;

        // Render card meta
        document.getElementById('exCodeText').textContent = `Bài tập ${activeExercise.exerciseCode || ''}`;
        document.getElementById('exDifficultyText').textContent = activeExercise.difficulty || 'Độ khó';
        document.getElementById('exBloomText').textContent = activeExercise.bloomLevel || 'Nhận thức';
        document.getElementById('exTitleText').textContent = activeExercise.exerciseName || 'Câu hỏi luyện tập';
        document.getElementById('exQuestionText').textContent = activeExercise.question;

        // Reset answer input
        const answerInput = document.getElementById('answerInput');
        answerInput.value = '';
        answerInput.disabled = false;
        document.getElementById('btnSubmitAnswer').disabled = false;

        const statusMsg = document.getElementById('answerStatusMsg');
        statusMsg.style.display = 'none';
        statusMsg.className = 'answer-status-msg';
    }

    // Submit answer to server
    function submitAnswer() {
        const answerInput = document.getElementById('answerInput');
        const answer = answerInput.value.trim();
        const statusMsg = document.getElementById('answerStatusMsg');

        if (!answer) {
            alert('Vui lòng nhập câu trả lời của bạn!');
            return;
        }

        answerInput.disabled = true;
        const btnSubmit = document.getElementById('btnSubmitAnswer');
        btnSubmit.disabled = true;

        statusMsg.style.display = 'block';
        statusMsg.className = 'answer-status-msg';
        statusMsg.style.background = '#f3f4f6';
        statusMsg.style.color = 'var(--text-2)';
        statusMsg.textContent = 'Đang nộp đáp án của bạn lên hệ thống...';

        fetch(`/api/v1/exercises/${activeExercise.id}/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify({ answer: answer })
        })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const result = resData.data;
                    if (result.isCorrect) {
                        statusMsg.style.background = '#ecfdf5';
                        statusMsg.style.color = '#059669';
                        statusMsg.textContent = '✓ ' + (result.message || 'Chính xác! Chúc mừng bạn.');

                        // Calculate and update progress bar before moving forward
                        const solvedCount = exercisesList.findIndex(ex => ex.id === activeExercise.id) + 1;
                        const pct = Math.round((solvedCount / exercisesList.length) * 100);
                        document.getElementById('progressPercentageText').textContent = `${pct}%`;
                        document.getElementById('progressBarFill').style.width = `${pct}%`;
                        document.getElementById('progressSummaryText').textContent = `Đã hoàn thành ${solvedCount}/${exercisesList.length} câu hỏi.`;

                        setTimeout(() => {
                            if (result.nextExerciseId) {
                                // Load next question
                                loadExercises();
                            } else {
                                // Completed all! Show celebration
                                showCelebration(true, result.chapterUnlockedName);
                            }
                        }, 1500);
                    } else {
                        statusMsg.style.background = '#fef2f2';
                        statusMsg.style.color = '#dc2626';
                        statusMsg.textContent = '✗ ' + (result.message || 'Đáp án chưa chính xác. Hãy suy nghĩ thêm nhé!');
                        answerInput.disabled = false;
                        btnSubmit.disabled = false;
                    }
                } else {
                    statusMsg.style.background = '#fef2f2';
                    statusMsg.style.color = '#dc2626';
                    statusMsg.textContent = 'Lỗi nộp bài: ' + resData.message;
                    answerInput.disabled = false;
                    btnSubmit.disabled = false;
                }
            })
            .catch(err => {
                console.error(err);
                statusMsg.style.background = '#fef2f2';
                statusMsg.style.color = '#dc2626';
                statusMsg.textContent = 'Lỗi kết nối mạng khi gửi đáp án.';
                answerInput.disabled = false;
                btnSubmit.disabled = false;
            });
    }

    // Show celebration screen
    function showCelebration(hasExercises = true, unlockedChapterName = null) {
        document.getElementById('exerciseCard').style.display = 'none';
        const celebrationCard = document.getElementById('celebrationCard');
        celebrationCard.style.display = 'block';

        // Update progress bar to 100%
        document.getElementById('progressPercentageText').textContent = '100%';
        document.getElementById('progressBarFill').style.width = '100%';

        if (hasExercises) {
            document.getElementById('progressSummaryText').textContent = `Chúc mừng! Bạn đã hoàn thành tất cả ${exercisesList.length} bài tập.`;
        } else {
            document.getElementById('progressSummaryText').textContent = 'Chương này không có bài tập bắt buộc.';
            celebrationCard.querySelector('.celebrate-title').textContent = 'Chương Học Hoàn Thành!';
            celebrationCard.querySelector('.celebrate-desc').textContent = 'Chương học này không chứa bài tập thực hành bắt buộc. Bạn đã tích lũy đủ điểm để học chương tiếp theo.';
        }

        // Determine if next chapter exists
        const nextIndex = activeChapterIndex + 1;
        const nextChapter = (nextIndex >= 0 && nextIndex < chaptersList.length) ? chaptersList[nextIndex] : null;

        const nextChapterBox = document.getElementById('nextChapterBox');
        const btnNext = document.getElementById('btnNextChapterLink');

        if (nextChapter) {
            nextChapterBox.style.display = 'block';
            document.getElementById('nextChapterNameText').textContent = unlockedChapterName || nextChapter.chapterName;
            btnNext.href = `ai-chat.html?id=${courseId}&les=${nextChapter.id}`;
            btnNext.style.display = 'inline-flex';
        } else {
            // End of course
            nextChapterBox.style.display = 'block';
            nextChapterBox.style.background = '#eff6ff';
            nextChapterBox.style.borderColor = '#bfdbfe';
            nextChapterBox.querySelector('.next-chapter-label').textContent = '🎓 BẠN ĐÃ HOÀN THÀNH KHÓA HỌC';
            nextChapterBox.querySelector('.next-chapter-label').style.color = '#1d4ed8';
            document.getElementById('nextChapterNameText').textContent = currentCourse.title;

            btnNext.href = `course-detail.html?id=${courseId}`;
            btnNext.textContent = 'Quay lại chi tiết khóa học';
            btnNext.style.display = 'inline-flex';
        }
    }

    // Set up click handlers
    document.addEventListener('DOMContentLoaded', () => {
        init();

        document.getElementById('btnSubmitAnswer').addEventListener('click', submitAnswer);
        document.getElementById('answerInput').addEventListener('keydown', e => {
            if (e.key === 'Enter') {
                e.preventDefault();
                submitAnswer();
            }
        });
    });
})();
