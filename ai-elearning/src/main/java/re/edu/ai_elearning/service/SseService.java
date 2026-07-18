package re.edu.ai_elearning.service;

import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

public interface SseService {
    SseEmitter subscribe(Long userId);
    void sendNotification(Long userId, Object notification);
    void broadcastNotification(Object notification);
}
