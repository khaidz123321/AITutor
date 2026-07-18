package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import re.edu.ai_elearning.dto.request.BroadcastNotificationRequest;
import re.edu.ai_elearning.dto.request.NotificationRequest;
import re.edu.ai_elearning.dto.response.NotificationResponse;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.entity.LearningProfile;
import re.edu.ai_elearning.entity.Notification;
import re.edu.ai_elearning.entity.User;
import re.edu.ai_elearning.entity.enums.NotificationType;
import re.edu.ai_elearning.exception.ForbiddenException;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.NotificationMapper;
import re.edu.ai_elearning.repository.LearningProfileRepository;
import re.edu.ai_elearning.repository.NotificationRepository;
import re.edu.ai_elearning.repository.UserRepository;
import re.edu.ai_elearning.service.NotificationService;
import re.edu.ai_elearning.service.SseService;

import java.time.LocalDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
public class NotificationServiceImpl implements NotificationService {

    private final NotificationRepository notificationRepository;
    private final UserRepository userRepository;
    private final LearningProfileRepository learningProfileRepository;
    private final NotificationMapper notificationMapper;
    private final SseService sseService;

    @Override
    @Transactional(readOnly = true)
    public PagedResponse<NotificationResponse> getUserNotifications(Long userId, int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size);
        Page<Notification> notificationPage = notificationRepository.findByUserId(userId, pageable);
        return PagedResponse.of(notificationPage, notificationMapper::toResponse);
    }

    @Override
    @Transactional
    public void markAsRead(Long userId, Long notificationId) {
        Notification notification = notificationRepository.findById(notificationId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy thông báo"));

        if (!notification.getUser().getId().equals(userId)) {
            throw new ForbiddenException("Bạn không có quyền thay đổi trạng thái của thông báo này");
        }

        notification.setIsRead(true);
        notificationRepository.save(notification);
    }

    @Override
    @Transactional
    public void markAllAsRead(Long userId) {
        notificationRepository.markAllAsRead(userId);
    }

    @Override
    @Transactional
    public void deleteNotification(Long userId, Long notificationId) {
        Notification notification = notificationRepository.findById(notificationId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy thông báo"));

        if (!notification.getUser().getId().equals(userId)) {
            throw new ForbiddenException("Bạn không có quyền xóa thông báo này");
        }

        notificationRepository.delete(notification);
    }

    @Override
    @Transactional
    public void sendNotification(NotificationRequest request) {
        for (Long targetUserId : request.getTargetUserIds()) {
            User user = userRepository.findById(targetUserId)
                    .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng ID: " + targetUserId));

            Notification notification = Notification.builder()
                    .user(user)
                    .message(request.getMessage())
                    .type(request.getType() != null ? request.getType() : NotificationType.SYSTEM)
                    .isRead(false)
                    .createdAt(LocalDateTime.now())
                    .build();
            notification = notificationRepository.save(notification);
            sseService.sendNotification(targetUserId, notificationMapper.toResponse(notification));
        }
    }

    @Override
    @Transactional
    public void broadcastNotification(BroadcastNotificationRequest request) {
        if (request.getCourseId() == null) {
            // Broadcast toàn bộ hệ thống
            List<User> allUsers = userRepository.findAll();
            for (User user : allUsers) {
                Notification notification = Notification.builder()
                        .user(user)
                        .message(request.getMessage())
                        .type(NotificationType.SYSTEM)
                        .isRead(false)
                        .createdAt(LocalDateTime.now())
                        .build();
                notification = notificationRepository.save(notification);
                sseService.sendNotification(user.getId(), notificationMapper.toResponse(notification));
            }
        } else {
            // Broadcast cho học viên đăng ký khóa học
            Pageable limit = PageRequest.of(0, 1000); // Lấy tối đa 1000 học viên để gửi nhanh
            List<LearningProfile> profiles = learningProfileRepository.findByCourseId(request.getCourseId(), limit).getContent();
            for (LearningProfile profile : profiles) {
                Notification notification = Notification.builder()
                        .user(profile.getUser())
                        .message(request.getMessage())
                        .type(NotificationType.COURSE_UPDATE)
                        .isRead(false)
                        .createdAt(LocalDateTime.now())
                        .build();
                notification = notificationRepository.save(notification);
                sseService.sendNotification(profile.getUser().getId(), notificationMapper.toResponse(notification));
            }
        }
    }

    @Override
    @Transactional
    public void createAndSendNotification(User user, String message, NotificationType type) {
        Notification notification = Notification.builder()
                .user(user)
                .message(message)
                .type(type)
                .isRead(false)
                .createdAt(LocalDateTime.now())
                .build();
        notification = notificationRepository.save(notification);
        sseService.sendNotification(user.getId(), notificationMapper.toResponse(notification));
    }
}
