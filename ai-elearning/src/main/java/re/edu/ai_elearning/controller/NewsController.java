package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.NewsRequest;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.dto.response.NewsResponse;
import re.edu.ai_elearning.service.NewsService;

import java.util.List;

@RestController
@RequestMapping("/api/v1/news")
@RequiredArgsConstructor
public class NewsController {

    private final NewsService newsService;

    @GetMapping
    public ResponseEntity<ApiResponse<List<NewsResponse>>> getAllNews(
            @RequestParam(required = false) String category) {
        List<NewsResponse> news = newsService.getAllNews(category);
        return ResponseEntity.ok(ApiResponse.success("Lấy danh sách tin tức thành công", news));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<NewsResponse>> getNewsById(@PathVariable Long id) {
        NewsResponse news = newsService.getNewsById(id);
        return ResponseEntity.ok(ApiResponse.success("Lấy chi tiết tin tức thành công", news));
    }

    @PostMapping
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<NewsResponse>> createNews(@Valid @RequestBody NewsRequest request) {
        NewsResponse created = newsService.createNews(request);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success("Đăng tin tức thành công", created));
    }

    @PutMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<NewsResponse>> updateNews(
            @PathVariable Long id,
            @Valid @RequestBody NewsRequest request) {
        NewsResponse updated = newsService.updateNews(id, request);
        return ResponseEntity.ok(ApiResponse.success("Cập nhật tin tức thành công", updated));
    }

    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ResponseEntity<ApiResponse<Void>> deleteNews(@PathVariable Long id) {
        newsService.deleteNews(id);
        return ResponseEntity.ok(ApiResponse.success("Xóa tin tức thành công"));
    }
}
