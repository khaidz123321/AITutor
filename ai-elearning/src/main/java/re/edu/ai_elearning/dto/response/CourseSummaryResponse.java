package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class CourseSummaryResponse {
    private Integer totalCourses;
    private Integer totalStudents;
    private Integer totalReviews;
    private Double avgRating;
}
