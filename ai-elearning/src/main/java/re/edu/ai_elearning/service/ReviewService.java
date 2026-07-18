package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.ReviewRequest;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.dto.response.ReviewResponse;

public interface ReviewService {
    PagedResponse<ReviewResponse> getCourseReviews(Long courseId, int page, int size);
    ReviewResponse submitReview(Long userId, Long courseId, ReviewRequest request);
    ReviewResponse updateReview(Long userId, Long id, ReviewRequest request);
    void deleteReview(Long userId, Long id);

    // Admin functions
    PagedResponse<ReviewResponse> getAllReviewsForAdmin(int page, int size);
    void toggleReviewVisibility(Long id, Boolean isVisible);
    void deleteReviewByAdmin(Long id);
}
