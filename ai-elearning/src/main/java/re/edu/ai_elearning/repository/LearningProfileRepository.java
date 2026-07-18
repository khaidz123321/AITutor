package re.edu.ai_elearning.repository;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.LearningProfile;

import java.util.List;
import java.util.Optional;

public interface LearningProfileRepository extends JpaRepository<LearningProfile, Long> {

    @Query("SELECT lp FROM LearningProfile lp WHERE lp.user.id = :userId AND lp.course.id = :courseId")
    Optional<LearningProfile> findByUserIdAndCourseId(@Param("userId") Long userId,
                                                       @Param("courseId") Long courseId);

    @Query("SELECT lp FROM LearningProfile lp WHERE lp.user.id = :userId ORDER BY lp.enrolledAt DESC")
    List<LearningProfile> findByUserId(@Param("userId") Long userId);

    @Query("SELECT lp FROM LearningProfile lp WHERE lp.course.id = :courseId ORDER BY lp.enrolledAt DESC")
    Page<LearningProfile> findByCourseId(@Param("courseId") Long courseId, Pageable pageable);

    @Query("SELECT COUNT(lp) > 0 FROM LearningProfile lp WHERE lp.user.id = :userId AND lp.course.id = :courseId")
    boolean existsByUserIdAndCourseId(@Param("userId") Long userId, @Param("courseId") Long courseId);

    @Query("SELECT COUNT(DISTINCT lp.user.id) FROM LearningProfile lp")
    long countTotalStudents();

    @Query("SELECT COUNT(lp) FROM LearningProfile lp WHERE lp.course.id = :courseId")
    long countStudentsByCourseId(@Param("courseId") Long courseId);

    @Query("SELECT AVG(lp.progressPercent) FROM LearningProfile lp WHERE lp.course.id = :courseId")
    Double findAvgProgressByCourseId(@Param("courseId") Long courseId);
}
