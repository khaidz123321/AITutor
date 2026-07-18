package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import re.edu.ai_elearning.entity.enums.CourseLevel;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CourseRequest {

    @NotBlank(message = "Tiêu đề khóa học không được để trống")
    private String title;

    private String description;

    @NotNull(message = "Trình độ khóa học không được để trống")
    private CourseLevel level;

    private String thumbnailUrl;

    private String lecturePdf;

    private Boolean isVisible;

    private String aiPersona;
}
