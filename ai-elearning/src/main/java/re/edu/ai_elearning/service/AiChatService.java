package re.edu.ai_elearning.service;

import re.edu.ai_elearning.dto.request.ChatRequest;
import re.edu.ai_elearning.dto.response.ChatMessageResponse;
import re.edu.ai_elearning.dto.response.ChatSessionResponse;

public interface AiChatService {
    ChatMessageResponse sendQuestion(Long userId, ChatRequest request);
    ChatSessionResponse getHistory(Long userId, Long chapterId);
    void deleteSession(Long userId, Long sessionId);
}
