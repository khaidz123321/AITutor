package re.edu.ai_elearning.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.Exercise;
import re.edu.ai_elearning.entity.enums.BloomLevel;
import re.edu.ai_elearning.entity.enums.Difficulty;

import java.util.List;

public interface ExerciseRepository extends JpaRepository<Exercise, Long> {

    @Query("SELECT e FROM Exercise e WHERE e.chapter.id = :chapterId ORDER BY e.exerciseCode ASC")
    List<Exercise> findByChapterIdOrdered(@Param("chapterId") Long chapterId);

    @Query("SELECT e FROM Exercise e WHERE e.chapter.id = :chapterId AND e.difficulty = :difficulty ORDER BY e.exerciseCode ASC")
    List<Exercise> findByChapterIdAndDifficulty(@Param("chapterId") Long chapterId,
                                                 @Param("difficulty") Difficulty difficulty);

    @Query("SELECT e FROM Exercise e WHERE e.chapter.id = :chapterId AND e.bloomLevel = :bloomLevel ORDER BY e.exerciseCode ASC")
    List<Exercise> findByChapterIdAndBloomLevel(@Param("chapterId") Long chapterId,
                                                 @Param("bloomLevel") BloomLevel bloomLevel);

    @Query("SELECT COUNT(e) > 0 FROM Exercise e WHERE e.chapter.id = :chapterId AND e.exerciseCode = :code")
    boolean existsByChapterIdAndCode(@Param("chapterId") Long chapterId, @Param("code") String code);

    @Query("SELECT COUNT(e) > 0 FROM Exercise e WHERE e.chapter.id = :chapterId AND e.exerciseCode = :code AND e.id <> :excludeId")
    boolean existsByChapterIdAndCodeExcluding(@Param("chapterId") Long chapterId,
                                               @Param("code") String code,
                                               @Param("excludeId") Long excludeId);

    @Query("SELECT COUNT(e) FROM Exercise e WHERE e.chapter.id = :chapterId")
    long countByChapterId(@Param("chapterId") Long chapterId);
}
