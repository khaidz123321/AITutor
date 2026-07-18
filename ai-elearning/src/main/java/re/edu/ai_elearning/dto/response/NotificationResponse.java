package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;
import re.edu.ai_elearning.entity.enums.NotificationType;

import java.time.LocalDateTime;

@Getter
@Builder
public class NotificationResponse {
    private Long id;
    private String message;
    private NotificationType type;
    private Boolean isRead;
    private LocalDateTime createdAt;
}
