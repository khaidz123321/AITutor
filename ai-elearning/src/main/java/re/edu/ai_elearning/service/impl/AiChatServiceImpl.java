package re.edu.ai_elearning.service.impl;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;
import re.edu.ai_elearning.dto.request.ChatRequest;
import re.edu.ai_elearning.dto.response.ChatMessageResponse;
import re.edu.ai_elearning.dto.response.ChatSessionResponse;
import re.edu.ai_elearning.entity.*;
import re.edu.ai_elearning.entity.enums.MessageRole;
import re.edu.ai_elearning.exception.ForbiddenException;
import re.edu.ai_elearning.exception.ResourceNotFoundException;
import re.edu.ai_elearning.mapper.ChatMapper;
import re.edu.ai_elearning.repository.*;
import re.edu.ai_elearning.service.AiChatService;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class AiChatServiceImpl implements AiChatService {

    private final ChatSessionRepository chatSessionRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final ChapterRepository chapterRepository;
    private final UserRepository userRepository;
    private final LearningProfileRepository learningProfileRepository;
    private final RestTemplate restTemplate;
    private final ChatMapper chatMapper;

    @Value("${ai.service.url}")
    private String aiServiceUrl;

    @Value("${ai.service.api-key}")
    private String aiApiKey;

    @Override
    @Transactional
    public ChatMessageResponse sendQuestion(Long userId, ChatRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy người dùng"));
        Chapter chapter = chapterRepository.findById(request.getChapterId())
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));

        // Kiểm tra xem người dùng đã đăng ký khóa học này chưa
        if (!learningProfileRepository.existsByUserIdAndCourseId(userId, chapter.getCourse().getId())) {
            throw new ForbiddenException("Bạn chưa đăng ký khóa học này");
        }

        // Lấy hoặc tạo phiên hội thoại hiện tại của user cho chapter
        List<ChatSession> sessions = chatSessionRepository.findByUserIdAndChapterId(userId, chapter.getId());
        ChatSession session;
        if (sessions.isEmpty()) {
            session = ChatSession.builder()
                    .user(user)
                    .chapter(chapter)
                    .createdAt(LocalDateTime.now())
                    .build();
            session = chatSessionRepository.save(session);
        } else {
            session = sessions.get(0);
        }

        // 1. Gọi AI Service TRƯỚC để lấy reply
        //    (thứ tự mới: gọi AI → nhận kết quả → lưu cả 2 tin nhắn cùng lúc)
        //    Python đọc lịch sử từ DB trước khi gọi → chưa có tin nhắn mới này → không bị trùng
        String aiReply = callAiService(userId, chapter.getId(), chapter, request.getQuestion());

        // 2. Lưu tin nhắn User (SAU khi AI đã xử lý xong)
        ChatMessage userMessage = ChatMessage.builder()
                .session(session)
                .role(MessageRole.USER)
                .content(request.getQuestion())
                .createdAt(LocalDateTime.now())
                .build();
        chatMessageRepository.save(userMessage);

        // 3. Lưu phản hồi AI
        ChatMessage aiMessage = ChatMessage.builder()
                .session(session)
                .role(MessageRole.ASSISTANT)
                .content(aiReply)
                .createdAt(LocalDateTime.now())
                .build();
        aiMessage = chatMessageRepository.save(aiMessage);

        return chatMapper.toResponse(aiMessage);
    }

    /**
     * Gọi Python AI Service với đúng URL, body, và headers.
     * URL   : POST {aiServiceUrl}/chat/
     * Body  : {"subject": slug, "chapter": slug, "message": question}
     * Header: X-User-Id, X-Chapter-Id → Python dùng để đọc lịch sử chat từ DB
     */
    private String callAiService(Long userId, Long chapterId, Chapter chapter, String question) {
        String url = aiServiceUrl + "/chat/";
        try {
            // Lấy slug từ chapter entity; tự sinh nếu chưa được set
            String subjectSlug = chapter.getSubjectSlug() != null
                    ? chapter.getSubjectSlug()
                    : toSlug(chapter.getSubjectName());
            String chapterSlug = chapter.getChapterSlug() != null
                    ? chapter.getChapterSlug()
                    : "chuong_" + chapter.getChapterNumber();

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            headers.set("Authorization", "Bearer " + aiApiKey);
            headers.set("X-User-Id", String.valueOf(userId));
            headers.set("X-Chapter-Id", String.valueOf(chapterId));

            Map<String, String> body = new HashMap<>();
            body.put("subject", subjectSlug);
            body.put("chapter", chapterSlug);
            body.put("message", question);
            // Truyền ai_persona từ DB vào Python để override file .txt tĩnh
            String aiPersona = chapter.getCourse() != null ? chapter.getCourse().getAiPersona() : null;
            if (aiPersona != null && !aiPersona.isBlank()) {
                body.put("ai_persona", aiPersona);
            }

            HttpEntity<Map<String, String>> entity = new HttpEntity<>(body, headers);
            ResponseEntity<Map> response = restTemplate.postForEntity(url, entity, Map.class);

            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                Object reply = response.getBody().get("reply");  // field là "reply", không phải "answer"
                return reply != null ? reply.toString() : generateMockResponse(chapter.getContent(), question);
            }
        } catch (Exception e) {
            log.warn("Lỗi khi kết nối tới AI Service (Python): {}. Chuyển sang phản hồi tự động.", e.getMessage());
        }

        return generateMockResponse(chapter.getContent(), question);
    }

    /**
     * Chuyển câu như "Giải tích 1" thành "giai_tich_1" (fallback khi chưa có slug).
     */
    private String toSlug(String text) {
        if (text == null || text.isBlank()) return "unknown";
        String normalized = java.text.Normalizer.normalize(text, java.text.Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "")
                .replace("đ", "d").replace("Đ", "d")
                .toLowerCase()
                .replaceAll("[^a-z0-9]+", "_")
                .replaceAll("^_|_$", "");
        return normalized;
    }

    private String generateMockResponse(String chapterContent, String question) {
        String answer = "[Hệ thống AI E-learning - Offline Mode]: ";
        if (question.toLowerCase().contains("giải thích") || question.toLowerCase().contains("là gì")) {
            answer += "Nội dung chương học này nói về lý thuyết và các khái niệm cơ bản. Dưới đây là tóm tắt ngữ cảnh bài học của bạn: \n\n\"" + 
                      (chapterContent != null && chapterContent.length() > 200 ? chapterContent.substring(0, 200) + "..." : chapterContent) + 
                      "\"\n\nBạn có thể làm bài tập thực hành để hiểu sâu hơn.";
        } else {
            answer += "Để trả lời câu hỏi '" + question + "', bạn nên tham khảo phần nội dung chính của chương này và cố gắng giải quyết các bài tập kèm theo. Nếu gặp khó khăn với thuật ngữ, hãy thảo luận thêm hoặc gửi lại câu hỏi chi tiết hơn.";
        }
        return answer;
    }

    @Override
    @Transactional(readOnly = true)
    public ChatSessionResponse getHistory(Long userId, Long chapterId) {
        List<ChatSession> sessions = chatSessionRepository.findByUserIdAndChapterId(userId, chapterId);
        if (sessions.isEmpty()) {
            Chapter chapter = chapterRepository.findById(chapterId)
                    .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy chương học"));
            return ChatSessionResponse.builder()
                    .chapterId(chapterId)
                    .chapterName(chapter.getChapterName())
                    .messages(List.of())
                    .build();
        }
        return chatMapper.toResponse(sessions.get(0));
    }

    @Override
    @Transactional
    public void deleteSession(Long userId, Long sessionId) {
        ChatSession session = chatSessionRepository.findById(sessionId)
                .orElseThrow(() -> new ResourceNotFoundException("Không tìm thấy phiên hội thoại"));

        if (!session.getUser().getId().equals(userId)) {
            throw new ForbiddenException("Bạn không có quyền xóa phiên hội thoại này");
        }

        chatSessionRepository.delete(session);
    }
}
