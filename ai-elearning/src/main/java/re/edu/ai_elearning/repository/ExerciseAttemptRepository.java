package re.edu.ai_elearning.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.ExerciseAttempt;

import java.util.List;

public interface ExerciseAttemptRepository extends JpaRepository<ExerciseAttempt, Long> {

    @Query("SELECT COUNT(ea) FROM ExerciseAttempt ea WHERE ea.exercise.id = :exerciseId")
    Long countTotalAttempts(@Param("exerciseId") Long exerciseId);

    @Query("SELECT COUNT(ea) FROM ExerciseAttempt ea WHERE ea.exercise.id = :exerciseId AND ea.isCorrect = true")
    Long countCorrectAttempts(@Param("exerciseId") Long exerciseId);

    @Query("SELECT ea FROM ExerciseAttempt ea WHERE ea.user.id = :userId AND ea.exercise.id = :exerciseId ORDER BY ea.attemptedAt DESC")
    List<ExerciseAttempt> findByUserIdAndExerciseId(@Param("userId") Long userId,
                                                     @Param("exerciseId") Long exerciseId);

    /**
     * Kiểm tra user đã trả lời đúng tất cả exercise trong chapter chưa.
     * Dùng native SQL để so sánh count.
     */
    @Query(value = """
            SELECT CASE
                WHEN COUNT(DISTINCT e.id) = 0 THEN false
                WHEN COUNT(DISTINCT ea.exercise_id) = COUNT(DISTINCT e.id) THEN true
                ELSE false
            END
            FROM exercises e
            LEFT JOIN exercise_attempts ea
                ON e.id = ea.exercise_id
                AND ea.user_id = :userId
                AND ea.is_correct = true
            WHERE e.chapter_id = :chapterId
            """, nativeQuery = true)
    boolean allExercisesCorrect(@Param("userId") Long userId, @Param("chapterId") Long chapterId);
}
