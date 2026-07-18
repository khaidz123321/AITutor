package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.NotificationResponse;
import re.edu.ai_elearning.entity.Notification;

@Component
public class NotificationMapper {

    public NotificationResponse toResponse(Notification notification) {
        if (notification == null) {
            return null;
        }

        return NotificationResponse.builder()
                .id(notification.getId())
                .message(notification.getMessage())
                .type(notification.getType())
                .isRead(notification.getIsRead())
                .createdAt(notification.getCreatedAt())
                .build();
    }
}
