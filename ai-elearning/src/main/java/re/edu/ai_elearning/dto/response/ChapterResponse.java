package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class ChapterResponse {
    private Long id;
    private Long courseId;
    private String subjectName;
    private Integer chapterNumber;
    private String chapterName;
    private String content;
    private Integer orderIndex;
    private Boolean isLocked;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
