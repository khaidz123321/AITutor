package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChapterRequest {

    private String subjectName;

    @NotNull(message = "Số chương không được để trống")
    private Integer chapterNumber;

    @NotBlank(message = "Tên chương không được để trống")
    private String chapterName;

    private String content;

    @NotNull(message = "Thứ tự hiển thị không được để trống")
    private Integer orderIndex;

    private Boolean isLocked;
}
