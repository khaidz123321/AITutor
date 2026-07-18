// =====================================================
// AUTH LOGIC — Single page (Login + Register toggle)
// =====================================================
document.addEventListener('DOMContentLoaded', () => {

    // ===== BANNER SLIDESHOW =====
    const banner = document.getElementById('authBanner');
    if (banner) {
        const images = [
            'https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1524178232363-1fb2b075b655?auto=format&fit=crop&w=900&q=80',
            'https://images.unsplash.com/photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=900&q=80',
        ];
        let current = 0;
        const indicators = document.querySelectorAll('.indicator');
        const content = document.getElementById('bannerContent');

        banner.style.backgroundSize = 'cover';
        banner.style.backgroundPosition = 'center';

        function goTo(idx) {
            current = idx;
            if (content) {
                content.style.transition = 'opacity .4s ease';
                content.style.opacity = '0';
            }
            setTimeout(() => {
                banner.style.backgroundImage =
                    `linear-gradient(160deg,rgba(0,0,0,.72),rgba(0,0,0,.52),rgba(0,0,0,.62)),url('${images[idx]}')`;
                indicators.forEach((ind, i) => ind.classList.toggle('active', i === idx));
                if (content) content.style.opacity = '1';
            }, 350);
        }

        goTo(0);
        indicators.forEach((ind, i) => ind.addEventListener('click', () => { clearInterval(timer); goTo(i); }));
        const timer = setInterval(() => goTo((current + 1) % images.length), 5000);
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
                        btn.textContent = '✓ Đang chuyển hướng...';
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
