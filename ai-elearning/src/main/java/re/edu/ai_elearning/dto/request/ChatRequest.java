package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
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
public class ChatRequest {

    @NotNull(message = "ID chương học không được để trống")
    private Long chapterId;

    @NotBlank(message = "Nội dung câu hỏi không được để trống")
    @Size(max = 2000, message = "Câu hỏi không được vượt quá 2000 ký tự")
    private String question;
}
