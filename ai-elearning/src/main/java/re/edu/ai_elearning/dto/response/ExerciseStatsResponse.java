package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ExerciseStatsResponse {
    private Long exerciseId;
    private String exerciseCode;
    private String exerciseName;
    private Long totalAttempts;
    private Long correctCount;
    private Long incorrectCount;
    private Double successRate;  // phần trăm đúng
}
