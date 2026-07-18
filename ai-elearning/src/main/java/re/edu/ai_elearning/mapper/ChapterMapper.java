package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.ChapterResponse;
import re.edu.ai_elearning.entity.Chapter;

@Component
public class ChapterMapper {

    public ChapterResponse toResponse(Chapter chapter, boolean isLockedForUser) {
        if (chapter == null) {
            return null;
        }

        return ChapterResponse.builder()
                .id(chapter.getId())
                .courseId(chapter.getCourse() != null ? chapter.getCourse().getId() : null)
                .subjectName(chapter.getSubjectName())
                .chapterNumber(chapter.getChapterNumber())
                .chapterName(chapter.getChapterName())
                .content(isLockedForUser ? "Nội dung chương này đã bị khóa. Hoàn thành bài tập chương trước để mở khóa." : chapter.getContent())
                .orderIndex(chapter.getOrderIndex())
                .isLocked(isLockedForUser)
                .createdAt(chapter.getCreatedAt())
                .updatedAt(chapter.getUpdatedAt())
                .build();
    }

    public ChapterResponse toResponse(Chapter chapter) {
        return toResponse(chapter, Boolean.TRUE.equals(chapter.getIsLocked()));
    }
}
