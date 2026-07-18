package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import re.edu.ai_elearning.entity.enums.BloomLevel;
import re.edu.ai_elearning.entity.enums.Difficulty;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ExerciseAiRequest {

    @NotBlank(message = "Mã bài tập không được để trống")
    private String exerciseCode;

    private String exerciseName;

    @NotNull(message = "Độ khó không được để trống")
    private Difficulty difficulty;

    @NotNull(message = "Mức độ Bloom không được để trống")
    private BloomLevel bloomLevel;

    @NotBlank(message = "Nội dung câu hỏi không được để trống")
    private String question;

    @NotBlank(message = "Đáp án đúng không được để trống")
    private String correctAnswer;
}
