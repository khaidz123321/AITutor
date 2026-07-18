package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.UpdateLearningProgressRequest;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.dto.response.CourseResponse;
import re.edu.ai_elearning.dto.response.LearningProfileResponse;
import re.edu.ai_elearning.dto.response.PagedResponse;
import re.edu.ai_elearning.security.UserPrincipal;
import re.edu.ai_elearning.service.LearningProfileService;

import java.util.List;

@RestController
@RequestMapping("/api/v1/learning-profiles")
@RequiredArgsConstructor
public class LearningProfileController {

    private final LearningProfileService learningProfileService;

    @GetMapping("/me")
    public ResponseEntity<ApiResponse<LearningProfileResponse>> getMyProfile(
            @RequestParam Long courseId,
            @AuthenticationPrincipal UserPrincipal principal) {
        LearningProfileResponse response = learningProfileService.getProfile(principal.getId(), courseId);
        return ResponseEntity.ok(ApiResponse.success("Lấy hồ sơ học tập thành công", response));
    }

    @GetMapping("/me/path")
    public ResponseEntity<ApiResponse<List<CourseResponse>>> getMyLearningPath(
            @AuthenticationPrincipal UserPrincipal principal) {
        List<CourseResponse> response = learningProfileService.getLearningPath(principal.getId());
        return ResponseEntity.ok(ApiResponse.success("Lấy lộ trình học gợi ý thành công", response));
    }

    @PostMapping("/me/progress")
    public ResponseEntity<ApiResponse<LearningProfileResponse>> updateProgress(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody UpdateLearningProgressRequest request) {
        LearningProfileResponse response = learningProfileService.updateProgress(principal.getId(), request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật tiến độ học tập thành công", response));
    }

    @GetMapping("/course/{courseId}")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<PagedResponse<LearningProfileResponse>>> getProfilesByCourse(
            @PathVariable Long courseId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        PagedResponse<LearningProfileResponse> response = learningProfileService.getProfilesByCourse(courseId, page, size);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách hồ sơ học tập của khóa học thành công", response));
    }
}
