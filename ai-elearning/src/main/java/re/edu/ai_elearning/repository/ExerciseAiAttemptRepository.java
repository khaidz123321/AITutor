package re.edu.ai_elearning.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.ExerciseAiAttempt;

import java.util.List;

public interface ExerciseAiAttemptRepository extends JpaRepository<ExerciseAiAttempt, Long> {

    @Query("SELECT COUNT(ea) FROM ExerciseAiAttempt ea WHERE ea.exerciseAi.id = :exerciseId")
    Long countTotalAttempts(@Param("exerciseId") Long exerciseId);

    @Query("SELECT COUNT(ea) FROM ExerciseAiAttempt ea WHERE ea.exerciseAi.id = :exerciseId AND ea.isCorrect = true")
    Long countCorrectAttempts(@Param("exerciseId") Long exerciseId);

    @Query("SELECT ea FROM ExerciseAiAttempt ea WHERE ea.user.id = :userId AND ea.exerciseAi.id = :exerciseId ORDER BY ea.attemptedAt DESC")
    List<ExerciseAiAttempt> findByUserIdAndExerciseId(@Param("userId") Long userId,
                                                     @Param("exerciseId") Long exerciseId);

    @Query(value = """
            SELECT CASE
                WHEN COUNT(DISTINCT e.id) = 0 THEN false
                WHEN COUNT(DISTINCT ea.exercise_ai_id) = COUNT(DISTINCT e.id) THEN true
                ELSE false
            END
            FROM exercise_ai e
            LEFT JOIN exercise_ai_attempts ea
                ON e.id = ea.exercise_ai_id
                AND ea.user_id = :userId
                AND ea.is_correct = true
            WHERE e.chapter_id = :chapterId
            """, nativeQuery = true)
    boolean allExercisesCorrect(@Param("userId") Long userId, @Param("chapterId") Long chapterId);
}
