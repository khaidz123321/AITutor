package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;
import re.edu.ai_elearning.entity.enums.BloomLevel;
import re.edu.ai_elearning.entity.enums.Difficulty;

import java.time.LocalDateTime;

@Getter
@Builder
public class ExerciseResponse {
    private Long id;
    private Long chapterId;
    private String exerciseCode;
    private String exerciseName;
    private Difficulty difficulty;
    private BloomLevel bloomLevel;
    private String question;
    // correctAnswer bị ẩn - không include trong response cho student
    private LocalDateTime createdAt;
}
