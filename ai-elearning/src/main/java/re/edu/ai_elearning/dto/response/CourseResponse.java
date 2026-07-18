package re.edu.ai_elearning.dto.response;

import lombok.Builder;
import lombok.Getter;
import re.edu.ai_elearning.entity.enums.CourseLevel;

import java.time.LocalDateTime;

@Getter
@Builder
public class CourseResponse {
    private Long id;
    private String title;
    private String description;
    private CourseLevel level;
    private Boolean isVisible;
    private String thumbnailUrl;
    private String lecturePdf;
    private String ocrStatus;
    private String aiPersona;
    private String createdByName;
    private Long createdById;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private long chapterCount;
    private long studentCount;
    private Double avgRating;
}
