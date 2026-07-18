package re.edu.ai_elearning.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.Chapter;

import java.util.List;
import java.util.Optional;

public interface ChapterRepository extends JpaRepository<Chapter, Long> {

    @Query("SELECT ch FROM Chapter ch WHERE ch.course.id = :courseId ORDER BY ch.orderIndex ASC")
    List<Chapter> findByCourseIdOrdered(@Param("courseId") Long courseId);

    @Query("SELECT ch FROM Chapter ch WHERE ch.course.id = :courseId AND ch.isLocked = false ORDER BY ch.orderIndex ASC")
    List<Chapter> findUnlockedByCourseId(@Param("courseId") Long courseId);

    @Query("SELECT MAX(ch.orderIndex) FROM Chapter ch WHERE ch.course.id = :courseId")
    Optional<Integer> findMaxOrderIndex(@Param("courseId") Long courseId);

    @Query("SELECT ch FROM Chapter ch WHERE ch.course.id = :courseId AND ch.orderIndex = :orderIndex")
    Optional<Chapter> findByOrderIndex(@Param("courseId") Long courseId, @Param("orderIndex") Integer orderIndex);

    @Query("SELECT COUNT(ch) > 0 FROM Chapter ch WHERE ch.course.id = :courseId AND ch.orderIndex = :orderIndex")
    boolean existsByOrderIndex(@Param("courseId") Long courseId, @Param("orderIndex") Integer orderIndex);

    @Query("SELECT ch FROM Chapter ch WHERE ch.course.id = :courseId AND ch.orderIndex = :orderIndex AND ch.id <> :excludeId")
    Optional<Chapter> findByOrderIndexExcluding(@Param("courseId") Long courseId,
                                                 @Param("orderIndex") Integer orderIndex,
                                                 @Param("excludeId") Long excludeId);

    @Query("SELECT COUNT(ch) FROM Chapter ch WHERE ch.course.id = :courseId")
    long countByCourseId(@Param("courseId") Long courseId);
}
