package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;
import re.edu.ai_elearning.entity.enums.MessageRole;

import java.time.LocalDateTime;

@Getter
@Builder
public class ChatMessageResponse {
    private Long id;
    private Long sessionId;
    private MessageRole role;
    private String content;
    private LocalDateTime createdAt;
}
