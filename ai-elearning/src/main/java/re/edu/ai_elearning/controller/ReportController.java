package re.edu.ai_elearning.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.dto.response.CourseSummaryResponse;
import re.edu.ai_elearning.dto.response.ReportDifficultyResponse;
import re.edu.ai_elearning.dto.response.ReportProgressResponse;
import re.edu.ai_elearning.service.ReportService;

import java.util.List;

@RestController
@RequestMapping("/api/v1/reports")
@RequiredArgsConstructor
public class ReportController {

    private final ReportService reportService;

    @GetMapping("/progress")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<List<ReportProgressResponse>>> getProgressReport() {
        List<ReportProgressResponse> response = reportService.getProgressReport();
        return ResponseEntity.ok(ApiResponse.success("Lấy báo cáo tiến độ học viên thành công", response));
    }

    @GetMapping("/exercise-difficulty")
    @PreAuthorize("hasAnyRole('ADMIN', 'TEACHER')")
    public ResponseEntity<ApiResponse<List<ReportDifficultyResponse>>> getDifficultyReport() {
        List<ReportDifficultyResponse> response = reportService.getDifficultyReport();
        return ResponseEntity.ok(ApiResponse.success("Lấy báo cáo độ khó bài tập thành công", response));
    }

    @GetMapping("/courses-summary")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<CourseSummaryResponse>> getCourseSummary() {
        CourseSummaryResponse response = reportService.getCourseSummary();
        return ResponseEntity.ok(ApiResponse.success("Lấy tổng quan hệ thống thành công", response));
    }
}
