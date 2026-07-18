package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ReportDifficultyResponse {
    private String bloomLevel;
    private Integer exerciseCount;
    private Double avgSuccessRate;
}
