package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.ChatMessageResponse;
import re.edu.ai_elearning.dto.response.ChatSessionResponse;
import re.edu.ai_elearning.entity.ChatMessage;
import re.edu.ai_elearning.entity.ChatSession;

import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

@Component
public class ChatMapper {

    public ChatMessageResponse toResponse(ChatMessage message) {
        if (message == null) {
            return null;
        }

        return ChatMessageResponse.builder()
                .id(message.getId())
                .sessionId(message.getSession() != null ? message.getSession().getId() : null)
                .role(message.getRole())
                .content(message.getContent())
                .createdAt(message.getCreatedAt())
                .build();
    }

    public ChatSessionResponse toResponse(ChatSession session) {
        if (session == null) {
            return null;
        }

        List<ChatMessageResponse> messages = session.getMessages() == null ? Collections.emptyList() :
                session.getMessages().stream()
                        .map(this::toResponse)
                        .collect(Collectors.toList());

        return ChatSessionResponse.builder()
                .id(session.getId())
                .chapterId(session.getChapter() != null ? session.getChapter().getId() : null)
                .chapterName(session.getChapter() != null ? session.getChapter().getChapterName() : null)
                .createdAt(session.getCreatedAt())
                .messages(messages)
                .build();
    }
}
