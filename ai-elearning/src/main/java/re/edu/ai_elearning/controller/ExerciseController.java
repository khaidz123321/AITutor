package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.AnswerSubmitRequest;
import re.edu.ai_elearning.dto.request.ExerciseRequest;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.dto.response.ExerciseResponse;
import re.edu.ai_elearning.dto.response.ExerciseResultResponse;
import re.edu.ai_elearning.dto.response.ExerciseStatsResponse;
import re.edu.ai_elearning.security.UserPrincipal;
import re.edu.ai_elearning.service.ExerciseService;

@RestController
@RequestMapping("/api/v1/exercises")
@RequiredArgsConstructor
public class ExerciseController {

    private final ExerciseService exerciseService;

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<ExerciseResponse>> getExerciseById(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal) {
        ExerciseResponse response = exerciseService.getExerciseById(principal.getId(), id);
        return ResponseEntity.ok(ApiResponse.success("Lấy thông tin bài tập thành công", response));
    }

    @PostMapping("/{id}/submit")
    public ResponseEntity<ApiResponse<ExerciseResultResponse>> submitAnswer(
            @PathVariable Long id,
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody AnswerSubmitRequest request) {
        ExerciseResultResponse response = exerciseService.submitAnswer(principal.getId(), id, request);
        return ResponseEntity.ok(ApiResponse.success("Nộp đáp án thành công", response));
    }

    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ExerciseResponse>> createExercise(
            @RequestParam Long chapterId,
            @Valid @RequestBody ExerciseRequest request) {
        ExerciseResponse response = exerciseService.createExercise(chapterId, request);
        return ResponseEntity.ok(ApiResponse.success("Tạo bài tập thành công", response));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ExerciseResponse>> updateExercise(
            @PathVariable Long id,
            @Valid @RequestBody ExerciseRequest request) {
        ExerciseResponse response = exerciseService.updateExercise(id, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật bài tập thành công", response));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<Void>> deleteExercise(@PathVariable Long id) {
        exerciseService.deleteExercise(id);
        return ResponseEntity.ok(ApiResponse.success("Xóa bài tập thành công"));
    }

    @GetMapping("/{id}/stats")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<ExerciseStatsResponse>> getExerciseStats(@PathVariable Long id) {
        ExerciseStatsResponse response = exerciseService.getExerciseStats(id);
        return ResponseEntity.ok(ApiResponse.success("Lấy thống kê bài tập thành công", response));
    }
}
