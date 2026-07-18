package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.BroadcastNotificationRequest;
import re.edu.ai_elearning.dto.request.NotificationRequest;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.dto.response.NotificationResponse;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.security.UserPrincipal;
import re.edu.ai_elearning.service.NotificationService;

import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import re.edu.ai_elearning.service.SseService;
import re.edu.ai_elearning.exception.UnauthorizedException;

@RestController
@RequestMapping("/api/v1/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService notificationService;
    private final SseService sseService;

    @GetMapping("/subscribe")
    public SseEmitter subscribe(@AuthenticationPrincipal UserPrincipal principal) {
        if (principal == null) {
            throw new UnauthorizedException("Chưa xác thực");
        }
        return sseService.subscribe(principal.getId());
    }

    @GetMapping
    public ResponseEntity<ApiResponse<PagedResponse<NotificationResponse>>> getUserNotifications(
            @AuthenticationPrincipal UserPrincipal principal,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        PagedResponse<NotificationResponse> response = notificationService.getUserNotifications(principal.getId(), page, size);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách thông báo thành công", response));
    }

    @PatchMapping("/{id}/read")
    public ResponseEntity<ApiResponse<Void>> markAsRead(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        notificationService.markAsRead(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Đánh dấu đã đọc thông báo thành công"));
    }

    @PatchMapping("/read-all")
    public ResponseEntity<ApiResponse<Void>> markAllAsRead(@AuthenticationPrincipal UserPrincipal principal) {
        notificationService.markAllAsRead(principal.getId());
        return ResponseEntity.ok(ApiResponse.success("Đánh dấu đã đọc toàn bộ thông báo thành công"));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<ApiResponse<Void>> deleteNotification(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        notificationService.deleteNotification(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Xóa thông báo thành công"));
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> sendNotification(@Valid @RequestBody NotificationRequest request) {
        notificationService.sendNotification(request);
        return ResponseEntity.ok(ApiResponse.success("Gửi thông báo thành công"));
    }

    @PostMapping("/broadcast")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> broadcastNotification(@Valid @RequestBody BroadcastNotificationRequest request) {
        notificationService.broadcastNotification(request);
        return ResponseEntity.ok(ApiResponse.success("Phát thông báo thành công"));
    }
}
