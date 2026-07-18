package re.edu.ai_elearning.mapper;

import org.springframework.stereotype.Component;
import re.edu.ai_elearning.dto.response.CourseResponse;
import re.edu.ai_elearning.entity.Course;

@Component
public class CourseMapper {

    public CourseResponse toResponse(Course course, long chapterCount, long studentCount, Double avgRating) {
        if (course == null) {
            return null;
        }

        return CourseResponse.builder()
                .id(course.getId())
                .title(course.getTitle())
                .description(course.getDescription())
                .level(course.getLevel())
                .isVisible(course.getIsVisible())
                .thumbnailUrl(course.getThumbnailUrl())
                .lecturePdf(course.getLecturePdf())
                .ocrStatus(course.getOcrStatus())
                .aiPersona(course.getAiPersona())
                .createdById(course.getCreatedBy() != null ? course.getCreatedBy().getId() : null)
                .createdByName(course.getCreatedBy() != null ? course.getCreatedBy().getFullName() : null)
                .createdAt(course.getCreatedAt())
                .updatedAt(course.getUpdatedAt())
                .chapterCount(chapterCount)
                .studentCount(studentCount)
                .avgRating(avgRating != null ? avgRating : 0.0)
                .build();
    }

    public CourseResponse toResponse(Course course) {
        if (course == null) {
            return null;
        }
        long chapters = course.getChapters() != null ? course.getChapters().size() : 0;
        return toResponse(course, chapters, 0, 0.0);
    }
}
