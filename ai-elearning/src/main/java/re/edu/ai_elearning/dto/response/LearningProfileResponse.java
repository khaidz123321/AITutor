package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class LearningProfileResponse {
    private Long id;
    private Long userId;
    private String userFullName;
    private Long courseId;
    private String courseTitle;
    private Integer progressPercent;
    private String bloomMastery;
    private LocalDateTime enrolledAt;
    private LocalDateTime lastStudied;
}
