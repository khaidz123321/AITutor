package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class SupportTicketRequest {
    @NotBlank(message = "Họ tên không được để trống")
    private String studentName;

    @NotBlank(message = "Email không được để trống")
    private String studentEmail;

    @NotBlank(message = "Loại vấn đề không được để trống")
    private String problemType;

    @NotBlank(message = "Nội dung không được để trống")
    private String message;
}
