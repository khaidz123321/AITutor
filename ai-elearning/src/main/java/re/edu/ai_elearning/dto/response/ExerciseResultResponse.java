package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ExerciseResultResponse {
    private Boolean isCorrect;
    private String message;
    private Long nextExerciseId;       // null nếu là bài cuối
    private Boolean chapterUnlocked;   // true nếu vừa mở khóa chapter tiếp theo
    private String chapterUnlockedName; // tên chapter mới mở khóa
}
