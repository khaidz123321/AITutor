package re.edu.ai_elearning.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class NewsRequest {

    @NotBlank(message = "Tiêu đề tin tức không được để trống")
    private String title;

    @NotBlank(message = "Danh mục tin tức không được để trống")
    private String category;

    @NotBlank(message = "Mô tả ngắn không được để trống")
    private String summary;

    private String content;
    private String imageUrl;
    private Boolean isSpotlight;
}
