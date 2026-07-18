package re.edu.ai_elearning.service;

public interface EmailService {
    void sendPasswordResetEmail(String email, String token);
}
