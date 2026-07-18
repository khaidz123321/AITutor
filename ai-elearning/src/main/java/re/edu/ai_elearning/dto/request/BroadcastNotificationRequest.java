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
public class BroadcastNotificationRequest {

    @NotBlank(message = "Nội dung thông báo không được để trống")
    private String message;

    private Long courseId; // null gửi toàn hệ thống, có ID gửi học viên trong khóa
}
