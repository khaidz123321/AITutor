package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.ReviewRequest;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.dto.response.ReviewResponse;
import re.edu.ai_elearning.entity.Course;
import re.edu.ai_elearning.entity.Review;
import re.edu.ai_elearning.entity.User;
import re.edu.ai_elearning.exception.BadRequestException;
import re.edu.ai_elearning.exception.ConflictException;
import re.edu.ai_elearning.exception.ForbiddenException;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.ReviewMapper;
import re.edu.ai_elearning.repository.CourseRepository;
import re.edu.ai_elearning.repository.LearningProfileRepository;
import re.edu.ai_elearning.repository.ReviewRepository;
import re.edu.ai_elearning.repository.UserRepository;
import re.edu.ai_elearning.service.ReviewService;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class ReviewServiceImpl implements ReviewService {

    private final ReviewRepository reviewRepository;
    private final UserRepository userRepository;
    private final CourseRepository courseRepository;
    private final LearningProfileRepository learningProfileRepository;
    private final ReviewMapper reviewMapper;

    @Override
    @Transactional(readOnly = true)
    public PagedResponse<ReviewResponse> getCourseReviews(Long courseId, int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size);
        Page<Review> reviewPage = reviewRepository.findVisibleByCourseId(courseId, pageable);
        return PagedResponse.of(reviewPage, reviewMapper::toResponse);
    }

    @Override
    @Transactional
    public ReviewResponse submitReview(Long userId, Long courseId, ReviewRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));
        Course course = courseRepository.findById(courseId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy khóa học"));

        // Người dùng phải đăng ký khóa học trước khi đánh giá
        if (!learningProfileRepository.existsByUserIdAndCourseId(userId, courseId)) {
            throw new BadRequestException("Bạn phải đăng ký khóa học trước khi đánh giá");
        }

        // Đã đánh giá rồi thì không cho tạo cái mới
        if (reviewRepository.findByUserIdAndCourseId(userId, courseId).isPresent()) {
            throw new ConflictException("Bạn đã đánh giá khóa học này");
        }

        Review review = Review.builder()
                .user(user)
                .course(course)
                .rating(request.getRating())
                .comment(request.getComment())
                .isVisible(true)
                .createdAt(LocalDateTime.now())
                .updatedAt(LocalDateTime.now())
                .build();

        review = reviewRepository.save(review);
        return reviewMapper.toResponse(review);
    }

    @Override
    @Transactional
    public ReviewResponse updateReview(Long userId, Long id, ReviewRequest request) {
        Review review = reviewRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy đánh giá"));

        if (!review.getUser().getId().equals(userId)) {
            throw new ForbiddenException("Bạn không có quyền chỉnh sửa đánh giá này");
        }

        review.setRating(request.getRating());
        review.setComment(request.getComment());
        review.setUpdatedAt(LocalDateTime.now());

        review = reviewRepository.save(review);
        return reviewMapper.toResponse(review);
    }

    @Override
    @Transactional
    public void deleteReview(Long userId, Long id) {
        Review review = reviewRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy đánh giá"));

        if (!review.getUser().getId().equals(userId)) {
            throw new ForbiddenException("Bạn không có quyền xóa đánh giá này");
        }

        reviewRepository.delete(review);
    }

    @Override
    @Transactional(readOnly = true)
    public PagedResponse<ReviewResponse> getAllReviewsForAdmin(int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size);
        Page<Review> reviewPage = reviewRepository.findAllForAdmin(pageable);
        return PagedResponse.of(reviewPage, reviewMapper::toResponse);
    }

    @Override
    @Transactional
    public void toggleReviewVisibility(Long id, Boolean isVisible) {
        Review review = reviewRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy đánh giá"));
        review.setIsVisible(isVisible);
        reviewRepository.save(review);
    }

    @Override
    @Transactional
    public void deleteReviewByAdmin(Long id) {
        Review review = reviewRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy đánh giá"));
        reviewRepository.delete(review);
    }
}
