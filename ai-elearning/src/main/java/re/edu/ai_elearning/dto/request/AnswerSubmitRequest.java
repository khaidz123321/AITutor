package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AnswerSubmitRequest {

    @NotBlank(message = "Đáp án nộp không được để trống")
    private String answer;
}
