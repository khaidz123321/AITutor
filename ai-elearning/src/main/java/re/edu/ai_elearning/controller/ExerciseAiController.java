package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.AnswerSubmitRequest;
import re.edu.ai_elearning.dto.request.ExerciseAiRequest;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.dto.response.ExerciseAiResponse;
import re.edu.ai_elearning.dto.response.ExerciseAiResultResponse;
import re.edu.ai_elearning.dto.response.ExerciseAiStatsResponse;
import re.edu.ai_elearning.security.UserPrincipal;
import re.edu.ai_elearning.service.ExerciseAiService;
import re.edu.ai_elearning.service.impl.ExerciseAiAsyncRunner;

import java.util.List;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class ExerciseAiController {

    private final ExerciseAiService exerciseAiService;
    private final ExerciseAiAsyncRunner exerciseAiAsyncRunner;

    @GetMapping("/exercises-ai/{id}")
    public ResponseEntity<ApiResponse<ExerciseAiResponse>> getExerciseById(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        ExerciseAiResponse response = exerciseAiService.getExerciseById(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Lấy thông tin bài tập AI thành công", response));
    }

    @PostMapping("/exercises-ai/{id}/submit")
    public ResponseEntity<ApiResponse<ExerciseAiResultResponse>> submitAnswer(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody AnswerSubmitRequest request) {
        ExerciseAiResultResponse response = exerciseAiService.submitAnswer(principal.getId(), id, request);
        return ResponseEntity.ok(ApiResponse.success("Nộp đáp án bài tập AI thành công", response));
    }

    @GetMapping("/exercises-ai/{id}/stats")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ExerciseAiStatsResponse>> getExerciseStats(@PathVariable Long id) {
        ExerciseAiStatsResponse response = exerciseAiService.getExerciseStats(id);
        return ResponseEntity.ok(ApiResponse.success("Lấy thống kê bài tập AI thành công", response));
    }

    @PutMapping("/exercises-ai/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ExerciseAiResponse>> updateExercise(
            @PathVariable Long id,
            @Valid @RequestBody ExerciseAiRequest request) {
        ExerciseAiResponse response = exerciseAiService.updateExercise(id, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật bài tập AI thành công", response));
    }

    @DeleteMapping("/exercises-ai/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<Void>> deleteExercise(@PathVariable Long id) {
        exerciseAiService.deleteExercise(id);
        return ResponseEntity.ok(ApiResponse.success("Xóa bài tập AI thành công"));
    }

    @GetMapping("/chapters/{chapterId}/exercises-ai")
    public ResponseEntity<ApiResponse<List<ExerciseAiResponse>>> getChapterExercises(
            @PathVariable Long chapterId,
            @AuthenticationPrincipal UserPrincipal principal) {
        List<ExerciseAiResponse> response = exerciseAiService.getExercisesByChapter(principal.getId(), chapterId);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách bài tập AI của chương thành công", response));
    }

    @PostMapping("/chapters/{chapterId}/exercises-ai")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ExerciseAiResponse>> createExerciseForChapter(
            @PathVariable Long chapterId,
            @Valid @RequestBody ExerciseAiRequest request) {
        ExerciseAiResponse response = exerciseAiService.createExercise(chapterId, request);
        return ResponseEntity.ok(ApiResponse.success("Tạo bài tập AI thành công", response));
    }

    @GetMapping("/chapters/{chapterId}/exercises-ai/next")
    public ResponseEntity<ApiResponse<ExerciseAiResponse>> getNextExercise(
            @PathVariable Long chapterId,
            @AuthenticationPrincipal UserPrincipal principal) {
        ExerciseAiResponse response = exerciseAiService.getNextExercise(principal.getId(), chapterId);
        return ResponseEntity.ok(ApiResponse.success("Lấy bài tập AI tiếp theo thành công", response));
    }

    @PostMapping(value = "/chapters/{chapterId}/exercises-ai/import-pdf", consumes = org.springframework.http.MediaType.MULTIPART_FORM_DATA_VALUE)
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<List<ExerciseAiResponse>>> importPdf(
            @PathVariable Long chapterId,
            @RequestParam("file") org.springframework.web.multipart.MultipartFile file) {
        List<ExerciseAiResponse> response = exerciseAiService.importExercisesFromPdf(chapterId, file);
        return ResponseEntity.ok(ApiResponse.success("AI dịch và tạo câu hỏi từ file PDF thành công", response));
    }

    @PostMapping("/chapters/{chapterId}/exercises-ai/generate-auto")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<String>> generateAutoExercises(
            @PathVariable Long chapterId) {
        // Dùng ExerciseAiAsyncRunner (bean riêng) để tránh Spring AOP self-invocation bypass.
        // @Async sẽ hoạt động đúng vì gọi qua Spring proxy của bean khác.
        // Trả 202 ngay, frontend sẽ polling kết quả.
        exerciseAiAsyncRunner.runGenerateAutoExercises(chapterId);
        return ResponseEntity.status(HttpStatus.ACCEPTED)
                .body(ApiResponse.success("AI đang sinh bài tập trong nền, vui lòng chờ...", "PROCESSING"));
    }

    @PostMapping("/chapters/{chapterId}/exercises-ai/sync")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<Void>> syncExercisesToAITutor(@PathVariable Long chapterId) {
        exerciseAiService.syncExercisesToAITutor(chapterId);
        return ResponseEntity.ok(ApiResponse.success("Đồng bộ bài tập sang AI Tutor thành công"));
    }
}
