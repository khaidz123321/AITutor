package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;

@Getter
@Builder
public class ChatSessionResponse {
    private Long id;
    private Long chapterId;
    private String chapterName;
    private LocalDateTime createdAt;
    private List<ChatMessageResponse> messages;
}
