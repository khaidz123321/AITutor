package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ReportProgressResponse {
    private Long courseId;
    private String courseTitle;
    private Integer totalStudents;
    private Double avgProgress;
    private Integer completedCount;
}
