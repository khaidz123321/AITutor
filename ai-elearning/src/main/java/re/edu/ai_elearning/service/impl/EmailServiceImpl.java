package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.stereotype.Service;
import re.edu.ai_elearning.service.EmailService;

@Slf4j
@Service
@RequiredArgsConstructor
public class EmailServiceImpl implements EmailService {

    private final JavaMailSender mailSender;

    @Value("${spring.mail.username:noreply@ai-elearning.com}")
    private String fromEmail;

    @Override
    public void sendPasswordResetEmail(String toEmail, String token) {
        try {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setFrom(fromEmail);
            message.setTo(toEmail);
            message.setSubject("Đặt lại mật khẩu tài khoản AI E-Learning");
            message.setText("Xin chào,\n\n" +
                    "Bạn nhận được email này vì đã yêu cầu đặt lại mật khẩu cho tài khoản AI E-Learning.\n" +
                    "Vui lòng sử dụng mã token sau để hoàn thành việc đặt lại mật khẩu:\n\n" +
                    token + "\n\n" +
                    "Hoặc truy cập link sau để đặt lại mật khẩu:\n" +
                    "http://localhost:3000/reset-password?token=" + token + "\n\n" +
                    "Mã token này sẽ hết hạn sau 15 phút.\n" +
                    "Nếu bạn không yêu cầu hành động này, vui lòng bỏ qua email này.\n\n" +
                    "Trân trọng,\n" +
                    "Đội ngũ AI E-Learning.");

            mailSender.send(message);
            log.info("Đã gửi email khôi phục tài khoản thành công tới {}", toEmail);
        } catch (Exception e) {
            log.error("Lỗi khi gửi email thực tế tới {} (Có thể chưa cấu hình đúng SMTP): {}", toEmail, e.getMessage());
            
            // Fallback: ghi vào console để kiểm thử không bị gián đoạn
            log.info("=========================================");
            log.info("[FALLBACK] MOCK EMAIL SENT TO: {}", toEmail);
            log.info("SUBJECT: Đặt lại mật khẩu tài khoản AI E-Learning");
            log.info("CONTENT: Xin chào, vui lòng sử dụng token sau để đặt lại mật khẩu của bạn: {}", token);
            log.info("Link: http://localhost:3000/reset-password?token={}", token);
            log.info("=========================================");
        }
    }
}
