package re.edu.ai_elearning.repository;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.ChatSession;

import java.util.List;

public interface ChatSessionRepository extends JpaRepository<ChatSession, Long> {

    @Query("SELECT cs FROM ChatSession cs WHERE cs.user.id = :userId AND cs.chapter.id = :chapterId ORDER BY cs.createdAt DESC")
    List<ChatSession> findByUserIdAndChapterId(@Param("userId") Long userId, @Param("chapterId") Long chapterId);

    @Query("SELECT cs FROM ChatSession cs WHERE cs.user.id = :userId ORDER BY cs.createdAt DESC")
    Page<ChatSession> findByUserId(@Param("userId") Long userId, Pageable pageable);
}
