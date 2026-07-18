package re.edu.ai_elearning.controller;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;
import re.edu.ai_elearning.dto.request.ChatRequest;
import re.edu.ai_elearning.dto.response.ApiResponse;
import re.edu.ai_elearning.dto.response.ChatMessageResponse;
import re.edu.ai_elearning.dto.response.ChatSessionResponse;
import re.edu.ai_elearning.security.UserPrincipal;
import re.edu.ai_elearning.service.AiChatService;

@RestController
@RequestMapping("/api/v1/ai/chat")
@RequiredArgsConstructor
public class AiChatController {

    private final AiChatService aiChatService;

    @PostMapping
    public ResponseEntity<ApiResponse<ChatMessageResponse>> sendQuestion(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody ChatRequest request) {
        ChatMessageResponse response = aiChatService.sendQuestion(principal.getId(), request);
        return ResponseEntity.ok(ApiResponse.success("Nhận câu trả lời từ AI thành công", response));
    }

    @GetMapping("/history")
    public ResponseEntity<ApiResponse<ChatSessionResponse>> getHistory(
            @RequestParam Long chapterId,
            @AuthenticationPrincipal UserPrincipal principal) {
        ChatSessionResponse response = aiChatService.getHistory(principal.getId(), chapterId);
        return ResponseEntity.ok(ApiResponse.success("Lấy lịch sử hội thoại thành công", response));
    }

    @DeleteMapping("/history/{sessionId}")
    public ResponseEntity<ApiResponse<Void>> deleteSession(
            @PathVariable Long sessionId,
            @AuthenticationPrincipal UserPrincipal principal) {
        aiChatService.deleteSession(principal.getId(), sessionId);
        return ResponseEntity.ok(ApiResponse.success("Xóa lịch sử hội thoại thành công"));
    }
}
