// System Toast Notification Helper
window.showSystemToast = function(message, type = 'error') {
    let container = document.querySelector('.system-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'system-toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `system-toast toast-${type}`;
    
    let iconSvg = '';
    if (type === 'success') {
        iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>`;
    } else if (type === 'warning') {
        iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
    } else {
        iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;
    }

    toast.innerHTML = `
        <div class="system-toast-icon">${iconSvg}</div>
        <div class="system-toast-msg">${message}</div>
        <button class="system-toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4500);
};

// Override native browser alert with system toast
window.alert = function(msg) {
    let type = 'error';
    if (msg.includes('thành công') || msg.includes('chuyển hướng')) type = 'success';
    else if (msg.includes('Mật khẩu') || msg.includes('tích chọn') || msg.includes('ít nhất')) type = 'warning';
    window.showSystemToast(msg, type);
};

document.addEventListener('DOMContentLoaded', () => {

    // ===== BANNER SLIDESHOW (4 IMAGES, 3 SECONDS EACH) =====
    const banner = document.getElementById('authBanner');
    if (banner) {
        const images = [
            'assets/images/auth_banner_1.png',
            'assets/images/auth_banner_2.png',
            'assets/images/auth_banner_3.png',
            'assets/images/auth_banner_4.png'
        ];
        let currentIndex = 0;
        const indicators = document.querySelectorAll('.indicator');

        banner.style.backgroundSize = 'cover';
        banner.style.backgroundPosition = 'center';
        banner.style.transition = 'background-image 0.8s ease-in-out';

        function showSlide(idx) {
            currentIndex = idx;
            banner.style.backgroundImage = `linear-gradient(160deg, rgba(15, 1, 2, 0.35), rgba(45, 5, 8, 0.25)), url('${images[idx]}')`;
            indicators.forEach((ind, i) => ind.classList.toggle('active', i === idx));
        }

        showSlide(0);

        indicators.forEach((ind, i) => {
            ind.addEventListener('click', () => showSlide(i));
        });

        setInterval(() => {
            showSlide((currentIndex + 1) % images.length);
        }, 3000);
    }    // ===== LOGIN FORM =====
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const email    = document.getElementById('loginEmail').value.trim();
            const password = document.getElementById('loginPassword').value;
            if (!email || !password) return;
            fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email, password: password })
            })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    const data = resData.data;
                    localStorage.setItem('ptit_token', data.accessToken);
                    
                    const userData = {
                        id: data.user.id,
                        name: data.user.fullName,
                        email: data.user.email,
                        role: (data.user.roles && data.user.roles.length > 0) ? data.user.roles[0] : 'STUDENT'
                    };
                    localStorage.setItem('ptit_user', JSON.stringify(userData));

                    // Gọi tiếp api /me để đồng bộ họ tên đầy đủ
                    fetch('/api/v1/auth/me', {
                        headers: { 'Authorization': 'Bearer ' + data.accessToken }
                    })
                    .then(r => r.json())
                    .then(meData => {
                        if (meData.success) {
                            userData.name = meData.data.fullName;
                            localStorage.setItem('ptit_user', JSON.stringify(userData));
                        }
                        const btn = loginForm.querySelector('button[type="submit"]');
                        btn.textContent = 'Đang chuyển hướng...';
                        btn.disabled = true;
                        if (userData.role === 'ADMIN' || userData.role === 'TEACHER') {
                            window.location.href = 'dashboard.html';
                        } else {
                            window.location.href = 'index.html';
                        }
                    })
                    .catch(() => {
                        if (userData.role === 'ADMIN' || userData.role === 'TEACHER') {
                            window.location.href = 'dashboard.html';
                        } else {
                            window.location.href = 'index.html';
                        }
                    });
                } else {
                    alert('Đăng nhập thất bại: ' + resData.message);
                }
            })
            .catch(err => {
                console.error(err);
                alert('Email hoặc mật khẩu không chính xác!');
            });
        });
    }



    // ===== REGISTER FORM =====
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const firstName = document.getElementById('firstName').value.trim();
            const lastName  = document.getElementById('lastName').value.trim();
            const email     = document.getElementById('regEmail').value.trim();
            const pass1     = document.getElementById('regPassword').value;
            const pass2     = document.getElementById('regPassword2').value;

            if (pass1 !== pass2) { alert('Mật khẩu xác nhận không khớp!'); return; }
            if (pass1.length < 8) { alert('Mật khẩu phải chứa ít nhất 8 ký tự!'); return; }

            const agreeCheckbox = document.getElementById('agreeTerms');
            if (!agreeCheckbox || !agreeCheckbox.checked) {
                alert('Bạn cần tích chọn đồng ý với Điều khoản dịch vụ và Chính sách bảo mật trước khi đăng ký tài khoản!');
                return;
            }

            let username = email.split('@')[0];
            if (username.length < 6) {
                username = username + "123456".slice(0, 6 - username.length);
            }

            fetch('/api/v1/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: username,
                    password: pass1,
                    email: email,
                    fullName: `${firstName} ${lastName}`
                })
            })
            .then(res => res.json())
            .then(resData => {
                if (resData.success) {
                    alert('Đăng ký thành công! Bạn có thể đăng nhập bằng email: ' + email);
                    showLogin();
                    const inputEmail = document.getElementById('loginEmail');
                    if (inputEmail) inputEmail.value = email;
                } else {
                    alert('Đăng ký thất bại: ' + resData.message);
                }
            })
            .catch(err => {
                console.error(err);
                alert('Tên đăng nhập hoặc email đã được sử dụng!');
            });
        });
    }
});

// ===== TAB TOGGLE =====
const bannerData = {
    login: {
        tag: 'Nền tảng học tập trực tuyến',
        h2:  'Học thông minh hơn<br>cùng AI gia sư',
        p:   'Tiếp cận hàng trăm bài giảng chất lượng cao, hỏi đáp tức thì với trí tuệ nhân tạo — mọi lúc, mọi nơi.',
        features: ['Dành riêng cho sinh viên PTIT', 'AI gia sư sẵn sàng 24/7', 'Nội dung chuẩn theo chương trình PTIT', 'Theo dõi tiến độ học tập chi tiết']
    },
    register: {
        tag: 'Tham gia cộng đồng học tập',
        h2:  'Bắt đầu hành trình<br>học tập của bạn',
        p:   'Hơn 12.000 sinh viên PTIT đã đăng ký và trải nghiệm cách học thông minh hơn với AI.',
        features: ['Đăng ký chỉ mất 1 phút', 'Không yêu cầu thông tin thanh toán', 'Truy cập ngay 50 khóa học', 'Hỏi AI gia sư không giới hạn']
    }
};

function updateBanner(mode) {
    const data = bannerData[mode];
    const content = document.getElementById('bannerContent');
    if (!content) return;

    content.style.transition = 'opacity .3s ease';
    content.style.opacity = '0';
    setTimeout(() => {
        document.getElementById('bannerTag').textContent = data.tag;
        document.getElementById('bannerH2').innerHTML = data.h2;
        document.getElementById('bannerP').textContent = data.p;
        document.getElementById('bannerFeatures').innerHTML =
            data.features.map(f => `<div class="auth-feature">${f}</div>`).join('');
        content.style.opacity = '1';
    }, 300);
}

function showLogin(e) {
    if (e) e.preventDefault();
    document.getElementById('loginPanel').style.display = 'block';
    document.getElementById('registerPanel').style.display = 'none';

    // Trigger animation replay
    const panel = document.getElementById('loginPanel');
    panel.style.animation = 'none';
    panel.offsetHeight; // reflow
    panel.style.animation = '';

    document.getElementById('tabLogin').classList.add('active');
    document.getElementById('tabRegister').classList.remove('active');
    updateBanner('login');
}

function showRegister(e) {
    if (e) e.preventDefault();
    document.getElementById('loginPanel').style.display = 'none';
    document.getElementById('registerPanel').style.display = 'block';

    // Trigger animation replay
    const panel = document.getElementById('registerPanel');
    panel.style.animation = 'none';
    panel.offsetHeight; // reflow
    panel.style.animation = '';

    document.getElementById('tabRegister').classList.add('active');
    document.getElementById('tabLogin').classList.remove('active');
    updateBanner('register');
}

// Quick Login Demo Helper
window.quickLogin = function(email, password) {
    const emailInput = document.getElementById('loginEmail');
    const passwordInput = document.getElementById('loginPassword');
    if (emailInput && passwordInput) {
        emailInput.value = email;
        passwordInput.value = password;
        const form = document.getElementById('loginForm');
        if (form) {
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit();
            } else {
                form.dispatchEvent(new Event('submit', { cancelable: true }));
            }
        }
    }
};

// Legal Modals Helper Functions
window.openTermsModal = function(e) {
    if (e) e.preventDefault();
    const modal = document.getElementById('termsModalOverlay');
    if (modal) modal.classList.add('active');
};

window.openPrivacyModal = function(e) {
    if (e) e.preventDefault();
    const modal = document.getElementById('privacyModalOverlay');
    if (modal) modal.classList.add('active');
};

window.closeLegalModal = function(e) {
    if (e && e.target !== e.currentTarget && !e.target.classList.contains('legal-modal-close')) return;
    document.querySelectorAll('.legal-modal-overlay').forEach(m => m.classList.remove('active'));
};

window.agreeLegalTerms = function() {
    const agreeCheckbox = document.getElementById('agreeTerms');
    if (agreeCheckbox) agreeCheckbox.checked = true;
    closeLegalModal();
};
