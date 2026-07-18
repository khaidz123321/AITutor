package re.edu.ai_elearning.service;

import java.time.LocalDateTime;

public interface TokenBlacklistService {
    void addToBlacklist(String token, LocalDateTime expiresAt);
    boolean isBlacklisted(String token);
    void cleanExpired();
}
