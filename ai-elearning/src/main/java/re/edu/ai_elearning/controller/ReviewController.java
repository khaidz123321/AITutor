package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.ReviewRequest;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.dto.response.ReviewResponse;
import re.edu.ai_elearning.security.UserPrincipal;
import re.edu.ai_elearning.service.ReviewService;

@RestController
@RequestMapping("/api/v1/reviews")
@RequiredArgsConstructor
public class ReviewController {

    private final ReviewService reviewService;

    @GetMapping("/course/{courseId}")
    public ResponseEntity<ApiResponse<PagedResponse<ReviewResponse>>> getCourseReviews(
            @PathVariable Long courseId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        PagedResponse<ReviewResponse> response = reviewService.getCourseReviews(courseId, page, size);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách đánh giá của khóa học thành công", response));
    }

    @PostMapping("/course/{courseId}")
    public ResponseEntity<ApiResponse<ReviewResponse>> submitReview(
            @PathVariable Long courseId,
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody ReviewRequest request) {
        ReviewResponse response = reviewService.submitReview(principal.getId(), courseId, request);
        return ResponseEntity.ok(ApiResponse.success("Gửi đánh giá thành công", response));
    }

    @PutMapping("/{id}")
    public ResponseEntity<ApiResponse<ReviewResponse>> updateReview(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody ReviewRequest request) {
        ReviewResponse response = reviewService.updateReview(principal.getId(), id, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật đánh giá thành công", response));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<ApiResponse<Void>> deleteReview(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        reviewService.deleteReview(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Xóa đánh giá thành công"));
    }

    // ==================== Admin Moderation ====================

    @GetMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<PagedResponse<ReviewResponse>>> getAllReviewsForAdmin(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        PagedResponse<ReviewResponse> response = reviewService.getAllReviewsForAdmin(page, size);
        return ResponseEntity.ok(ApiResponse.success("Lấy tất cả danh sách đánh giá quản trị thành công", response));
    }

    @PatchMapping("/{id}/visibility")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> toggleReviewVisibility(
            @PathVariable Long id,
            @RequestParam Boolean isVisible) {
        reviewService.toggleReviewVisibility(id, isVisible);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật trạng thái hiển thị đánh giá thành công"));
    }

    @DeleteMapping("/{id}/admin")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> deleteReviewByAdmin(@PathVariable Long id) {
        reviewService.deleteReviewByAdmin(id);
        return ResponseEntity.ok(ApiResponse.success("Xóa đánh giá vi phạm thành công"));
    }
}
