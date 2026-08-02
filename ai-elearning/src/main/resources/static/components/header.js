// =====================================================
// HEADER COMPONENT - Premium Glass Edition
// =====================================================
(function () {
    const token = localStorage.getItem('ptit_token');
    const currentPath = window.location.pathname;

    // Check if token is missing and not on login/register pages
    if (!token && !currentPath.endsWith('login.html') && !currentPath.endsWith('register.html')) {
        window.location.href = 'login.html';
        return;
    }

    const isLoggedIn = localStorage.getItem('ptit_user') !== null;
    const user = isLoggedIn ? JSON.parse(localStorage.getItem('ptit_user')) : null;
    const initials = user && user.name ? user.name.split(' ').filter(w => w).map(w => w[0]).join('').slice(0, 2).toUpperCase() : 'PT';
    const avatarInner = (user && user.avatarUrl) 
        ? `<img src="${user.avatarUrl}" alt="Avatar" style="width:100%; height:100%; border-radius:50%; object-fit:cover;">` 
        : initials;

    window.updateHeaderAvatar = function (avatarUrl) {
        const btn = document.getElementById('userAvatarBtn');
        if (!btn) return;
        const storedUser = JSON.parse(localStorage.getItem('ptit_user') || '{}');
        if (avatarUrl) {
            storedUser.avatarUrl = avatarUrl;
            btn.innerHTML = `<img src="${avatarUrl}" alt="Avatar" style="width:100%; height:100%; border-radius:50%; object-fit:cover;">`;
        } else {
            const inits = storedUser.name ? storedUser.name.split(' ').filter(w => w).map(w => w[0]).join('').slice(0, 2).toUpperCase() : 'PT';
            btn.textContent = inits;
        }
        localStorage.setItem('ptit_user', JSON.stringify(storedUser));
    };

    if (!document.getElementById('i18nAutoEngine')) {
        const s = document.createElement('script');
        s.id = 'i18nAutoEngine';
        s.src = 'js/i18n.js';
        document.head.appendChild(s);
    }

    const currentLang = localStorage.getItem('ptit_lang') === 'en' ? 'en' : 'vi';

    const headerHTML = `
<header class="site-header" id="siteHeader">
    <div class="container">
        <a href="index.html" class="header-logo" style="display:flex; align-items:center; text-decoration:none;">
            <img src="assets/images/Logo-Hoc-Vien-Cong-Nghe-Buu-Chinh-Vien-Thong-PTITSimple.webp" alt="PTIT Logo" style="height:46px; width:auto; object-fit:contain; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.05));">
        </a>

        <div class="header-actions" style="display:flex; align-items:center; gap: 16px;">
            <a href="my-courses.html" class="btn-my-courses" style="background: linear-gradient(135deg, #7a1318 0%, #54090c 100%); color: #ffffff; font-weight: 700; border-radius: 24px; padding: 9px 22px; font-size: 13.5px; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 4px 14px rgba(122, 19, 24, 0.28); transition: all 0.25s ease;">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                <span data-i18n="my_courses">Khóa học của tôi</span>
            </a>

            <!-- Language Selector Dropdown Button -->
            <div class="lang-selector" id="langSelectorBtn" onclick="if(window.toggleLangDropdown) window.toggleLangDropdown(event);" title="Chọn ngôn ngữ / Select Language" style="position: relative; display:flex; align-items:center; gap: 6px; font-size: 13px; font-weight: 700; color: var(--text-2); cursor: pointer; padding: 6px 14px; border-radius: 20px; background: rgba(0,0,0,0.04); border: 1px solid rgba(0,0,0,0.08); transition: all 0.2s ease; user-select:none;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                <span id="langCurrentText">${currentLang === 'en' ? 'EN' : 'VN'}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>

                <div class="lang-dropdown-menu" id="langDropdownMenu" style="display:none; position:absolute; top:calc(100% + 8px); right:0; background:#ffffff; border:1px solid rgba(0,0,0,0.1); border-radius:12px; box-shadow:0 12px 30px rgba(0,0,0,0.15); padding:6px; min-width:145px; z-index:9999;">
                    <div class="lang-item" onclick="if(window.selectLanguage) window.selectLanguage('vi', event);" style="padding:10px 14px; border-radius:8px; display:flex; align-items:center; gap:10px; font-size:13px; color:#1e293b; font-weight:600; cursor:pointer; transition:background 0.2s;">
                        <span style="font-size:16px;">🇻🇳</span> Tiếng Việt
                    </div>
                    <div class="lang-item" onclick="if(window.selectLanguage) window.selectLanguage('en', event);" style="padding:10px 14px; border-radius:8px; display:flex; align-items:center; gap:10px; font-size:13px; color:#1e293b; font-weight:600; cursor:pointer; transition:background 0.2s;">
                        <span style="font-size:16px;">🇬🇧</span> English
                    </div>
                </div>
            </div>

            ${isLoggedIn ? `
            <button class="noti-btn" id="notificationBtn" title="Thông báo"
                style="position:relative; width:40px; height:40px; border-radius:50%; display:flex; align-items:center; justify-content:center; background: rgba(0,0,0,0.03); border: 1px solid rgba(0,0,0,0.06); color: var(--text-2); cursor:pointer; transition:all var(--transition); flex-shrink:0;">
                <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="m13.73 21a2 2 0 0 1-3.46 0"/></svg>
                <span id="notiBadge" style="display:none; position:absolute; top:-3px; right:-3px; background:#ef4444; color:#fff; font-size:10px; font-weight:700; min-width:16px; height:16px; border-radius:50%; align-items:center; justify-content:center; line-height:1; border:2px solid var(--bg-white); padding:0 2px;">0</span>
            </button>

            <div class="user-menu" id="userMenu" style="position:relative;">
                <button class="user-avatar-btn" id="userAvatarBtn" title="${user ? user.name : ''}" style="width:40px; height:40px; border-radius:50%; background: linear-gradient(135deg, #7a1318, #54090c); color:#fff; font-weight:800; font-size:14px; border:2px solid #ffffff; box-shadow:0 2px 8px rgba(122,19,24,0.25); cursor:pointer; display:flex; align-items:center; justify-content:center; overflow:hidden; padding:0; transition:all 0.2s ease;">${avatarInner}</button>
                <div class="user-dropdown" id="userDropdown">
                    <div class="user-info">
                        <div class="name">${user.name}</div>
                        <div class="email">${user.email}</div>
                    </div>
                    <hr>
                    <a href="profile.html">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M6 20v-2a6 6 0 0 1 12 0v2"/></svg>
                        <span data-i18n="profile">Hồ sơ cá nhân</span>
                    </a>
                    <a href="student-dashboard.html">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                        <span data-i18n="learning_mgmt">Quản lý học tập</span>
                    </a>
                    <a href="my-courses.html">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                        <span data-i18n="my_courses">Khóa học của tôi</span>
                    </a>
                    ${(user && (user.role === 'ADMIN' || user.role === 'TEACHER')) ? `
                    <a href="dashboard.html" style="color: #7a1318; font-weight: 700;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/><path d="M14 9h7"/><path d="M14 15h7"/></svg>
                        <span data-i18n="admin_mgmt">Quản trị Admin</span>
                    </a>` : ''}
                    <hr>
                    <a href="#" id="logoutBtn" style="color:var(--primary);">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                        <span data-i18n="logout">Đăng xuất</span>
                    </a>
                </div>
            </div>
            ` : `
            <a href="login.html" class="btn btn-secondary btn-sm" style="border-radius:20px; padding:7px 18px; font-weight:600;" data-i18n="login">Đăng nhập</a>
            `}
        </div>
    </div>
</header>

<!-- Notification Drawer -->
<div id="notiDrawer" style="position:fixed;top:0;right:-380px;width:380px;height:100%;background:var(--bg-white);border-left:1px solid var(--border);box-shadow:var(--shadow-xl);transition:right .35s cubic-bezier(.4,0,.2,1);z-index:1000;display:flex;flex-direction:column;">
    <div style="padding:20px 24px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;background:linear-gradient(135deg,#1e0304,#7a1318);color:#fff;">
        <div>
            <div style="font-size:16px;font-weight:800;letter-spacing:-.3px;">Thông báo</div>
            <div style="font-size:12px;opacity:.7;margin-top:2px;">Cập nhật mới nhất của bạn</div>
        </div>
        <button id="closeNotiBtn" style="background:rgba(255,255,255,.15);border:none;width:32px;height:32px;border-radius:50%;font-size:18px;cursor:pointer;color:#fff;display:flex;align-items:center;justify-content:center;transition:background .2s;">&#x2715;</button>
    </div>
    <div id="notiList" style="flex:1;overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px;">
        <div style="text-align:center;color:var(--text-3);padding:48px 20px;font-size:14px;">
            <div style="font-size:40px;margin-bottom:12px;">🔔</div>
            Đang tải thông báo...
        </div>
    </div>
</div>
<div id="notiBackdrop" style="position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:999;display:none;backdrop-filter:blur(2px);"></div>
`;

    document.write(headerHTML);

    document.addEventListener('DOMContentLoaded', () => {
        // Scroll effect
        const header = document.getElementById('siteHeader');
        if (header) {
            const onScroll = () => {
                if (window.scrollY > 20) {
                    header.classList.add('scrolled');
                } else {
                    header.classList.remove('scrolled');
                }
            };
            window.addEventListener('scroll', onScroll, { passive: true });
            onScroll();
        }

        // Active nav link
        const path = window.location.pathname.split('/').pop() || 'index.html';
        document.querySelectorAll('.nav-link').forEach(link => {
            if (link.getAttribute('href') === path) link.classList.add('active');
        });

        // Logout
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', (e) => {
                e.preventDefault();
                localStorage.removeItem('ptit_user');
                localStorage.removeItem('ptit_token');
                window.location.href = 'index.html';
            });
        }

        // Avatar dropdown
        const userAvatarBtn = document.getElementById('userAvatarBtn');
        const userMenu = document.getElementById('userMenu');
        if (userAvatarBtn) {
            userAvatarBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                userMenu.classList.toggle('open');
            });
            document.addEventListener('click', () => userMenu.classList.remove('open'));
        }

        // --- Notifications ---
        if (token && isLoggedIn) {
            window.loadNotifications = function () {
                fetch('/api/v1/notifications', {
                    headers: { 'Authorization': 'Bearer ' + token }
                })
                .then(res => {
                    if (res.status === 401) return { success: false, data: { items: [] } };
                    return res.json();
                })
                .then(resData => {
                    if (resData && resData.success) {
                        const notifications = resData.data.items || [];
                        const unread = notifications.filter(n => !n.isRead);
                        const badge = document.getElementById('notiBadge');
                        if (badge) {
                            if (unread.length > 0) {
                                badge.textContent = unread.length;
                                badge.style.display = 'flex';
                            } else {
                                badge.style.display = 'none';
                            }
                        }
                        renderNotiList(notifications);
                    }
                })
                .catch(err => console.error(err));
            };
            loadNotifications();

            // SSE Real-time Connect
            const connectSSE = () => {
                const sseUrl = `/api/v1/notifications/subscribe?token=${token}`;
                const eventSource = new EventSource(sseUrl);

                eventSource.addEventListener('notification', (e) => {
                    try {
                        const noti = JSON.parse(e.data);
                        console.log('Real-time notification received:', noti);
                        if (typeof loadNotifications === 'function') {
                            loadNotifications();
                        }
                        showRealtimeToast(noti.message, noti.type);
                    } catch (err) {
                        console.error('Failed to parse SSE event data:', err);
                    }
                });

                eventSource.onerror = (err) => {
                    console.error('EventSource error, reconnecting...', err);
                    eventSource.close();
                    setTimeout(connectSSE, 5000);
                };
            };
            connectSSE();
        }

        function showRealtimeToast(message, type) {
            let container = document.getElementById('realtimeToastContainer');
            if (!container) {
                container = document.createElement('div');
                container.id = 'realtimeToastContainer';
                container.style.position = 'fixed';
                container.style.bottom = '24px';
                container.style.right = '24px';
                container.style.zIndex = '9999';
                container.style.display = 'flex';
                container.style.flexDirection = 'column';
                container.style.gap = '10px';
                container.style.maxWidth = '360px';
                container.style.width = '100%';
                document.body.appendChild(container);
            }

            const toast = document.createElement('div');
            toast.style.background = '#fff';
            toast.style.border = '1px solid var(--border)';
            toast.style.borderLeft = '4px solid var(--primary)';
            toast.style.borderRadius = '8px';
            toast.style.boxShadow = '0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)';
            toast.style.padding = '14px 18px';
            toast.style.fontSize = '13.5px';
            toast.style.lineHeight = '1.5';
            toast.style.color = 'var(--text-1)';
            toast.style.display = 'flex';
            toast.style.flexDirection = 'column';
            toast.style.gap = '4px';
            toast.style.animation = 'slideInNoti 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
            toast.style.transition = 'all 0.3s ease';

            const styleSheet = document.getElementById('realtimeToastStyle') || document.createElement('style');
            styleSheet.id = 'realtimeToastStyle';
            styleSheet.textContent = `
                @keyframes slideInNoti {
                    from { transform: translateX(120%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
            `;
            if (!document.getElementById('realtimeToastStyle')) {
                document.head.appendChild(styleSheet);
            }

            const title = type === 'CHAPTER_UNLOCKED' ? 'Chương Mới Đã Mở Khóa!' : (type === 'COURSE_UPDATE' ? 'Cập Nhật Khóa Học' : 'Thông Báo Mới');
            toast.innerHTML = `
                <div style="font-weight: 800; font-size: 11.5px; color: var(--primary); text-transform: uppercase; letter-spacing: 0.5px;">${title}</div>
                <div>${message}</div>
            `;

            container.appendChild(toast);

            setTimeout(() => {
                toast.style.transform = 'translateX(120%)';
                toast.style.opacity = '0';
                setTimeout(() => {
                    toast.remove();
                }, 300);
            }, 6000);
        }

        const notiBtn      = document.getElementById('notificationBtn');
        const notiDrawer   = document.getElementById('notiDrawer');
        const notiBackdrop = document.getElementById('notiBackdrop');
        const closeNotiBtn = document.getElementById('closeNotiBtn');

        if (notiBtn && notiDrawer && notiBackdrop && closeNotiBtn) {
            notiBtn.addEventListener('click', (e) => {
                e.preventDefault();
                notiDrawer.style.right = '0px';
                notiBackdrop.style.display = 'block';
                if (typeof loadNotifications === 'function') loadNotifications();
            });
            const closeDrawer = () => {
                notiDrawer.style.right = '-380px';
                notiBackdrop.style.display = 'none';
            };
            closeNotiBtn.addEventListener('click', closeDrawer);
            notiBackdrop.addEventListener('click', closeDrawer);
            closeNotiBtn.addEventListener('mouseenter', () => closeNotiBtn.style.background = 'rgba(255,255,255,.25)');
            closeNotiBtn.addEventListener('mouseleave', () => closeNotiBtn.style.background = 'rgba(255,255,255,.15)');
        }

        function renderNotiList(notifications) {
            const listContainer = document.getElementById('notiList');
            if (!listContainer) return;
            if (notifications.length === 0) {
                listContainer.innerHTML = `
                    <div style="text-align:center;color:var(--text-3);padding:48px 20px;font-size:14px;">
                        <div style="font-size:48px;margin-bottom:12px;opacity:.5;">📭</div>
                        <div style="font-weight:600;margin-bottom:4px;">Không có thông báo nào</div>
                        <div style="font-size:12px;">Bạn đã đọc hết rồi!</div>
                    </div>`;
                return;
            }
            listContainer.innerHTML = notifications.map(n => {
                const bg   = n.isRead ? 'var(--bg-white)' : 'var(--primary-light)';
                const border = n.isRead ? 'var(--border)' : 'rgba(193,32,38,.2)';
                const title = n.type || 'HỆ THỐNG';
                const date  = new Date(n.createdAt).toLocaleString('vi-VN');
                const badgeClass = n.type === 'SYSTEM' ? 'badge-primary' : 'badge-success';
                return `
                <div style="background:${bg};padding:14px 16px;border:1px solid ${border};border-radius:var(--radius-lg);display:flex;flex-direction:column;gap:8px;transition:all var(--transition);">
                    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                        <span class="badge ${badgeClass}" style="font-size:9px;padding:2px 8px;">${title}</span>
                        <span style="font-size:11px;color:var(--text-4);white-space:nowrap;">${date}</span>
                    </div>
                    <div style="font-size:13px;color:var(--text-2);line-height:1.5;">${n.message}</div>
                    ${!n.isRead ? `<button onclick="markNotificationRead(${n.id})"
                        style="align-self:flex-end;background:var(--primary-light);border:1px solid rgba(193,32,38,.2);color:var(--primary);font-size:12px;font-weight:600;cursor:pointer;padding:4px 10px;border-radius:var(--radius);font-family:var(--font);transition:all var(--transition);">Đánh dấu đã đọc</button>` : ''}
                </div>`;
            }).join('');
        }

        window.markNotificationRead = function (notiId) {
            fetch(`/api/v1/notifications/${notiId}/read`, {
                method: 'PATCH',
                headers: { 'Authorization': 'Bearer ' + token }
            })
            .then(res => res.json())
            .then(resData => {
                if (resData.success && typeof loadNotifications === 'function') loadNotifications();
            })
            .catch(err => console.error(err));
        };
    });
})();
