// =====================================================
// AUTOMATIC FULL-PAGE GOOGLE TRANSLATION ENGINE & GLOBAL TOAST
// =====================================================
(function () {
    // -----------------------------------------------------
    // GLOBAL TOAST NOTIFICATION ENGINE (BOTTOM RIGHT OVERRIDE)
    // -----------------------------------------------------
    function getToastContainer() {
        let container = document.getElementById('globalToastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'globalToastContainer';
            container.style.cssText = `
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 999999;
                display: flex;
                flex-direction: column;
                gap: 10px;
                max-width: 380px;
                width: calc(100vw - 48px);
                pointer-events: none;
            `;
            const parent = document.body || document.documentElement;
            if (parent) parent.appendChild(container);
        }
        return container;
    }

    window.showToast = function (message, type = 'info', duration = 4000) {
        if (!message) return;
        const container = getToastContainer();
        if (!container) return;

        const toast = document.createElement('div');
        toast.style.cssText = `
            pointer-events: auto;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.15), 0 2px 6px rgba(0, 0, 0, 0.06);
            padding: 14px 18px;
            font-size: 13.5px;
            line-height: 1.5;
            font-weight: 600;
            color: #1e293b;
            display: flex;
            align-items: flex-start;
            gap: 12px;
            position: relative;
            overflow: hidden;
            border-left: 4px solid #7a1318;
            transform: translateX(120%);
            opacity: 0;
            transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
            font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;

        let accentColor = '#7a1318';
        let badgeTitle = 'THÔNG BÁO';
        let iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;

        const lower = String(message).toLowerCase();
        if (type === 'error' || lower.includes('lỗi') || lower.includes('thất bại') || lower.includes('không') || lower.includes('sai') || lower.includes('thiếu')) {
            accentColor = '#ef4444';
            badgeTitle = 'THÔNG BÁO LỖI';
            iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
        } else if (type === 'success' || lower.includes('thành công') || lower.includes('đã lưu') || lower.includes('đã thêm') || lower.includes('chính xác')) {
            accentColor = '#10b981';
            badgeTitle = 'THÀNH CÔNG';
            iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;
        } else if (type === 'warning' || lower.includes('cảnh báo') || lower.includes('vui lòng')) {
            accentColor = '#f59e0b';
            badgeTitle = 'CẢNH BÁO';
            iconSvg = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2.2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
        }

        toast.style.borderLeftColor = accentColor;

        toast.innerHTML = `
            <div style="color: ${accentColor}; flex-shrink: 0; margin-top: 1px;">
                ${iconSvg}
            </div>
            <div style="flex: 1;">
                <div style="font-size: 11px; font-weight: 800; color: ${accentColor}; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px;">
                    ${badgeTitle}
                </div>
                <div style="color: #334155; font-size: 13px; font-weight: 600; line-height: 1.4;">
                    ${message}
                </div>
            </div>
            <button class="toast-close-btn" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 16px; line-height: 1; padding: 2px 4px; margin-left: 4px; border-radius: 4px; transition: color 0.2s;">×</button>
        `;

        const closeBtn = toast.querySelector('.toast-close-btn');
        const removeToast = () => {
            toast.style.transform = 'translateX(120%)';
            toast.style.opacity = '0';
            setTimeout(() => {
                if (toast.parentNode) toast.remove();
            }, 350);
        };

        if (closeBtn) closeBtn.onclick = removeToast;

        container.appendChild(toast);

        requestAnimationFrame(() => {
            toast.style.transform = 'translateX(0)';
            toast.style.opacity = '1';
        });

        setTimeout(removeToast, duration);
    };

    // -----------------------------------------------------
    // GLOBAL CONFIRM MODAL ENGINE
    // -----------------------------------------------------
    window.showConfirm = function (message, title = 'XÁC NHẬN HỆ THỐNG') {
        return new Promise((resolve) => {
            let backdrop = document.getElementById('globalConfirmBackdrop');
            if (!backdrop) {
                backdrop = document.createElement('div');
                backdrop.id = 'globalConfirmBackdrop';
                backdrop.style.cssText = `
                    position: fixed;
                    inset: 0;
                    background: rgba(15, 23, 42, 0.65);
                    backdrop-filter: blur(8px);
                    -webkit-backdrop-filter: blur(8px);
                    z-index: 9999999;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    padding: 20px;
                    opacity: 0;
                    transition: opacity 0.25s ease;
                `;
                const parent = document.body || document.documentElement;
                if (parent) parent.appendChild(backdrop);
            }

            backdrop.innerHTML = `
                <div style="
                    background: #ffffff;
                    border-radius: 20px;
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(0, 0, 0, 0.05);
                    width: 100%;
                    max-width: 440px;
                    overflow: hidden;
                    transform: scale(0.92);
                    transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
                    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                ">
                    <div style="
                        background: linear-gradient(135deg, #7a1318 0%, #450a0d 100%);
                        color: #ffffff;
                        padding: 18px 24px;
                        display: flex;
                        align-items: center;
                        gap: 12px;
                    ">
                        <div style="
                            width: 38px;
                            height: 38px;
                            border-radius: 10px;
                            background: rgba(255, 255, 255, 0.15);
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            flex-shrink: 0;
                        ">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2">
                                <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                                <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                            </svg>
                        </div>
                        <div>
                            <div style="font-size: 11px; font-weight: 800; opacity: 0.85; text-transform: uppercase; letter-spacing: 0.8px;">Gia Sư AI PTIT</div>
                            <div style="font-size: 15px; font-weight: 700;">${title}</div>
                        </div>
                    </div>

                    <div style="padding: 24px; color: #334155; font-size: 14.5px; line-height: 1.6; font-weight: 500;">
                        ${message}
                    </div>

                    <div style="
                        padding: 16px 24px 24px 24px;
                        display: flex;
                        gap: 12px;
                        justify-content: flex-end;
                        background: #f8fafc;
                        border-top: 1px solid #e2e8f0;
                    ">
                        <button id="confirmCancelBtn" style="
                            padding: 10px 20px;
                            border-radius: 10px;
                            border: 1px solid #cbd5e1;
                            background: #ffffff;
                            color: #475569;
                            font-weight: 600;
                            font-size: 14px;
                            cursor: pointer;
                            transition: all 0.2s;
                        ">Hủy bỏ</button>
                        <button id="confirmOkBtn" style="
                            padding: 10px 22px;
                            border-radius: 10px;
                            border: none;
                            background: linear-gradient(135deg, #7a1318 0%, #54090c 100%);
                            color: #ffffff;
                            font-weight: 700;
                            font-size: 14px;
                            cursor: pointer;
                            box-shadow: 0 4px 12px rgba(122, 19, 24, 0.3);
                            transition: all 0.2s;
                        ">Đồng ý</button>
                    </div>
                </div>
            `;

            backdrop.style.display = 'flex';
            requestAnimationFrame(() => {
                backdrop.style.opacity = '1';
                const card = backdrop.firstElementChild;
                if (card) card.style.transform = 'scale(1)';
            });

            const cleanup = (result) => {
                backdrop.style.opacity = '0';
                const card = backdrop.firstElementChild;
                if (card) card.style.transform = 'scale(0.92)';
                setTimeout(() => {
                    backdrop.style.display = 'none';
                    resolve(result);
                }, 200);
            };

            const cancelBtn = document.getElementById('confirmCancelBtn');
            const okBtn = document.getElementById('confirmOkBtn');
            if (cancelBtn) cancelBtn.onclick = () => cleanup(false);
            if (okBtn) okBtn.onclick = () => cleanup(true);
        });
    };

    // Override browser window.alert globally to force all alerts to bottom-right toast
    window.alert = function (msg) {
        if (!msg) return;
        window.showToast(String(msg));
    };

    // Override browser window.confirm to prevent standard localhost alert popups
    window.confirm = function (msg) {
        if (!msg) return true;
        window.showToast(String(msg), 'warning');
        return true;
    };

    // -----------------------------------------------------
    // GOOGLE TRANSLATION ENGINE LOGIC
    // -----------------------------------------------------
    document.addEventListener('DOMContentLoaded', () => {
        if (!document.getElementById('google_translate_element')) {
            const div = document.createElement('div');
            div.id = 'google_translate_element';
            div.style.display = 'none';
            document.body.appendChild(div);
        }
    });

    if (!document.getElementById('googleTranslateStyle')) {
        const style = document.createElement('style');
        style.id = 'googleTranslateStyle';
        style.textContent = `
            .goog-te-banner-frame,
            .goog-te-banner-frame.skiptranslate,
            iframe.goog-te-banner-frame,
            iframe[id*=":1.container"],
            iframe[id*=":2.container"],
            iframe[id*=":0.container"],
            iframe[class*="goog"],
            .VIpgJd-ZJuEfc-aL92ed,
            .VIpgJd-ZJuEfc-Lg4e8b,
            .VIpgJd-ZJuEfc-qYrOfd-wT6pbd,
            #goog-gt-tt,
            .goog-te-balloon-part,
            .goog-tooltip,
            .goog-tooltip:hover {
                display: none !important;
                visibility: hidden !important;
                opacity: 0 !important;
                height: 0 !important;
                width: 0 !important;
                max-height: 0 !important;
                pointer-events: none !important;
            }

            body {
                top: 0px !important;
                position: static !important;
                margin-top: 0px !important;
            }

            .goog-text-highlight {
                background-color: transparent !important;
                box-shadow: none !important;
            }

            #google_translate_element {
                display: none !important;
            }

            font {
                background-color: transparent !important;
                box-shadow: none !important;
            }

            .lang-item:hover {
                background: rgba(122, 19, 24, 0.08) !important;
                color: #7a1318 !important;
            }
        `;
        document.head.appendChild(style);
    }

    const keepLayoutClean = () => {
        if (document.body.style.top !== '0px') {
            document.body.style.top = '0px';
        }
        if (document.body.style.position === 'relative') {
            document.body.style.position = 'static';
        }
        const gFrames = document.querySelectorAll('iframe.goog-te-banner-frame, .VIpgJd-ZJuEfc-aL92ed, .VIpgJd-ZJuEfc-Lg4e8b');
        gFrames.forEach(f => {
            f.style.display = 'none';
            f.style.visibility = 'hidden';
        });
    };

    setInterval(keepLayoutClean, 150);

    window.googleTranslateElementInit = function () {
        if (window.google && window.google.translate) {
            new window.google.translate.TranslateElement({
                pageLanguage: 'vi',
                includedLanguages: 'vi,en',
                autoDisplay: false
            }, 'google_translate_element');
        }
    };

    if (!document.getElementById('googleTranslateScript')) {
        const script = document.createElement('script');
        script.id = 'googleTranslateScript';
        script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
        document.head.appendChild(script);
    }

    window.toggleLangDropdown = function (e) {
        if (e) e.stopPropagation();
        const menu = document.getElementById('langDropdownMenu');
        if (!menu) return;
        const isVisible = menu.style.display === 'block';
        menu.style.display = isVisible ? 'none' : 'block';
    };

    window.selectLanguage = function (targetLang, e) {
        if (e) e.stopPropagation();
        const menu = document.getElementById('langDropdownMenu');
        if (menu) menu.style.display = 'none';

        const currentLang = localStorage.getItem('ptit_lang') || 'vi';
        localStorage.setItem('ptit_lang', targetLang);

        const langText = document.getElementById('langCurrentText');
        if (langText) {
            langText.textContent = targetLang.toUpperCase();
        }

        if (currentLang === targetLang) return;

        const select = document.querySelector('.goog-te-combo');
        if (select) {
            select.value = targetLang;
            select.dispatchEvent(new Event('change'));
        } else {
            document.cookie = `googtrans=/vi/${targetLang}; path=/`;
            window.location.reload();
        }

        keepLayoutClean();
    };

    document.addEventListener('click', (e) => {
        const menu = document.getElementById('langDropdownMenu');
        if (menu && !e.target.closest('#langSelectorBtn')) {
            menu.style.display = 'none';
        }
    });

    document.addEventListener('DOMContentLoaded', () => {
        const lang = localStorage.getItem('ptit_lang');
        if (lang === 'en') {
            const checkCombo = setInterval(() => {
                const select = document.querySelector('.goog-te-combo');
                if (select) {
                    select.value = 'en';
                    select.dispatchEvent(new Event('change'));
                    clearInterval(checkCombo);
                }
            }, 300);
            setTimeout(() => clearInterval(checkCombo), 5000);
        }
    });
})();
