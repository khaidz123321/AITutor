package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import re.edu.ai_elearning.entity.enums.NotificationType;

import java.util.List;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class NotificationRequest {

    @NotBlank(message = "Nội dung thông báo không được để trống")
    private String message;

    @NotNull(message = "Loại thông báo không được để trống")
    private NotificationType type;

    @NotEmpty(message = "Danh sách người nhận không được để trống")
    private List<Long> targetUserIds;
}
