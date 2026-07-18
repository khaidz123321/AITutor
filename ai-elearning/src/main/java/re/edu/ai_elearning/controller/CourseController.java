package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import re.edu.ai_elearning.dto.request.*;
import re.edu.ai_elearning.dto.response.*;
import re.edu.ai_elearning.security.UserPrincipal;
import re.edu.ai_elearning.service.CourseService;
import re.edu.ai_elearning.service.ReviewService;
import re.edu.ai_elearning.service.ChapterService;

import java.util.List;

@RestController
@RequestMapping("/api/v1/courses")
@RequiredArgsConstructor
public class CourseController {

    private final CourseService courseService;
    private final ReviewService reviewService;
    private final ChapterService chapterService;

    @GetMapping
    public ResponseEntity<ApiResponse<PagedResponse<CourseResponse>>> getAllVisibleCourses(
            @RequestParam(required = false) String keyword,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        PagedResponse<CourseResponse> response = courseService.getAllPublicCourses(keyword, page, size);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách khóa học thành công", response));
    }

    @GetMapping("/all")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<PagedResponse<CourseResponse>>> getAllCoursesForAdmin(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        PagedResponse<CourseResponse> response = courseService.getAllCoursesForAdmin(page, size);
        return ResponseEntity.ok(ApiResponse.success("Lấy tất cả danh sách khóa học quản trị thành công", response));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<CourseResponse>> getCourseById(@PathVariable Long id) {
        CourseResponse response = courseService.getCourseById(id);
        return ResponseEntity.ok(ApiResponse.success("Lấy thông tin khóa học thành công", response));
    }

    @GetMapping("/enrolled")
    public ResponseEntity<ApiResponse<List<CourseResponse>>> getMyEnrolledCourses(
            @AuthenticationPrincipal UserPrincipal principal) {
        List<CourseResponse> response = courseService.getMyEnrolledCourses(principal.getId());
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách khóa học đã đăng ký thành công", response));
    }

    @PostMapping("/{id}/enroll")
    public ResponseEntity<ApiResponse<LearningProfileResponse>> enrollCourse(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        LearningProfileResponse response = courseService.enrollCourse(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Đăng ký khóa học thành công", response));
    }

    @GetMapping("/{id}/chapters")
    public ResponseEntity<ApiResponse<List<ChapterResponse>>> getCourseChapters(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        List<ChapterResponse> response = courseService.getCourseChapters(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách chương học thành công", response));
    }

    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<CourseResponse>> createCourse(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody CourseRequest request) {
        CourseResponse response = courseService.createCourse(principal.getId(), request);
        return ResponseEntity.ok(ApiResponse.success("Tạo khóa học thành công", response));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<CourseResponse>> updateCourse(
            @PathVariable Long id,
            @Valid @RequestBody CourseRequest request) {
        CourseResponse response = courseService.updateCourse(id, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật khóa học thành công", response));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> deleteCourse(@PathVariable Long id) {
        courseService.deleteCourse(id);
        return ResponseEntity.ok(ApiResponse.success("Xóa khóa học thành công"));
    }

    @PatchMapping("/{id}/visibility")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<Void>> toggleCourseVisibility(
            @PathVariable Long id,
            @RequestParam Boolean isVisible) {
        courseService.toggleCourseVisibility(id, isVisible);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật trạng thái hiển thị khóa học thành công"));
    }

    @GetMapping("/{id}/reviews")
    public ResponseEntity<ApiResponse<PagedResponse<ReviewResponse>>> getCourseReviews(
            @PathVariable Long id,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        PagedResponse<ReviewResponse> response = reviewService.getCourseReviews(id, page, size);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách đánh giá của khóa học thành công", response));
    }

    @PostMapping("/{id}/reviews")
    public ResponseEntity<ApiResponse<ReviewResponse>> submitReview(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody ReviewRequest request) {
        ReviewResponse response = reviewService.submitReview(principal.getId(), id, request);
        return ResponseEntity.ok(ApiResponse.success("Gửi đánh giá thành công", response));
    }

    @PostMapping("/{courseId}/chapters")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ChapterResponse>> createChapterForCourse(
            @PathVariable Long courseId,
            @Valid @RequestBody ChapterRequest request) {
        ChapterResponse response = chapterService.createChapter(courseId, request);
        return ResponseEntity.ok(ApiResponse.success("Tạo chương học thành công", response));
    }

    @PostMapping("/{id}/upload-pdf")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<CourseResponse>> uploadLecturePdf(
            @PathVariable Long id,
            @RequestParam("file") MultipartFile file) {
        CourseResponse response = courseService.uploadLecturePdf(id, file);
        return ResponseEntity.ok(ApiResponse.success("Tải lên bài giảng PDF thành công", response));
    }
}
