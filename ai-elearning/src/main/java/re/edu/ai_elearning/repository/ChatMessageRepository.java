package re.edu.ai_elearning.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.ChatMessage;

import java.util.List;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, Long> {

    @Query("SELECT cm FROM ChatMessage cm WHERE cm.session.id = :sessionId ORDER BY cm.createdAt ASC")
    List<ChatMessage> findBySessionId(@Param("sessionId") Long sessionId);
}
