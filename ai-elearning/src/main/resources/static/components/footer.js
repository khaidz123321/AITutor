// =====================================================
// FOOTER COMPONENT - Commercial style with mini map
// =====================================================
(function () {
    const footerHTML = `
<footer class="site-footer">
    <div class="container">
        <div class="footer-grid">
            <div>
                <div style="margin-bottom: 16px;">
                    <a href="index.html" style="display:inline-block;">
                        <img src="assets/images/Logo-Hoc-Vien-Cong-Nghe-Buu-Chinh-Vien-Thong-PTITSimple.webp" alt="PTIT Logo" style="height: 60px; width: auto;">
                    </a>
                </div>
                <p class="footer-desc">Hệ thống học tập trực tuyến tích hợp trí tuệ nhân tạo của Học viện Công nghệ Bưu chính Viễn thông. Học mọi lúc, mọi nơi.</p>
                <div style="display:flex;gap:10px;margin-top:12px;">
                    <a href="https://ptit.edu.vn" target="_blank" rel="noopener noreferrer" class="footer-social-link" title="Website PTIT">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="2" y1="12" x2="22" y2="12"></line>
                            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
                        </svg>
                    </a>
                    <a href="https://www.facebook.com/HocvienPTIT" target="_blank" rel="noopener noreferrer" class="footer-social-link" title="Facebook PTIT">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"></path>
                        </svg>
                    </a>
                    <a href="https://www.instagram.com/ptit.edu.vn" target="_blank" rel="noopener noreferrer" class="footer-social-link" title="Instagram PTIT">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect>
                            <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path>
                            <line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line>
                        </svg>
                    </a>
                </div>
            </div>
            <div>
                <div class="footer-col-title">Khóa học</div>
                <div class="footer-links">
                    <a href="courses.html">Tất cả khóa học</a>
                    <a href="courses.html?cat=daicuong">Các môn Đại cương</a>
                    <a href="courses.html?cat=chuyennganh">Chuyên ngành CNTT</a>
                    <a href="my-courses.html">Khóa học của tôi</a>
                </div>
            </div>
            <div>
                <div class="footer-col-title">Khám phá & Hỗ trợ</div>
                <div class="footer-links">
                    <a href="introduction.html">Giới thiệu nền tảng</a>
                    <a href="news.html">Tin tức & Sự kiện</a>
                    <a href="support.html">Hướng dẫn & Hỗ trợ</a>
                    <a href="support.html#faq">Câu hỏi thường gặp (FAQ)</a>
                    <a href="support.html#contactForm">Gửi yêu cầu hỗ trợ</a>
                </div>
            </div>
            <div>
                <div class="footer-col-title">Liên hệ</div>
                <div class="footer-links">
                    <a href="https://ptit.edu.vn" target="_blank" rel="noopener noreferrer">ptit.edu.vn</a>
                    <a href="tel:02433528122">024 3352 8122</a>
                    <a href="https://maps.google.com/?q=Học+viện+Công+nghệ+Bưu+chính+Viễn+thông" target="_blank" rel="noopener noreferrer">Km10, Nguyễn Trãi, Hà Đông, Hà Nội</a>
                    <a href="mailto:cskh@ptit.edu.vn">cskh@ptit.edu.vn</a>
                </div>
                <!-- MINI MAP EMBED -->
                <div style="margin-top: 14px; border-radius: 8px; overflow: hidden; border: 1px solid rgba(255,255,255,0.12); height: 120px;">
                    <iframe 
                        src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3725.292516487841!2d105.78505507596952!3d20.98091298942159!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x3135accdd8a1ad71%3A0xa2f9b16016648114!2zSOG7jWMgdmnhu4duIEPDtG5nIG5naOG7hyBCxrB1IGNow61uaCBWaeG7hW4gdGjDtG5n!5e0!3m2!1svi!2s!4v1700000000000!5m2!1svi!2s" 
                        width="100%" 
                        height="100%" 
                        style="border:0;" 
                        allowfullscreen="" 
                        loading="lazy" 
                        referrerpolicy="no-referrer-when-downgrade">
                    </iframe>
                </div>
            </div>
        </div>
        <div class="footer-bottom">
            <span>&copy; 2026 PTIT E-Learning. D.T.T.Quynh - V.Q.Khai - N.D.Thang</span>
            <div style="display:flex;gap:20px;">
                <a href="introduction.html">Điều khoản sử dụng</a>
                <a href="introduction.html">Chính sách bảo mật</a>
            </div>
        </div>
    </div>
</footer>`;

    document.write(footerHTML);
})();


