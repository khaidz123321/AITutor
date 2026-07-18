package re.edu.ai_elearning.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.RevokedToken;

import java.time.LocalDateTime;

public interface RevokedTokenRepository extends JpaRepository<RevokedToken, Long> {

    @Query("SELECT COUNT(rt) > 0 FROM RevokedToken rt WHERE rt.tokenHash = :tokenHash")
    boolean isTokenRevoked(@Param("tokenHash") String tokenHash);

    @Modifying
    @Query("DELETE FROM RevokedToken rt WHERE rt.expiresAt < :now")
    void deleteExpiredTokens(@Param("now") LocalDateTime now);
}
