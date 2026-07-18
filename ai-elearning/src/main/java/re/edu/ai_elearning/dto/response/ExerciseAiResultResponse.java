package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ExerciseAiResultResponse {
    private Boolean isCorrect;
    private String message;
    private Long nextExerciseId;
    private Boolean chapterUnlocked;
    private String chapterUnlockedName;
}
