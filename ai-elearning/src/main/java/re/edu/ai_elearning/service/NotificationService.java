package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.BroadcastNotificationRequest;
import re.edu.ai_elearning.dto.request.NotificationRequest;
import re.edu.ai_elearning.dto.response.NotificationResponse;
import re.edu.ai_elearning.dto.response.PagedResponse;

import re.edu.ai_elearning.entity.User;
import re.edu.ai_elearning.entity.enums.NotificationType;

public interface NotificationService {
    PagedResponse<NotificationResponse> getUserNotifications(Long userId, int page, int size);
    void markAsRead(Long userId, Long notificationId);
    void markAllAsRead(Long userId);
    void deleteNotification(Long userId, Long notificationId);

    // Admin functions
    void sendNotification(NotificationRequest request);
    void broadcastNotification(BroadcastNotificationRequest request);
    void createAndSendNotification(User user, String message, NotificationType type);
}
