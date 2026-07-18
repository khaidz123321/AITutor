package re.edu.ai_elearning.repository;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.Course;

import java.util.List;

public interface CourseRepository extends JpaRepository<Course, Long> {

    @Query(value = "SELECT c FROM Course c JOIN FETCH c.createdBy WHERE c.isVisible = true ORDER BY c.createdAt DESC",
           countQuery = "SELECT COUNT(c) FROM Course c WHERE c.isVisible = true")
    Page<Course> findAllVisible(Pageable pageable);

    @Query(value = "SELECT c FROM Course c JOIN FETCH c.createdBy ORDER BY c.createdAt DESC",
           countQuery = "SELECT COUNT(c) FROM Course c")
    Page<Course> findAllCourses(Pageable pageable);

    @Query("SELECT c FROM Course c WHERE c.createdBy.id = :userId ORDER BY c.createdAt DESC")
    List<Course> findByCreatedBy(@Param("userId") Long userId);

    @Query(value = "SELECT c FROM Course c JOIN FETCH c.createdBy WHERE c.isVisible = true AND LOWER(c.title) LIKE LOWER(CONCAT('%', :keyword, '%')) ORDER BY c.createdAt DESC",
           countQuery = "SELECT COUNT(c) FROM Course c WHERE c.isVisible = true AND LOWER(c.title) LIKE LOWER(CONCAT('%', :keyword, '%'))")
    Page<Course> searchByTitle(@Param("keyword") String keyword, Pageable pageable);

    @Query("SELECT COUNT(c) FROM Course c")
    long countTotalCourses();

    @Query("SELECT c.id AS courseId, " +
           "(SELECT COUNT(ch) FROM Chapter ch WHERE ch.course.id = c.id) AS chapterCount, " +
           "(SELECT COUNT(lp) FROM LearningProfile lp WHERE lp.course.id = c.id) AS studentCount, " +
           "(SELECT COALESCE(AVG(r.rating), 0.0) FROM Review r WHERE r.course.id = c.id) AS avgRating " +
           "FROM Course c WHERE c.id IN :courseIds")
    List<CourseStatsProjection> findStatsByCourseIds(@Param("courseIds") List<Long> courseIds);
}
