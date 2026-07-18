package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.entity.RevokedToken;
import re.edu.ai_elearning.repository.RevokedTokenRepository;
import re.edu.ai_elearning.service.TokenBlacklistService;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.HexFormat;

@Slf4j
@Service
@RequiredArgsConstructor
public class TokenBlacklistServiceImpl implements TokenBlacklistService {

    private final StringRedisTemplate redisTemplate;
    private final RevokedTokenRepository revokedTokenRepository;
    private static final String REDIS_PREFIX = "jwt:blacklist:";

    private String hashToken(String token) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(token.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (NoSuchAlgorithmException e) {
            log.error("Lỗi khi băm token", e);
            return String.valueOf(token.hashCode());
        }
    }

    @Override
    @Transactional
    public void addToBlacklist(String token, LocalDateTime expiresAt) {
        String tokenHash = hashToken(token);
        long secondsRemaining = Duration.between(LocalDateTime.now(), expiresAt).getSeconds();

        if (secondsRemaining > 0) {
            try {
                redisTemplate.opsForValue().set(REDIS_PREFIX + tokenHash, "revoked", Duration.ofSeconds(secondsRemaining));
                log.info("Đã thêm token vào blacklist trong Redis: {} giây", secondsRemaining);
            } catch (Exception e) {
                log.warn("Không thể lưu token blacklist vào Redis, dùng Database thay thế: {}", e.getMessage());
            }

            // Đồng bộ ghi vào DB để lưu trữ bền vững
            RevokedToken revokedToken = RevokedToken.builder()
                    .tokenHash(tokenHash)
                    .expiresAt(expiresAt)
                    .build();
            revokedTokenRepository.save(revokedToken);
        }
    }

    @Override
    @Transactional(readOnly = true)
    public boolean isBlacklisted(String token) {
        String tokenHash = hashToken(token);
        try {
            Boolean hasKey = redisTemplate.hasKey(REDIS_PREFIX + tokenHash);
            if (Boolean.TRUE.equals(hasKey)) {
                return true;
            }
        } catch (Exception e) {
            log.warn("Lỗi khi kiểm tra Redis, kiểm tra ở Database: {}", e.getMessage());
        }

        return revokedTokenRepository.isTokenRevoked(tokenHash);
    }

    @Override
    @Transactional
    @org.springframework.scheduling.annotation.Scheduled(cron = "0 0 3 * * ?") // Chạy hàng ngày lúc 3h sáng
    public void cleanExpired() {
        revokedTokenRepository.deleteExpiredTokens(LocalDateTime.now());
        log.info("Đã dọn dẹp các token hết hạn trong database");
    }
}
