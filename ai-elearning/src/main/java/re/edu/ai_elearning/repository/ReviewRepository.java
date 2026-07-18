package re.edu.ai_elearning.repository;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import re.edu.ai_elearning.entity.Review;

import java.util.List;
import java.util.Optional;

public interface ReviewRepository extends JpaRepository<Review, Long> {

    @Query("SELECT r FROM Review r WHERE r.course.id = :courseId AND r.isVisible = true ORDER BY r.createdAt DESC")
    Page<Review> findVisibleByCourseId(@Param("courseId") Long courseId, Pageable pageable);

    @Query("SELECT r FROM Review r WHERE r.user.id = :userId ORDER BY r.createdAt DESC")
    List<Review> findByUserId(@Param("userId") Long userId);

    @Query("SELECT r FROM Review r WHERE r.user.id = :userId AND r.course.id = :courseId")
    Optional<Review> findByUserIdAndCourseId(@Param("userId") Long userId, @Param("courseId") Long courseId);

    @Query("SELECT AVG(r.rating) FROM Review r WHERE r.course.id = :courseId AND r.isVisible = true")
    Optional<Double> findAvgRatingByCourseId(@Param("courseId") Long courseId);

    @Query("SELECT r FROM Review r ORDER BY r.createdAt DESC")
    Page<Review> findAllForAdmin(Pageable pageable);

    @Query("SELECT COUNT(r) FROM Review r")
    long countTotalReviews();

    @Query("SELECT AVG(r.rating) FROM Review r WHERE r.isVisible = true")
    Optional<Double> findOverallAvgRating();
}
