package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.ReviewResponse;
import re.edu.ai_elearning.entity.Review;

@Component
public class ReviewMapper {

    public ReviewResponse toResponse(Review review) {
        if (review == null) {
            return null;
        }

        return ReviewResponse.builder()
                .id(review.getId())
                .userId(review.getUser() != null ? review.getUser().getId() : null)
                .userFullName(review.getUser() != null ? review.getUser().getFullName() : null)
                .courseId(review.getCourse() != null ? review.getCourse().getId() : null)
                .courseTitle(review.getCourse() != null ? review.getCourse().getTitle() : null)
                .rating(review.getRating())
                .comment(review.getComment())
                .isVisible(review.getIsVisible())
                .createdAt(review.getCreatedAt())
                .updatedAt(review.getUpdatedAt())
                .build();
    }
}
