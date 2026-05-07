// =====================================================
// HEADER COMPONENT - Commercial style, no icons
// =====================================================
(function () {
    const isLoggedIn = localStorage.getItem('ptit_user') !== null;
    const user = isLoggedIn ? JSON.parse(localStorage.getItem('ptit_user')) : null;
    const initials = user ? user.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() : 'PT';

    const headerHTML = `
<header class="site-header" id="siteHeader">
    <div class="container">
        <a href="index.html" class="header-logo">
            <img src="assets/images/Logo-Hoc-Vien-Cong-Nghe-Buu-Chinh-Vien-Thong-PTITSimple.webp" alt="PTIT Logo" style="height: 40px; width: auto; object-fit: contain;">
        </a>

        <div class="header-search">
            <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" id="headerSearch" placeholder="Tìm kiếm khóa học..." autocomplete="off">
        </div>

        <nav class="header-nav">
            <a href="index.html" class="nav-link">Trang chủ</a>
            <a href="courses.html" class="nav-link">Khóa học</a>
            <a href="introduction.html" class="nav-link">Giới thiệu</a>
            ${isLoggedIn ? `<a href="my-courses.html" class="nav-link">Học của tôi</a>` : ''}
        </nav>

        <div class="header-actions">
            ${isLoggedIn ? `
            <div class="user-menu" id="userMenu">
                <button class="user-avatar-btn" id="userAvatarBtn" title="${user.name}">${initials}</button>
                <div class="user-dropdown" id="userDropdown">
                    <div class="user-info">
                        <div class="name">${user.name}</div>
                        <div class="email">${user.email}</div>
                    </div>
                    <hr>
                    <a href="profile.html">Hồ sơ cá nhân</a>
                    <a href="my-courses.html">Khóa học của tôi</a>
                    <hr>
                    <a href="#" id="logoutBtn" style="color:#c12026;">Đăng xuất</a>
                </div>
            </div>
            ` : `
            <a href="login.html" class="btn btn-secondary btn-sm">Đăng nhập</a>
            <a href="register.html" class="btn btn-primary btn-sm">Đăng ký</a>
            `}
        </div>
    </div>
</header>`;

    document.write(headerHTML);

    document.addEventListener('DOMContentLoaded', () => {
        const path = window.location.pathname.split('/').pop() || 'index.html';
        document.querySelectorAll('.nav-link').forEach(link => {
            if (link.getAttribute('href') === path) link.classList.add('active');
        });

        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', (e) => {
                e.preventDefault();
                localStorage.removeItem('ptit_user');
                window.location.href = 'index.html';
            });
        }

        const userAvatarBtn = document.getElementById('userAvatarBtn');
        const userMenu = document.getElementById('userMenu');
        if (userAvatarBtn) {
            userAvatarBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                userMenu.classList.toggle('open');
            });
            document.addEventListener('click', () => userMenu.classList.remove('open'));
        }

        const headerSearch = document.getElementById('headerSearch');
        if (headerSearch) {
            headerSearch.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && headerSearch.value.trim()) {
                    window.location.href = `courses.html?search=${encodeURIComponent(headerSearch.value.trim())}`;
                }
            });
        }
    });
})();
