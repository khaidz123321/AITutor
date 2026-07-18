package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.ChapterRequest;
import re.edu.ai_elearning.dto.request.ReorderChapterRequest;
import re.edu.ai_elearning.dto.request.ExerciseRequest;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.dto.response.ChapterResponse;
import re.edu.ai_elearning.dto.response.ExerciseResponse;
import re.edu.ai_elearning.security.UserPrincipal;
import re.edu.ai_elearning.service.ChapterService;
import re.edu.ai_elearning.service.ExerciseService;

import java.util.List;

@RestController
@RequestMapping("/api/v1/chapters")
@RequiredArgsConstructor
public class ChapterController {

    private final ChapterService chapterService;
    private final ExerciseService exerciseService;

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<ChapterResponse>> getChapterById(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        ChapterResponse response = chapterService.getChapterById(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Lấy thông tin chương học thành công", response));
    }

    @GetMapping("/{id}/exercises")
    public ResponseEntity<ApiResponse<List<ExerciseResponse>>> getChapterExercises(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        List<ExerciseResponse> response = exerciseService.getExercisesByChapter(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách bài tập của chương thành công", response));
    }

    @GetMapping("/{id}/exercises/next")
    public ResponseEntity<ApiResponse<ExerciseResponse>> getNextExercise(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        ExerciseResponse response = exerciseService.getNextExercise(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Lấy bài tập tiếp theo thành công", response));
    }

    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ChapterResponse>> createChapter(
            @RequestParam Long courseId,
            @Valid @RequestBody ChapterRequest request) {
        ChapterResponse response = chapterService.createChapter(courseId, request);
        return ResponseEntity.ok(ApiResponse.success("Tạo chương học thành công", response));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ChapterResponse>> updateChapter(
            @PathVariable Long id,
            @Valid @RequestBody ChapterRequest request) {
        ChapterResponse response = chapterService.updateChapter(id, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật chương học thành công", response));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<Void>> deleteChapter(@PathVariable Long id) {
        chapterService.deleteChapter(id);
        return ResponseEntity.ok(ApiResponse.success("Xóa chương học thành công"));
    }

    @PatchMapping("/{id}/order")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ChapterResponse>> reorderChapter(
            @PathVariable Long id,
            @Valid @RequestBody ReorderChapterRequest request) {
        ChapterResponse response = chapterService.reorderChapter(id, request);
        return ResponseEntity.ok(ApiResponse.success("Thay đổi thứ tự chương học thành công", response));
    }

    @PatchMapping("/{id}/lock")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<Void>> toggleChapterLock(
            @PathVariable Long id,
            @RequestParam Boolean isLocked) {
        chapterService.toggleChapterLock(id, isLocked);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật trạng thái khóa chương học thành công"));
    }

    @PostMapping("/{chapterId}/exercises")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ExerciseResponse>> createExerciseForChapter(
            @PathVariable Long chapterId,
            @Valid @RequestBody ExerciseRequest request) {
        ExerciseResponse response = exerciseService.createExercise(chapterId, request);
        return ResponseEntity.ok(ApiResponse.success("Tạo bài tập thành công", response));
    }
}
